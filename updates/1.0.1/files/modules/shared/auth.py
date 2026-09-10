# modules/shared/auth.py
# ============================================================
# AUTH - RUTAS DE AUTENTICACIÓN (CORREGIDO + C4)
# ============================================================
# C4: la sesión deja de crearse con rol 'usuario' a ciegas y deja de
# auto-crear usuarios al vuelo. La identidad/roles/permisos se derivan del
# GestorUsuarios (usuarios.json + roles.json), única fuente de verdad.

import subprocess
from flask import Blueprint, request, jsonify, session, g
from modules.shared.auth_windows import (
    verificar_credenciales_windows,
    get_current_windows_user,
    crear_sesion,
    validar_sesion,
    cerrar_sesion,
    JWT_EXPIRATION
)
from modules.shared.usuarios import get_gestor_usuarios
import logging

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
logger = logging.getLogger(__name__)

# ============================================================
# FUNCIÓN PARA OBTENER MENÚ (TEMPORAL)
# ============================================================
def get_menu_items(rol):
    """Obtiene los items del menú según el rol"""
    menu = {
        'admin': [
            {'icono': '📊', 'nombre': 'Dashboard', 'url': '/dashboard'},
            {'icono': '👥', 'nombre': 'Usuarios', 'url': '/usuarios'},
            {'icono': '🔐', 'nombre': 'Permisos', 'url': '/permisos'},
            {'icono': '📋', 'nombre': 'Auditoría', 'url': '/auditoria'}
        ],
        'gerente': [
            {'icono': '📊', 'nombre': 'Dashboard', 'url': '/dashboard'},
            {'icono': '📄', 'nombre': 'Reportes', 'url': '/reportes'}
        ],
        'usuario': [
            {'icono': '📊', 'nombre': 'Dashboard', 'url': '/dashboard'}
        ]
    }
    return menu.get(rol, menu.get('usuario', []))

# ============================================================
# FUNCIÓN AUXILIAR: MATERIALIZAR SESIÓN (C4)
# ============================================================
def _materializar_sesion(user_data, user_info=None):
    """Crea JWT + claves de sesión a partir del user_data del gestor.
    El rol que viaja en JWT/sesión es el real (roles[0]), no 'usuario'."""
    token = crear_sesion(user_data['username'], user_data['rol'], user_info)
    session['username'] = user_data['username']
    session['rol'] = user_data['rol']
    session['nombre'] = user_data.get('nombre') or user_data['username']
    session['es_superadmin'] = user_data['es_superadmin']
    session['permisos'] = user_data['permisos']
    session['user_data'] = user_data
    return token


def _verificar_usuario_habilitado(gestor, username):
    """Devuelve (error_response|None, user_data|None). No crea usuarios."""
    if username not in gestor.usuarios:
        return (
            jsonify({
                'error': 'Usuario no autorizado. Contactá al administrador para darte de alta.',
                'code': 'USER_NOT_AUTHORIZED'
            }), 403
        ), None
    u = gestor.usuarios[username]
    if not u.activo:
        return (jsonify({
            'error': 'Usuario desactivado',
            'code': 'USER_DISABLED'
        }), 403), None
    if u.bloqueado:
        return (jsonify({
            'error': 'Usuario bloqueado',
            'code': 'USER_BLOCKED'
        }), 403), None
    return None, gestor.datos_usuario_completo(username)


# ============================================================
# 1. LOGIN CON CREDENCIALES DE WINDOWS
# ============================================================

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Inicia sesión con credenciales de Windows (validación real de password).
    El usuario DEBE estar dado de alta en el sistema (gestor); no se crea al vuelo.
    """
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({
            'error': 'Usuario y contraseña requeridos',
            'code': 'MISSING_CREDENTIALS'
        }), 400
    
    success, msg, user_info = verificar_credenciales_windows(username, password)
    
    if not success:
        logger.warning(f"Intento de login fallido: {username} - {msg}")
        return jsonify({
            'error': msg,
            'code': 'AUTH_FAILED'
        }), 401
    
    logger.info(f"Login exitoso: {username} - {user_info.get('auth_type', 'windows')}")
    
    gestor = get_gestor_usuarios()
    error_resp, user_data = _verificar_usuario_habilitado(gestor, username)
    if error_resp:
        return error_resp
    if not user_data:
        return jsonify({
            'error': 'Usuario no autorizado. Contactá al administrador para darte de alta.',
            'code': 'USER_NOT_AUTHORIZED'
        }), 403

    user_info = user_info or {}
    user_info['nombre'] = user_data.get('nombre') or user_info.get('nombre') or username
    user_info['email'] = user_data.get('email') or user_info.get('email')
    token = _materializar_sesion(user_data, user_info)
    
    return jsonify({
        'success': True,
        'username': username,
        'rol': user_data['rol'],
        'nombre': user_data.get('nombre', username),
        'auth_type': user_info.get('auth_type', 'windows'),
        'token': token,
        'menu': get_menu_items(user_data['rol']),
        'expires_in': JWT_EXPIRATION * 3600
    })

# ============================================================
# 2. LOGIN AUTOMÁTICO (SINGLE SIGN-ON) - C4: solo localhost
# ============================================================

@auth_bp.route('/login_sso', methods=['GET'])
def login_sso():
    """
    Inicia sesión automáticamente con el usuario actual de Windows.

    C4: solo se acepta desde la misma máquina (127.0.0.1/::1) y solo si el
    usuario ya está dado de alta y activo. Antes, cualquiera en la LAN que
    llamara este endpoint heredaba la sesión del usuario que corre el proceso.
    """
    if request.remote_addr not in ('127.0.0.1', '::1'):
        logger.warning(f"SSO rechazado por origen remoto: {request.remote_addr}")
        return jsonify({
            'error': 'SSO disponible solo desde la misma máquina. Usá el login con usuario y contraseña.',
            'code': 'SSO_REMOTE_FORBIDDEN'
        }), 403

    username = get_current_windows_user()
    
    if not username:
        return jsonify({
            'error': 'No se pudo obtener el usuario de Windows',
            'code': 'NO_WINDOWS_USER'
        }), 401
    
    logger.info(f"SSO Login: {username}")
    
    gestor = get_gestor_usuarios()
    error_resp, user_data = _verificar_usuario_habilitado(gestor, username)
    if error_resp:
        return error_resp
    if not user_data:
        return jsonify({
            'error': 'Usuario no autorizado. Contactá al administrador para darte de alta.',
            'code': 'USER_NOT_AUTHORIZED'
        }), 403

    token = _materializar_sesion(user_data, {'auth_type': 'sso'})
    
    return jsonify({
        'success': True,
        'username': username,
        'rol': user_data['rol'],
        'nombre': user_data.get('nombre', username),
        'auth_type': 'sso',
        'token': token,
        'menu': get_menu_items(user_data['rol']),
        'expires_in': JWT_EXPIRATION * 3600
    })

# ============================================================
# 3. DETERMINAR ROL SEGÚN GRUPOS DE AD (referencia; el alta la hace el admin)
# ============================================================

def determinar_rol_ad(user_info):
    """
    Determina el rol del usuario según sus grupos de Active Directory.
    NOTA C4: ya no se usa para auto-crear usuarios en login; queda como
    referencia para que el admin asigne roles equivalentes al dar de alta.
    """
    groups = user_info.get('groups', [])
    
    rol_mapping = {
        'ERP_ADMIN': 'administrador',
        'ERP_SUPERVISOR': 'gerente',
        'ERP_CONTADOR': 'contador',
        'ERP_STOCK': 'usuario',
    }
    
    for group in groups:
        for ad_group, erp_role in rol_mapping.items():
            if ad_group in group:
                return erp_role
    
    return 'usuario'

# ============================================================
# 4. VERIFICAR SESIÓN
# ============================================================

@auth_bp.route('/check', methods=['GET'])
def check_session():
    """
    Verifica si hay una sesión activa. Devuelve el rol REAL del gestor
    (sana sesiones viejas creadas con rol 'usuario' por el SSO anterior).
    """
    success, payload = validar_sesion()
    
    if not success:
        return jsonify({
            'authenticated': False,
            'error': payload
        }), 401

    username = payload['username']
    gestor = get_gestor_usuarios()
    user_data = gestor.datos_usuario_completo(username)
    rol = user_data['rol'] if user_data else payload.get('rol', 'usuario')

    if user_data:
        session['rol'] = user_data['rol']
        session['es_superadmin'] = user_data['es_superadmin']
        session['permisos'] = user_data['permisos']
        session['user_data'] = user_data

    return jsonify({
        'authenticated': True,
        'username': username,
        'rol': rol,
        'nombre': user_data.get('nombre', username) if user_data else payload.get('nombre', username),
        'auth_type': payload.get('auth_type', 'windows')
    })

# ============================================================
# 5. LOGOUT
# ============================================================

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Cierra la sesión actual
    """
    username = session.get('username', 'desconocido')
    logger.info(f"Logout: {username}")
    
    cerrar_sesion()
    return jsonify({'success': True})

# ============================================================
# 6. CAMBIAR CONTRASEÑA DE WINDOWS (CORREGIDO - SIN SHELL=True)
# ============================================================

@auth_bp.route('/cambiar_password', methods=['POST'])
def cambiar_password_windows():
    """
    Cambia la contraseña de Windows del usuario actual
    """
    if 'username' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    data = request.json
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    
    if not old_password or not new_password or not confirm_password:
        return jsonify({'error': 'Todos los campos son requeridos'}), 400
    
    if new_password != confirm_password:
        return jsonify({'error': 'Las contraseñas no coinciden'}), 400
    
    username = session['username']
    success, _, _ = verificar_credenciales_windows(username, old_password)
    
    if not success:
        return jsonify({'error': 'Contraseña actual incorrecta'}), 401
    
    try:
        # ✅ CORREGIDO: Usar shell=False con lista de argumentos
        cmd = ['net', 'user', username, new_password]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'Contraseña cambiada exitosamente'})
        else:
            return jsonify({'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# 7. OBTENER INFORMACIÓN DEL USUARIO
# ============================================================

@auth_bp.route('/me', methods=['GET'])
def get_user_info():
    """
    Obtiene información del usuario actual. C4: se deriva del gestor y
    sanea las claves de sesión (rol real), no del session['rol'] viejo.
    """
    if 'username' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    username = session['username']
    gestor = get_gestor_usuarios()
    user_data = gestor.datos_usuario_completo(username)
    
    if user_data:
        session['rol'] = user_data['rol']
        session['es_superadmin'] = user_data['es_superadmin']
        session['permisos'] = user_data['permisos']
        session['user_data'] = user_data
        rol = user_data['rol']
        nombre = user_data.get('nombre', username)
        permisos = user_data['permisos']
    else:
        rol = session.get('rol', 'usuario')
        nombre = session.get('nombre', username)
        permisos = session.get('permisos', [])
    
    return jsonify({
        'username': username,
        'rol': rol,
        'nombre': nombre,
        'auth_type': session.get('auth_type', 'windows'),
        'menu': get_menu_items(rol),
        'permisos': permisos,
        'es_superadmin': session.get('es_superadmin', False),
        'created': session.get('created'),
        'is_admin': gestor.es_admin(username)
    })
