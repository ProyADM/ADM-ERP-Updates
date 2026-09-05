# deploy_update.py
# ============================================================
# DEPLOY SIMPLIFICADO - SIN ZIP (SOLO PARA GITHUB)
# ============================================================

import os
import sys
import json
import shutil
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIGURACIÓN
# ============================================================

VERSION_FILE = "version.json"
CHANGELOG_FILE = "CHANGELOG.md"
MANIFEST_FILE = "manifest.json"

# Archivos a ignorar
IGNORAR_ARCHIVOS = [
    'venv', '__pycache__', '.git', 'data', 
    'updates', 'backups', 'build', 'dist',
    '*.pyc', '*.pyo', '.DS_Store',
    'node_modules', '*.log', '*.tmp', '*.swp'
]

# ============================================================
# FUNCIONES DE VERSIÓN
# ============================================================

def leer_version_actual():
    """Lee la versión actual desde version.json"""
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('version', '1.0.0')
    except:
        return '1.0.0'

def incrementar_version(version, tipo):
    """Incrementa la versión según el tipo"""
    parts = version.split('.')
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    
    if tipo == 'patch':
        patch += 1
        tipo_nombre = "PATCH (Corrección de bugs)"
    elif tipo == 'minor':
        minor += 1
        patch = 0
        tipo_nombre = "MINOR (Nueva funcionalidad)"
    elif tipo == 'major':
        major += 1
        minor = 0
        patch = 0
        tipo_nombre = "MAJOR (Cambio incompatible)"
    else:
        return None, None
    
    nueva_version = f"{major}.{minor}.{patch}"
    return nueva_version, tipo_nombre

# ============================================================
# FUNCIONES DE CHANGELOG
# ============================================================

def actualizar_changelog(version, tipo, cambios):
    """Actualiza el archivo CHANGELOG.md con la nueva versión"""
    print(f"\n📝 Actualizando CHANGELOG.md...")
    
    # Separar cambios por categoría
    cambios_added = []
    cambios_fixed = []
    cambios_changed = []
    cambios_otros = []
    
    for cambio in cambios:
        if cambio.startswith('+'):
            cambios_added.append(cambio.replace('+', '').strip())
        elif cambio.startswith('!'):
            cambios_fixed.append(cambio.replace('!', '').strip())
        elif cambio.startswith('~'):
            cambios_changed.append(cambio.replace('~', '').strip())
        else:
            cambios_otros.append(cambio.strip())
    
    # Construir entrada del changelog
    changelog_entry = f"""
## [{version}] - {datetime.now().strftime('%Y-%m-%d')}

### {tipo}

"""
    
    if cambios_added:
        changelog_entry += "### ✨ Añadido\n"
        for cambio in cambios_added:
            changelog_entry += f"- {cambio}\n"
        changelog_entry += "\n"
    
    if cambios_fixed:
        changelog_entry += "### 🐛 Corregido\n"
        for cambio in cambios_fixed:
            changelog_entry += f"- {cambio}\n"
        changelog_entry += "\n"
    
    if cambios_changed:
        changelog_entry += "### 🔄 Cambiado\n"
        for cambio in cambios_changed:
            changelog_entry += f"- {cambio}\n"
        changelog_entry += "\n"
    
    if cambios_otros:
        changelog_entry += "### 📝 Otros\n"
        for cambio in cambios_otros:
            changelog_entry += f"- {cambio}\n"
        changelog_entry += "\n"
    
    # Leer changelog actual
    contenido_actual = ""
    if os.path.exists(CHANGELOG_FILE):
        with open(CHANGELOG_FILE, 'r', encoding='utf-8') as f:
            contenido_actual = f.read()
    
    if not contenido_actual:
        contenido_actual = """# 📋 CHANGELOG - SIDESYS ERP

Todas las actualizaciones notables de este proyecto serán documentadas en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/).

---
"""
    
    # Insertar nueva entrada después del primer ---
    if '---' in contenido_actual:
        partes = contenido_actual.split('---', 1)
        nuevo_contenido = partes[0] + '---' + changelog_entry + partes[1]
    else:
        nuevo_contenido = contenido_actual + '\n---' + changelog_entry
    
    with open(CHANGELOG_FILE, 'w', encoding='utf-8') as f:
        f.write(nuevo_contenido)
    
    print(f"✅ CHANGELOG.md actualizado con versión {version}")
    return True

# ============================================================
# FUNCIONES DE MANIFEST
# ============================================================

def generar_manifest():
    """Genera el manifest.json con todos los archivos"""
    print("\n📂 Generando manifest de archivos...")
    
    app_dir = os.path.dirname(os.path.abspath(__file__))
    manifest = {}
    
    extensiones = ['.py', '.js', '.css', '.html', '.json', '.txt', '.exe', '.ico', '.png', '.jpg', '.svg', '.md']
    
    for root, dirs, files in os.walk(app_dir):
        if any(excl in root for excl in IGNORAR_ARCHIVOS):
            continue
        
        for file in files:
            if any(file.endswith(ext) for ext in extensiones):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, app_dir)
                
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                        file_hash = hashlib.md5(content).hexdigest()
                    
                    manifest[rel_path] = {
                        'hash': file_hash,
                        'size': len(content),
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    }
                except:
                    pass
    
    with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Manifest generado: {len(manifest)} archivos")
    return manifest

# ============================================================
# FUNCIONES DE COMMIT AUTOMÁTICO
# ============================================================

def hacer_commit(version, cambios):
    """Hace commit automático de los cambios"""
    print("\n📤 Preparando commit a GitHub...")
    
    # Verificar si hay cambios
    result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    if not result.stdout.strip():
        print("  ℹ️ No hay cambios para commit")
        return True
    
    # Agregar archivos
    print("  📦 Agregando archivos...")
    subprocess.run(['git', 'add', '.'], check=True)
    
    # Crear mensaje de commit
    mensaje = f"feat: actualización a versión {version}\n\n"
    for cambio in cambios:
        mensaje += f"- {cambio}\n"
    
    print(f"  📝 Mensaje: {mensaje[:50]}...")
    
    # Hacer commit
    subprocess.run(['git', 'commit', '-m', mensaje], check=True)
    print("  ✅ Commit realizado")
    
    # Preguntar si hacer push
    push = input(f"\n  ¿Deseas hacer push ahora? (S/N): ").strip().upper()
    if push == 'S':
        print("  📤 Subiendo a GitHub...")
        subprocess.run(['git', 'push', 'origin', 'main'], check=True)
        print("  ✅ Push realizado")
    else:
        print("  ⏭️ Push omitido. Ejecuta: git push")
    
    return True

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def main():
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
    except:
        # Si no está colorama, usar texto plano
        class Fore:
            CYAN = ''; GREEN = ''; YELLOW = ''; RED = ''; WHITE = ''; BLUE = ''
        class Style:
            BRIGHT = ''
    
    print("\n" + "=" * 60)
    print(f"{Fore.CYAN}{Style.BRIGHT}  🚀 DEPLOY ACTUALIZACIÓN - SIDESYS ERP")
    print("=" * 60)
    
    # ============================================================
    # PASO 1: LEER VERSIÓN ACTUAL
    # ============================================================
    version_actual = leer_version_actual()
    print(f"\n{Fore.YELLOW}📌 Versión actual: {Fore.WHITE}{version_actual}")
    print()
    
    # ============================================================
    # PASO 2: SELECCIONAR TIPO DE CAMBIO
    # ============================================================
    print(f"{Fore.CYAN}¿Qué tipo de cambio realizaste?")
    print()
    print(f"  {Fore.GREEN}1.{Fore.WHITE} PATCH    (Corrección de bugs)")
    print(f"  {Fore.YELLOW}2.{Fore.WHITE} MINOR    (Nueva funcionalidad)")
    print(f"  {Fore.RED}3.{Fore.WHITE} MAJOR    (Cambio incompatible)")
    print(f"  {Fore.BLUE}4.{Fore.WHITE} MANUAL   (Especificar versión)")
    print()
    
    opcion = input(f"{Fore.CYAN}Selecciona una opción (1-4): {Fore.WHITE}").strip()
    
    if opcion == '4':
        nueva_version = input(f"{Fore.CYAN}Nueva versión: {Fore.WHITE}").strip()
        tipo_nombre = "MANUAL"
        tipo = "Manual"
    elif opcion in ['1', '2', '3']:
        tipo_map = {'1': 'patch', '2': 'minor', '3': 'major'}
        tipo = tipo_map[opcion]
        tipo_nombres = {'patch': 'PATCH', 'minor': 'MINOR', 'major': 'MAJOR'}
        nueva_version, _ = incrementar_version(version_actual, tipo)
        tipo_nombre = tipo_nombres[tipo]
    else:
        print(f"{Fore.RED}❌ Opción inválida")
        return
    
    # ============================================================
    # PASO 3: INGRESAR CAMBIOS
    # ============================================================
    print(f"\n{Fore.CYAN}Ingresa los cambios (línea por línea, Enter vacío para terminar):")
    print(f"{Fore.WHITE}  💡 Usa prefijos para categorizar:")
    print(f"  {Fore.GREEN}  +  Añadido (nueva funcionalidad)")
    print(f"  {Fore.RED}  !  Corregido (bug fix)")
    print(f"  {Fore.YELLOW}  ~  Cambiado (modificación)")
    print()
    print(f"{Fore.WHITE}  • ", end="")
    
    cambios = []
    while True:
        line = input()
        if not line:
            break
        cambios.append(line)
        print(f"  • ", end="")
    
    if not cambios:
        cambios = [f"Actualización a versión {nueva_version}"]
    
    # ============================================================
    # PASO 4: CONFIRMAR
    # ============================================================
    print()
    print(f"{Fore.YELLOW}{'=' * 60}")
    print(f"{Fore.YELLOW}  📋 RESUMEN DE LA ACTUALIZACIÓN")
    print(f"{Fore.YELLOW}{'=' * 60}")
    print()
    print(f"  {Fore.WHITE}Versión actual: {Fore.GREEN}{version_actual}")
    print(f"  {Fore.WHITE}Nueva versión:  {Fore.GREEN}{nueva_version}")
    print(f"  {Fore.WHITE}Tipo:          {Fore.GREEN}{tipo_nombre}")
    print()
    print(f"  {Fore.WHITE}Cambios:")
    for i, cambio in enumerate(cambios, 1):
        print(f"    {Fore.WHITE}{i}. {cambio}")
    print()
    print(f"{Fore.YELLOW}{'=' * 60}")
    print()
    
    confirmar = input(f"{Fore.CYAN}¿Confirmar y proceder? (S/N): {Fore.WHITE}").strip().upper()
    
    if confirmar != 'S':
        print(f"\n{Fore.RED}❌ Cancelado por el usuario")
        return
    
    # ============================================================
    # PASO 5: ACTUALIZAR CHANGELOG
    # ============================================================
    actualizar_changelog(nueva_version, tipo_nombre, cambios)
    
    # ============================================================
    # PASO 6: ACTUALIZAR VERSION.JSON
    # ============================================================
    print(f"\n📝 Actualizando version.json a {nueva_version}...")
    
    data = {
        "version": nueva_version,
        "release_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "changelog": cambios,
        "requires_restart": True,
        "force_update": False
    }
    
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ version.json actualizado a {nueva_version}")
    
    # ============================================================
    # PASO 7: GENERAR MANIFEST
    # ============================================================
    manifest = generar_manifest()
    
    # ============================================================
    # PASO 8: HACER COMMIT AUTOMÁTICO
    # ============================================================
    print()
    hacer_commit(nueva_version, cambios)
    
    # ============================================================
    # PASO 9: RESUMEN FINAL
    # ============================================================
    print()
    print(f"{Fore.GREEN}{'=' * 60}")
    print(f"{Fore.GREEN}{Style.BRIGHT}  ✅ ¡ACTUALIZACIÓN COMPLETADA!")
    print(f"{Fore.GREEN}{'=' * 60}")
    print()
    print(f"  {Fore.WHITE}📦 Nueva versión: {Fore.GREEN}{nueva_version}")
    print(f"  {Fore.WHITE}📂 Archivos manifest: {Fore.GREEN}{len(manifest)}")
    print()
    print(f"  {Fore.WHITE}📝 CHANGELOG actualizado: {Fore.GREEN}{CHANGELOG_FILE}")
    print(f"  {Fore.WHITE}📄 version.json actualizado: {Fore.GREEN}{VERSION_FILE}")
    print(f"  {Fore.WHITE}📋 manifest.json actualizado: {Fore.GREEN}{MANIFEST_FILE}")
    print()
    print(f"  {Fore.CYAN}🚀 ¡Los usuarios recibirán la actualización automáticamente!")
    print(f"{Fore.GREEN}{'=' * 60}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n❌ Proceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)