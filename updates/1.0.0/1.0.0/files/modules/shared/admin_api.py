# modules/shared/admin_api.py
# ============================================================
# API DEL PANEL DE ADMINISTRACIÓN - SIDESYS ERP
# ============================================================

from flask import Blueprint, jsonify, request, session
from .permisos import PermisosSistema
from .usuarios import get_gestor_usuarios
from .decorators import requiere_autenticacion, requiere_permiso, requiere_admin, requiere_superadmin
import os
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin_api', __name__, url_prefix='/api/admin')
gestor = get_gestor_usuarios()

# ============================================================
# DASHBOARD ADMIN
# ============================================================

@admin_bp.route('/dashboard', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_DASHBOARD)
def dashboard_admin():
    try:
        stats = gestor.get_stats()
        return jsonify(stats)
    except ValueError as e:
        return jsonify({"error": f"Error de validación: {str(e)}"}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en dashboard_admin: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

# ============================================================
# GESTIÓN DE USUARIOS
# ============================================================

@admin_bp.route('/usuarios', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_USUARIOS_VER)
def listar_usuarios():
    try:
        usuarios = gestor.listar_usuarios()
        return jsonify({
            "usuarios": usuarios,
            "total": len(usuarios)
        })
    except ValueError as e:
        return jsonify({"error": f"Error de validación: {str(e)}"}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en listar_usuarios: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/usuarios/<username>', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_USUARIOS_VER)
def obtener_usuario(username):
    try:
        if not username or not username.strip():
            return jsonify({"error": "Nombre de usuario requerido"}), 400
            
        usuario = gestor.obtener_usuario(username)
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404
        return jsonify(usuario)
    except ValueError as e:
        return jsonify({"error": f"Error de validación: {str(e)}"}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en obtener_usuario: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/usuarios', methods=['POST'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_USUARIOS_CREAR)
def crear_usuario():
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "Datos requeridos"}), 400
            
        username = data.get('username')
        if not username or not username.strip():
            return jsonify({"error": "Usuario es requerido"}), 400
        
        gestor.crear_usuario(
            username=username.strip(),
            email=data.get('email'),
            nombre=data.get('nombre'),
            roles=data.get('roles', ['invitado']),
            usar_sso=True
        )
        
        return jsonify({
            "mensaje": "Usuario creado exitosamente (usa SSO de Windows)",
            "usuario": username
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en crear_usuario: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/usuarios/<username>', methods=['PUT'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_USUARIOS_EDITAR)
def editar_usuario(username):
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "Datos requeridos"}), 400
            
        if username == session.get('username'):
            if data.get('bloqueado') is True:
                return jsonify({"error": "No puedes bloquearte a ti mismo"}), 400
            if data.get('activo') is False:
                return jsonify({"error": "No puedes desactivarte a ti mismo"}), 400
        
        gestor.editar_usuario(username, **data)
        return jsonify({
            "mensaje": "Usuario actualizado exitosamente",
            "usuario": username
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en editar_usuario: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/usuarios/<username>', methods=['DELETE'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_USUARIOS_ELIMINAR)
def eliminar_usuario(username):
    try:
        if username == session.get('username'):
            return jsonify({"error": "No puedes eliminarte a ti mismo"}), 400
        
        gestor.eliminar_usuario(username)
        return jsonify({
            "mensaje": "Usuario eliminado exitosamente",
            "usuario": username
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en eliminar_usuario: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/usuarios/<username>/bloquear', methods=['POST'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_USUARIOS_BLOQUEAR)
def bloquear_usuario(username):
    try:
        if username == session.get('username'):
            return jsonify({"error": "No puedes bloquearte a ti mismo"}), 400
        
        gestor.bloquear_usuario(username)
        return jsonify({
            "mensaje": f"Usuario {username} bloqueado exitosamente"
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en bloquear_usuario: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/usuarios/<username>/desbloquear', methods=['POST'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_USUARIOS_BLOQUEAR)
def desbloquear_usuario(username):
    try:
        gestor.desbloquear_usuario(username)
        return jsonify({
            "mensaje": f"Usuario {username} desbloqueado exitosamente"
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en desbloquear_usuario: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

# ============================================================
# ASIGNAR ROL ADMIN (SOLO SUPERADMIN)
# ============================================================

@admin_bp.route('/usuarios/<username>/asignar_admin', methods=['POST'])
@requiere_autenticacion
@requiere_superadmin
def asignar_admin(username):
    try:
        if not username or not username.strip():
            return jsonify({"error": "Nombre de usuario requerido"}), 400
            
        gestor.asignar_rol_admin(username)
        return jsonify({
            "mensaje": f"Rol admin asignado a {username}",
            "usuario": username,
            "roles": gestor.usuarios[username].roles
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en asignar_admin: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/usuarios/<username>/quitar_admin', methods=['POST'])
@requiere_autenticacion
@requiere_superadmin
def quitar_admin(username):
    try:
        if not username or not username.strip():
            return jsonify({"error": "Nombre de usuario requerido"}), 400
            
        gestor.quitar_rol_admin(username)
        return jsonify({
            "mensaje": f"Rol admin quitado a {username}",
            "usuario": username,
            "roles": gestor.usuarios[username].roles
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en quitar_admin: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

# ============================================================
# GESTIÓN DE USUARIO PRUEBA
# ============================================================

@admin_bp.route('/prueba/regenerar_password', methods=['POST'])
@requiere_autenticacion
@requiere_admin
def regenerar_password_prueba():
    try:
        nueva_password = gestor.generar_contraseña_usuario_prueba()
        usuario = gestor.obtener_usuario("prueba")
        
        return jsonify({
            "mensaje": "Contraseña del usuario 'prueba' regenerada exitosamente",
            "usuario": "prueba",
            "nueva_contraseña": nueva_password,
            "rol": usuario.get('roles', ['invitado'])[0] if usuario else 'invitado'
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en regenerar_password_prueba: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/prueba/credenciales', methods=['GET'])
@requiere_autenticacion
@requiere_admin
def obtener_credenciales_prueba():
    try:
        usuario = gestor.obtener_usuario("prueba")
        
        if not usuario:
            return jsonify({"error": "Usuario 'prueba' no encontrado"}), 404
        
        return jsonify({
            "usuario": "prueba",
            "nombre": usuario.get('nombre'),
            "email": usuario.get('email'),
            "roles": usuario.get('roles', ['invitado']),
            "activo": usuario.get('activo', True),
            "bloqueado": usuario.get('bloqueado', False),
            "mensaje": "Para obtener una nueva contraseña, usa /prueba/regenerar_password"
        })
    except ValueError as e:
        return jsonify({"error": f"Error de validación: {str(e)}"}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en obtener_credenciales_prueba: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

# ============================================================
# GESTIÓN DE ROLES
# ============================================================

@admin_bp.route('/roles', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_ROLES_VER)
def listar_roles():
    try:
        roles = gestor.listar_roles()
        return jsonify({
            "roles": roles,
            "total": len(roles)
        })
    except ValueError as e:
        return jsonify({"error": f"Error de validación: {str(e)}"}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en listar_roles: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/roles', methods=['POST'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_ROLES_CREAR)
def crear_rol():
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "Datos requeridos"}), 400
            
        rol_id = data.get('id')
        nombre = data.get('nombre')
        
        if not rol_id or not rol_id.strip():
            return jsonify({"error": "ID del rol es requerido"}), 400
        if not nombre or not nombre.strip():
            return jsonify({"error": "Nombre del rol es requerido"}), 400
        
        gestor.crear_rol(
            rol_id=rol_id.strip(),
            nombre=nombre.strip(),
            descripcion=data.get('descripcion', ''),
            permisos=data.get('permisos', []),
            nivel=data.get('nivel', 0),
            color=data.get('color', '#6c757d')
        )
        return jsonify({
            "mensaje": "Rol creado exitosamente",
            "rol": rol_id
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en crear_rol: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/roles/<rol_id>', methods=['PUT'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_ROLES_EDITAR)
def editar_rol(rol_id):
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "Datos requeridos"}), 400
            
        gestor.editar_rol(rol_id, **data)
        return jsonify({
            "mensaje": "Rol actualizado exitosamente",
            "rol": rol_id
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en editar_rol: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/roles/<rol_id>', methods=['DELETE'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_ROLES_ELIMINAR)
def eliminar_rol(rol_id):
    try:
        gestor.eliminar_rol(rol_id)
        return jsonify({
            "mensaje": "Rol eliminado exitosamente",
            "rol": rol_id
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Error del sistema: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error en eliminar_rol: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

# ============================================================
# PERMISOS DEL SISTEMA
# ============================================================

@admin_bp.route('/permisos', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_PERMISOS_ASIGNAR)
def listar_permisos():
    try:
        from .permisos import PermisosSistema
        return jsonify(PermisosSistema.obtener_permisos_agrupados())
    except ImportError as e:
        return jsonify({"error": f"Error de importación: {str(e)}"}), 500
    except ValueError as e:
        return jsonify({"error": f"Error de validación: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Error en listar_permisos: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

# ============================================================
# CONFIGURACIÓN DE BASES Y MÓDULOS (CORREGIDO)
# ============================================================

@admin_bp.route('/bases', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_BASES_CONFIG)
def listar_bases():
    try:
        bases = []
        paises = ['UY', 'RD', 'HN', 'GT', 'CO', 'PE', 'PY', 'EC', 'MX', 'CR', 'AR']
        
        for pais in paises:
            server = os.environ.get(f'{pais}_SERVER')
            # ✅ CORREGIDO: Validar variable de entorno
            if server:
                bases.append({
                    "id": pais.lower(),
                    "nombre": f"Base {pais}",
                    "pais": pais,
                    "server": server,
                    "activo": True
                })
            else:
                logger.warning(f"Variable {pais}_SERVER no definida en entorno")
        
        if not bases:
            bases = [
                {"id": "produccion", "nombre": "Base de Producción", "activo": True},
                {"id": "test", "nombre": "Base de Test", "activo": True},
                {"id": "desarrollo", "nombre": "Base de Desarrollo", "activo": False}
            ]
        
        return jsonify({"bases": bases})
    except KeyError as e:
        return jsonify({"error": f"Variable de entorno faltante: {str(e)}"}), 500
    except ValueError as e:
        return jsonify({"error": f"Error de validación: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Error en listar_bases: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/modulos', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_MODULOS_CONFIG)
def listar_modulos():
    try:
        modulos = [
            {"id": "cxp", "nombre": "Cuentas por Pagar", "activo": True},
            {"id": "stock", "nombre": "Inventario", "activo": True},
            {"id": "cotizaciones", "nombre": "Cotizaciones", "activo": True},
            {"id": "reportes", "nombre": "Reportes", "activo": True}
        ]
        return jsonify({"modulos": modulos})
    except ValueError as e:
        return jsonify({"error": f"Error de validación: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Error en listar_modulos: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

# ============================================================
# AUDITORÍA
# ============================================================

@admin_bp.route('/auditoria', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_AUDITORIA_VER)
def obtener_auditoria():
    try:
        import json
        from datetime import datetime, timedelta
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        log_file = os.path.join(base_dir, 'data', 'auditoria.log')
        
        logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        dias = request.args.get('dias', default=7, type=int)
        if dias <= 0 or dias > 365:
            dias = 7
            
        fecha_corte = datetime.now() - timedelta(days=dias)
        
        logs_filtrados = [
            log for log in logs 
            if datetime.fromisoformat(log.get('fecha', '2000-01-01')) > fecha_corte
        ]
        
        return jsonify({
            "auditoria": logs_filtrados[-100:],
            "total": len(logs_filtrados)
        })
    except FileNotFoundError as e:
        return jsonify({"error": f"Archivo de auditoría no encontrado: {str(e)}"}), 404
    except PermissionError as e:
        return jsonify({"error": f"Permiso denegado: {str(e)}"}), 403
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Error al leer archivo de auditoría: {str(e)}"}), 500
    except ValueError as e:
        return jsonify({"error": f"Error de validación: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Error en obtener_auditoria: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500