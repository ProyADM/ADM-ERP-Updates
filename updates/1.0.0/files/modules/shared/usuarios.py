# modules/shared/usuarios.py
# ============================================================
# GESTIÓN DE USUARIOS Y ROLES - SIDESYS ERP
# ============================================================

import json
import os
import bcrypt
import secrets
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Any
from .permisos import PermisosSistema

# ============================================================
# CONFIGURACIÓN DEL SUPERADMIN (DESDE VARIABLES DE ENTORNO)
# ============================================================

def _get_superadmin_email() -> str:
    email = os.environ.get('SUPERADMIN_EMAIL')
    if not email:
        print("[WARN] SUPERADMIN_EMAIL no definido en .env")
        print("   Usando valor por defecto: pedro.molina@sidesys.com")
        return "pedro.molina@sidesys.com"
    return email

def _get_superadmin_username() -> str:
    username = os.environ.get('SUPERADMIN_USERNAME')
    if not username:
        print("[WARN] SUPERADMIN_USERNAME no definido en .env")
        print("   Usando valor por defecto: pmolina")
        return "pmolina"
    return username

def _get_prueba_password() -> str:
    password = os.environ.get('PRUEBA_PASSWORD')
    if not password:
        return "prueba123"
    return password

SUPERADMIN_EMAIL = _get_superadmin_email()
SUPERADMIN_USERNAME = _get_superadmin_username()
PRUEBA_PASSWORD = _get_prueba_password()

class Usuario:
    """Representa un usuario del sistema"""
    
    def __init__(self, username: str, password: str = None, 
                 email: str = None, nombre: str = None):
        self.username = username
        self.email = email or f"{username}@sidesys.com"
        self.nombre = nombre or username
        self.password_hash = None
        if password:
            self.password_hash = bcrypt.hashpw(
                password.encode(), 
                bcrypt.gensalt()
            ).decode()
        
        self.roles: List[str] = []
        self.permisos_extra: List[str] = []
        self.permisos_restringidos: List[str] = []
        self.activo: bool = True
        self.bloqueado: bool = False
        self.creado: str = datetime.now().isoformat()
        self.ultimo_acceso: Optional[str] = None
        self.es_superadmin: bool = False
        self.bases_permitidas: List[str] = []
        self.modulos_permitidos: List[str] = []
        self.intentos_fallidos: int = 0
        self.ultimo_intento: Optional[str] = None
        self.es_usuario_prueba: bool = False
        self.usar_sso: bool = True
        
    def to_dict(self) -> Dict:
        return {
            "username": self.username,
            "email": self.email,
            "nombre": self.nombre,
            "password_hash": self.password_hash,
            "roles": self.roles,
            "permisos_extra": self.permisos_extra,
            "permisos_restringidos": self.permisos_restringidos,
            "activo": self.activo,
            "bloqueado": self.bloqueado,
            "creado": self.creado,
            "ultimo_acceso": self.ultimo_acceso,
            "es_superadmin": self.es_superadmin,
            "bases_permitidas": self.bases_permitidas,
            "modulos_permitidos": self.modulos_permitidos,
            "intentos_fallidos": self.intentos_fallidos,
            "ultimo_intento": self.ultimo_intento,
            "es_usuario_prueba": self.es_usuario_prueba,
            "usar_sso": self.usar_sso
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Usuario':
        usuario = cls(
            username=data['username'],
            email=data.get('email'),
            nombre=data.get('nombre')
        )
        usuario.password_hash = data.get('password_hash')
        usuario.roles = data.get('roles', [])
        usuario.permisos_extra = data.get('permisos_extra', [])
        usuario.permisos_restringidos = data.get('permisos_restringidos', [])
        usuario.activo = data.get('activo', True)
        usuario.bloqueado = data.get('bloqueado', False)
        usuario.creado = data.get('creado', datetime.now().isoformat())
        usuario.ultimo_acceso = data.get('ultimo_acceso')
        usuario.es_superadmin = data.get('es_superadmin', False)
        usuario.bases_permitidas = data.get('bases_permitidas', [])
        usuario.modulos_permitidos = data.get('modulos_permitidos', [])
        usuario.intentos_fallidos = data.get('intentos_fallidos', 0)
        usuario.ultimo_intento = data.get('ultimo_intento')
        usuario.es_usuario_prueba = data.get('es_usuario_prueba', False)
        usuario.usar_sso = data.get('usar_sso', True)
        return usuario


class GestorUsuarios:
    """Gestiona usuarios, roles y permisos"""
    
    def __init__(self, archivo_usuarios: str = None):
        if archivo_usuarios is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            data_dir = os.path.join(base_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            archivo_usuarios = os.path.join(data_dir, 'usuarios.json')
        
        self.archivo_usuarios = archivo_usuarios
        self.archivo_roles = os.path.join(os.path.dirname(archivo_usuarios), 'roles.json')
        self.usuarios: Dict[str, Usuario] = {}
        self.roles: Dict[str, Dict] = {}
        self._cargar_datos()
        self._crear_usuarios_base()
    
    def _cargar_datos(self):
        """Carga datos desde archivos JSON con manejo de errores robusto"""
        # ============================================================
        # CARGAR ROLES
        # ============================================================
        try:
            if os.path.exists(self.archivo_roles):
                with open(self.archivo_roles, 'r', encoding='utf-8') as f:
                    self.roles = json.load(f)
                if not isinstance(self.roles, dict):
                    raise ValueError("Los roles no son un diccionario válido")
            else:
                self._crear_roles_base()
                self._guardar_roles()
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[WARN] Archivo {self.archivo_roles} corrupto: {e}")
            print("[INFO] Regenerando roles...")
            if os.path.exists(self.archivo_roles):
                backup_file = self.archivo_roles + '.corrupto'
                try:
                    if os.path.exists(backup_file):
                        os.remove(backup_file)
                        print(f"[INFO] Backup anterior eliminado: {backup_file}")
                    os.rename(self.archivo_roles, backup_file)
                    print(f"[INFO] Backup guardado en: {backup_file}")
                except Exception as be:
                    print(f"[WARN] No se pudo hacer backup: {be}")
                    try:
                        os.remove(self.archivo_roles)
                        print(f"[INFO] Archivo corrupto eliminado: {self.archivo_roles}")
                    except:
                        pass
            self._crear_roles_base()
            self._guardar_roles()
        except Exception as e:
            print(f"[ERROR] Error al cargar roles: {e}")
            self._crear_roles_base()
            self._guardar_roles()
        
        # ============================================================
        # CARGAR USUARIOS
        # ============================================================
        try:
            if os.path.exists(self.archivo_usuarios):
                with open(self.archivo_usuarios, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
                    if not isinstance(datos, dict):
                        raise ValueError("Los usuarios no son un diccionario válido")
                    for username, data in datos.items():
                        self.usuarios[username] = Usuario.from_dict(data)
            else:
                self.usuarios = {}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[WARN] Archivo {self.archivo_usuarios} corrupto: {e}")
            print("[INFO] Regenerando usuarios...")
            if os.path.exists(self.archivo_usuarios):
                backup_file = self.archivo_usuarios + '.corrupto'
                try:
                    if os.path.exists(backup_file):
                        os.remove(backup_file)
                    os.rename(self.archivo_usuarios, backup_file)
                    print(f"[INFO] Backup guardado en: {backup_file}")
                except Exception as be:
                    print(f"[WARN] No se pudo hacer backup: {be}")
                    try:
                        os.remove(self.archivo_usuarios)
                        print(f"[INFO] Archivo corrupto eliminado: {self.archivo_usuarios}")
                    except:
                        pass
            self.usuarios = {}
        except Exception as e:
            print(f"[ERROR] Error al cargar usuarios: {e}")
            self.usuarios = {}
    
    def _guardar_usuarios(self):
        """Guarda usuarios en archivo"""
        try:
            datos = {username: usuario.to_dict() 
                    for username, usuario in self.usuarios.items()}
            with open(self.archivo_usuarios, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Error al guardar usuarios: {e}")
    
    def _guardar_roles(self):
        """Guarda roles en archivo"""
        try:
            if not isinstance(self.roles, dict):
                print(f"[ERROR] roles no es un diccionario válido: {type(self.roles)}")
                return
            
            with open(self.archivo_roles, 'w', encoding='utf-8') as f:
                json.dump(self.roles, f, indent=2, ensure_ascii=False)
        except TypeError as e:
            print(f"[ERROR] Error al guardar roles (TypeError): {e}")
            self._crear_roles_base()
            try:
                with open(self.archivo_roles, 'w', encoding='utf-8') as f:
                    json.dump(self.roles, f, indent=2, ensure_ascii=False)
                print("[INFO] Roles regenerados y guardados correctamente")
            except Exception as e2:
                print(f"[ERROR] No se pudo guardar roles después de regenerar: {e2}")
        except Exception as e:
            print(f"[ERROR] Error al guardar roles: {e}")
    
    def _crear_roles_base(self):
        """Crea los roles base del sistema (set canónico, espejo de roles.json)"""
        # ⚠️ Set CANÓNICO de roles. Debe coincidir con data/roles.json (fuente
        # de verdad): solo se usa si el archivo falta o está corrupto. Si se
        # cambian roles/permisos, cambiar AMBOS lugares.
        self.roles = {
            "superadmin": {
                "id": "superadmin",
                "nombre": "Super Administrador",
                "descripcion": "Acceso TOTAL - Solo el creador del sistema",
                "permisos": [
                    "admin.acceso", "admin.auditoria.exportar", "admin.auditoria.ver",
                    "admin.backup", "admin.bases.config", "admin.dashboard",
                    "admin.modulos.config", "admin.permisos.asignar", "admin.restaurar",
                    "admin.roles.crear", "admin.roles.editar", "admin.roles.eliminar",
                    "admin.roles.ver", "admin.sistema.config", "admin.usuarios.asignar_rol",
                    "admin.usuarios.bloquear", "admin.usuarios.crear", "admin.usuarios.editar",
                    "admin.usuarios.eliminar", "admin.usuarios.ver",
                    "base.desarrollo.editar", "base.desarrollo.ver",
                    "base.produccion.editar", "base.produccion.ver",
                    "base.test.editar", "base.test.ver",
                    "cotizaciones.anular", "cotizaciones.aprobar", "cotizaciones.config",
                    "cotizaciones.crear", "cotizaciones.editar", "cotizaciones.eliminar",
                    "cotizaciones.exportar", "cotizaciones.reportes", "cotizaciones.ver",
                    "cxp.anular", "cxp.aprobar", "cxp.config", "cxp.crear", "cxp.editar",
                    "cxp.eliminar", "cxp.exportar", "cxp.importar", "cxp.reportes", "cxp.ver",
                    "reportes.config", "reportes.crear", "reportes.editar", "reportes.eliminar",
                    "reportes.exportar", "reportes.importar", "reportes.programar", "reportes.ver",
                    "stock.ajustar", "stock.config", "stock.crear", "stock.editar",
                    "stock.eliminar", "stock.exportar", "stock.importar", "stock.reportes",
                    "stock.transferir", "stock.ver"
                ],
                "es_admin": True,
                "nivel": 100,
                "color": "#dc3545"
            },
            "administrador": {
                "id": "administrador",
                "nombre": "Administrador",
                "descripcion": "Administración general - sin acceso a configuración crítica del sistema",
                "permisos": [
                    "admin.dashboard", "admin.modulos.config", "admin.roles.ver",
                    "admin.usuarios.asignar_rol", "admin.usuarios.bloquear",
                    "admin.usuarios.crear", "admin.usuarios.editar", "admin.usuarios.ver",
                    "cotizaciones.anular", "cotizaciones.aprobar", "cotizaciones.crear",
                    "cotizaciones.editar", "cotizaciones.eliminar", "cotizaciones.exportar",
                    "cotizaciones.reportes", "cotizaciones.ver",
                    "cxp.anular", "cxp.aprobar", "cxp.crear", "cxp.editar",
                    "cxp.eliminar", "cxp.exportar", "cxp.importar", "cxp.reportes", "cxp.ver",
                    "reportes.crear", "reportes.editar", "reportes.eliminar",
                    "reportes.exportar", "reportes.ver",
                    "stock.ajustar", "stock.crear", "stock.editar", "stock.eliminar",
                    "stock.exportar", "stock.importar", "stock.reportes",
                    "stock.transferir", "stock.ver"
                ],
                "es_admin": True,
                "nivel": 90,
                "color": "#fd7e14"
            },
            "gerente": {
                "id": "gerente",
                "nombre": "Gerente",
                "descripcion": "Acceso a reportes y gestión, sin configuración ni eliminación",
                "permisos": [
                    "admin.dashboard", "admin.roles.ver", "admin.usuarios.ver",
                    "cotizaciones.aprobar", "cotizaciones.crear", "cotizaciones.editar",
                    "cotizaciones.exportar", "cotizaciones.reportes", "cotizaciones.ver",
                    "cxp.aprobar", "cxp.crear", "cxp.editar", "cxp.exportar",
                    "cxp.importar", "cxp.reportes", "cxp.ver",
                    "reportes.crear", "reportes.editar", "reportes.exportar", "reportes.ver",
                    "stock.ajustar", "stock.crear", "stock.editar", "stock.exportar",
                    "stock.reportes", "stock.transferir", "stock.ver"
                ],
                "es_admin": False,
                "nivel": 80,
                "color": "#fd7e14"
            },
            "usuario": {
                "id": "usuario",
                "nombre": "Usuario",
                "descripcion": "Acceso básico - solo lectura y creación de registros",
                "permisos": [
                    "admin.dashboard", "admin.usuarios.ver",
                    "cotizaciones.crear", "cotizaciones.ver",
                    "cxp.crear", "cxp.ver",
                    "reportes.ver",
                    "stock.crear", "stock.ver"
                ],
                "es_admin": False,
                "nivel": 50,
                "color": "#0dcaf0"
            },
            "invitado": {
                "id": "invitado",
                "nombre": "Invitado",
                "descripcion": "Acceso solo lectura a reportes y dashboard",
                "permisos": [
                    "admin.dashboard",
                    "cotizaciones.ver", "cxp.ver", "reportes.ver", "stock.ver"
                ],
                "es_admin": False,
                "nivel": 10,
                "color": "#6c757d"
            }
        }
    
    def _crear_usuarios_base(self):
        # ============================================================
        # 1. CREAR SUPERADMIN (FORZADO - SIEMPRE pmolina)
        # ============================================================
        # ✅ FORZAR superadmin con tus datos (SIEMPRE)
        superadmin = Usuario(
            username="pmolina",
            password=None,
            email="pedro.molina@sidesys.com",
            nombre="Super Administrador"
        )
        superadmin.es_superadmin = True
        superadmin.roles = ["superadmin"]
        superadmin.bases_permitidas = ["*"]
        superadmin.modulos_permitidos = ["*"]
        superadmin.usar_sso = True
        self.usuarios["pmolina"] = superadmin  # ← FORZAR sobrescritura
    
        print("=" * 60)
        print("  👑 SUPERADMIN CREADO (FORZADO)")
        print("=" * 60)
        print(f"  Usuario Windows: pmolina")
        print(f"  Email: pedro.molina@sidesys.com")
        print()
        print("  ✅ Este es el usuario con MÁXIMOS PRIVILEGIOS")
        print("=" * 60)
    
        # ============================================================
        # 2. CREAR USUARIO PRUEBA (si no existe)
        # ============================================================
        if "prueba" not in self.usuarios:
            prueba = Usuario(
                username="prueba",
                password=PRUEBA_PASSWORD,
                email="prueba@sidesys.com",
                nombre="Usuario de Prueba"
            )
            prueba.roles = ["invitado"]
            prueba.bases_permitidas = ["*"]
            prueba.modulos_permitidos = ["*"]
            prueba.es_usuario_prueba = True
            prueba.usar_sso = False
            self.usuarios["prueba"] = prueba
        
            print("=" * 60)
            print("  🧪 USUARIO DE PRUEBA CREADO")
            print("=" * 60)
            print("  Usuario: prueba")
            print("  Contraseña: ******** (oculta)")
            print("  Rol: invitado")
            print("=" * 60)
    
            self._guardar_usuarios()
    
    # ============================================================
    # MÉTODOS DE GESTIÓN
    # ============================================================
    
    def crear_usuario(self, username: str, email: str = None, 
                     nombre: str = None, roles: List[str] = None,
                     usar_sso: bool = True) -> bool:
        if username in self.usuarios:
            raise ValueError(f"El usuario {username} ya existe")
        
        if roles:
            for rol in roles:
                if rol not in self.roles:
                    raise ValueError(f"El rol {rol} no existe")
        
        usuario = Usuario(
            username=username,
            password=None,
            email=email,
            nombre=nombre
        )
        usuario.roles = roles or ["invitado"]
        usuario.usar_sso = usar_sso
        usuario.activo = True
        
        self.usuarios[username] = usuario
        self._guardar_usuarios()
        return True
    
    def generar_contraseña_usuario_prueba(self) -> str:
        if "prueba" not in self.usuarios:
            raise ValueError("El usuario 'prueba' no existe")
        
        nueva_password = secrets.token_urlsafe(10)
        password_hash = bcrypt.hashpw(
            nueva_password.encode(), 
            bcrypt.gensalt()
        ).decode()
        
        self.usuarios["prueba"].password_hash = password_hash
        self._guardar_usuarios()
        return nueva_password
    
    def editar_usuario(self, username: str, **kwargs) -> bool:
        if username not in self.usuarios:
            raise ValueError(f"El usuario {username} no existe")
        
        usuario = self.usuarios[username]
        
        # ✅ No permitir modificar al superadmin
        if usuario.es_superadmin:
            raise ValueError("No puedes modificar al superadmin")
        
        if 'password' in kwargs and usuario.usar_sso:
            raise ValueError("Los usuarios con SSO no pueden tener contraseña")
        
        if 'password' in kwargs and username == "prueba":
            usuario.password_hash = bcrypt.hashpw(
                kwargs['password'].encode(), 
                bcrypt.gensalt()
            ).decode()
            del kwargs['password']
        
        if 'roles' in kwargs:
            for rol in kwargs['roles']:
                if rol not in self.roles:
                    raise ValueError(f"El rol {rol} no existe")
            usuario.roles = kwargs['roles']
            del kwargs['roles']
        
        for key, value in kwargs.items():
            if hasattr(usuario, key):
                setattr(usuario, key, value)
        
        self._guardar_usuarios()
        return True
    
    def eliminar_usuario(self, username: str) -> bool:
        if username not in self.usuarios:
            raise ValueError(f"El usuario {username} no existe")
        
        usuario = self.usuarios[username]
        
        if usuario.es_superadmin:
            raise ValueError("No se puede eliminar al superadmin")
        
        if username == "prueba":
            raise ValueError("No se puede eliminar al usuario de prueba")
        
        del self.usuarios[username]
        self._guardar_usuarios()
        return True
    
    def bloquear_usuario(self, username: str) -> bool:
        if username not in self.usuarios:
            raise ValueError(f"El usuario {username} no existe")
        
        if self.usuarios[username].es_superadmin:
            raise ValueError("No se puede bloquear al superadmin")
        
        if username == "prueba":
            raise ValueError("No se puede bloquear al usuario de prueba")
        
        self.usuarios[username].bloqueado = True
        self._guardar_usuarios()
        return True
    
    def desbloquear_usuario(self, username: str) -> bool:
        if username not in self.usuarios:
            raise ValueError(f"El usuario {username} no existe")
        
        self.usuarios[username].bloqueado = False
        self.usuarios[username].intentos_fallidos = 0
        self._guardar_usuarios()
        return True
    
    # ============================================================
    # MÉTODOS DE VERIFICACIÓN
    # ============================================================
    
    def verificar_credenciales(self, username: str, password: str) -> Optional[Usuario]:
        if username not in self.usuarios:
            return None
        
        usuario = self.usuarios[username]
        
        if not usuario.activo:
            raise ValueError("Usuario inactivo")
        
        if usuario.bloqueado:
            raise ValueError("Usuario bloqueado")
        
        if usuario.usar_sso:
            raise ValueError("Este usuario usa autenticación SSO de Windows")
        
        if not usuario.password_hash:
            raise ValueError("Usuario sin contraseña configurada")
        
        if not bcrypt.checkpw(password.encode(), usuario.password_hash.encode()):
            usuario.intentos_fallidos += 1
            usuario.ultimo_intento = datetime.now().isoformat()
            
            if usuario.intentos_fallidos >= 5:
                usuario.bloqueado = True
            
            self._guardar_usuarios()
            return None
        
        usuario.intentos_fallidos = 0
        usuario.ultimo_acceso = datetime.now().isoformat()
        self._guardar_usuarios()
        return usuario
    
    def obtener_permisos_usuario(self, username: str) -> List[str]:
        if username not in self.usuarios:
            return []
        
        usuario = self.usuarios[username]
        
        if usuario.es_superadmin:
            from .permisos import PermisosSistema
            return PermisosSistema.obtener_todos_permisos()
        
        permisos = set()
        
        for rol_id in usuario.roles:
            if rol_id in self.roles:
                permisos.update(self.roles[rol_id].get('permisos', []))
        
        permisos.update(usuario.permisos_extra)
        permisos.difference_update(usuario.permisos_restringidos)
        
        return list(permisos)
    
    def tiene_permiso(self, username: str, permiso: str) -> bool:
        if username not in self.usuarios:
            return False
        
        usuario = self.usuarios[username]
        
        if usuario.es_superadmin:
            return True
        
        permisos = self.obtener_permisos_usuario(username)
        return permiso in permisos or "*" in permisos
    
    def es_superadmin(self, username: str) -> bool:
        if username not in self.usuarios:
            return False
        return self.usuarios[username].es_superadmin
    
    def es_admin(self, username: str) -> bool:
        if username not in self.usuarios:
            return False
        
        usuario = self.usuarios[username]
        if usuario.es_superadmin:
            return True
        # Rol canónico: 'administrador' (roles.json). 'admin' se conserva como
        # alias legacy de flujos AD/versiones anteriores.
        return any(r in ('administrador', 'admin') for r in usuario.roles)
    
    def tiene_acceso_a_base(self, username: str, base: str) -> bool:
        if username not in self.usuarios:
            return False
        
        usuario = self.usuarios[username]
        
        if usuario.es_superadmin:
            return True
        
        if "*" in usuario.bases_permitidas:
            return True
        
        return base in usuario.bases_permitidas
    
    def tiene_acceso_a_modulo(self, username: str, modulo: str) -> bool:
        if username not in self.usuarios:
            return False
        
        usuario = self.usuarios[username]
        
        if usuario.es_superadmin:
            return True
        
        if "*" in usuario.modulos_permitidos:
            return True
        
        return modulo in usuario.modulos_permitidos
    
    # ============================================================
    # C4 - FUENTE DE VERDAD ÚNICA PARA AUTORIZACIÓN
    # ============================================================

    def puede_acceder_todas_bases(self, username: str) -> bool:
        """True solo para superadmin o usuarios con bases_permitidas=['*'].
        C4: los reportes/escrituras multi-base (todas las bases) exigen esto."""
        if username not in self.usuarios:
            return False
        usuario = self.usuarios[username]
        return usuario.es_superadmin or "*" in usuario.bases_permitidas

    def datos_usuario_completo(self, username: str) -> Optional[Dict]:
        """Shape único del usuario (roles + permisos + bases) usado por app.py,
        decoradores y /api/auth/current_user. Reemplaza la lectura cruda de
        roles.json/usuarios.json que duplicaba esta lógica en app.py."""
        usuario = self.usuarios.get(username)
        if not usuario:
            return None
        rol = usuario.roles[0] if usuario.roles else 'invitado'
        return {
            'username': usuario.username,
            'nombre': usuario.nombre,
            'email': usuario.email,
            'rol': rol,
            'roles': list(usuario.roles),
            'permisos': self.obtener_permisos_usuario(username),
            'es_superadmin': usuario.es_superadmin,
            'activo': usuario.activo,
            'bloqueado': usuario.bloqueado,
            'bases_permitidas': list(usuario.bases_permitidas),
            'modulos_permitidos': list(usuario.modulos_permitidos),
            'permisos_extra': list(usuario.permisos_extra),
            'permisos_restringidos': list(usuario.permisos_restringidos)
        }

    # ============================================================
    # MÉTODOS PARA ADMIN
    # ============================================================
    
    def listar_usuarios(self) -> List[Dict]:
        return [
            {
                "username": u.username,
                "email": u.email,
                "nombre": u.nombre,
                "roles": u.roles,
                "es_superadmin": u.es_superadmin,
                "activo": u.activo,
                "bloqueado": u.bloqueado,
                "ultimo_acceso": u.ultimo_acceso,
                "creado": u.creado,
                "bases_permitidas": u.bases_permitidas,
                "modulos_permitidos": u.modulos_permitidos,
                "intentos_fallidos": u.intentos_fallidos,
                "usar_sso": u.usar_sso,
                "es_usuario_prueba": u.es_usuario_prueba,
                "permisos": self.obtener_permisos_usuario(u.username)
            }
            for u in self.usuarios.values()
        ]
    
    def listar_roles(self) -> List[Dict]:
        return [
            {
                "id": rol_id,
                "nombre": rol.get("nombre", rol_id),
                "descripcion": rol.get("descripcion", ""),
                "permisos": rol.get("permisos", []),
                "es_admin": rol.get("es_admin", False),
                "nivel": rol.get("nivel", 0),
                "color": rol.get("color", "#6c757d"),
                "cantidad_usuarios": len([
                    u for u in self.usuarios.values() 
                    if rol_id in u.roles
                ])
            }
            for rol_id, rol in self.roles.items()
        ]
    
    def obtener_usuario(self, username: str) -> Optional[Dict]:
        if username not in self.usuarios:
            return None
        
        usuario = self.usuarios[username]
        return {
            "username": usuario.username,
            "email": usuario.email,
            "nombre": usuario.nombre,
            "roles": usuario.roles,
            "es_superadmin": usuario.es_superadmin,
            "activo": usuario.activo,
            "bloqueado": usuario.bloqueado,
            "creado": usuario.creado,
            "ultimo_acceso": usuario.ultimo_acceso,
            "bases_permitidas": usuario.bases_permitidas,
            "modulos_permitidos": usuario.modulos_permitidos,
            "usar_sso": usuario.usar_sso,
            "es_usuario_prueba": usuario.es_usuario_prueba,
            "permisos": self.obtener_permisos_usuario(username)
        }
    
    def crear_rol(self, rol_id: str, nombre: str, descripcion: str, 
                 permisos: List[str], nivel: int = 0, color: str = "#6c757d") -> bool:
        if rol_id in self.roles:
            raise ValueError(f"El rol {rol_id} ya existe")
        
        self.roles[rol_id] = {
            "id": rol_id,
            "nombre": nombre,
            "descripcion": descripcion,
            "permisos": permisos,
            "es_admin": False,
            "nivel": nivel,
            "color": color
        }
        self._guardar_roles()
        return True
    
    def editar_rol(self, rol_id: str, **kwargs) -> bool:
        if rol_id not in self.roles:
            raise ValueError(f"El rol {rol_id} no existe")
        
        if rol_id in ["superadmin"]:
            raise ValueError("No se puede editar el rol superadmin")
        
        self.roles[rol_id].update(kwargs)
        self._guardar_roles()
        return True
    
    def eliminar_rol(self, rol_id: str) -> bool:
        if rol_id not in self.roles:
            raise ValueError(f"El rol {rol_id} no existe")
        
        if rol_id in ["superadmin", "admin"]:
            raise ValueError("No se puede eliminar el rol superadmin o admin")
        
        usuarios_con_rol = [
            u.username for u in self.usuarios.values() 
            if rol_id in u.roles
        ]
        if usuarios_con_rol:
            raise ValueError(
                f"No se puede eliminar el rol porque está asignado a: {', '.join(usuarios_con_rol)}"
            )
        
        del self.roles[rol_id]
        self._guardar_roles()
        return True
    
    def get_stats(self) -> Dict:
        usuarios = self.usuarios.values()
        
        return {
            "total_usuarios": len(self.usuarios),
            "total_roles": len(self.roles),
            "usuarios_activos": len([u for u in usuarios if u.activo]),
            "usuarios_bloqueados": len([u for u in usuarios if u.bloqueado]),
            "superadmin": len([u for u in usuarios if u.es_superadmin]),
            "usuarios_admin": len([u for u in usuarios if 'admin' in u.roles]),
            "usuarios_sso": len([u for u in usuarios if u.usar_sso]),
            "ultimo_acceso": max([u.ultimo_acceso for u in usuarios if u.ultimo_acceso], default=None),
            "permisos_totales": len(PermisosSistema.obtener_todos_permisos())
        }

    def asignar_rol_admin(self, username: str) -> bool:
        if username not in self.usuarios:
            raise ValueError(f"El usuario {username} no existe")
        
        usuario = self.usuarios[username]
        
        if usuario.es_superadmin:
            raise ValueError("El superadmin ya tiene todos los permisos")
        
        if 'admin' in usuario.roles:
            raise ValueError(f"El usuario {username} ya tiene el rol admin")
        
        usuario.roles.append('admin')
        self._guardar_usuarios()
        return True
    
    def quitar_rol_admin(self, username: str) -> bool:
        if username not in self.usuarios:
            raise ValueError(f"El usuario {username} no existe")
        
        usuario = self.usuarios[username]
        
        if usuario.es_superadmin:
            raise ValueError("No se puede quitar el rol al superadmin")
        
        if 'admin' not in usuario.roles:
            raise ValueError(f"El usuario {username} no tiene el rol admin")
        
        usuario.roles.remove('admin')
        self._guardar_usuarios()
        return True


# ============================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================

_gestor_global = None

def get_gestor_usuarios() -> GestorUsuarios:
    global _gestor_global
    if _gestor_global is None:
        _gestor_global = GestorUsuarios()
    return _gestor_global

def get_users() -> Dict:
    gestor = get_gestor_usuarios()
    return {u.username: u.to_dict() for u in gestor.usuarios.values()}

def crear_usuario(username: str, password: str = None, rol: str = "usuario",
                  nombre: str = None, email: str = None, usar_sso: bool = True) -> bool:
    gestor = get_gestor_usuarios()
    return gestor.crear_usuario(
        username=username,
        email=email,
        nombre=nombre,
        roles=[rol] if rol else [],
        usar_sso=usar_sso
    )

def verificar_usuario(username: str, password: str) -> Optional[Dict]:
    gestor = get_gestor_usuarios()
    usuario = gestor.verificar_credenciales(username, password)
    return usuario.to_dict() if usuario else None