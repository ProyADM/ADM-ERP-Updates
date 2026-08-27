# app.py
# ============================================================
# SIDESYS ERP - APLICACIÓN PRINCIPAL (CON PANEL ADMIN Y UPDATER)
# ============================================================

import os
import sys
import time
import subprocess
import threading
import json
import hashlib
import shutil
import winreg  # 🔴 NUEVO: Para leer el registro de Windows
from flask import Flask, send_from_directory, jsonify, request, g, session
from flask_cors import CORS
from flask_session import Session
import secrets

# ============================================================
# CONFIGURACIÓN DE SESIÓN SEGURA - CORREGIDO
# ============================================================
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
SECRET_KEY = os.environ.get('SESSION_SECRET_KEY')

if not SECRET_KEY:
    if FLASK_ENV == 'production':
        raise ValueError(
            "❌ SESSION_SECRET_KEY es OBLIGATORIA en producción.\n"
            "   Define SESSION_SECRET_KEY en .env.production"
        )
    SECRET_KEY = secrets.token_hex(32)
    print(f"[WARN] No se encontró SESSION_SECRET_KEY en .env, usando clave generada temporalmente")
    print(f"[WARN] Las sesiones se reiniciarán al reiniciar el servidor")

# ============================================================
# VERSIÓN DE LA APLICACIÓN
# ============================================================
APP_VERSION = "1.0.1"
VERSION_URL = "https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/version.json"
UPDATE_URL = "https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/updates/"

# ============================================================
# FUNCIÓN PARA OBTENER LA RUTA DE INSTALACIÓN REAL
# ============================================================
def obtener_ruta_instalacion():
    """
    Obtiene la ruta de instalación real desde el registro de Windows.
    Si no existe, usa el directorio del script actual (fallback).
    """
    try:
        # Buscar en el registro de usuario
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Sidesys\ADM-ERP")
        path, _ = winreg.QueryValueEx(key, "InstallPath")
        winreg.CloseKey(key)
        if os.path.isdir(path):
            print(f"📂 Ruta de instalación detectada: {path}")
            return path
    except WindowsError:
        pass
    
    # Fallback: directorio del script
    fallback = os.path.dirname(os.path.abspath(__file__))
    print(f"⚠️ No se encontró ruta de instalación en el registro, usando: {fallback}")
    return fallback

# ============================================================
# IMPORTAR BLUEPRINTS
# ============================================================
from modules.stock import stock_bp
from modules.cxp import cxp_bp
from modules.cotizaciones import cotizaciones_bp
from modules.shared.routes import shared_bp
from modules.shared.database import set_contexto_base
from modules.reportes import reportes_bp
from config import BASE_DEFAULT, SOCIEDAD_DEFAULT
from modules.shared.dashboard import dashboard_bp

# 🔴 IMPORTAR AUTENTICACIÓN
from modules.shared.auth import auth_bp
from modules.shared.auth_windows import get_current_windows_user, validar_sesion

# 🔴 IMPORTAR PANEL DE ADMINISTRACIÓN
from modules.shared.admin_api import admin_bp

# ============================================================
# FUNCIONES DE ACTUALIZACIÓN (INTEGRADAS DIRECTAMENTE)
# ============================================================

# Directorios de actualización
PROGRAM_DATA = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
UPDATE_DIR = os.path.join(PROGRAM_DATA, "SidesysERP", "updates")
BACKUP_DIR = os.path.join(PROGRAM_DATA, "SidesysERP", "backups")
VERSION_FILE = os.path.join(PROGRAM_DATA, "SidesysERP", "version.txt")

def obtener_version_actual():
    """Obtiene la versión actual del sistema"""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("Versión:"):
                        return line.split(":")[1].strip()
        except:
            pass
    return APP_VERSION

def guardar_version(version):
    """Guarda la versión actual"""
    os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Versión: {version}\n")
        f.write(f"Actualizado: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

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

def check_actualizaciones():
    """Verifica si hay una nueva versión disponible"""
    try:
        import requests
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

def descargar_archivos_diferenciales(version_info):
    """Descarga SOLO los archivos que cambiaron"""
    try:
        import requests
        import zipfile
        import io
        
        version_remota = version_info.get('version')
        manifest_url = version_info.get('manifest_url')
        files_url = version_info.get('files_url')
        
        if not manifest_url or not files_url:
            return descargar_actualizacion_completa(version_info)
        
        print(f"📥 Descargando manifest de versión {version_remota}...")
        response = requests.get(manifest_url, timeout=10)
        response.raise_for_status()
        manifest_remoto = response.json()
        
        archivos_actualizar = []
        app_dir = obtener_ruta_instalacion()  # 🔴 CAMBIO: usar ruta de instalación real
        
        for file_path, info_remoto in manifest_remoto.items():
            local_path = os.path.join(app_dir, file_path)
            if os.path.exists(local_path):
                with open(local_path, 'rb') as f:
                    local_hash = hashlib.md5(f.read()).hexdigest()
                if info_remoto['hash'] != local_hash:
                    archivos_actualizar.append(file_path)
            else:
                archivos_actualizar.append(file_path)
        
        if not archivos_actualizar:
            print("✅ No hay archivos que actualizar")
            return True, []
        
        print(f"📥 Descargando {len(archivos_actualizar)} archivos modificados...")
        
        archivos_descargados = []
        for file_path in archivos_actualizar:
            file_url = f"{files_url}/{file_path}"
            try:
                response = requests.get(file_url, timeout=30)
                response.raise_for_status()
                
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
    """Fallback: descarga la actualización completa"""
    try:
        import requests
        import zipfile
        
        download_url = version_info.get('download_url')
        if not download_url:
            return False, []
        
        print(f"📥 Descargando actualización completa...")
        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()
        
        zip_path = os.path.join(UPDATE_DIR, f"update_{version_info['version']}.zip")
        os.makedirs(UPDATE_DIR, exist_ok=True)
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print("📦 Extrayendo archivos...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(UPDATE_DIR)
        
        os.remove(zip_path)
        return True, []
        
    except Exception as e:
        print(f"❌ Error descargando actualización completa: {e}")
        return False, []

def instalar_actualizacion_diferencial():
    """Instala los archivos descargados en el directorio de la aplicación"""
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, timestamp)
        os.makedirs(backup_path, exist_ok=True)
        
        app_dir = obtener_ruta_instalacion()  # 🔴 CAMBIO: usar ruta de instalación real
        
        # Backup de archivos existentes
        for root, dirs, files in os.walk(app_dir):
            for file in files:
                if file.endswith(('.py', '.js', '.css', '.html', '.json', '.txt')):
                    src = os.path.join(root, file)
                    rel = os.path.relpath(src, app_dir)
                    dst = os.path.join(backup_path, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
        
        print(f"📁 Backup creado en: {backup_path}")
        
        # Copiar archivos desde UPDATE_DIR a app_dir
        archivos_copiados = 0
        for root, dirs, files in os.walk(UPDATE_DIR):
            for file in files:
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, UPDATE_DIR)
                dst_file = os.path.join(app_dir, rel_path)
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                shutil.copy2(src_file, dst_file)
                archivos_copiados += 1
        
        print(f"✅ {archivos_copiados} archivos copiados correctamente")
        
        # 🔴 NUEVO: Limpiar archivos temporales después de instalar
        limpiar_archivos_temporales()
        
        return True
        
    except Exception as e:
        print(f"❌ Error instalando actualización: {e}")
        restaurar_backup()
        return False

def restaurar_backup():
    """Restaura desde el backup en caso de error"""
    try:
        backups = sorted([d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d))])
        if backups:
            last_backup = os.path.join(BACKUP_DIR, backups[-1])
            app_dir = obtener_ruta_instalacion()  # 🔴 CAMBIO: usar ruta de instalación real
            
            print(f"🔄 Restaurando backup: {last_backup}")
            for root, dirs, files in os.walk(last_backup):
                for file in files:
                    src = os.path.join(root, file)
                    rel = os.path.relpath(src, last_backup)
                    dst = os.path.join(app_dir, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
            
            print("✅ Backup restaurado correctamente")
            return True
    except Exception as e:
        print(f"❌ Error restaurando backup: {e}")
        return False

def verificar_y_actualizar():
    """Función principal que verifica y ejecuta la actualización"""
    print("🔍 Verificando actualizaciones...")
    
    hay_actualizacion, version_info = check_actualizaciones()
    
    if not hay_actualizacion:
        print("✅ Ya tienes la última versión")
        limpiar_archivos_temporales()  # Limpiar por si quedan residuos
        return None
    
    if not version_info:
        print("⚠️ No se pudo obtener información de versiones")
        limpiar_archivos_temporales()
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
    
    print("\n📥 Descargando actualización...")
    
    if version_info.get('manifest_url'):
        success, archivos = descargar_archivos_diferenciales(version_info)
    else:
        success, archivos = descargar_actualizacion_completa(version_info)
    
    if not success:
        print("❌ Error al descargar la actualización")
        limpiar_archivos_temporales()
        return None
    
    print("\n🔄 Instalando actualización...")
    if not instalar_actualizacion_diferencial():
        print("❌ Error al instalar la actualización")
        limpiar_archivos_temporales()
        return None
    
    guardar_version(version_remota)
    
    # 🔴 NUEVO: Limpiar después de instalar (ya se llama dentro de instalar, pero por si acaso)
    limpiar_archivos_temporales()
    
    print(f"\n✅ Actualización a versión {version_remota} completada")
    return version_info

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
# CREAR APLICACIÓN FLASK
# ============================================================
app = Flask(__name__, 
            static_folder="frontend", 
            static_url_path="")

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# ============================================================
# CONFIGURACIÓN DE SEGURIDAD
# ============================================================
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 horas
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'sidesys_'

# Inicializar sesión
Session(app)

# ============================================================
# CONFIGURAR CORS - CORREGIDO
# ============================================================
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000').split(',')
CORS(app, supports_credentials=True, origins=ALLOWED_ORIGINS)

# ============================================================
# MIDDLEWARE DE CONTEXTO DE BASE
# ============================================================
@app.before_request
def _resolver_base_activa():
    base = request.headers.get("X-Base", BASE_DEFAULT)
    sociedad = request.headers.get("X-Sociedad")
    set_contexto_base(base, sociedad)

# ============================================================
# FUNCIONES DE GESTIÓN DE ROLES Y PERMISOS (ACTUALIZADAS)
# ============================================================

def cargar_roles():
    """Carga los roles desde roles.json"""
    roles_path = os.path.join(os.path.dirname(__file__), 'data', 'roles.json')
    try:
        with open(roles_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] No se pudo cargar roles.json: {e}")
        return {}

def cargar_usuarios():
    """Carga los usuarios desde usuarios.json"""
    usuarios_path = os.path.join(os.path.dirname(__file__), 'data', 'usuarios.json')
    try:
        with open(usuarios_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] No se pudo cargar usuarios.json: {e}")
        return {}

def obtener_rol_usuario(user_data):
    """
    Obtiene el rol del usuario desde diferentes formatos de JSON
    Soporta: 'rol': 'valor' o 'roles': ['valor'] o 'rol': ['valor']
    """
    # Si tiene 'rol' directamente
    if 'rol' in user_data:
        rol = user_data['rol']
        if isinstance(rol, list) and len(rol) > 0:
            return rol[0]
        return rol
    
    # Si tiene 'roles' (array)
    if 'roles' in user_data:
        roles = user_data['roles']
        if isinstance(roles, list) and len(roles) > 0:
            return roles[0]
        return 'usuario'
    
    # Si tiene 'rol' como lista (caso borde)
    if 'rol' in user_data and isinstance(user_data['rol'], list):
        return user_data['rol'][0] if len(user_data['rol']) > 0 else 'usuario'
    
    return 'usuario'

def obtener_permisos_rol(rol_nombre):
    """
    Obtiene la lista de permisos para un rol específico
    """
    roles = cargar_roles()
    if rol_nombre in roles:
        return roles[rol_nombre].get('permisos', [])
    return []

def obtener_datos_usuario_completo(username):
    """
    Obtiene todos los datos del usuario incluyendo permisos del rol
    """
    usuarios = cargar_usuarios()
    user_data = usuarios.get(username, {})
    
    if not user_data:
        return None
    
    # Obtener el nombre del rol
    rol_nombre = obtener_rol_usuario(user_data)
    
    # 🔴 CARGAR PERMISOS DESDE ROLES.JSON
    permisos = []
    roles_data = cargar_roles()
    if rol_nombre in roles_data:
        permisos = roles_data[rol_nombre].get('permisos', [])
    
    # Agregar permisos extra del usuario (si los tiene)
    if 'permisos_extra' in user_data:
        permisos.extend(user_data['permisos_extra'])
    
    # Quitar permisos restringidos del usuario
    if 'permisos_restringidos' in user_data:
        for restringido in user_data['permisos_restringidos']:
            if restringido in permisos:
                permisos.remove(restringido)
    
    # Verificar si es superadmin
    es_superadmin = (
        user_data.get('es_superadmin', False) or 
        rol_nombre == 'superadmin' or
        'admin.acceso' in permisos
    )
    
    # Construir objeto completo
    return {
        'username': user_data.get('username', username),
        'nombre': user_data.get('nombre', username),
        'email': user_data.get('email', ''),
        'rol': rol_nombre,
        'roles': user_data.get('roles', [rol_nombre]),
        'permisos': permisos,
        'es_superadmin': es_superadmin,
        'activo': user_data.get('activo', True),
        'bloqueado': user_data.get('bloqueado', False),
        'bases_permitidas': user_data.get('bases_permitidas', ['*']),
        'modulos_permitidos': user_data.get('modulos_permitidos', ['*']),
        'permisos_extra': user_data.get('permisos_extra', []),
        'permisos_restringidos': user_data.get('permisos_restringidos', [])
    }

# ============================================================
# MIDDLEWARE DE AUTENTICACIÓN - CORREGIDO
# ============================================================
@app.before_request
def _verificar_autenticacion():
    """
    Middleware que verifica autenticación para rutas protegidas
    """
    # Rutas públicas (no requieren autenticación)
    rutas_publicas = [
        '/api/auth/login', '/api/auth/login_sso', 
        '/api/auth/check', '/api/auth/logout',
        '/frontend/', '/app.js', '/style.css', '/favicon.ico',
        '/api/test', '/api/__version', '/api/version', 
        '/api/check_update', '/api/download_update', '/api/update/check',
        '/api/update/install', '/api/update/notification',
        '/api/dashboard/actividad'
    ]
    
    # ✅ Verificar si es ruta pública
    es_ruta_publica = False
    for ruta in rutas_publicas:
        if request.path.startswith(ruta):
            es_ruta_publica = True
            break
    
    # ✅ La ruta principal también es pública
    if request.path == '/':
        es_ruta_publica = True
    
    # Si ya hay sesión válida, continuar
    if 'username' in session:
        success, _ = validar_sesion()
        if success:
            return None
        else:
            session.clear()
    
    # ✅ SSO AUTOMÁTICO - SIEMPRE intentar, incluso en rutas públicas
    if not request.path.startswith('/api/auth'):
        username = get_current_windows_user()
        if username:
            try:
                from modules.shared.usuarios import get_users, crear_usuario
                users = get_users()
                
                if username not in users:
                    # Crear usuario con rol 'usuario' por defecto
                    crear_usuario(
                        username=username,
                        password='',
                        rol='usuario',
                        nombre=username,
                        email=f'{username}@sidesys.com'
                    )
                    users = get_users()
                
                user = users.get(username, {})
                if user.get('activo', True):
                    # 🔴 CORREGIDO: Obtener datos completos del usuario
                    user_data = obtener_datos_usuario_completo(username)
                    if user_data:
                        from modules.shared.auth_windows import crear_sesion
                        # Guardar toda la información en la sesión
                        session['username'] = username
                        session['rol'] = user_data['rol']
                        session['es_superadmin'] = user_data['es_superadmin']
                        session['permisos'] = user_data['permisos']
                        session['user_data'] = user_data
                        crear_sesion(username, user_data['rol'])
                    
                    # ✅ Si es la ruta principal, continuar sin error
                    if request.path == '/' or es_ruta_publica:
                        return None
            except Exception as e:
                print(f"[WARN] SSO automático falló: {e}")
    
    # Si la ruta es pública, permitir acceso sin autenticación
    if es_ruta_publica or request.path == '/':
        return None
    
    # Si es una petición API y no está autenticado, devolver error
    if request.path.startswith('/api/') and not request.path.startswith('/api/auth/'):
        return jsonify({
            'error': 'No autenticado',
            'code': 'UNAUTHORIZED',
            'login_url': '/'
        }), 401

# ============================================================
# REGISTRAR BLUEPRINTS
# ============================================================
app.register_blueprint(stock_bp, url_prefix='/api')
app.register_blueprint(cxp_bp, url_prefix='/api')
app.register_blueprint(cotizaciones_bp, url_prefix='/api/cotizaciones')
app.register_blueprint(shared_bp, url_prefix='/api')
app.register_blueprint(reportes_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(dashboard_bp)

# ============================================================
# RUTAS PRINCIPALES
# ============================================================

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")

@app.route("/style.css")
def serve_css():
    return send_from_directory("frontend", "style.css")

@app.route("/app.js")
def serve_app_js():
    return send_from_directory("frontend", "app.js")

@app.route("/frontend/modules/<path:filename>")
def serve_modules(filename):
    return send_from_directory("frontend/modules", filename)

@app.route("/frontend/templates/<path:filename>")
def serve_templates(filename):
    return send_from_directory("frontend/templates", filename)

@app.route("/frontend/css/<path:filename>")
def serve_css_files(filename):
    return send_from_directory("frontend/css", filename)

# ============================================================
# API - USUARIO ACTUAL (NUEVO - DEVUELVE DATOS COMPLETOS)
# ============================================================

@app.route("/api/auth/current_user", methods=['GET'])
def api_current_user():
    """Devuelve los datos completos del usuario autenticado"""
    if 'username' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    username = session['username']
    user_data = obtener_datos_usuario_completo(username)
    
    if not user_data:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    return jsonify({
        'success': True,
        'user': user_data,
        'session': {
            'username': session.get('username'),
            'rol': session.get('rol'),
            'es_superadmin': session.get('es_superadmin', False)
        }
    })

# ============================================================
# API - VERSIÓN
# ============================================================

@app.route("/api/__version")
def api_version():
    try:
        h1 = hashlib.md5(open(__file__, "rb").read()).hexdigest()[:8]
        h2 = hashlib.md5(open(os.path.join(os.path.dirname(__file__), "frontend/index.html"), "rb").read()).hexdigest()[:8]
        h3 = hashlib.md5(open(os.path.join(os.path.dirname(__file__), "frontend/style.css"), "rb").read()).hexdigest()[:8]
        return jsonify({"version": h1 + h2 + h3})
    except Exception as e:
        return jsonify({"version": "unknown", "error": str(e)})

# ============================================================
# API - ACTUALIZACIONES
# ============================================================

@app.route("/api/version")
def api_version_info():
    """Devuelve la versión actual de la aplicación"""
    return jsonify({
        'version': obtener_version_actual(),
        'check_url': VERSION_URL,
        'app_version': APP_VERSION
    })

@app.route("/api/check_update")
def api_check_update():
    """Verifica si hay actualizaciones disponibles"""
    try:
        hay, version_info = check_actualizaciones()
        
        if hay and version_info:
            return jsonify({
                'has_update': True,
                'version': version_info.get('version'),
                'release_date': version_info.get('release_date'),
                'changelog': version_info.get('changelog', []),
                'current_version': obtener_version_actual()
            })
        else:
            return jsonify({
                'has_update': False,
                'message': 'Ya tienes la última versión',
                'current_version': obtener_version_actual()
            })
    except Exception as e:
        return jsonify({
            'has_update': False,
            'error': str(e),
            'message': 'Error al verificar actualizaciones'
        }), 500

@app.route("/api/download_update", methods=['POST'])
def api_download_update():
    """Descarga e instala la actualización en segundo plano"""
    try:
        hay, version_info = check_actualizaciones()
        
        if not hay or not version_info:
            return jsonify({
                'success': False,
                'message': 'No hay actualizaciones disponibles'
            }), 400
        
        def update_thread():
            try:
                print(f"[UPDATER] Iniciando actualización a versión {version_info['version']}")
                verificar_y_actualizar()
            except Exception as e:
                print(f"[UPDATER] Error en hilo de actualización: {e}")
        
        thread = threading.Thread(target=update_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Actualización iniciada en segundo plano',
            'version': version_info.get('version'),
            'status': 'downloading'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Error al iniciar la actualización'
        }), 500

# ============================================================
# API - NOTIFICACIÓN DE ACTUALIZACIÓN (PARA EL FRONTEND)
# ============================================================

@app.route('/api/update/notification', methods=['GET'])
def api_update_notification():
    """
    Devuelve la notificación de actualización si existe
    """
    try:
        hay, version_info = check_actualizaciones()
        
        if hay and version_info:
            return jsonify({
                'has_update': True,
                'version': version_info.get('version'),
                'release_date': version_info.get('release_date'),
                'changelog': version_info.get('changelog', []),
                'url': '/api/download_update'
            })
        else:
            return jsonify({
                'has_update': False,
                'message': 'No hay actualizaciones disponibles'
            })
    except Exception as e:
        return jsonify({
            'has_update': False,
            'error': str(e)
        }), 500

# ============================================================
# API - UPDATE (NUEVO ENDPOINT PARA FRONTEND)
# ============================================================

@app.route('/api/update/check', methods=['GET'])
def api_update_check():
    """Verifica actualizaciones para el frontend"""
    return api_check_update()

@app.route('/api/update/install', methods=['POST'])
def api_update_install():
    """Instala actualización desde el frontend"""
    return api_download_update()

@app.route('/favicon.ico')
def favicon():
    return '', 204

# ============================================================
# API - TEST
# ============================================================

@app.route("/api/test")
def test_api():
    """Ruta de prueba - pública"""
    return jsonify({
        "status": "ok", 
        "message": "API funcionando correctamente",
        "authenticated": 'username' in session,
        "version": obtener_version_actual()
    })

# ============================================================
# API - DEBUG STOCK (SEGURIZADA)
# ============================================================

@app.route('/api/debug/stock', methods=['GET'])
def debug_stock():
    """Ruta de debug de stock - requiere autenticación"""
    if 'username' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    try:
        from modules.shared.database import run_sql
        
        info = {
            'db_server': getattr(g, 'db_server', 'NO SETEADO'),
            'db_database': getattr(g, 'db_database', 'NO SETEADO'),
            'division': getattr(g, 'division', 'NO SETEADO'),
            'sucursal': getattr(g, 'sucursal', 'NO SETEADO'),
            'authenticated_user': session.get('username'),
            'rol': session.get('rol', 'usuario'),
            'es_superadmin': session.get('es_superadmin', False),
            'permisos': session.get('permisos', [])
        }
        
        rows = run_sql("SELECT TOP 1 ARTS_ARTICULO FROM STOC_ARTS")
        info['consulta_ok'] = True
        info['resultado'] = 'ok' if rows else 'vacio'
        
        return jsonify(info)
    except Exception as e:
        return jsonify({
            'error': 'Ocurrió un error en la base de datos.',
            'details': str(e)
        }), 500

# ============================================================
# MANEJO DE ERRORES
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Recurso no encontrado"}), 404

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({
        "error": "No autenticado",
        "code": "UNAUTHORIZED",
        "login_url": "/"
    }), 401

@app.errorhandler(403)
def forbidden(e):
    return jsonify({
        "error": "No tienes permiso para acceder a este recurso",
        "code": "FORBIDDEN"
    }), 403

# ============================================================
# FUNCIÓN PARA VERIFICAR ACTUALIZACIONES EN SEGUNDO PLANO
# ============================================================

def verificar_actualizaciones_fondo():
    """Verifica actualizaciones en segundo plano al iniciar la app"""
    try:
        time.sleep(5)
        
        print("\n🔍 Verificando actualizaciones en segundo plano...")
        
        hay, version_info = check_actualizaciones()
        
        if hay and version_info:
            version_actual = obtener_version_actual()
            version_nueva = version_info.get('version', '0.0.0')
            
            print(f"\n📢 NUEVA VERSIÓN DISPONIBLE: {version_nueva}")
            print(f"   Versión actual: {version_actual}")
            print(f"   Fecha: {version_info.get('release_date', 'N/A')}")
            print()
            print("   Cambios:")
            for cambio in version_info.get('changelog', []):
                print(f"   • {cambio}")
            print()
            print("   Visita /api/download_update para instalar automáticamente")
            print("=" * 60)
            
            update_info_file = os.path.join(PROGRAM_DATA, "SidesysERP", "update_available.json")
            os.makedirs(os.path.dirname(update_info_file), exist_ok=True)
            
            with open(update_info_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': version_nueva,
                    'release_date': version_info.get('release_date'),
                    'changelog': version_info.get('changelog', []),
                    'detected_at': time.time()
                }, f, indent=2)
                
    except Exception as e:
        print(f"[WARN] Error verificando actualizaciones en fondo: {e}")

# ============================================================
# EJECUCIÓN - CORREGIDO
# ============================================================

if __name__ == "__main__":
    import psutil
    
    os.makedirs(UPDATE_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # 🔴 CORREGIDO: DEBUG desactivado en producción
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Si estamos en producción y debug está activado, advertir
    if FLASK_ENV == 'production' and debug_mode:
        print("[WARN] ⚠️ DEBUG activado en producción - DESACTIVANDO")
        debug_mode = False
    
    print("=" * 60)
    print("  SIDESYS ERP - MODO DESARROLLO")
    print("=" * 60)
    print(f"  Versión: {APP_VERSION}")
    print(f"  SECRET_KEY: {SECRET_KEY[:10]}...")
    print(f"  Sesiones expiran en: {app.config['PERMANENT_SESSION_LIFETIME']} segundos")
    print("  Autenticación de Windows: ACTIVADA")
    print("  Panel de Administración: ACTIVADO")
    print("  Sistema de Actualizaciones: ACTIVADO")
    print(f"  Entorno: {FLASK_ENV}")
    print(f"  DEBUG: {debug_mode}")
    print("=" * 60)
    print()
    
    thread = threading.Thread(target=verificar_actualizaciones_fondo)
    thread.daemon = True
    thread.start()
    
    def monitorear_navegador():
        time.sleep(3)
        navegadores = ["chrome.exe", "firefox.exe", "msedge.exe", "brave.exe"]
        pid_navegador = None
        
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() in navegadores:
                try:
                    for conn in proc.net_connections():
                        if conn.laddr.port == 5000:
                            pid_navegador = proc.info['pid']
                            break
                except:
                    pass
                if pid_navegador:
                    break
        
        if pid_navegador:
            print(f"[INFO] Monitoreando navegador (PID: {pid_navegador})")
            while True:
                try:
                    psutil.Process(pid_navegador)
                    time.sleep(3)
                except psutil.NoSuchProcess:
                    print("[INFO] Navegador cerrado. Deteniendo servidor...")
                    os._exit(0)
                    break
    
    threading.Thread(target=monitorear_navegador, daemon=True).start()
    
    app.run(
        host="0.0.0.0", 
        port=5000, 
        debug=debug_mode,
        threaded=True
    )