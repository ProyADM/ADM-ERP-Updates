# scripts/generar_update.py
# ============================================================
# GENERADOR DE ACTUALIZACIONES CON MANIFEST Y ARCHIVOS INDIVIDUALES
# ============================================================
# Uso: python scripts/generar_update.py 1.0.1 [changelog.txt]
# ============================================================

import os
import json
import hashlib
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

def generar_manifest_completo():
    """
    Genera el manifest.json con todos los archivos de la aplicación (SHA-256)
    """
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest = {}
    
    extensiones = ['.py', '.js', '.css', '.html', '.json', '.txt', '.ico', '.png', '.jpg']
    excluir = ['venv', '__pycache__', '.git', 'data', 'updates', 'backups', 'build', 'dist', 'logs', 'flask_session']
    
    print("📂 Generando manifest de archivos...")
    
    for root, dirs, files in os.walk(app_dir):
        if any(excl in root for excl in excluir):
            continue
        
        for file in files:
            if any(file.endswith(ext) for ext in extensiones):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, app_dir)
                
                with open(file_path, 'rb') as f:
                    content = f.read()
                    file_hash = hashlib.sha256(content).hexdigest()
                
                manifest[rel_path] = {
                    'hash': file_hash,
                    'size': len(content)
                }
    
    return manifest

def copiar_archivos_individuales(version):
    """
    Copia todos los archivos (excepto los excluidos) a updates/{version}/files/
    para descarga diferencial individual.
    """
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_files_dir = os.path.join(app_dir, 'updates', version, 'files')
    
    # Eliminar si existe para empezar limpio
    if os.path.exists(output_files_dir):
        shutil.rmtree(output_files_dir)
    
    excluir = ['venv', '__pycache__', '.git', 'data', 'updates', 'backups', 'build', 'dist', 'logs', 'flask_session']
    
    print(f"📂 Copiando archivos individuales a {output_files_dir}...")
    
    for root, dirs, files in os.walk(app_dir):
        if any(excl in root for excl in excluir):
            continue
        
        for file in files:
            if file.endswith(('.py', '.js', '.css', '.html', '.json', '.txt', '.ico', '.png', '.jpg')):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, app_dir)
                dst_path = os.path.join(output_files_dir, rel_path)
                
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
    
    print(f"✅ Archivos individuales copiados a {output_files_dir}")
    return output_files_dir

def generar_zip_actualizacion(version):
    """
    Genera un ZIP con todos los archivos (fallback para descarga completa)
    """
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(app_dir, 'updates', version)
    os.makedirs(output_dir, exist_ok=True)
    
    zip_path = os.path.join(output_dir, f'update_{version}.zip')
    
    print(f"📦 Generando ZIP de actualización {version}...")
    
    excluir = ['venv', '__pycache__', '.git', 'data', 'updates', 'backups', 'build', 'dist', 'logs', 'flask_session']
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(app_dir):
            if any(excl in root for excl in excluir):
                continue
            
            for file in files:
                if file.endswith(('.py', '.js', '.css', '.html', '.json', '.txt', '.ico', '.png', '.jpg')):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, app_dir)
                    zipf.write(file_path, rel_path)
    
    print(f"✅ ZIP generado: {zip_path}")
    return zip_path

def generar_version_json(version, changelog):
    """
    Genera el archivo version.json para el servidor (incluye URLs de manifest y archivos)
    """
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(app_dir, 'updates', version, f'update_{version}.zip')
    
    if os.path.exists(zip_path):
        with open(zip_path, 'rb') as f:
            checksum = hashlib.sha256(f.read()).hexdigest()
    else:
        checksum = ''
    
    version_info = {
        'version': version,
        'release_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'changelog': changelog,
        'checksum': checksum,
        'download_url': f'https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/updates/update_{version}.zip',
        'manifest_url': f'https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/updates/{version}/manifest.json',
        'files_url': f'https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/updates/{version}/files/',
        'installer_url': 'https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/ADM-ERP_Setup_Latest.exe',
        'requires_restart': True,
        'force_update': False
    }
    
    with open('version.json', 'w', encoding='utf-8') as f:
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
    
    # ============================================================
    # LEER CHANGELOG
    # ============================================================
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
    
    # 1. Generar manifest
    manifest = generar_manifest_completo()
    
    # 2. Guardar manifest en updates/{version}/manifest.json
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(app_dir, 'updates', VERSION, 'manifest.json')
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"✅ Manifest guardado en: {manifest_path}")
    
    # 3. Copiar archivos individuales (para descarga diferencial)
    copiar_archivos_individuales(VERSION)
    
    # 4. Generar ZIP (fallback)
    zip_path = generar_zip_actualizacion(VERSION)
    
    # 5. Generar version.json
    version_info = generar_version_json(VERSION, changelog)
    
    print("\n" + "=" * 60)
    print("  ✅ ACTUALIZACIÓN GENERADA")
    print("=" * 60)
    print()
    print(f"  📦 Versión: {VERSION}")
    print(f"  📂 Archivos en manifest: {len(manifest)}")
    print(f"  📁 ZIP: {zip_path}")
    print(f"  📁 Archivos individuales: updates/{VERSION}/files/")
    print()
    print("  Archivos generados:")
    print(f"  • manifest.json (raíz y updates/{VERSION}/)")
    print(f"  • version.json (raíz)")
    print(f"  • updates/{VERSION}/ (carpeta completa con files/ y manifest.json)")
    print("=" * 60)