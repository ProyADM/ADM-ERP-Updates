# scripts/generar_update.py
# ============================================================
# GENERADOR DE ACTUALIZACIONES CON MANIFEST DIFERENCIAL
# ============================================================
# Solo empaqueta lo que cambió respecto a la última versión publicada
# (comparando contra manifest.json en la raíz, que actúa de baseline).
# No genera ZIP: el updater del cliente descarga archivo por archivo.
#
# Uso: python scripts/generar_update.py 1.0.1 [changelog.txt]
# ============================================================

import os
import json
import hashlib
import shutil
from datetime import datetime

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_MANIFEST_PATH = os.path.join(APP_DIR, 'manifest.json')

EXTENSIONES = ('.py', '.js', '.css', '.html', '.json', '.txt', '.ico', '.png', '.jpg')
EXCLUIR = ['venv', '__pycache__', '.git', 'data', 'updates', 'backups', 'build', 'dist', 'logs', 'flask_session']


def generar_manifest_completo():
    """
    Genera el manifest.json con todos los archivos de la aplicación (SHA-256)
    Las rutas se guardan con '/' (formato URL) en lugar de '\'
    """
    manifest = {}
    print("📂 Escaneando archivos del proyecto...")

    for root, dirs, files in os.walk(APP_DIR):
        if any(excl in root for excl in EXCLUIR):
            continue

        for file in files:
            if file.endswith(EXTENSIONES):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, APP_DIR).replace('\\', '/')

                with open(file_path, 'rb') as f:
                    content = f.read()
                    file_hash = hashlib.sha256(content).hexdigest()

                manifest[rel_path] = {
                    'hash': file_hash,
                    'size': len(content)
                }

    return manifest


def cargar_manifest_anterior():
    """
    Carga el manifest de la última versión publicada (baseline en la raíz del repo).
    Si no existe (primera publicación), devuelve {} -> todo se considera nuevo.
    """
    if os.path.exists(BASELINE_MANIFEST_PATH):
        with open(BASELINE_MANIFEST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    print("⚠️ No se encontró manifest.json previo en la raíz — se tratará como primera publicación")
    return {}


def calcular_diff(manifest_nuevo, manifest_anterior):
    """
    Compara ambos manifests y devuelve (archivos_a_publicar, archivos_eliminados).
    archivos_a_publicar: nuevos o con hash distinto.
    archivos_eliminados: existían antes y ya no están.
    """
    archivos_a_publicar = []
    for rel_path, info in manifest_nuevo.items():
        info_anterior = manifest_anterior.get(rel_path)
        if info_anterior is None or info_anterior.get('hash') != info['hash']:
            archivos_a_publicar.append(rel_path)

    archivos_eliminados = [
        rel_path for rel_path in manifest_anterior
        if rel_path not in manifest_nuevo
    ]

    return archivos_a_publicar, archivos_eliminados


def copiar_archivos_modificados(version, archivos_a_publicar):
    """
    Copia SOLO los archivos nuevos/modificados a updates/{version}/files/.
    Esto es lo que reduce el tamaño publicado: antes se copiaba la app entera
    en cada versión, ahora solo el diff real.
    """
    output_files_dir = os.path.join(APP_DIR, 'updates', version, 'files')

    if os.path.exists(output_files_dir):
        shutil.rmtree(output_files_dir)

    print(f"📂 Copiando {len(archivos_a_publicar)} archivo(s) modificado(s)/nuevo(s) a {output_files_dir}...")

    for rel_path in archivos_a_publicar:
        src_path = os.path.join(APP_DIR, rel_path)
        dst_path = os.path.join(output_files_dir, rel_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copy2(src_path, dst_path)

    print(f"✅ Archivos copiados a {output_files_dir}")
    return output_files_dir


def guardar_deleted_json(version, archivos_eliminados):
    """
    Registra qué archivos existían en la versión anterior y ya no existen,
    para que el cliente los borre en vez de dejarlos huérfanos en disco.
    """
    deleted_path = os.path.join(APP_DIR, 'updates', version, 'deleted.json')
    os.makedirs(os.path.dirname(deleted_path), exist_ok=True)
    with open(deleted_path, 'w', encoding='utf-8') as f:
        json.dump(archivos_eliminados, f, indent=2, ensure_ascii=False)
    if archivos_eliminados:
        print(f"🗑️  {len(archivos_eliminados)} archivo(s) marcado(s) para eliminar en el cliente")
    return deleted_path


def generar_version_json(version, changelog, hay_deleted):
    """
    Genera el archivo version.json para el servidor (URLs de manifest, archivos y borrados).
    Ya no hay ZIP: el updater del cliente siempre trabaja por manifest diferencial.
    """
    version_info = {
        'version': version,
        'release_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'changelog': changelog,
        'manifest_url': f'https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/updates/{version}/manifest.json',
        'files_url': f'https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/updates/{version}/files/',
        'deleted_url': (
            f'https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/updates/{version}/deleted.json'
            if hay_deleted else None
        ),
        'installer_url': 'https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/ADM-ERP_Setup_Latest.exe',
        'requires_restart': True,
        'force_update': False
    }

    with open(os.path.join(APP_DIR, 'version.json'), 'w', encoding='utf-8') as f:
        json.dump(version_info, f, indent=2, ensure_ascii=False)

    print(f"✅ version.json generado: {version}")
    return version_info


if __name__ == "__main__":
    import sys

    # ============================================================
    # LEER VERSIÓN Y CHANGELOG
    # ============================================================

    if len(sys.argv) < 2:
        print("❌ Debes especificar la versión")
        print("   Uso: python scripts/generar_update.py 1.0.1 [archivo_changelog.txt]")
        sys.exit(1)

    VERSION = sys.argv[1]

    changelog = []

    if len(sys.argv) >= 3:
        changelog_file = sys.argv[2]
        if os.path.exists(changelog_file):
            with open(changelog_file, 'r', encoding='utf-8') as f:
                changelog = [line.strip() for line in f if line.strip()]
            print(f"📄 Changelog leído desde: {changelog_file}")

    if not changelog and not sys.stdin.isatty():
        changelog = [line.strip() for line in sys.stdin if line.strip()]
        print(f"📄 Changelog leído desde STDIN ({len(changelog)} líneas)")

    if not changelog:
        print("\n📝 Ingresa los cambios (línea por línea, Enter vacío para terminar):")
        while True:
            try:
                line = input("  • ")
                if not line:
                    break
                changelog.append(line)
            except EOFError:
                break

    if not changelog:
        changelog = [f"Actualización a versión {VERSION}"]

    print("\n" + "=" * 60)
    print(f"  🔧 GENERANDO ACTUALIZACIÓN {VERSION}")
    print("=" * 60)
    print()

    # 1. Generar manifest completo del estado actual
    manifest_nuevo = generar_manifest_completo()

    # 2. Cargar el manifest de la última versión publicada (baseline)
    manifest_anterior = cargar_manifest_anterior()

    # 3. Calcular diff: qué se agrega/modifica y qué se elimina
    archivos_a_publicar, archivos_eliminados = calcular_diff(manifest_nuevo, manifest_anterior)

    if not archivos_a_publicar and not archivos_eliminados:
        print("✅ No hay cambios respecto a la última versión publicada. Nada que generar.")
        sys.exit(2)

    # 4. Guardar manifest completo de esta versión (para que el cliente compare)
    manifest_path = os.path.join(APP_DIR, 'updates', VERSION, 'manifest.json')
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_nuevo, f, indent=2, ensure_ascii=False)
    print(f"✅ Manifest completo guardado en: {manifest_path}")

    # 5. Copiar SOLO los archivos nuevos/modificados
    copiar_archivos_modificados(VERSION, archivos_a_publicar)

    # 6. Registrar archivos eliminados para que el cliente los borre
    guardar_deleted_json(VERSION, archivos_eliminados)

    # 7. Generar version.json
    version_info = generar_version_json(VERSION, changelog, hay_deleted=bool(archivos_eliminados))

    # 8. Actualizar el baseline en la raíz para la próxima publicación
    with open(BASELINE_MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest_nuevo, f, indent=2, ensure_ascii=False)
    print(f"✅ Baseline actualizado: {BASELINE_MANIFEST_PATH}")

    print("\n" + "=" * 60)
    print("  ✅ ACTUALIZACIÓN GENERADA (SOLO DIFF)")
    print("=" * 60)
    print()
    print(f"  📦 Versión: {VERSION}")
    print(f"  📄 Archivos totales en manifest: {len(manifest_nuevo)}")
    print(f"  🆕 Archivos nuevos/modificados publicados: {len(archivos_a_publicar)}")
    print(f"  🗑️  Archivos eliminados: {len(archivos_eliminados)}")
    print()
    print("  Archivos generados:")
    print(f"  • manifest.json (raíz, nuevo baseline) y updates/{VERSION}/manifest.json (snapshot completo)")
    print(f"  • updates/{VERSION}/files/ (solo el diff, {len(archivos_a_publicar)} archivo(s))")
    if archivos_eliminados:
        print(f"  • updates/{VERSION}/deleted.json ({len(archivos_eliminados)} archivo(s) a borrar en el cliente)")
    print(f"  • version.json (raíz)")
    print("=" * 60)
