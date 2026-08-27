# updater.py
# ============================================================
# SISTEMA DE ACTUALIZACIÓN POR ARCHIVOS - SIDESYS ERP
# ============================================================

import os
import sys
import json
import hashlib
import shutil
import tempfile
import subprocess
import requests
import zipfile
import io
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIGURACIÓN
# ============================================================

VERSION_ACTUAL = "1.0.0"
# ⚠️ IMPORTANTE: Actualiza estas URLs con las de tu repositorio público
VERSION_URL = "https://tu-repo.com/updates/version.json"
UPDATE_URL = "https://tu-repo.com/updates/"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
UPDATE_DIR = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "SidesysERP", "updates")
BACKUP_DIR = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "SidesysERP", "backups")
LOG_DIR = os.path.join(APP_DIR, "logs")

# ============================================================
# FUNCIONES DE VERSIÓN (CORREGIDAS)
# ============================================================

def obtener_version_actual():
    """Obtiene la versión actual del sistema desde el directorio de la aplicación"""
    version_file = os.path.join(APP_DIR, "version.txt")
    
    if os.path.exists(version_file):
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("Versión:"):
                        return line.split(":")[1].strip()
        except:
            pass
    
    return VERSION_ACTUAL

def guardar_version(version):
    """Guarda la versión actual en el directorio de la aplicación"""
    version_file = os.path.join(APP_DIR, "version.txt")
    os.makedirs(os.path.dirname(version_file), exist_ok=True)
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(f"Versión: {version}\n")
        f.write(f"Actualizado: {datetime.now().isoformat()}\n")
    print(f"💾 Versión {version} guardada en {version_file}")

def comparar_versiones(v1: str, v2: str) -> int:
    """Compara dos versiones semánticas"""
    def parse_version(v):
        v = v.replace('v', '').strip()
        parts = v.split('.')
        while len(parts) < 3:
            parts.append('0')
        return [int(p) for p in parts[:3]]
    
    v1_parts = parse_version(v1)
    v2_parts = parse_version(v2)
    
    for i in range(3):
        if v1_parts[i] < v2_parts[i]:
            return -1
        elif v1_parts[i] > v2_parts[i]:
            return 1
    
    return 0

# ============================================================
# FUNCIONES DE CHECK DE ACTUALIZACIONES
# ============================================================

def check_actualizaciones():
    """
    Verifica si hay una nueva versión disponible
    RETURNS: (hay_actualizacion, version_info)
    """
    try:
        response = requests.get(VERSION_URL, timeout=10)
        response.raise_for_status()
        
        version_info = response.json()
        version_remota = version_info.get('version', '0.0.0')
        version_actual = obtener_version_actual()
        
        if comparar_versiones(version_actual, version_remota) < 0:
            return True, version_info
        
        return False, version_info
        
    except Exception as e:
        print(f"[WARN] No se pudo verificar actualizaciones: {e}")
        return False, None

def generar_manifest(version):
    """
    Genera un manifest de todos los archivos con sus checksums
    """
    manifest = {}
    base_dir = APP_DIR
    
    # Archivos a incluir en el manifest
    extensiones = ['.py', '.js', '.css', '.html', '.json', '.txt', '.exe']
    archivos_excluir = ['venv', '__pycache__', '.git', 'data', 'updates', 'backups']
    
    for root, dirs, files in os.walk(base_dir):
        # Saltar directorios excluidos
        if any(excl in root for excl in archivos_excluir):
            continue
        
        for file in files:
            if any(file.endswith(ext) for ext in extensiones):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, base_dir)
                
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                
                manifest[rel_path] = {
                    'hash': file_hash,
                    'size': os.path.getsize(file_path),
                    'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                }
    
    return manifest

# ============================================================
# FUNCIONES DE DESCARGA DIFERENCIAL
# ============================================================

def descargar_archivos_diferenciales(version_info):
    """
    Descarga SOLO los archivos que cambiaron
    """
    try:
        version_remota = version_info.get('version')
        manifest_url = version_info.get('manifest_url')
        files_url = version_info.get('files_url')
        
        if not manifest_url or not files_url:
            # Fallback: descargar actualización completa
            return descargar_actualizacion_completa(version_info)
        
        # Descargar manifest remoto
        print(f"📥 Descargando manifest de versión {version_remota}...")
        response = requests.get(manifest_url, timeout=10)
        response.raise_for_status()
        manifest_remoto = response.json()
        
        # Obtener manifest local
        manifest_local = generar_manifest(obtener_version_actual())
        
        # Determinar archivos que cambiaron
        archivos_actualizar = []
        
        for file_path, info_remoto in manifest_remoto.items():
            if file_path in manifest_local:
                info_local = manifest_local[file_path]
                if info_remoto['hash'] != info_local['hash']:
                    archivos_actualizar.append(file_path)
            else:
                # Archivo nuevo
                archivos_actualizar.append(file_path)
        
        # Archivos que se eliminaron (si se debe eliminar)
        for file_path in manifest_local:
            if file_path not in manifest_remoto:
                archivos_eliminar = True  # Marcar para eliminar
        
        if not archivos_actualizar:
            print("✅ No hay archivos que actualizar")
            return True, []
        
        print(f"📥 Descargando {len(archivos_actualizar)} archivos modificados...")
        
        # Descargar archivos uno por uno
        archivos_descargados = []
        
        for file_path in archivos_actualizar:
            # Descargar archivo individual
            file_url = f"{UPDATE_URL}{version_remota}/{file_path}"
            
            try:
                response = requests.get(file_url, timeout=30)
                response.raise_for_status()
                
                # Guardar en el directorio de actualizaciones
                temp_file = os.path.join(UPDATE_DIR, file_path)
                os.makedirs(os.path.dirname(temp_file), exist_ok=True)
                
                with open(temp_file, 'wb') as f:
                    f.write(response.content)
                
                archivos_descargados.append({
                    'path': file_path,
                    'size': len(response.content)
                })
                
                print(f"   ✓ {file_path} ({len(response.content)} bytes)")
                
            except Exception as e:
                print(f"   ✗ Error descargando {file_path}: {e}")
                return False, []
        
        return True, archivos_descargados
        
    except Exception as e:
        print(f"❌ Error en descarga diferencial: {e}")
        return False, []

def descargar_actualizacion_completa(version_info):
    """
    Fallback: descarga la actualización completa (método tradicional)
    """
    try:
        download_url = version_info.get('download_url')
        if not download_url:
            return False, []
        
        print(f"📥 Descargando actualización completa...")
        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()
        
        # Guardar como zip
        zip_path = os.path.join(UPDATE_DIR, f"update_{version_info['version']}.zip")
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Extraer
        print("📦 Extrayendo archivos...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(UPDATE_DIR)
        
        # ✅ ELIMINAR EL ZIP DESPUÉS DE EXTRAER
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print("🗑️ ZIP de actualización eliminado después de extraer")
        
        return True, []
        
    except Exception as e:
        print(f"❌ Error descargando actualización completa: {e}")
        return False, []

# ============================================================
# FUNCIONES DE INSTALACIÓN DE ACTUALIZACIONES (CORREGIDAS)
# ============================================================

def instalar_actualizacion_diferencial(version_remota):
    """
    Instala los archivos descargados en el directorio de la aplicación
    """
    print(f"📂 Directorio de la aplicación: {APP_DIR}")
    print(f"📂 Directorio de actualizaciones: {UPDATE_DIR}")
    
    try:
        # Crear backup antes de instalar
        crear_backup()
        
        # Copiar archivos descargados
        archivos_copiados = 0
        
        for root, dirs, files in os.walk(UPDATE_DIR):
            for file in files:
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, UPDATE_DIR)
                dst_file = os.path.join(APP_DIR, rel_path)
                
                # Crear directorio destino si no existe
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                
                # Copiar archivo
                shutil.copy2(src_file, dst_file)
                archivos_copiados += 1
        
        print(f"✅ {archivos_copiados} archivos copiados correctamente")
        
        # ✅ ELIMINAR LA CARPETA DE ACTUALIZACIONES DESPUÉS DE INSTALAR
        if os.path.exists(UPDATE_DIR):
            shutil.rmtree(UPDATE_DIR)
            print("🗑️ Carpeta de actualizaciones eliminada después de instalar")
        
        # ✅ GUARDAR LA NUEVA VERSIÓN (AHORA SÍ)
        guardar_version(version_remota)
        
        return True
        
    except Exception as e:
        print(f"❌ Error instalando actualización: {e}")
        restaurar_backup()
        return False

def crear_backup():
    """Crea un backup antes de instalar"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, timestamp)
        os.makedirs(backup_path, exist_ok=True)
        
        # Copiar archivos principales
        for root, dirs, files in os.walk(APP_DIR):
            for file in files:
                if file.endswith('.py') or file.endswith('.js') or file.endswith('.css') or file.endswith('.html'):
                    src = os.path.join(root, file)
                    rel = os.path.relpath(src, APP_DIR)
                    dst = os.path.join(backup_path, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
        
        print(f"📁 Backup creado en: {backup_path}")
        return backup_path
        
    except Exception as e:
        print(f"⚠️ Error creando backup: {e}")
        return None

def restaurar_backup():
    """Restaura desde el backup en caso de error"""
    try:
        backups = sorted([d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d))])
        if backups:
            last_backup = os.path.join(BACKUP_DIR, backups[-1])
            print(f"🔄 Restaurando backup: {last_backup}")
            
            for root, dirs, files in os.walk(last_backup):
                for file in files:
                    src = os.path.join(root, file)
                    rel = os.path.relpath(src, last_backup)
                    dst = os.path.join(APP_DIR, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
            
            print("✅ Backup restaurado correctamente")
            return True
            
    except Exception as e:
        print(f"❌ Error restaurando backup: {e}")
        return False

def limpiar_archivos_viejos():
    """Limpia archivos de actualizaciones antiguos y mantiene solo los últimos 2 ZIPs"""
    try:
        # ✅ CREAR DIRECTORIO DE LOGS SI NO EXISTE
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # Mantener solo los últimos 3 backups
        backups = sorted([d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d))])
        while len(backups) > 3:
            old = os.path.join(BACKUP_DIR, backups.pop(0))
            shutil.rmtree(old)
            print(f"🗑️ Eliminado backup antiguo: {old}")
            
            # ✅ REGISTRAR EN LOG DE AUDITORÍA
            with open(os.path.join(LOG_DIR, 'auditoria_limpieza.log'), 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()} | BACKUP_ELIMINADO | {old}\n")
        
        # ✅ LIMPIAR ZIPs ANTIGUOS (MANTENER SOLO ÚLTIMOS 2)
        updates_dir = UPDATE_DIR
        if os.path.exists(updates_dir):
            zips = sorted([f for f in os.listdir(updates_dir) if f.endswith('.zip')])
            
            if len(zips) > 2:
                for zip_file in zips[:-2]:
                    zip_path = os.path.join(updates_dir, zip_file)
                    version = zip_file.replace('update_', '').replace('.zip', '')
                    
                    # ✅ REGISTRAR EN LOG DE AUDITORÍA
                    with open(os.path.join(LOG_DIR, 'auditoria_limpieza.log'), 'a', encoding='utf-8') as f:
                        f.write(f"{datetime.now().isoformat()} | ZIP_ELIMINADO | {version} | {zip_path}\n")
                    
                    os.remove(zip_path)
                    print(f"🗑️ Eliminado ZIP antiguo: {zip_file}")
            
    except Exception as e:
        print(f"⚠️ Error limpiando archivos viejos: {e}")

# ============================================================
# FUNCIÓN PRINCIPAL DE ACTUALIZACIÓN (CORREGIDA)
# ============================================================

def verificar_y_actualizar():
    """
    Función principal que verifica y ejecuta la actualización
    """
    print("🔍 Verificando actualizaciones...")
    
    hay_actualizacion, version_info = check_actualizaciones()
    
    if not hay_actualizacion:
        print("✅ Ya tienes la última versión")
        return None
    
    if not version_info:
        print("⚠️ No se pudo obtener información de versiones")
        return None
    
    version_remota = version_info.get('version')
    
    print(f"\n📢 Nueva versión disponible: {version_remota}")
    print(f"   Versión actual: {obtener_version_actual()}")
    print(f"   Fecha: {version_info.get('release_date', 'N/A')}")
    print()
    print("   Cambios:")
    for cambio in version_info.get('changelog', []):
        print(f"   • {cambio}")
    print()
    
    # Preguntar al usuario
    respuesta = input("  ¿Deseas actualizar ahora? (S/N): ").strip().upper()
    
    if respuesta != 'S':
        print("  ⏭️ Actualización cancelada por el usuario")
        return None
    
    # Descargar actualización
    print("\n📥 Descargando actualización...")
    
    if version_info.get('manifest_url'):
        success, archivos = descargar_archivos_diferenciales(version_info)
    else:
        success, archivos = descargar_actualizacion_completa(version_info)
    
    if not success:
        print("❌ Error al descargar la actualización")
        return None
    
    # Instalar (pasando la versión remota)
    print("\n🔄 Instalando actualización...")
    
    if not instalar_actualizacion_diferencial(version_remota):
        print("❌ Error al instalar la actualización")
        return None
    
    # Limpiar archivos viejos
    limpiar_archivos_viejos()
    
    print(f"\n✅ Actualización a versión {version_remota} completada")
    print("   La aplicación se reiniciará automáticamente")
    
    return version_info

# ============================================================
# FUNCIONES PARA GENERAR MANIFEST PARA EL SERVIDOR
# ============================================================

def generar_manifest_completo():
    """
    Genera el manifest completo para subir al servidor
    """
    manifest = generar_manifest(VERSION_ACTUAL)
    
    # Guardar en archivo
    with open('manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✅ Manifest generado con {len(manifest)} archivos")
    print("   Sube este archivo al servidor como manifest.json")
    return manifest

# ============================================================
# FUNCIONES DE LIMPIEZA
# ============================================================

def limpiar_archivos_temporales():
    """Limpia archivos temporales de actualización"""
    try:
        if os.path.exists(UPDATE_DIR):
            for item in os.listdir(UPDATE_DIR):
                item_path = os.path.join(UPDATE_DIR, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
        print("🧹 Archivos temporales limpiados")
    except Exception as e:
        print(f"⚠️ Error limpiando archivos: {e}")

# ============================================================
# FUNCIÓN PARA ELIMINAR ZIPs DESPUÉS DE INSTALAR
# ============================================================

def eliminar_zip_actualizacion(version):
    """
    Elimina el ZIP de una versión específica después de instalar
    """
    try:
        zip_path = os.path.join(UPDATE_DIR, f"update_{version}.zip")
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print(f"🗑️ ZIP de versión {version} eliminado")
            
            # ✅ REGISTRAR EN LOG DE AUDITORÍA
            with open(os.path.join(LOG_DIR, 'auditoria_limpieza.log'), 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()} | ZIP_ELIMINADO_DESPUES_INSTALAR | {version} | {zip_path}\n")
            
            return True
        return False
    except Exception as e:
        print(f"⚠️ Error eliminando ZIP: {e}")
        return False

# ============================================================
# INTERFAZ DE COMANDOS PARA DESARROLLADOR
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Sistema de actualizaciones Sidesys ERP')
    parser.add_argument('--manifest', action='store_true', help='Genera el manifest.json')
    parser.add_argument('--clean', action='store_true', help='Limpia archivos temporales')
    parser.add_argument('--update', action='store_true', help='Verifica e instala actualizaciones')
    
    args = parser.parse_args()
    
    if args.manifest:
        generar_manifest_completo()
    
    if args.clean:
        limpiar_archivos_temporales()
    
    if args.update:
        verificar_y_actualizar()
    
    if not any(vars(args).values()):
        print("""
    ============================================================
    SISTEMA DE ACTUALIZACIONES - SIDESYS ERP
    ============================================================
    
    Uso:
    
    1. Generar manifest (desarrollador):
       python updater.py --manifest
    
    2. Limpiar archivos temporales:
       python updater.py --clean
    
    3. Verificar e instalar actualizaciones:
       python updater.py --update
    
    ============================================================
        """)