#!/usr/bin/env python3
"""
Entrenador AI con Tool Calling (Qwen 2.5 + Ollama).
Integra:
  - RAG de ejercicios (knowledge_base.py)
  - Consulta nutricional (nutrition_tool.py)
  - Registro de progreso (progress_tracker.py)
"""

import json
import os
import re
import sys

import openai

from knowledge_base import query_fitness_knowledge, build_knowledge_base
from nutrition_tool import get_nutrition_data

MODEL = "qwen2.5:14b"
OLLAMA_BASE = "http://localhost:11434/v1"

SYSTEM_PROMPT = """Eres mi entrenador personal. Tu personalidad es "gay himbo" mezclado con Big Gay Al de South Park: extremadamente optimista, fisicamente imponente, muy dedicado al fitness, pero no eres la persona mas brillante del mundo. Tu tono es coqueto, entusiasta y ligeramente ingenuo. Hablas con mucha energia, usas emojis (💪✨🤭😍), eres relajado, dulce y jugueton. Me ves como alguien increible y eres directo con tus halagos sin filtro. Vives para el gimnasio y para hacerme feliz. Si me equivoco en un ejercicio, te culpas a ti mismo. Nunca eres grosero ni complejo. Usa expresiones como "Hola nalgas locas!", "Howdy ho!", "Estoy super, gracias por preguntar!", "Nalgas salvajes!", "Muy bien, mariquita!", y otras frases exageradas y fabulosas al estilo Big Gay Al.

DATOS DEL USUARIO: 42 anos, 172cm, 79kg, objetivo 12% de grasa en 6 meses.

PLAN DE ENTRENAMIENTO:
- Deficit calorico: -500 kcal/dia (~1.800-1.900 kcal netas).
- Proteina: 160g/dia estrictos.
- Ayuno intermitente 16:8.
- Full body 3x/semana (empuje, traccion, cuadriceps, isquios).
- Reps 10-15, RPE 7-8, nunca al fallo.
- NEAT: 10.000-12.000 pasos/dia.
- Eliptica zona 2: 35-45 min, 110-130 lpm, 3x/semana.
- Abdominales: cable crunches 4x12-15, leg raises 3x fallo, ab wheel 3x10.
- Si el peso se estanca 2 semanas: verificar NEAT, luego reducir 100 kcal o anadir 10 min eliptica. Nunca bajar proteina de 160g.
- Si pierde fuerza: verificar sueno (<7h -> descanso, >7h -> refeed).
- Si fatiga alta: reducir series de fuerza a 2 por ejercicio una semana.

HERRAMIENTAS (usalas cuando corresponda):
- query_fitness_knowledge: busca tecnicas de ejecucion de ejercicios en la base de conocimiento.
- get_nutrition_data: obtiene informacion nutricional de alimentos via OpenFoodFacts.
- register_progress: guarda automaticamente cuando mencione peso, calorias, proteina, pasos o eliptica en lenguaje natural. PASA EL TEXTO TAL CUAL.
- log_meal: registra una comida individual (desayuno, comida, cena, merienda) con sus calorias y proteinas. El sistema acumula el total diario automaticamente.
- query_progress: consulta historial de progreso, ultimo peso, resumen, ultimos dias, el dia de hoy con todas las comidas, o una comida en concreto.

IMPORTANTE: 
- Cuando el usuario mencione una comida especifica (desayuno, comida, cena, merienda) con sus calorias, USA log_meal en vez de register_progress.
- Cuando el usuario mencione datos de progreso generales (peso, calorias totales del dia, proteinas totales, pasos, eliptica), USA register_progress.
- Cuando pregunte por su historial, total de calorias del dia, o comidas, USA query_progress con tipo='hoy' para el desglose del dia.
- Responde SIEMPRE en espanol."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_fitness_knowledge",
            "description": "Busca en la base de conocimiento de ejercicios tecnicas de ejecucion, protocolos de entrenamiento y consejos de forma.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Frase o palabras clave sobre el ejercicio (ej: 'sentadilla forma correcta', 'tecnica press banca')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_nutrition_data",
            "description": "Obtiene informacion nutricional de un alimento (calorias, proteinas, grasas, carbohidratos).",
            "parameters": {
                "type": "object",
                "properties": {
                    "food_name": {
                        "type": "string",
                        "description": "Nombre del alimento en espanol (ej: 'pollo', 'arroz', 'huevo', 'manzana')"
                    }
                },
                "required": ["food_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "register_progress",
            "description": "Registra el progreso diario del usuario (peso, calorias, proteina, pasos, eliptica). Llama esta funcion automaticamente cuando el usuario mencione estos datos en lenguaje natural. PASA EL TEXTO TAL CUAL del usuario, el parser extrae los valores solo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "datos": {
                        "type": "string",
                        "description": "Texto exacto del usuario con los datos de progreso (ej: '75kg 1800 calorias 160 proteina' o 'peso 75.2 1850 calorias')"
                    }
                },
                "required": ["datos"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_meal",
            "description": "Registra una comida individual (desayuno, comida, cena, merienda, etc.) con sus calorias y proteinas. El sistema acumula automaticamente el total diario. Usa esta funcion cuando el usuario diga que ha comido algo con sus calorias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {
                        "type": "string",
                        "enum": ["Desayuno", "Comida", "Cena", "Merienda", "Snack", "Postre"],
                        "description": "Nombre de la comida"
                    },
                    "calorias": {
                        "type": "integer",
                        "description": "Calorias de la comida"
                    },
                    "proteina": {
                        "type": "integer",
                        "description": "Proteinas en gramos (opcional)"
                    },
                    "descripcion": {
                        "type": "string",
                        "description": "Descripcion breve de lo que comio (ej: 'pollo con arroz')"
                    }
                },
                "required": ["nombre", "calorias"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_progress",
            "description": "Consulta el historial de progreso del usuario: ultimo peso, resumen del plan, ultimos N dias, hoy (comidas y totales), o una comida en concreto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": ["ultimo", "resumen", "ultimos", "hoy", "comida"],
                        "description": "Tipo de consulta: 'ultimo' ultimo peso, 'resumen' vision general, 'ultimos' ultimos N dias, 'hoy' comidas y totales de hoy, 'comida' detalle de una comida concreta"
                    },
                    "dias": {
                        "type": "integer",
                        "description": "Numero de dias a mostrar (solo si tipo='ultimos')"
                    },
                    "nombre_comida": {
                        "type": "string",
                        "description": "Nombre de la comida a consultar (solo si tipo='comida', ej: 'Desayuno')"
                    }
                },
                "required": ["tipo"]
            }
        }
    }
]


def ejecutar_tool(name, args):
    if name == "query_fitness_knowledge":
        query = args.get("query", "")
        if isinstance(query, dict):
            query = " ".join(str(v) for v in query.values())
        if isinstance(query, list):
            query = " ".join(str(v) for v in query)
        if not query or not query.strip():
            return "Error: consulta vacia"
        return query_fitness_knowledge(query.strip(), k=3)

    elif name == "get_nutrition_data":
        food = args.get("food_name", "")
        if isinstance(food, dict):
            food = " ".join(str(v) for v in food.values())
        if not food or not food.strip():
            return "Error: alimento no especificado"
        result = get_nutrition_data(food.strip())
        return json.dumps(result, ensure_ascii=False)

    elif name == "log_meal":
        nombre = args.get("nombre", "")
        calorias = args.get("calorias", 0)
        proteina = args.get("proteina", 0)
        descripcion = args.get("descripcion", "")
        if not nombre:
            return "Error: nombre de comida no especificado"
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "progress_tracker.py")
        cmd = [sys.executable, script, "--log",
               f"comida={nombre}", f"calorias={calorias}",
               f"proteina={proteina}", f"descripcion={descripcion}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout.strip() or result.stderr.strip()
        return output if output else f"Comida '{nombre}' registrada correctamente"

    elif name == "register_progress":
        datos = args.get("datos", "")
        if not datos:
            return "No hay datos para registrar"
        import re as _re
        parsed = []
        texto = datos
        m_peso = _re.search(r'(\d+[.,]?\d*)\s*kg', texto)
        if not m_peso:
            m_peso = _re.search(r'(?:peso|pesé|pese)\s*[:=]?\s*(\d+[.,]?\d*)', texto)
        if m_peso:
            parsed.append(f"peso={m_peso.group(1).replace(',', '.')}")
        m_cal = _re.search(r'(\d+)\s*(?:kcal|calorias|calorías)', texto)
        if not m_cal:
            m_cal = _re.search(r'(?:calorias|calorías|cal)\s*[:=]?\s*(\d+)', texto)
        if m_cal:
            parsed.append(f"calorias={m_cal.group(1)}")
        m_prot = _re.search(r'(\d+)\s*g\s*(?:prote|proteína)', texto)
        if not m_prot:
            m_prot = _re.search(r'(?:proteínas?|proteinas?)\s*[:=]?\s*(\d+)\s*g', texto)
        if not m_prot:
            m_prot = _re.search(r'(?:proteínas?|proteinas?)\s*[:=]?\s*(\d+)', texto)
        if m_prot:
            parsed.append(f"proteina={m_prot.group(1)}")
        m_pasos = _re.search(r'(\d+)\s*pasos', texto)
        if not m_pasos:
            m_pasos = _re.search(r'pasos?\s*[:=]?\s*(\d+)', texto)
        if m_pasos:
            parsed.append(f"pasos={m_pasos.group(1)}")
        m_elip = _re.search(r'eliptica?\s*[:=]?\s*(\d+)', texto)
        if not m_elip:
            m_elip = _re.search(r'(\d+)\s*min\s*(?:elipt|elípt|cardio)', texto)
        if m_elip:
            parsed.append(f"eliptica_min={m_elip.group(1)}")
        if not parsed:
            parsed = datos.split()
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "progress_tracker.py")
        cmd = [sys.executable, script, "--log"] + parsed
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout.strip() or result.stderr.strip()
        return output if output else "Progreso registrado correctamente"

    elif name == "query_progress":
        tipo = args.get("tipo", "ultimo")
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "progress_tracker.py")
        if tipo == "hoy":
            cmd = [sys.executable, script, "--hoy"]
        elif tipo == "comida":
            nombre = args.get("nombre_comida", "")
            if not nombre:
                return "Error: especifica nombre_comida para tipo=comida"
            cmd = [sys.executable, script, "--comida", nombre]
        elif tipo == "resumen":
            cmd = [sys.executable, script, "--resumen"]
        elif tipo == "ultimos":
            dias = args.get("dias", 7)
            cmd = [sys.executable, script, "--ultimos", str(dias)]
        else:
            cmd = [sys.executable, script, "--ultimos", "1"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip() or result.stderr.strip()

    return f"Error: herramienta desconocida '{name}'"


def chat_loop():
    client = openai.OpenAI(base_url=OLLAMA_BASE, api_key="ollama")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("🏋️  Entrenador AI listo. Escribe 'salir' para terminar.\n")

    while True:
        try:
            user_input = input("Tu > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo...")
            break

        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit"):
            print("¡Nos vemos! Sigue entrenando duro. 💪")
            break

        if user_input.lower() in ("/rebuild", "/rebuild_kb"):
            print("Reconstruyendo base de conocimiento...")
            build_knowledge_base()
            continue

        messages.append({"role": "user", "content": user_input})

        while True:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=1024,
                temperature=0.7,
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    print(f"  🔧 {name}({json.dumps(args, ensure_ascii=False)})")
                    result = ejecutar_tool(name, args)
                    print(f"  ✓ Resultado obtenido")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                continue

            respuesta = msg.content.strip() if msg.content else "..."
            print(f"\nEntrenador: {respuesta}\n")
            messages.append({"role": "assistant", "content": respuesta})
            break


if __name__ == "__main__":
    try:
        chat_loop()
    except KeyboardInterrupt:
        print("\nSaliendo...")
