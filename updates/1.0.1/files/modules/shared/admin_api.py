# modules/shared/admin_api.py
# ============================================================
# API DEL PANEL DE ADMINISTRACIÓN - SIDESYS ERP
# ============================================================

from flask import Blueprint, jsonify, request, session
from .permisos import PermisosSistema
from .usuarios import get_gestor_usuarios
from .decorators import requiere_autenticacion, requiere_permiso, requiere_admin, requiere_superadmin
from . import config_central
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin_api', __name__, url_prefix='/api/admin')
gestor = get_gestor_usuarios()

# ============================================================
# HELPERS DEL ALMACÉN CENTRAL
# ============================================================

def _auditar(accion, **datos):
    """Registra la operación en el log del almacén (arreglo 13.1 #2).

    `config_central.auditar` nunca lanza: la operación sigue aunque la
    auditoría no se pueda escribir (spec §7)."""
    evento = {'accion': accion, 'por': session.get('username', 'desconocido')}
    evento.update(datos)
    config_central.auditar(evento)


def _cuerpo_json():
    """Body JSON como dict, o None si no es un objeto (el handler responde 400)."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


# Campos que el PUT /usuarios/<username> puede tocar. Todo lo demás (sobre todo
# `es_superadmin`, `password_hash`, `username`, `revision`) se rechaza con 400.
CAMPOS_EDITABLES_USUARIO = {
    'email', 'nombre', 'roles', 'permisos_extra', 'permisos_restringidos',
    'activo', 'bloqueado', 'bases_permitidas', 'modulos_permitidos', 'usar_sso',
}


def _error_almacen(e):
    """503 cuando el almacén está configurado y no se pudo escribir.

    ⚠️ `config_central.AlmacenNoDisponible` hereda de RuntimeError: su `except`
    tiene que ir ANTES del genérico `except RuntimeError` de cada handler."""
    return jsonify({
        "error": "El almacén central de configuración no está accesible: no se aplicó el cambio.",
        "code": "ALMACEN_NO_DISPONIBLE",
        "detalle": str(e),
    }), 503

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
        # Arreglo 13.1 #5: el GET también devuelve las excepciones por usuario.
        # `gestor.obtener_usuario` / `datos_usuario_completo` arman el shape público
        # (nunca incluyen password_hash).
        completo = gestor.datos_usuario_completo(username) or {}
        usuario["permisos_extra"] = completo.get("permisos_extra", [])
        usuario["permisos_restringidos"] = completo.get("permisos_restringidos", [])
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
        data = _cuerpo_json()
        
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
        _auditar('usuario.crear', usuario=username.strip(), roles=data.get('roles'))
        
        return jsonify({
            "mensaje": "Usuario creado exitosamente (usa SSO de Windows)",
            "usuario": username
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        data = _cuerpo_json()
        
        if not data:
            return jsonify({"error": "Datos requeridos"}), 400
        
        # Whitelist: por este endpoint NO se edita `es_superadmin` (ni ningún otro
        # campo interno). Sin esto, un administrador con `admin.usuarios.editar`
        # podía hacer PUT {"es_superadmin": true} sobre sí mismo y quedar como
        # superadmin en el almacén compartido, propagado a todas las PCs.
        no_editables = sorted(set(data) - CAMPOS_EDITABLES_USUARIO)
        if no_editables:
            return jsonify({
                "error": f"Campos no editables por este endpoint: {', '.join(no_editables)}"
            }), 400
            
        if username == session.get('username'):
            if data.get('bloqueado') is True:
                return jsonify({"error": "No puedes bloquearte a ti mismo"}), 400
            if data.get('activo') is False:
                return jsonify({"error": "No puedes desactivarte a ti mismo"}), 400
        
        for campo in ('permisos_extra', 'permisos_restringidos'):
            if campo not in data:
                continue
            valor = data[campo]
            if not isinstance(valor, list) or not all(isinstance(p, str) for p in valor):
                return jsonify({
                    "error": f"{campo} debe ser una lista de permisos"
                }), 400
            invalidos = [p for p in valor if not PermisosSistema.es_permiso_valido(p)]
            if invalidos:
                return jsonify({
                    "error": f"Permisos inexistentes en {campo}: {', '.join(invalidos)}"
                }), 400

        gestor.editar_usuario(username, **data)
        _auditar('usuario.editar', usuario=username, campos=sorted(data.keys()))
        return jsonify({
            "mensaje": "Usuario actualizado exitosamente",
            "usuario": username
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        _auditar('usuario.eliminar', usuario=username)
        return jsonify({
            "mensaje": "Usuario eliminado exitosamente",
            "usuario": username
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        _auditar('usuario.bloquear', usuario=username)
        return jsonify({
            "mensaje": f"Usuario {username} bloqueado exitosamente"
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        _auditar('usuario.desbloquear', usuario=username)
        return jsonify({
            "mensaje": f"Usuario {username} desbloqueado exitosamente"
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        _auditar('usuario.asignar_admin', usuario=username)
        return jsonify({
            "mensaje": f"Rol admin asignado a {username}",
            "usuario": username,
            "roles": gestor.usuarios[username].roles
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        _auditar('usuario.quitar_admin', usuario=username)
        return jsonify({
            "mensaje": f"Rol admin quitado a {username}",
            "usuario": username,
            "roles": gestor.usuarios[username].roles
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        usuario = gestor.obtener_usuario("prueba")
        if usuario is None:
            # El usuario 'prueba' ya no se crea en ninguna instalación nueva
            # (decisión 12/09): el endpoint se mantiene por tolerancia, pero
            # si no existe tiene que ser un 404 explícito, no un 400 genérico.
            return jsonify({
                "error": "El usuario 'prueba' ya no existe en este sistema",
                "code": "USUARIO_PRUEBA_ELIMINADO"
            }), 404

        nueva_password = gestor.generar_contraseña_usuario_prueba()
        _auditar('usuario.regenerar_password', usuario='prueba')
        
        return jsonify({
            "mensaje": "Contraseña del usuario 'prueba' regenerada exitosamente",
            "usuario": "prueba",
            "nueva_contraseña": nueva_password,
            "rol": usuario.get('roles', ['invitado'])[0] if usuario else 'invitado'
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        data = _cuerpo_json()
        
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
        _auditar('rol.crear', rol=rol_id)
        return jsonify({
            "mensaje": "Rol creado exitosamente",
            "rol": rol_id
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        data = _cuerpo_json()
        
        if not data:
            return jsonify({"error": "Datos requeridos"}), 400
            
        gestor.editar_rol(rol_id, **data)
        _auditar('rol.editar', rol=rol_id)
        return jsonify({
            "mensaje": "Rol actualizado exitosamente",
            "rol": rol_id
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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
        _auditar('rol.eliminar', rol=rol_id)
        return jsonify({
            "mensaje": "Rol eliminado exitosamente",
            "rol": rol_id
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
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

def _bases_desde_config():
    """Bases reales del sistema: las de BASES_DISPONIBLES (mismos ids que usa
    `bases_permitidas` y todo el resto de la app). Arreglo 13.1 #4.

    Solo se expone lo que el panel necesita (id/nombre/pais/activo): nada de
    `server` (host:puerto interno) ni de credenciales (`user`/`password`)."""
    from config import BASES_DISPONIBLES
    bases = []
    for base_id, cfg in BASES_DISPONIBLES.items():
        bases.append({
            "id": base_id,
            "nombre": cfg.get("label", base_id),
            "pais": cfg.get("sigla", ""),
            "activo": True,
        })
    return bases


@admin_bp.route('/bases', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_BASES_CONFIG)
def listar_bases():
    try:
        return jsonify({"bases": _bases_desde_config()})
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
# ALMACÉN CENTRAL: ESTADO, RESPALDO Y SIEMBRA MANUAL
# ============================================================

@admin_bp.route('/config/estado', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_ACCESO)
def estado_config():
    try:
        return jsonify(config_central.estado())
    except Exception as e:
        logger.error(f"Error en estado_config: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/config/recargar', methods=['POST'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_ACCESO)
def recargar_config():
    """Fuerza la relectura del almacén (spec §6.3).

    Es una LECTURA: con el almacén degradado igual devuelve 200 con el modo,
    porque no hay nada que escribir y el panel necesita poder refrescar el
    estado sin que parezca un error."""
    try:
        recargado = bool(gestor.recargar_si_cambio(forzar=True))
        return jsonify({'recargado': recargado, 'estado': config_central.estado()})
    except Exception as e:
        logger.error(f'Error en recargar_config: {e}')
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500


def _conflictos_del_almacen():
    """Nombres de los archivos de conflictos, del más nuevo al más viejo.

    Un almacén que no se puede listar (ACL denegada, carpeta que desaparece
    entre el `isdir` y el `listdir`) cuenta como "no accesible": lista vacía,
    no una excepción que el handler convierta en 500 (spec §6.4)."""
    destino = config_central.resolver_central_dir()
    if not destino or not os.path.isdir(destino):
        return []
    try:
        entradas = os.listdir(destino)
    except OSError:
        return []
    nombres = [
        n for n in entradas
        if n.startswith(config_central.PREFIJO_CONFLICTOS) and n.endswith('.json')
        and os.path.isfile(os.path.join(destino, n))
    ]
    return sorted(nombres, reverse=True)


@admin_bp.route('/config/conflictos', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_ACCESO)
def listar_conflictos():
    """Conflictos de merge que dejó la sincronización entre PCs (spec §6.4)."""
    try:
        archivos = []
        for nombre in _conflictos_del_almacen():
            ruta = os.path.join(config_central.resolver_central_dir(), nombre)
            try:
                archivos.append({'nombre': nombre, 'bytes': os.path.getsize(ruta),
                                 'fecha': datetime.fromtimestamp(
                                     os.path.getmtime(ruta)).isoformat()})
            except OSError:
                continue
        return jsonify({'total': len(archivos), 'archivos': archivos})
    except Exception as e:
        logger.error(f'Error en listar_conflictos: {e}')
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500


@admin_bp.route('/config/conflictos/<path:nombre>', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_ACCESO)
def ver_conflicto(nombre):
    """Contenido de un archivo de conflictos.

    El nombre que llega del cliente NUNCA se usa para armar la ruta: se valida
    contra la lista real del almacén (spec §6.4)."""
    try:
        if nombre not in _conflictos_del_almacen():
            return jsonify({'error': 'Conflicto no encontrado'}), 404
        ruta = os.path.join(config_central.resolver_central_dir(), nombre)
        return jsonify({'nombre': nombre, 'contenido': config_central.leer_json(ruta, {})})
    except Exception as e:
        logger.error(f'Error en ver_conflicto: {e}')
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/config/exportar', methods=['POST'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_BACKUP)
def exportar_config():
    try:
        from datetime import datetime as _dt
        # El respaldo va a data/ (copia local del operador), nunca al almacén.
        destino = os.path.join(
            config_central.data_dir(),
            f"config_export_{_dt.now().strftime('%Y%m%d_%H%M%S')}.json")
        config_central.exportar(destino)
        _auditar('config.exportar', archivo=os.path.basename(destino))
        return jsonify({"mensaje": "Configuración exportada", "archivo": destino})
    except ValueError as e:
        # Almacén vacío: no se genera un respaldo que al importarse borraría todo.
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error en exportar_config: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/config/importar', methods=['POST'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_RESTAURAR)
def importar_config():
    try:
        # `or {}`: si el body no es un objeto, `archivo` queda None → 400, no 500.
        data = _cuerpo_json() or {}
        origen = data.get('archivo')
        if not origen or not os.path.exists(origen):
            return jsonify({"error": "Archivo de respaldo no encontrado"}), 400
        # `importar` valida la forma del respaldo ANTES de escribir el almacén.
        n_u, n_r, _ = config_central.importar(origen, cambiado_por=session.get('username'))
        gestor._cargar_datos()
        _auditar('config.importar', archivo=os.path.basename(origen),
                 usuarios=n_u, roles=n_r)
        return jsonify({"mensaje": "Configuración importada", "usuarios": n_u, "roles": n_r})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except config_central.AlmacenNoDisponible as e:
        return _error_almacen(e)
    except Exception as e:
        logger.error(f"Error en importar_config: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

# ============================================================
# AUDITORÍA
# ============================================================

@admin_bp.route('/auditoria', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_AUDITORIA_VER)
def obtener_auditoria():
    try:
        dias = request.args.get('dias', default=7, type=int)
        if dias <= 0 or dias > 365:
            dias = 7
        # `limite` lo usa el "mostrar más" del panel (spec §5.4): acotado a 500
        # para que una consulta del panel no traiga un archivo entero.
        limite = request.args.get('limite', default=100, type=int)
        if limite <= 0 or limite > 500:
            limite = 100
        # Lee el log real del almacén (auditoria.jsonl), no el data/auditoria.log
        # que nadie escribía (hallazgo 13.1 #2).
        eventos = config_central.leer_auditoria(dias=dias, limite=limite)
        return jsonify({"auditoria": eventos, "total": len(eventos)})
    except Exception as e:
        logger.error(f"Error en obtener_auditoria: {e}")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@admin_bp.route('/accesos-rechazados', methods=['GET'])
@requiere_autenticacion
@requiere_permiso(PermisosSistema.ADMIN_USUARIOS_CREAR)
def listar_accesos_rechazados():
    """Intentos de acceso rechazados, agrupados por usuario de Windows.

    Es lo que permite el "dar de alta en un clic" del panel: el rechazado no
    tiene que adivinar su nombre de usuario (spec §6.2)."""
    try:
        from datetime import datetime as _dt

        # Un solo retrato del almacén para todo el request: `usuarios` se
        # reemplaza entero al recargar (swap atómico), así que `ya_existe` y
        # `activo` no pueden salir de dos revisiones distintas.
        almacen = gestor.usuarios
        # Windows no distingue mayúsculas y el usuario puede teclear la grafía que
        # quiera, mientras el detalle se busca por clave EXACTA
        # (`usuarios.py:obtener_usuario`). El mapa traduce la grafía tecleada a la
        # clave REAL del almacén, si existe. `agrupados` sí queda en minúsculas
        # (una sola fila por persona) y `usuario` devuelve la clave real cuando el
        # usuario existe: si no, la vista mostraba "Ver usuario" y el GET exacto
        # contestaba 404 ("El registro ya no existe").
        claves_reales = {clave.lower(): clave for clave in almacen}
        eventos = config_central.leer_auditoria(dias=30, limite=500)
        agrupados = {}
        for ev in eventos:
            if ev.get('accion') != 'acceso.rechazado':
                continue
            usuario = (ev.get('por') or '').strip()
            if not usuario:
                continue
            clave = usuario.lower()
            fecha = ev.get('fecha') or ''
            actual = agrupados.get(clave)
            if actual is None:
                real = claves_reales.get(clave)
                agrupados[clave] = {
                    'usuario': real if real is not None else usuario,
                    'pc': ev.get('pc') or '',
                    'motivo': ev.get('motivo') or '',
                    'veces': 1,
                    'ultimo': fecha,
                    'ya_existe': real is not None,
                    'activo': almacen[real].activo if real is not None else None,
                }
            else:
                actual['veces'] += 1
                if fecha > (actual['ultimo'] or ''):
                    actual['ultimo'] = fecha
                    actual['pc'] = ev.get('pc') or actual['pc']
                    actual['motivo'] = ev.get('motivo') or actual['motivo']
        usuarios = sorted(agrupados.values(),
                          key=lambda u: u['ultimo'] or '', reverse=True)
        return jsonify({
            'total': len(usuarios),
            'generado': _dt.now().isoformat(),
            'usuarios': usuarios,
        })
    except Exception as e:
        logger.error(f'Error en listar_accesos_rechazados: {e}')
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500
