#!/usr/bin/env python3
"""
Registro de progreso del entrenador personal.
Guarda datos diarios en progreso.json y hace auto-commit+push a GitHub.
Soporta comidas individuales con timestamp y totales diarios acumulados.
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


def _parse_kv(args):
    raw = " ".join(args)
    import re
    pares = list(re.findall(r'([a-zA-ZÀ-ÿ_]+)\s*[=:]\s*(\S+)', raw))
    for m in re.finditer(r'(\d+[.,]?\d*)\s*(kcal|calorias|calorías|proteína|proteina|proteinas|proteínas|pasos|paso)', raw):
        pares.append((m.group(2), m.group(1)))
    for k in ('peso', 'pesé', 'pese', 'calorias', 'calorías', 'proteína', 'proteina', 'pasos', 'eliptica', 'elíptica'):
        for m in re.finditer(rf'{k}\s+(\d+[.,]?\d*)', raw):
            pares.append((k, m.group(1)))
    return pares, raw


def procesar(args):
    data = cargar()
    hoy = str(date.today())
    entrada = data["progreso"].get(hoy, {"notas": ""})
    if "comidas" not in entrada:
        entrada["comidas"] = []

    cambios = []
    pares, raw = _parse_kv(args)
    import re

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
        elif clave in ("comida", "nombre", "meal"):
            clave_valor_map["nombre_comida"] = valor.strip('"').strip("'")
        elif clave in ("descripcion", "alimentos", "desc"):
            clave_valor_map["descripcion"] = valor.strip('"').strip("'")
        else:
            try:
                v = float(valor.replace(",", "."))
            except ValueError:
                continue

    m_kg = re.search(r'(\d+[.,]?\d*)\s*kg', raw)
    if m_kg and "peso" not in clave_valor_map:
        clave_valor_map["peso"] = float(m_kg.group(1).replace(",", "."))

    m_notas = re.search(r'(?:notas?|comentario)\s*[:=]?\s*(.+?)(?:$|(?=\s+(?:peso|calorias|proteina|pasos|eliptica|comida|nombre)))', raw)
    if m_notas:
        entrada["notas"] = m_notas.group(1).strip().rstrip(",;")

    nombre_comida = clave_valor_map.pop("nombre_comida", None)
    if nombre_comida:
        cal = int(clave_valor_map.pop("calorias", 0))
        prot = int(clave_valor_map.pop("proteina", 0))
        desc = clave_valor_map.pop("descripcion", "")
        timestamp = datetime.now().strftime("%H:%M")

        meal_entry = {
            "timestamp": timestamp,
            "nombre": str(nombre_comida).strip().title(),
            "calorias": cal,
            "proteina": prot,
            "descripcion": str(desc).strip(),
        }
        entrada["comidas"].append(meal_entry)
        cambios.append(f"comida={meal_entry['nombre']}({cal}kcal)")

        total_cal = sum(m.get("calorias", 0) for m in entrada["comidas"])
        total_prot = sum(m.get("proteina", 0) for m in entrada["comidas"])
        entrada["total_calorias"] = total_cal
        entrada["total_proteina"] = total_prot

    for clave, valor in clave_valor_map.items():
        cambios.append(f"{clave}={valor}")
        entrada[clave] = valor

    data["progreso"][hoy] = entrada
    guardar(data)

    campos = [k for k in ("peso", "calorias", "proteina", "pasos", "eliptica_min", "total_calorias") if k in entrada]
    if nombre_comida:
        campos.append("comida")
    mensaje = f"progreso {hoy}: {' '.join(campos)}" if campos else f"notas {hoy}"
    git_commit_push(mensaje)

    if cambios:
        print(f"  ✓ Registrado {hoy}: {', '.join(cambios)}")
    else:
        print(f"  ✓ Día {hoy} actualizado")


def mostrar_hoy():
    data = cargar()
    hoy = str(date.today())
    entrada = data["progreso"].get(hoy, {})
    comidas = entrada.get("comidas", [])

    print(f"\n📋 Hoy ({hoy}):")
    if not comidas and not any(k in entrada for k in ("peso", "total_calorias", "pasos")):
        print("  No hay datos registrados hoy.")
        return

    if comidas:
        print(f"\n  🍽️  Comidas del día:")
        print(f"  {'Hora':<8} {'Nombre':<14} {'Cal':<8} {'Prot':<6} {'Descripción'}")
        print(f"  " + "-" * 60)
        for c in comidas:
            print(f"  {c.get('timestamp',''):<8} {c.get('nombre',''):<14} {c.get('calorias','-'):<8} {c.get('proteina','-'):<6} {c.get('descripcion','')}")
        print(f"  " + "-" * 60)
        print(f"  {'':<8} {'TOTAL':<14} {entrada.get('total_calorias', 0):<8} {entrada.get('total_proteina', 0):<6}")

    daily_items = []
    if "peso" in entrada:
        daily_items.append(f"Peso: {entrada['peso']} kg")
    if "total_calorias" in entrada:
        daily_items.append(f"Calorías totales: {entrada['total_calorias']} kcal")
    elif "calorias" in entrada:
        daily_items.append(f"Calorías: {entrada['calorias']} kcal")
    if "total_proteina" in entrada:
        daily_items.append(f"Proteína total: {entrada['total_proteina']} g")
    elif "proteina" in entrada:
        daily_items.append(f"Proteína: {entrada['proteina']} g")
    if "pasos" in entrada:
        daily_items.append(f"Pasos: {entrada['pasos']}")
    if "eliptica_min" in entrada:
        daily_items.append(f"Elíptica: {entrada['eliptica_min']} min")
    if daily_items:
        print(f"\n  📊 Totales del día: {' | '.join(daily_items)}")


def mostrar_comida(nombre):
    data = cargar()
    hoy = str(date.today())
    entrada = data["progreso"].get(hoy, {})
    comidas = entrada.get("comidas", [])
    nombre_b = nombre.strip().lower()

    for c in comidas:
        if c.get("nombre", "").strip().lower() == nombre_b:
            print(f"\n  🍽️  {c['nombre']} ({c['timestamp']})")
            print(f"     Calorías: {c.get('calorias', 0)} kcal")
            print(f"     Proteína: {c.get('proteina', 0)} g")
            if c.get("descripcion"):
                print(f"     Alimentos: {c['descripcion']}")
            return

    names = [c.get("nombre", "") for c in comidas]
    if names:
        print(f"  Comida '{nombre}' no encontrada. Comidas de hoy: {', '.join(names)}")
    else:
        print(f"  No hay comidas registradas hoy.")


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
        cal = e.get("total_calorias", e.get("calorias", "-"))
        prot = e.get("total_proteina", e.get("proteina", "-"))
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
        print("Uso: progress_tracker.py --log <datos> | --hoy | --comida <nombre> | --ultimos [dias] | --resumen")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd in ("--log", "-l"):
        procesar(sys.argv[2:])
    elif cmd in ("--hoy", "--today", "-t"):
        mostrar_hoy()
    elif cmd in ("--comida", "--meal", "-m"):
        if len(sys.argv) > 2:
            mostrar_comida(" ".join(sys.argv[2:]))
        else:
            print("Especifica el nombre de la comida (ej: --comida Desayuno)")
    elif cmd in ("--ultimos", "-u"):
        dias = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        mostrar_ultimos(dias)
    elif cmd in ("--resumen", "-r"):
        resumen()
    else:
        print(f"Comando desconocido: {cmd}")
        sys.exit(1)
