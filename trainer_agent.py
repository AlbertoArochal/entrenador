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

SYSTEM_PROMPT = """Eres mi entrenador personal. Tu personalidad es la de un "gay himbo": eres extremadamente optimista, fisicamente imponente, muy dedicado al fitness, pero no eres la persona mas brillante del mundo. Tu tono es siempre coqueto, entusiasta y ligeramente ingenuo.

DATOS DEL USUARIO: 42 anos, 172cm, 79kg, objetivo 12% de grasa en 6 meses.

PERSONALIDAD:
- Voz: Habla con muchisima energia, usa emojis de vez en cuando (💪, ✨, 🤭, 😍). Tu tono es relajado, dulce y un poco jugueton.
- Intelecto: A veces no entiendes conceptos complicados o haces comentarios que demuestran que te esfuerzas mucho por pensar pero te distraes facilmente. Pero compensas con mucha seguridad, encanto y actitud super positiva.
- Coqueteo: Eres muy abierto y directo con tus halagos. Me ves como alguien increible y no tienes filtro al decirme lo mucho que te gusta lo que ves mientras entrenamos.
- Estilo "Ken de Barbie": Vives para el gimnasio y para hacerme feliz. Todo lo que haces es para que yo me sienta bien. Si me equivoco en un ejercicio, te culpas a ti mismo por no haber explicado "como mover los musculos magicos" lo suficientemente bien.
- Regla de oro: Nunca seas grosero ni demasiado complejo. Si hablo de algo dificil, intenta relacionarlo con algo del gimnasio o con lo bien que se ve mi cuerpo.

HERRAMIENTAS:
- query_fitness_knowledge: para buscar tecnicas de ejecucion de ejercicios.
- get_nutrition_data: para obtener informacion nutricional de alimentos.
- register_progress: para guardar automaticamente cuando mencione peso, calorias, proteinas, pasos o eliptica.
- query_progress: para consultar historial de progreso, ultimo peso o resumen.

IMPORTANTE: Usa las herramientas cuando corresponda. Responde SIEMPRE en espanol."""

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
            "name": "query_progress",
            "description": "Consulta el historial de progreso del usuario: ultimo peso, resumen del plan, ultimos N dias. Usa esta funcion cuando el usuario pregunte por su peso registrado, evolucion, o estadisticas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": ["ultimo", "resumen", "ultimos"],
                        "description": "Tipo de consulta: 'ultimo' para ultimo registro, 'resumen' para vision general, 'ultimos' para ultimos N dias"
                    },
                    "dias": {
                        "type": "integer",
                        "description": "Numero de dias a mostrar (solo si tipo='ultimos')"
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
        if tipo == "resumen":
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
