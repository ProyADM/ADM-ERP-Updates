# modules/shared/decorators.py
# ============================================================
# DECORADORES DE AUTENTICACIÓN Y PERMISOS - SIDESYS ERP
# ============================================================

from functools import wraps
from flask import session, jsonify, request, g
from .usuarios import get_gestor_usuarios
import logging

logger = logging.getLogger(__name__)
gestor = get_gestor_usuarios()

def requiere_autenticacion(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            if 'username' not in session:
                return jsonify({
                    "error": "No autenticado",
                    "code": "UNAUTHORIZED",
                    "login_url": "/"
                }), 401
            
            username = session.get('username')
            if not username:
                session.clear()
                return jsonify({
                    "error": "Sesión inválida",
                    "code": "INVALID_SESSION"
                }), 401
                
            if username not in gestor.usuarios:
                session.clear()
                return jsonify({
                    "error": "Usuario no válido",
                    "code": "INVALID_USER"
                }), 401
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error en requiere_autenticacion: {e}")
            return jsonify({
                "error": "Error de autenticación",
                "code": "AUTH_ERROR"
            }), 500
    return decorated

def requiere_permiso(permiso):
    def decorador(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                if 'username' not in session:
                    return jsonify({
                        "error": "No autenticado",
                        "code": "UNAUTHORIZED"
                    }), 401
                
                username = session.get('username')
                if not username:
                    return jsonify({
                        "error": "Sesión inválida",
                        "code": "INVALID_SESSION"
                    }), 401
                
                if not gestor.tiene_permiso(username, permiso):
                    logger.warning(f"Permiso denegado: {username} -> {permiso}")
                    return jsonify({
                        "error": "No tienes permiso para realizar esta acción",
                        "permiso_requerido": permiso,
                        "code": "FORBIDDEN"
                    }), 403
                
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error en requiere_permiso: {e}")
                return jsonify({
                    "error": "Error al verificar permisos",
                    "code": "PERMISSION_ERROR"
                }), 500
        return decorated
    return decorador

def requiere_permisos(permisos):
    def decorador(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                if 'username' not in session:
                    return jsonify({
                        "error": "No autenticado",
                        "code": "UNAUTHORIZED"
                    }), 401
                
                username = session.get('username')
                if not username:
                    return jsonify({
                        "error": "Sesión inválida",
                        "code": "INVALID_SESSION"
                    }), 401
                
                faltantes = []
                for permiso in permisos:
                    if not gestor.tiene_permiso(username, permiso):
                        faltantes.append(permiso)
                
                if faltantes:
                    logger.warning(f"Permisos faltantes para {username}: {faltantes}")
                    return jsonify({
                        "error": "No tienes los permisos requeridos",
                        "permisos_faltantes": faltantes,
                        "code": "FORBIDDEN"
                    }), 403
                
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error en requiere_permisos: {e}")
                return jsonify({
                    "error": "Error al verificar permisos",
                    "code": "PERMISSION_ERROR"
                }), 500
        return decorated
    return decorador

def requiere_roles(roles_permitidos):
    def decorador(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                if 'username' not in session:
                    return jsonify({
                        "error": "No autenticado",
                        "code": "UNAUTHORIZED"
                    }), 401
                
                username = session.get('username')
                if not username:
                    return jsonify({
                        "error": "Sesión inválida",
                        "code": "INVALID_SESSION"
                    }), 401
                    
                usuario = gestor.usuarios.get(username)
                if not usuario:
                    return jsonify({
                        "error": "Usuario no encontrado",
                        "code": "USER_NOT_FOUND"
                    }), 401
                
                tiene_rol = any(rol in usuario.roles for rol in roles_permitidos)
                
                if not tiene_rol and not usuario.es_superadmin:
                    logger.warning(f"Roles insuficientes para {username}")
                    return jsonify({
                        "error": f"No tienes los roles requeridos",
                        "roles_requeridos": roles_permitidos,
                        "tus_roles": usuario.roles,
                        "code": "FORBIDDEN"
                    }), 403
                
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error en requiere_roles: {e}")
                return jsonify({
                    "error": "Error al verificar roles",
                    "code": "ROLE_ERROR"
                }), 500
        return decorated
    return decorador

def requiere_superadmin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            if 'username' not in session:
                return jsonify({
                    "error": "No autenticado",
                    "code": "UNAUTHORIZED"
                }), 401
            
            username = session.get('username')
            if not username:
                return jsonify({
                    "error": "Sesión inválida",
                    "code": "INVALID_SESSION"
                }), 401
            
            if not gestor.es_superadmin(username):
                logger.warning(f"Intento de acceso superadmin denegado: {username}")
                return jsonify({
                    "error": "Se requieren permisos de SUPERADMIN",
                    "code": "SUPERADMIN_REQUIRED"
                }), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error en requiere_superadmin: {e}")
            return jsonify({
                "error": "Error al verificar superadmin",
                "code": "SUPERADMIN_ERROR"
            }), 500
    return decorated

def requiere_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            if 'username' not in session:
                return jsonify({
                    "error": "No autenticado",
                    "code": "UNAUTHORIZED"
                }), 401
            
            username = session.get('username')
            if not username:
                return jsonify({
                    "error": "Sesión inválida",
                    "code": "INVALID_SESSION"
                }), 401
            
            if not gestor.es_admin(username):
                logger.warning(f"Intento de acceso admin denegado: {username}")
                return jsonify({
                    "error": "Se requieren permisos de administrador",
                    "code": "ADMIN_REQUIRED"
                }), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error en requiere_admin: {e}")
            return jsonify({
                "error": "Error al verificar administrador",
                "code": "ADMIN_ERROR"
            }), 500
    return decorated

def requiere_acceso_modulo(modulo):
    def decorador(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                if 'username' not in session:
                    return jsonify({
                        "error": "No autenticado",
                        "code": "UNAUTHORIZED"
                    }), 401
                
                username = session.get('username')
                if not username:
                    return jsonify({
                        "error": "Sesión inválida",
                        "code": "INVALID_SESSION"
                    }), 401
                
                if not gestor.tiene_acceso_a_modulo(username, modulo):
                    logger.warning(f"Acceso al módulo {modulo} denegado para {username}")
                    return jsonify({
                        "error": f"No tienes acceso al módulo {modulo}",
                        "modulo": modulo,
                        "code": "FORBIDDEN"
                    }), 403
                
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error en requiere_acceso_modulo: {e}")
                return jsonify({
                    "error": "Error al verificar acceso al módulo",
                    "code": "MODULE_ERROR"
                }), 500
        return decorated
    return decorador

def requiere_acceso_base(base):
    def decorador(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                if 'username' not in session:
                    return jsonify({
                        "error": "No autenticado",
                        "code": "UNAUTHORIZED"
                    }), 401
                
                username = session.get('username')
                if not username:
                    return jsonify({
                        "error": "Sesión inválida",
                        "code": "INVALID_SESSION"
                    }), 401
                
                if not gestor.tiene_acceso_a_base(username, base):
                    logger.warning(f"Acceso a la base {base} denegado para {username}")
                    return jsonify({
                        "error": f"No tienes acceso a la base {base}",
                        "base": base,
                        "code": "FORBIDDEN"
                    }), 403
                
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error en requiere_acceso_base: {e}")
                return jsonify({
                    "error": "Error al verificar acceso a la base",
                    "code": "BASE_ERROR"
                }), 500
        return decorated
    return decorador


# ============================================================
# C4 - VALIDACIÓN DE BASE EN HANDLERS (base dinámica / multi-base)
# ============================================================
# Estas funciones se invocan DENTRO del handler cuando la base no viene del
# header X-Base (middleware) sino de query params o del cuerpo del request.
# Retornan None si está OK, o una respuesta Flask 401/403 lista para devolver.

def chequear_acceso_base(base):
    """Valida que el usuario actual tenga acceso a la base indicada."""
    username = session.get('username')
    if not username:
        return jsonify({
            "error": "No autenticado",
            "code": "UNAUTHORIZED",
            "login_url": "/"
        }), 401
    if not gestor.tiene_acceso_a_base(username, base):
        logger.warning(f"Base '{base}' no autorizada para {username} (chequeo dinámico)")
        return jsonify({
            "error": f"Base \"{base}\" no autorizada para este usuario",
            "code": "BASE_FORBIDDEN"
        }), 403
    return None


def chequear_acceso_total_bases():
    """Valida que el usuario actual pueda operar sobre TODAS las bases
    (superadmin o bases_permitidas=['*']). Para reportes/escrituras
    multi-base que no admiten acceso parcial."""
    username = session.get('username')
    if not username:
        return jsonify({
            "error": "No autenticado",
            "code": "UNAUTHORIZED",
            "login_url": "/"
        }), 401
    if not gestor.puede_acceder_todas_bases(username):
        logger.warning(f"Acceso multi-base denegado para {username}")
        return jsonify({
            "error": "Se requieren permisos sobre todas las bases para esta operación",
            "code": "BASE_FORBIDDEN"
        }), 403
    return None