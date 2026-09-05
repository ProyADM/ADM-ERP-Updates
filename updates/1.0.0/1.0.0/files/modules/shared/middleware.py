# modules/shared/middleware.py
# ============================================================
# MIDDLEWARE - PROTECCIÓN DE RUTAS (CORREGIDO)
# ============================================================

from functools import wraps
from flask import request, jsonify, session, g
from modules.shared.auth_windows import validar_sesion
import logging
import os
import jwt

logger = logging.getLogger(__name__)

# ============================================================
# FUNCIÓN VERIFICAR JWT (CORREGIDO)
# ============================================================

def verificar_jwt(token):
    """
    Verifica un JWT token - Función local
    """
    try:
        SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
        if not SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY no definida en variables de entorno")
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return True, payload
    except jwt.ExpiredSignatureError:
        return False, "Token expirado"
    except jwt.InvalidTokenError:
        return False, "Token inválido"
    except Exception as e:
        logger.error(f"Error al verificar JWT: {e}")
        return False, f"Error: {str(e)}"

# ============================================================
# 1. VERIFICAR AUTENTICACIÓN
# ============================================================

def login_required(f):
    """
    Decorador que verifica que el usuario esté autenticado
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Verificar JWT en header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
                success, payload = verificar_jwt(token)
                if success:
                    g.username = payload['username']
                    g.rol = payload['rol']
                    g.nombre = payload['nombre']
                    return f(*args, **kwargs)
            
            # Verificar sesión de Flask
            success, payload = validar_sesion()
            if success:
                return f(*args, **kwargs)
            
            logger.warning(f"Intento de acceso no autenticado a {request.path}")
            return jsonify({
                'error': 'No autenticado',
                'code': 'UNAUTHORIZED'
            }), 401
        except Exception as e:
            logger.error(f"Error en login_required: {e}")
            return jsonify({
                'error': 'Error de autenticación',
                'code': 'AUTH_ERROR'
            }), 500
    return decorated_function

# ============================================================
# 2. ADMIN REQUIRED
# ============================================================

def admin_required(f):
    """
    Decorador que verifica que sea administrador
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        try:
            rol = getattr(g, 'rol', session.get('rol', 'usuario'))
            username = getattr(g, 'username', session.get('username'))
            
            # Verificar si es admin o superadmin usando el gestor
            try:
                from modules.shared.usuarios import get_gestor_usuarios
                gestor = get_gestor_usuarios()
                is_admin = gestor.es_admin(username)
            except Exception as e:
                logger.error(f"Error al verificar admin en middleware: {e}")
                is_admin = rol in ['admin', 'superadmin']
            
            if not is_admin:
                logger.warning(f"Acceso admin denegado: {rol} en {request.path}")
                return jsonify({
                    'error': 'Se requieren permisos de administrador',
                    'code': 'ADMIN_REQUIRED'
                }), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error en admin_required: {e}")
            return jsonify({
                'error': 'Error al verificar permisos de administrador',
                'code': 'ADMIN_ERROR'
            }), 500
    return decorated_function

# ============================================================
# 3. SUPERVISOR REQUIRED
# ============================================================

def supervisor_required(f):
    """
    Decorador que verifica que sea supervisor o administrador
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        try:
            rol = getattr(g, 'rol', session.get('rol', 'usuario'))
            
            if rol not in ['admin', 'superadmin', 'supervisor']:
                logger.warning(f"Acceso supervisor denegado: {rol} en {request.path}")
                return jsonify({
                    'error': 'Se requieren permisos de supervisor',
                    'code': 'SUPERVISOR_REQUIRED'
                }), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error en supervisor_required: {e}")
            return jsonify({
                'error': 'Error al verificar permisos de supervisor',
                'code': 'SUPERVISOR_ERROR'
            }), 500
    return decorated_function

# ============================================================
# 4. LOG DE ACCESOS
# ============================================================

def log_access(f):
    """
    Decorador que registra los accesos a las rutas
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        try:
            username = getattr(g, 'username', session.get('username', 'desconocido'))
            logger.info(f"Acceso: {username} -> {request.method} {request.path}")
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error en log_access: {e}")
            return jsonify({
                'error': 'Error al registrar acceso',
                'code': 'LOG_ERROR'
            }), 500
    return decorated_function