#!/usr/bin/env python3
"""
Registro de progreso del entrenador personal.
Guarda datos diarios en progreso.json y hace auto-commit+push a GitHub.
"""

import json
import os
import subprocess
import sys
from datetime import date, datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(REPO_DIR, "progreso.json")
GIT_REMOTE = "https://github.com/AlbertoArochal/entrenador.git"


def cargar():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "cliente": {
            "edad": 42,
            "altura": 172,
            "peso_inicial": 79,
            "grasa_inicial": "20-22%",
            "peso_objetivo": 71,
        },
        "progreso": {},
    }


def guardar(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def git_commit_push(mensaje):
    try:
        os.chdir(REPO_DIR)
        subprocess.run(["git", "add", "."], capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", mensaje], capture_output=True, text=True
        )
        if result.returncode == 0:
            subprocess.run(["git", "push"], capture_output=True)
            print(f"  ✓ Commit + push: {mensaje}")
        else:
            if "nothing to commit" in result.stderr or "nothing to commit" in result.stdout:
                pass
            else:
                print(f"  ⚠ {result.stderr.strip()}")
    except Exception as e:
        print(f"  ⚠ Error en git: {e}")


def procesar(args):
    data = cargar()
    hoy = str(date.today())
    entrada = data["progreso"].get(hoy, {"notas": ""})

    cambios = []
    raw = " ".join(args)
    import re

    # 1) key=value or key:value
    pares = list(re.findall(r'([a-zA-ZÀ-ÿ_]+)\s*[=:]\s*(\S+)', raw))
    # 2) value key  (e.g. "1800 calorias", "165 proteina")
    for m in re.finditer(r'(\d+[.,]?\d*)\s*(kcal|calorias|calorías|proteína|proteina|proteinas|proteínas|pasos|paso)', raw):
        pares.append((m.group(2), m.group(1)))
    # 3) key then value separated by whitespace  (e.g. "peso 76.8")
    for k in ('peso', 'pesé', 'pese', 'calorias', 'calorías', 'proteína', 'proteina', 'pasos', 'eliptica', 'elíptica'):
        for m in re.finditer(rf'{k}\s+(\d+[.,]?\d*)', raw):
            pares.append((k, m.group(1)))

    clave_valor_map = {}
    for clave, valor in pares:
        clave = clave.strip().lower().replace(" ", "_")
        valor = valor.strip().rstrip(",;").strip()

        if clave in ("peso", "pesé", "pese"):
            if "peso" not in clave_valor_map:
                try:
                    v = float(valor.replace("kg", "").replace(",", ".").strip())
                    clave_valor_map["peso"] = v
                except ValueError:
                    pass
        elif clave in ("calorias", "calorías", "kcal"):
            if "calorias" not in clave_valor_map:
                try:
                    v = int(valor.replace("kcal", "").replace("cal", "").strip())
                    clave_valor_map["calorias"] = v
                except ValueError:
                    pass
        elif clave in ("proteina", "proteína", "proteinas", "proteínas"):
            if "proteina" not in clave_valor_map:
                try:
                    v = int(valor.replace("g", "").strip())
                    clave_valor_map["proteina"] = v
                except ValueError:
                    pass
        elif clave in ("pasos", "paso"):
            if "pasos" not in clave_valor_map:
                try:
                    v = int(valor.replace(",", "").strip())
                    clave_valor_map["pasos"] = v
                except ValueError:
                    pass
        elif clave in ("eliptica", "elíptica", "eliptica_min", "cardio", "min"):
            if "eliptica_min" not in clave_valor_map:
                try:
                    v = int(valor.replace("min", "").replace("minutos", "").strip())
                    clave_valor_map["eliptica_min"] = v
                except ValueError:
                    pass
        else:
            try:
                v = float(valor.replace(",", "."))
            except ValueError:
                continue

    # Also detect standalone "XXkg" patterns
    m_kg = re.search(r'(\d+[.,]?\d*)\s*kg', raw)
    if m_kg and "peso" not in clave_valor_map:
        clave_valor_map["peso"] = float(m_kg.group(1).replace(",", "."))

    # Check for notas in raw text
    m_notas = re.search(r'(?:notas?|comentario)\s*[:=]?\s*(.+?)(?:$|(?=\s+(?:peso|calorias|proteina|pasos|eliptica)))', raw)
    if m_notas:
        entrada["notas"] = m_notas.group(1).strip().rstrip(",;")

    for clave, valor in clave_valor_map.items():
        cambios.append(f"{clave}={valor}")
        entrada[clave] = valor

    data["progreso"][hoy] = entrada
    guardar(data)

    campos_registrados = [k for k in ("peso", "calorias", "proteina", "pasos", "eliptica_min") if k in entrada]
    mensaje = f"progreso {hoy}: {' '.join(campos_registrados)}" if campos_registrados else f"notas {hoy}"
    git_commit_push(mensaje)

    if cambios:
        print(f"  ✓ Registrado {hoy}: {', '.join(cambios)}")
    else:
        print(f"  ✓ Día {hoy} actualizado")


def mostrar_ultimos(dias=7):
    data = cargar()
    progreso = data["progreso"]
    fechas = sorted(progreso.keys(), reverse=True)[:dias]
    print(f"\nÚltimos {len(fechas)} días de progreso:")
    print(f"{'Fecha':<14} {'Peso':<8} {'Cal':<8} {'Prot':<6} {'Pasos':<8} {'Elip':<6}")
    print("-" * 60)
    for f in fechas:
        e = progreso[f]
        peso = e.get("peso", "-")
        cal = e.get("calorias", "-")
        prot = e.get("proteina", "-")
        pasos = e.get("pasos", "-")
        elip = e.get("eliptica_min", "-")
        print(f"{f:<14} {str(peso):<8} {str(cal):<8} {str(prot):<6} {str(pasos):<8} {str(elip):<6}")


def resumen():
    data = cargar()
    progreso = data["progreso"]
    fechas = sorted(progreso.keys())
    if not fechas:
        print("  No hay datos registrados.")
        return
    inicio = fechas[0]
    total_dias = len(fechas)
    semanas = total_dias // 7
    primer_peso = progreso[fechas[0]].get("peso")
    ultimo_peso = progreso[fechas[-1]].get("peso")
    perdido = ""
    if primer_peso and ultimo_peso:
        perdido = f"{primer_peso - ultimo_peso:.1f} kg"
    print(f"\n📊 Resumen del plan:")
    print(f"  Inicio: {inicio}")
    print(f"  Días registrados: {total_dias} ({semanas} semanas)")
    if perdido:
        print(f"  Peso perdido: {perdido}")
    print(f"  Último peso: {ultimo_peso} kg" if ultimo_peso else "")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: progress_tracker.py --log <datos> | --ultimos [dias] | --resumen")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd in ("--log", "-l"):
        procesar(sys.argv[2:])
    elif cmd in ("--ultimos", "-u"):
        dias = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        mostrar_ultimos(dias)
    elif cmd in ("--resumen", "-r"):
        resumen()
    else:
        print(f"Comando desconocido: {cmd}")
        sys.exit(1)
