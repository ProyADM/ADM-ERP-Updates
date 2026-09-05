# modules/shared/auth.py
# ============================================================
# AUTH - RUTAS DE AUTENTICACIÓN (CORREGIDO)
# ============================================================

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
from modules.shared.usuarios import get_users, crear_usuario
from modules.shared.decorators import requiere_autenticacion
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
# 1. LOGIN CON CREDENCIALES DE WINDOWS
# ============================================================

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Inicia sesión con credenciales de Windows
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
    
    users = get_users()
    
    if username not in users:
        rol = determinar_rol_ad(user_info) if user_info.get('groups') else 'usuario'
        
        crear_usuario(
            username=username,
            password='',
            rol=rol,
            nombre=user_info.get('nombre', username) if user_info else username,
            email=user_info.get('email') if user_info else f'{username}@sidesys.com'
        )
        users = get_users()
    
    user = users.get(username, {})
    
    if not user.get('activo', True):
        return jsonify({
            'error': 'Usuario desactivado',
            'code': 'USER_DISABLED'
        }), 403
    
    token = crear_sesion(username, user.get('rol', 'usuario'), user_info)
    
    return jsonify({
        'success': True,
        'username': username,
        'rol': user.get('rol', 'usuario'),
        'nombre': user.get('nombre', username),
        'auth_type': user_info.get('auth_type', 'windows') if user_info else 'windows',
        'token': token,
        'menu': get_menu_items(user.get('rol', 'usuario')),
        'expires_in': JWT_EXPIRATION * 3600
    })

# ============================================================
# 2. LOGIN AUTOMÁTICO (SINGLE SIGN-ON)
# ============================================================

@auth_bp.route('/login_sso', methods=['GET'])
def login_sso():
    """
    Inicia sesión automáticamente con el usuario actual de Windows
    """
    username = get_current_windows_user()
    
    if not username:
        return jsonify({
            'error': 'No se pudo obtener el usuario de Windows',
            'code': 'NO_WINDOWS_USER'
        }), 401
    
    logger.info(f"SSO Login: {username}")
    
    users = get_users()
    
    if username not in users:
        crear_usuario(
            username=username,
            password='',
            rol='usuario',
            nombre=username,
            email=f'{username}@sidesys.com'
        )
        users = get_users()
    
    user = users.get(username, {})
    
    if not user.get('activo', True):
        return jsonify({
            'error': 'Usuario desactivado',
            'code': 'USER_DISABLED'
        }), 403
    
    token = crear_sesion(username, user.get('rol', 'usuario'))
    
    return jsonify({
        'success': True,
        'username': username,
        'rol': user.get('rol', 'usuario'),
        'nombre': user.get('nombre', username),
        'auth_type': 'sso',
        'token': token,
        'menu': get_menu_items(user.get('rol', 'usuario')),
        'expires_in': JWT_EXPIRATION * 3600
    })

# ============================================================
# 3. DETERMINAR ROL SEGÚN GRUPOS DE AD
# ============================================================

def determinar_rol_ad(user_info):
    """
    Determina el rol del usuario según sus grupos de Active Directory
    """
    groups = user_info.get('groups', [])
    
    rol_mapping = {
        'ERP_ADMIN': 'admin',
        'ERP_SUPERVISOR': 'supervisor',
        'ERP_CONTADOR': 'contador',
        'ERP_STOCK': 'stock',
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
    Verifica si hay una sesión activa
    """
    success, payload = validar_sesion()
    
    if not success:
        return jsonify({
            'authenticated': False,
            'error': payload
        }), 401
    
    return jsonify({
        'authenticated': True,
        'username': payload['username'],
        'rol': payload['rol'],
        'nombre': payload['nombre'],
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
    Obtiene información del usuario actual
    """
    if 'username' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    users = get_users()
    user = users.get(session['username'], {})
    
    return jsonify({
        'username': session['username'],
        'rol': session.get('rol', 'usuario'),
        'nombre': session.get('nombre', session['username']),
        'auth_type': session.get('auth_type', 'windows'),
        'menu': get_menu_items(session.get('rol', 'usuario')),
        'created': session.get('created'),
        'is_admin': session.get('rol', '') == 'admin'
    })