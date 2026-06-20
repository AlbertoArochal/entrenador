# 🏋️ AI Personal Trainer

Entrenador personal con IA, multi-usuario, con registro automático de progreso, consulta nutricional y base de conocimiento de ejercicios. Usa Qwen 2.5 via Ollama con function calling.

## Requisitos

- Python 3.11+
- [Ollama](https://ollama.ai) con modelo `qwen2.5:14b`
- ChromaDB + SentenceTransformers (para RAG de ejercicios)

```bash
ollama pull qwen2.5:14b
pip install openai chromadb sentence-transformers requests
```

## Inicio rápido

```bash
python3 trainer_agent.py
```

El asistente pedirá **nombre y contraseña**:

- **Usuario nuevo** → flujo de registro (edad, altura, peso, objetivo)
- **Usuario existente** → verifica contraseña y entra al chat

### CLI también acepta:

```bash
# Especificar usuario directamente
python3 trainer_agent.py --usuario Alberto

# Ver perfil sin entrar al chat
python3 trainer_agent.py --usuario Alberto --perfil
```

## Arquitectura

```
trainer_agent.py        ← CLI chat con function calling (Qwen + Ollama)
├── nutrition_tool.py   ← Consulta nutricional (OpenFoodFacts)
├── progress_tracker.py ← Persistencia multi-usuario + auto-commit GitHub
├── knowledge_base.py   ← RAG de ejercicios (ChromaDB + SentenceTransformers)
├── entrenador_ia.md    ← Documento de referencia del system prompt
└── Modelfile           ← Configuración del modelo Ollama
```

## Capacidades

### 🔐 Autenticación multi-usuario

- Registro con nombre, contraseña y perfil (edad, altura, peso, objetivo)
- Login con verificación de contraseña (SHA256)
- Datos de progreso aislados por usuario
- Cambio de contraseña desde línea de comandos

### 📊 Registro automático de progreso

El modelo detecta en lenguaje natural cuando mencionas peso, calorías, pasos, etc. y lo guarda automáticamente.

```
Tu > hoy peso 78.5kg, 1800 calorias, 160g proteina, 11000 pasos
```

**Comandos del tracker:**

| Comando | Descripción |
|---------|-------------|
| `--log peso=XX calorias=XX ...` | Registrar progreso |
| `--log comida=Desayuno calorias=400 proteina=20 descripcion="avena"` | Registrar comida |
| `--hoy` | Ver comidas y totales del día |
| `--comida <nombre>` | Ver detalle de una comida |
| `--ultimos [dias]` | Historial de últimos N días |
| `--resumen` | Resumen global del plan |
| `--perfil` | Ver perfil del usuario |
| `--users` | Listar todos los usuarios |
| `--set-password` | Cambiar contraseña |

### 🍽️ Registro de comidas

Las comidas se guardan con timestamp y se acumulan automáticamente en el total diario.

```bash
python3 progress_tracker.py --usuario Alberto --log comida=Desayuno calorias=400 proteina=20 descripcion="avena con leche"
python3 progress_tracker.py --usuario Alberto --log comida=Comida calorias=494 proteina=50 descripcion="pollo con arroz"
python3 progress_tracker.py --usuario Alberto --hoy
```

### 🔎 Consulta nutricional (OpenFoodFacts)

Consulta información nutricional de alimentos via API de OpenFoodFacts con reintentos automáticos ante 503.

```bash
python3 nutrition_tool.py "pollo"
```

### 📚 Base de conocimiento de ejercicios (RAG)

Usa ChromaDB + SentenceTransformers para buscar técnicas de ejecución de ejercicios.

```bash
# Reconstruir base de conocimiento desde HuggingFace
python3 trainer_agent.py  # luego /rebuild en el chat
```

### 🤖 Tools del modelo (function calling)

El modelo tiene acceso a 6 herramientas:

| Tool | Función |
|------|---------|
| `query_fitness_knowledge` | Busca técnicas de ejercicios en la base RAG |
| `get_nutrition_data` | Consulta información nutricional de alimentos |
| `log_meal` | Registra una comida (desayuno, comida, cena, etc.) |
| `register_progress` | Registra peso, calorías totales, pasos, etc. |
| `query_progress` | Consulta historial, hoy, resumen, comidas |
| `register_user` | Crea o actualiza perfil de usuario |

### 💾 Persistencia automática (Git)

Cada registro se guarda en `progreso.json` y se hace **commit + push automático** a GitHub.

### 🎭 Personalidad del entrenador

Personalidad "gay himbo" mezclada con Big Gay Al de South Park: optimista, entusiasta, coqueto, ligeramente ingenuo, dedicado al fitness. Habla siempre en español con emojis (💪✨🤭😍).

## Plan de entrenamiento base

- **Déficit calórico**: -500 kcal/día (~1.800-1.900 kcal netas)
- **Proteína**: 160g/día estrictos
- **Ayuno intermitente**: 16:8
- **Fuerza**: Full body 3x/semana, 10-15 reps, RPE 7-8
- **NEAT**: 10.000-12.000 pasos/día
- **Cardio**: Elíptica zona 2, 35-45 min, 3x/semana
- **Abdominales**: Cable crunches, leg raises, ab wheel

## Licencia

Uso personal.
