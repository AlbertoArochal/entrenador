#!/usr/bin/env python3
"""
Registro de progreso del entrenador personal.
Soporta multiples usuarios con autenticacion por nombre y password.
Guarda datos en progreso.json y hace auto-commit+push a GitHub.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(REPO_DIR, "progreso.json")


def _hash(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()


def _user_id(nombre):
    return nombre.strip().lower().replace(' ', '_')


def _migrar(data):
    if "usuarios" not in data:
        old_cliente = data.get("cliente", {})
        old_progreso = data.get("progreso", {})
        nombre = old_cliente.get("nombre", "Usuario").strip()
        if not nombre:
            nombre = "Usuario"
        uid = _user_id(nombre)
        data = {
            "usuarios": {
                uid: {
                    "password": _hash("cambiame"),
                    "cliente": {**old_cliente, "nombre": nombre},
                    "progreso": old_progreso,
                }
            }
        }
        guardar(data)
        print(f"  ↪ Datos migrados a multi-usuario: {uid}")
        return data

    changed = False
    for uid in list(data["usuarios"].keys()):
        if "_" in uid:
            parts = uid.rsplit("_", 1)
            if parts[1].isdigit():
                nuevo_uid = parts[0]
                if nuevo_uid in data["usuarios"]:
                    data["usuarios"][nuevo_uid]["progreso"].update(data["usuarios"][uid].get("progreso", {}))
                    del data["usuarios"][uid]
                else:
                    data["usuarios"][nuevo_uid] = data["usuarios"].pop(uid)
                if "password" not in data["usuarios"].get(nuevo_uid, {}):
                    data["usuarios"][nuevo_uid]["password"] = _hash("cambiame")
                changed = True

    for uid in list(data["usuarios"].keys()):
        if "password" not in data["usuarios"][uid]:
            data["usuarios"][uid]["password"] = _hash("cambiame")
            changed = True

    if changed:
        guardar(data)
    return data


def cargar():
    if not os.path.exists(DATA_FILE):
        return {"usuarios": {}}
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    return _migrar(data)


def guardar(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


PUSH_MARKER = os.path.join(REPO_DIR, ".last_push")


def git_commit(mensaje):
    try:
        os.chdir(REPO_DIR)
        subprocess.run(["git", "add", "."], capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", mensaje], capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  ✓ Commit: {mensaje}")
            git_push_daily()
        else:
            if "nothing to commit" in result.stderr or "nothing to commit" in result.stdout:
                pass
            else:
                print(f"  ⚠ {result.stderr.strip()}")
    except Exception as e:
        print(f"  ⚠ Error en git: {e}")


def git_push_daily():
    try:
        hoy = str(date.today())
        if os.path.exists(PUSH_MARKER):
            with open(PUSH_MARKER) as f:
                if f.read().strip() == hoy:
                    return
        subprocess.run(["git", "push"], capture_output=True, timeout=30)
        with open(PUSH_MARKER, "w") as f:
            f.write(hoy)
        print(f"  ✓ Push diario completado")
    except Exception as e:
        print(f"  ⚠ Error en push: {e}")


def login(nombre, password):
    data = cargar()
    uid = _user_id(nombre)
    if uid not in data["usuarios"]:
        return "NOT_FOUND"
    if data["usuarios"][uid].get("password") != _hash(password):
        return "WRONG_PASSWORD"
    cliente = data["usuarios"][uid].get("cliente", {})
    return json.dumps({"status": "ok", "cliente": cliente}, ensure_ascii=False)


def register(nombre, password, **kwargs):
    data = cargar()
    uid = _user_id(nombre)
    if uid in data["usuarios"]:
        return "EXISTS"
    data["usuarios"][uid] = {
        "password": _hash(password),
        "cliente": {"nombre": nombre.strip().title(), **kwargs},
        "progreso": {},
    }
    guardar(data)
    git_commit(f"[{nombre}] nuevo usuario registrado")
    return "OK"


def cambiar_password(nombre, old_password, new_password):
    data = cargar()
    uid = _user_id(nombre)
    if uid not in data["usuarios"]:
        return "NOT_FOUND"
    if data["usuarios"][uid].get("password") != _hash(old_password):
        return "WRONG_PASSWORD"
    data["usuarios"][uid]["password"] = _hash(new_password)
    guardar(data)
    git_commit(f"[{nombre}] password cambiada")
    return "OK"


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


def procesar(args, uid, nombre):
    data = cargar()
    if uid not in data["usuarios"]:
        return print(f"  Usuario '{nombre}' no encontrado.")
    usuario = data["usuarios"][uid]
    hoy = str(date.today())
    entrada = usuario["progreso"].get(hoy, {"notas": ""})
    if "comidas" not in entrada:
        entrada["comidas"] = []

    cambios = []
    pares, raw = _parse_kv(args)
    import re

    cliente_map = {}
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
        elif clave in ("altura", "talla"):
            try:
                cliente_map["altura"] = int(valor)
            except ValueError:
                pass
        elif clave in ("peso_inicial", "peso_inicial_kg"):
            try:
                cliente_map["peso_inicial"] = float(valor.replace(",", "."))
            except ValueError:
                pass
        elif clave in ("peso_objetivo", "objetivo"):
            try:
                cliente_map["peso_objetivo"] = float(valor.replace(",", "."))
            except ValueError:
                pass
        elif clave in ("grasa_inicial", "grasa"):
            cliente_map["grasa_inicial"] = valor
        else:
            try:
                v = float(valor.replace(",", "."))
            except ValueError:
                continue

    m_kg = re.search(r'(\d+[.,]?\d*)\s*kg', raw)
    if m_kg and "peso" not in clave_valor_map:
        clave_valor_map["peso"] = float(m_kg.group(1).replace(",", "."))

    m_notas = re.search(r'(?:notas?|comentario)\s*[:=]?\s*(.+?)(?:$|(?=\s+(?:peso|calorias|proteina|pasos|eliptica|comida|nombre|altura|peso_objetivo)))', raw)
    if m_notas:
        entrada["notas"] = m_notas.group(1).strip().rstrip(",;")

    if cliente_map:
        usuario["cliente"].update(cliente_map)
        cambios.extend(f"perfil:{k}={v}" for k, v in cliente_map.items())

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

    usuario["progreso"][hoy] = entrada
    guardar(data)

    campos = [k for k in ("peso", "calorias", "proteina", "pasos", "eliptica_min", "total_calorias") if k in entrada]
    if nombre_comida:
        campos.append("comida")
    mensaje = f"[{nombre}] progreso {hoy}: {' '.join(campos)}" if campos else f"[{nombre}] notas {hoy}"
    git_commit(mensaje)

    if cambios:
        print(f"  ✓ {nombre}: {', '.join(cambios)}")
    else:
        print(f"  ✓ {nombre}: Día {hoy} actualizado")


def init_usuario(uid, nombre, **kwargs):
    data = cargar()
    if uid in data["usuarios"]:
        print(f"  ⚠ Usuario '{nombre}' ya existe. Actualizando perfil.")
        data["usuarios"][uid]["cliente"].update(kwargs)
    else:
        data["usuarios"][uid] = {
            "password": _hash("cambiame"),
            "cliente": {"nombre": nombre.strip().title(), **kwargs},
            "progreso": {},
        }
    guardar(data)
    print(f"  ✓ Usuario '{nombre}' inicializado.")
    git_commit(f"[{nombre}] perfil actualizado")


def mostrar_hoy(uid, nombre):
    data = cargar()
    if uid not in data["usuarios"]:
        print(f"  Usuario '{nombre}' no encontrado.")
        return
    progreso = data["usuarios"][uid]["progreso"]
    hoy = str(date.today())
    entrada = progreso.get(hoy, {})
    comidas = entrada.get("comidas", [])

    print(f"\n📋 {nombre} - Hoy ({hoy}):")
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
        daily_items.append(f"Calorías: {entrada['total_calorias']} kcal")
    elif "calorias" in entrada:
        daily_items.append(f"Calorías: {entrada['calorias']} kcal")
    if "total_proteina" in entrada:
        daily_items.append(f"Proteína: {entrada['total_proteina']} g")
    elif "proteina" in entrada:
        daily_items.append(f"Proteína: {entrada['proteina']} g")
    if "pasos" in entrada:
        daily_items.append(f"Pasos: {entrada['pasos']}")
    if "eliptica_min" in entrada:
        daily_items.append(f"Elíptica: {entrada['eliptica_min']} min")
    if daily_items:
        print(f"\n  📊 Totales del día: {' | '.join(daily_items)}")


def mostrar_comida(nombre_comida, uid, nombre):
    data = cargar()
    if uid not in data["usuarios"]:
        print(f"  Usuario '{nombre}' no encontrado.")
        return
    progreso = data["usuarios"][uid]["progreso"]
    hoy = str(date.today())
    entrada = progreso.get(hoy, {})
    comidas = entrada.get("comidas", [])
    target = nombre_comida.strip().lower()

    for c in comidas:
        if c.get("nombre", "").strip().lower() == target:
            print(f"\n  🍽️  {c['nombre']} ({c['timestamp']})")
            print(f"     Calorías: {c.get('calorias', 0)} kcal")
            print(f"     Proteína: {c.get('proteina', 0)} g")
            if c.get("descripcion"):
                print(f"     Alimentos: {c['descripcion']}")
            return

    names = [c.get("nombre", "") for c in comidas]
    if names:
        print(f"  Comida '{nombre_comida}' no encontrada. Comidas de hoy: {', '.join(names)}")
    else:
        print(f"  No hay comidas registradas hoy.")


def mostrar_ultimos(dias, uid, nombre):
    data = cargar()
    if uid not in data["usuarios"]:
        print(f"  Usuario '{nombre}' no encontrado.")
        return
    progreso = data["usuarios"][uid]["progreso"]
    fechas = sorted(progreso.keys(), reverse=True)[:dias]
    print(f"\n{nombre} - Últimos {len(fechas)} días:")
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


def resumen(uid, nombre):
    data = cargar()
    if uid not in data["usuarios"]:
        print(f"  Usuario '{nombre}' no encontrado.")
        return
    usuario = data["usuarios"][uid]
    progreso = usuario["progreso"]
    cliente = usuario["cliente"]
    fechas = sorted(progreso.keys())
    if not fechas:
        print(f"  {nombre}: No hay datos registrados.")
        return
    inicio = fechas[0]
    total_dias = len(fechas)
    semanas = total_dias // 7
    primer_peso = progreso[fechas[0]].get("peso")
    ultimo_peso = progreso[fechas[-1]].get("peso")
    perdido = ""
    if primer_peso and ultimo_peso:
        perdido = f"{primer_peso - ultimo_peso:.1f} kg"
    print(f"\n📊 {nombre} - Resumen del plan:")
    if cliente.get("edad"):
        print(f"  Edad: {cliente['edad']} años")
    if cliente.get("altura"):
        print(f"  Altura: {cliente['altura']} cm")
    if cliente.get("peso_objetivo"):
        print(f"  Peso objetivo: {cliente['peso_objetivo']} kg")
    print(f"  Inicio: {inicio}")
    print(f"  Días registrados: {total_dias} ({semanas} semanas)")
    if perdido:
        print(f"  Peso perdido: {perdido}")
    print(f"  Último peso: {ultimo_peso} kg" if ultimo_peso else "")


def listar_usuarios():
    data = cargar()
    if not data["usuarios"]:
        print("  No hay usuarios registrados.")
        return
    print("\n👥 Usuarios registrados:")
    for uid, info in data["usuarios"].items():
        c = info["cliente"]
        edad = c.get("edad", "?")
        peso_obj = c.get("peso_objetivo", "")
        nombre = c.get("nombre", uid.title())
        has_pwd = info.get("password") and info["password"] != _hash("cambiame")
        print(f"  - {nombre} ({edad} años)" + (f" → {peso_obj} kg" if peso_obj else "") + ("" if has_pwd else " ⚠️  password por defecto"))


def mostrar_perfil(uid, nombre):
    data = cargar()
    if uid not in data["usuarios"]:
        print(f"  Usuario '{nombre}' no encontrado.")
        return
    c = data["usuarios"][uid]["cliente"]
    print(f"\n📋 Perfil de {c.get('nombre', nombre)}:")
    for k, v in c.items():
        if k != "nombre":
            print(f"  {k.replace('_', ' ').title()}: {v}")


def mostrar_usuario_info(uid, nombre):
    data = cargar()
    if uid not in data["usuarios"]:
        return ""
    c = data["usuarios"][uid]["cliente"]
    parts = [f"{c.get('nombre', nombre)}"]
    if c.get("edad"):
        parts.append(f"{c['edad']} años")
    if c.get("altura"):
        parts.append(f"{c['altura']}cm")
    if c.get("peso_inicial"):
        parts.append(f"{c['peso_inicial']}kg inicial")
    if c.get("peso_objetivo"):
        parts.append(f"objetivo {c['peso_objetivo']}kg")
    if c.get("grasa_inicial"):
        parts.append(f"grasa {c['grasa_inicial']}")
    return " | ".join(parts)


if __name__ == "__main__":
    args = sys.argv[1:]

    usuario = None
    password = None

    while args and args[0] in ("--usuario", "--user", "-u"):
        if len(args) < 2:
            print("  Error: --usuario requiere un nombre")
            sys.exit(1)
        usuario = args[1]
        args = args[2:]

    while args and args[0] in ("--password", "--pass", "-p"):
        if len(args) < 2:
            print("  Error: --password requiere una contraseña")
            sys.exit(1)
        password = args[1]
        args = args[2:]

    if not args:
        print("Uso: progress_tracker.py [--usuario <nombre>] [--password <pass>] <comando> [args...]")
        print("Comandos: --login | --register | --set-password | --log <datos> | --hoy | --comida <nombre> | --ultimos [dias] | --resumen | --init | --users | --perfil")
        sys.exit(1)

    cmd = args[0]

    if cmd == "--users":
        listar_usuarios()
        sys.exit(0)

    if cmd == "--login":
        if not usuario:
            print("  Error: --login requiere --usuario")
            sys.exit(1)
        if not password:
            import getpass
            password = getpass.getpass("  Contraseña: ")
        result = login(usuario, password)
        print(result)
        sys.exit(0)

    if cmd == "--register":
        if not usuario:
            print("  Error: --register requiere --usuario")
            sys.exit(1)
        if not password:
            import getpass
            password = getpass.getpass("  Contraseña: ")
            pwd2 = getpass.getpass("  Repite contraseña: ")
            if password != pwd2:
                print("  Error: las contraseñas no coinciden")
                sys.exit(1)
        kwargs = {}
        rest = args[1:]
        i = 0
        while i < len(rest):
            k = rest[i].lstrip("--").replace("-", "_")
            if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
                v = rest[i + 1]
                try:
                    v = int(v)
                except ValueError:
                    try:
                        v = float(v)
                    except ValueError:
                        pass
                kwargs[k] = v
                i += 2
            else:
                i += 1
        result = register(usuario, password, **kwargs)
        if result == "EXISTS":
            print(f"  Error: el usuario '{usuario}' ya existe. Usa --login o --set-password.")
        elif result == "OK":
            print(f"  ✓ Usuario '{usuario}' registrado correctamente.")
        else:
            print(result)
        sys.exit(0)

    if cmd == "--set-password":
        if not usuario or not password:
            print("  Error: --set-password requiere --usuario y --password (actual)")
            sys.exit(1)
        import getpass
        new_pwd = getpass.getpass("  Nueva contraseña: ")
        pwd2 = getpass.getpass("  Repite contraseña: ")
        if new_pwd != pwd2:
            print("  Error: las contraseñas no coinciden")
            sys.exit(1)
        result = cambiar_password(usuario, password, new_pwd)
        if result == "NOT_FOUND":
            print(f"  Error: usuario '{usuario}' no encontrado.")
        elif result == "WRONG_PASSWORD":
            print("  Error: contraseña actual incorrecta.")
        elif result == "OK":
            print(f"  ✓ Contraseña actualizada para '{usuario}'.")
        sys.exit(0)

    if not usuario:
        print("  Error: este comando requiere --usuario <nombre>")
        sys.exit(1)

    uid = _user_id(usuario)

    if cmd == "--init":
        kwargs = {}
        rest = args[1:]
        i = 0
        while i < len(rest):
            k = rest[i].lstrip("--").replace("-", "_")
            if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
                v = rest[i + 1]
                try:
                    v = int(v)
                except ValueError:
                    try:
                        v = float(v)
                    except ValueError:
                        pass
                kwargs[k] = v
                i += 2
            else:
                i += 1
        init_usuario(uid, usuario, **kwargs)
        sys.exit(0)

    if cmd in ("--perfil", "--profile"):
        mostrar_perfil(uid, usuario)
        sys.exit(0)

    if cmd in ("--log", "-l"):
        procesar(args[1:], uid, usuario)
    elif cmd in ("--hoy", "--today", "-t"):
        mostrar_hoy(uid, usuario)
    elif cmd in ("--comida", "--meal", "-m"):
        if len(args) > 1:
            mostrar_comida(" ".join(args[1:]), uid, usuario)
        else:
            print("  Especifica el nombre de la comida (ej: --comida Desayuno)")
    elif cmd in ("--ultimos", "-u"):
        dias = int(args[1]) if len(args) > 1 else 7
        mostrar_ultimos(dias, uid, usuario)
    elif cmd in ("--resumen", "-r"):
        resumen(uid, usuario)
    else:
        print(f"  Comando desconocido: {cmd}")
        sys.exit(1)
