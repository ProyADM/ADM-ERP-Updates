# modules/shared/usuarios.py
# ============================================================
# GESTIÓN DE USUARIOS Y ROLES - SIDESYS ERP
# ============================================================

import copy
import os
import bcrypt
import secrets
import time
from datetime import datetime
from functools import wraps
from typing import List, Dict, Optional, Any
from .permisos import PermisosSistema
from . import config_central

# ============================================================
# TRADUCCIÓN SIGLA ↔ PAÍS (para el alcance por país de las ventas manuales)
# ============================================================
# VENTAS_MANUALES guarda el NOMBRE del país, mientras que `bases_permitidas`
# guarda el id de la base (plataforma_rd). Esta es la única traducción del
# sistema; antes estaba duplicada dentro del servicio de consolidado.
_SIGLA_A_PAIS = {
    'AR': 'Argentina', 'UY': 'Uruguay', 'RD': 'República Dominicana',
    'HN': 'Honduras', 'GT': 'Guatemala', 'CO': 'Colombia',
    'PE': 'Perú', 'PY': 'Paraguay', 'EC': 'Ecuador',
    'MX': 'México', 'CR': 'Costa Rica',
}

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

SUPERADMIN_EMAIL = _get_superadmin_email()
SUPERADMIN_USERNAME = _get_superadmin_username()

def _reversible(fn):
    """Si el almacén no se puede escribir, revierte el cambio en memoria."""
    @wraps(fn)
    def envuelto(self, *a, **kw):
        # Copia PROFUNDA también de cada usuario: `to_dict()` devuelve las mismas
        # listas (`roles`, `permisos_extra`, ...), así que un append in place mutaría
        # el snapshot y el restore dejaría el cambio aplicado.
        snapshot = (
            {k: copy.deepcopy(u.to_dict()) for k, u in self.usuarios.items()},
            copy.deepcopy(self.roles),
            copy.deepcopy(self.lapidas),
            copy.deepcopy(self.lapidas_roles),
        )
        try:
            return fn(self, *a, **kw)
        except config_central.AlmacenNoDisponible:
            usuarios, roles, lapidas, lapidas_roles = snapshot
            self.usuarios = {k: Usuario.from_dict(v) for k, v in usuarios.items()}
            self.roles = roles
            self.lapidas = lapidas
            self.lapidas_roles = lapidas_roles
            raise
    return envuelto


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
        # Base con la que ESTE usuario arranca la aplicación (17/09/2026). Es una
        # preferencia de arranque, no un permiso: si tiene más bases permitidas,
        # después puede cambiarse. Sin ella, el frontend arrancaba siempre en la
        # base por defecto del sistema (`plataforma_rd`) y cada usuario tenía que
        # cambiar de base a mano al entrar.
        self.base_default: Optional[str] = None
        self.intentos_fallidos: int = 0
        self.ultimo_intento: Optional[str] = None
        self.es_usuario_prueba: bool = False
        self.usar_sso: bool = True
        # Revisión del registro en el almacén (spec §5). Sin estos dos campos el
        # merge de tres vías veía "cambiado" TODO registro en cada guardado y,
        # con la base local vieja, descartaba la edición al archivo de
        # conflictos respondiendo igual 200 (CRITICAL 1).
        self.revision: Optional[str] = None
        self.modificado_por: Optional[str] = None
        
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
            "base_default": self.base_default,
            "intentos_fallidos": self.intentos_fallidos,
            "ultimo_intento": self.ultimo_intento,
            "es_usuario_prueba": self.es_usuario_prueba,
            "usar_sso": self.usar_sso,
            "revision": self.revision,
            "modificado_por": self.modificado_por
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
        usuario.base_default = data.get('base_default')
        usuario.intentos_fallidos = data.get('intentos_fallidos', 0)
        usuario.ultimo_intento = data.get('ultimo_intento')
        usuario.es_usuario_prueba = data.get('es_usuario_prueba', False)
        usuario.usar_sso = data.get('usar_sso', True)
        usuario.revision = data.get('revision')
        usuario.modificado_por = data.get('modificado_por')
        return usuario


class GestorUsuarios:
    """Gestiona usuarios, roles y permisos"""
    
    def __init__(self, archivo_usuarios: str = None, carpeta_central: str = None):
        # `archivo_usuarios` se conserva en la firma por compatibilidad: la
        # persistencia local la resuelve `config_central` (`data_dir()` /
        # `_local_dir`), así que no se guarda ni se lee (limpieza 12/09).
        self.carpeta_central = carpeta_central
        # El override de carpeta es de pruebas: la cache se va con el al temp para no
        # ensuciar el data/cache_central del desarrollador.
        self.cache_central = (carpeta_central + '_cache') if carpeta_central else None
        if self.cache_central:
            # La caché es la copia buena del modo degradado: si el directorio no
            # existe, `guardar()` no puede dejar el fallback (T14). En producción lo
            # crea `config_central.cache_dir()`.
            os.makedirs(self.cache_central, exist_ok=True)
        # El fallback local va al temp por el mismo motivo: `_local_dir` es de dónde
        # se SIEMBRA el almacén y adónde escribe la rama local; sin el seam, las
        # pruebas leerían el data/ real y dejarían ahí los *.pre-central.json.
        self.local_central = (carpeta_central + '_local') if carpeta_central else None
        self.usuarios: Dict[str, Usuario] = {}
        self.roles: Dict[str, Dict] = {}
        # Lápidas: registros borrados que hay que reenviar al almacén para que el
        # borrado se propague a las demás PCs (sección 5 del spec).
        self.lapidas: Dict[str, Dict] = {}
        # Lápidas de ROL: se guardan aparte de `self.roles` (si entraran ahí, un rol
        # borrado seguiría otorgando sus permisos hasta la poda). Sin guardarlas y
        # reenviarlas, `config_central.guardar` las re-sintetizaba con
        # `revision = now` en cada guardado: nunca llegaban a los 90 días de
        # `_podar_lapidas` y cada escritura con base vieja dejaba un conflicto
        # espurio por lápida.
        self.lapidas_roles: Dict[str, Dict] = {}
        self.estado_central: Dict = {}
        self._sello_actual = None
        self._ultimo_chequeo = 0.0
        self._reload_seg = config_central.ajustes()['reload_seg']
        self._cargar_datos()
        self._crear_usuarios_base()
    
    def _cargar_datos(self):
        """Carga usuarios y roles delegando en el almacén central."""
        # Sin try/except a propósito: con CENTRAL_STRICT=yes y sin almacén, `cargar`
        # lanza RuntimeError y el arranque DEBE fallar (fail-closed, spec §13.3).
        datos_u, datos_r, estado = config_central.cargar(
            carpeta=self.carpeta_central, _local_dir=self.local_central,
            _cache_dir=self.cache_central)

        self.estado_central = estado
        self._sello_actual = estado.get('sello')
        # Las lápidas de rol NO entran a `self.roles` (spec §5): si entraran, un rol
        # borrado en otra PC seguiría otorgando sus permisos hasta la poda de 90 días.
        # Pero tampoco se descartan: hay que reenviarlas tal cual (con su `revision`)
        # en cada guardado, como se hace con las lápidas de usuario.
        nuevos_roles = {}
        nuevas_lapidas_roles = {}
        for rol_id, data in (datos_r or {}).items():
            if not isinstance(data, dict):
                continue
            if data.get('eliminado'):
                nuevas_lapidas_roles[rol_id] = data
                continue
            nuevos_roles[rol_id] = data
        self.roles = nuevos_roles
        self.lapidas_roles = nuevas_lapidas_roles

        # Se arma en dicts locales y se asignan de una sola vez (swap atómico bajo
        # el GIL): el server es threaded=True y un lector que viera `self.usuarios`
        # vacío durante la recarga daría `datos_usuario_completo() is None` →
        # session.clear() (logout espurio) o `tiene_permiso` False (403 espurio),
        # justo mientras se aplica un cambio de permisos. No hace falta lock: una
        # recarga duplicada es inofensiva.
        nuevos_usuarios = {}
        nuevas_lapidas = {}
        for username, data in (datos_u or {}).items():
            if not isinstance(data, dict):
                continue
            if data.get('eliminado'):
                nuevas_lapidas[username] = data
                continue
            try:
                nuevos_usuarios[username] = Usuario.from_dict(data)
            except (KeyError, TypeError) as e:
                print(f'[WARN] Usuario {username} inválido en el almacén: {e}')

        self.usuarios = nuevos_usuarios   # swap atómico: ningún lector ve el dict a medio armar
        self.lapidas = nuevas_lapidas

        # El fallback de roles base va DESPUÉS de cargar los usuarios: su guardado
        # best-effort manda el estado completo, y si `self.usuarios` todavía fuera
        # {} la red de seguridad de `guardar` sintetizaría una lápida por cada
        # usuario del almacén (pérdida de datos en un store con usuarios y sin
        # roles: spec §5).
        if not self.roles:
            self._crear_roles_base()
            self._guardar_sin_bloquear('los roles base')
        elif self._reconciliar_permisos_nuevos():
            # El almacén se sembró antes de que existieran permisos nuevos: los
            # roles guardados no los tienen y NADIE los recibiría (ni el
            # superadmin por rol). Se agregan y se guarda una sola vez.
            self._guardar_sin_bloquear('permisos nuevos del catálogo')

        if estado.get('modo') == 'degradado':
            print(f"[WARN] {estado.get('mensaje')}")

    def _reconciliar_permisos_nuevos(self):
        """Agrega a los roles guardados los permisos del set CANÓNICO que faltan.

        Motivo (17/09/2026): al agregar `admin.diagnostico` al catálogo, el
        almacén —sembrado mucho antes— no lo tenía en ningún rol, así que ni el
        `administrador` podía ver la pestaña nueva. El set de `_crear_roles_base`
        es el espejo de `data/roles.json` (defaults del sistema), así que un
        permiso que está ahí y falta en el almacén es una versión vieja, no una
        personalización del administrador.

        Alcance deliberadamente acotado: solo AGREGA lo que falta en roles que
        existen en el canónico. Nunca quita permisos (una personalización del
        administrador se respeta) y nunca crea roles borrados a propósito.

        Devuelve True si hubo algo que agregar (para guardar una sola vez).
        """
        canonicos = {}
        previos = getattr(self, 'roles', None)
        try:
            self._crear_roles_base()          # deja el set canónico en self.roles
            canonicos = self.roles or {}
        finally:
            self.roles = previos              # se restauran los roles reales
        if not canonicos or not self.roles:
            return False

        cambios = 0
        for rol_id, canonico in canonicos.items():
            actual = self.roles.get(rol_id)
            if not isinstance(actual, dict):
                continue
            presentes = actual.get('permisos')
            if not isinstance(presentes, list):
                continue
            faltantes = [p for p in (canonico.get('permisos') or [])
                         if p not in presentes]
            if faltantes:
                actual['permisos'] = sorted(set(presentes) | set(faltantes))
                cambios += len(faltantes)
                print(f"[INFO] Rol '{rol_id}': se agregaron {len(faltantes)} permiso(s) "
                      f"nuevo(s) del catálogo: {', '.join(sorted(faltantes))}")
        return cambios > 0
    
    def _usuario_actual(self):
        """Quién está haciendo el cambio (para modificado_por). Sin Flask = 'sistema'."""
        try:
            from flask import session
            return session.get('username') or 'sistema'
        except Exception:
            return 'sistema'

    def _datos_para_guardar(self):
        datos = {username: usuario.to_dict()
                 for username, usuario in self.usuarios.items()}
        datos.update(self.lapidas)
        return datos

    def _roles_para_guardar(self):
        """Roles vivos + lápidas de rol (espejo de `_datos_para_guardar`).

        ⚠️ INVARIANTE: las lápidas van SIEMPRE al final del payload (igual que
        `datos.update(self.lapidas)` en los usuarios). Si la memoria tiene un rol
        vivo viejo y el disco ya tiene la lápida, tiene que ganar la LÁPIDA
        (`m == b` → gana el disco) para que el borrado se propague. La vuelta a
        crear un rol la resuelve el `self.lapidas_roles.pop(rol_id, None)` de
        `crear_rol`, NO el orden del spread: invertirlo para "que gane el vivo"
        resucita roles borrados por otra PC con todos sus permisos, sin conflicto
        y propagado a todas las PCs.

        Mandar `self.roles` solo (sin las lápidas) hacía que
        `config_central.guardar` re-sintetizara cada lápida con `revision = now`
        en CADA guardado: la poda de 90 días (spec §5) no las veía nunca y cada
        escritura con base vieja dejaba un `conflictos_*` espurio por lápida."""
        return {**self.roles, **self.lapidas_roles}

    def _guardar_usuarios(self):
        """Delega en el almacén central (o en data/ si no hay CENTRAL_DIR).

        No atrapa nada: quien sabe cómo reportar es el caller (`_guardar_sin_bloquear`
        avisa y sigue en arranque/login; la API de admin traduce a 503)."""
        sello = config_central.guardar(self._datos_para_guardar(),
                                       self._roles_para_guardar(),
                                       cambiado_por=self._usuario_actual(),
                                       carpeta=self.carpeta_central,
                                       _local_dir=self.local_central,
                                       _cache_dir=self.cache_central)
        self._sello_actual = sello
        self.estado_central = dict(self.estado_central, sello=sello)
        self._refrescar_revisiones()

    def _refrescar_revisiones(self):
        """Pone en los objetos en memoria la `revision` que quedó ESCRITA.

        `config_central.guardar` estampa la revisión en los dicts que escribe, no
        en los objetos `Usuario`. Sin este refresco, un usuario creado o editado
        en esta sesión seguiría con la revisión vieja (o `None`) y el próximo
        merge lo volvería a ver "cambiado": el mismo defecto del CRITICAL 1, ahora
        en los registros que toca esta PC.

        Además RESINCRONIZA las lápidas en memoria con las que quedaron escritas:
        `_podar_lapidas` puede haber quitado una lápida de más de 90 días, y si
        siguiera en memoria el guardado siguiente la resucitaría con
        `revision = now` (la base ya no la tiene y el disco tampoco): la poda del
        spec §5 no se sostendría nunca.

        Y todo rol cuya escritura quedó como LÁPIDA (lo borró otra PC mientras
        esta tenía la memoria vieja, o lo borró este proceso) sale de `self.roles`:
        si no, seguiría listándose y otorgando permisos en esta PC hasta la
        recarga por sello. Las lápidas van al final del payload (ver
        `_roles_para_guardar`) y eso evita la resurrección en el ALMACÉN; este
        `pop` la evita en MEMORIA."""
        escrito = config_central.ultimo_escrito()
        escritos = escrito.get('usuarios') or {}
        for username, usuario in self.usuarios.items():
            rec = escritos.get(username)
            if isinstance(rec, dict):
                usuario.revision = rec.get('revision')
                usuario.modificado_por = rec.get('modificado_por')
        self.lapidas = {k: v for k, v in escritos.items()
                        if isinstance(v, dict) and v.get('eliminado')}
        escritos_r = escrito.get('roles') or {}
        self.lapidas_roles = {k: v for k, v in escritos_r.items()
                              if isinstance(v, dict) and v.get('eliminado')}
        for rol_id in self.lapidas_roles:
            self.roles.pop(rol_id, None)

    def _guardar_roles(self):
        """Igual que _guardar_usuarios, pero solo cambian los roles."""
        self._guardar_usuarios()

    def _guardar_sin_bloquear(self, contexto):
        """Guardado best-effort del arranque/login: si el almacén está configurado y
        no se puede escribir, avisa y sigue (spec §7: el fallback mantiene el ERP
        operativo). Las operaciones de ADMIN no usan esto: ellas propagan
        AlmacenNoDisponible para que la API devuelva 503."""
        try:
            self._guardar_usuarios()
            return True
        except (config_central.AlmacenNoDisponible, OSError) as e:
            print(f'[WARN] No se pudo persistir {contexto} (almacén central no disponible): {e}')
            return False

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
                    "admin.diagnostico",
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
                    "admin.dashboard", "admin.diagnostico", "admin.modulos.config", "admin.roles.ver",
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
        """Garantiza que exista el superadmin. NO crea usuarios de desarrollo
        (decisión 12/09: el usuario 'prueba' se elimina de todas las instalaciones)
        y NUNCA pisa un registro que ya venga del almacén (arreglo 13.1 #1)."""
        if SUPERADMIN_USERNAME in self.usuarios:
            return
        if SUPERADMIN_USERNAME in self.lapidas:
            print(f'[WARN] {SUPERADMIN_USERNAME} está marcado como eliminado: no se recrea')
            return

        superadmin = Usuario(
            username=SUPERADMIN_USERNAME,
            password=None,
            email=SUPERADMIN_EMAIL,
            nombre='Super Administrador'
        )
        superadmin.es_superadmin = True
        superadmin.roles = ['superadmin']
        superadmin.bases_permitidas = ['*']
        superadmin.modulos_permitidos = ['*']
        superadmin.usar_sso = True
        self.usuarios[SUPERADMIN_USERNAME] = superadmin
        if self._guardar_sin_bloquear('el superadmin inicial'):
            print(f'[INFO] Superadmin {SUPERADMIN_USERNAME} creado en el almacén')
        else:
            print(f'[INFO] Superadmin {SUPERADMIN_USERNAME} creado en memoria '
                  f'(se persistirá cuando el almacén esté disponible)')

    # ============================================================
    # MÉTODOS DE GESTIÓN
    # ============================================================
    
    @_reversible
    def crear_usuario(self, username: str, email: str = None, 
                     nombre: str = None, roles: List[str] = None,
                     usar_sso: bool = True) -> bool:
        if username in self.usuarios:
            raise ValueError(f"El usuario {username} ya existe")

        # Mismo guard que en `editar_usuario`: sin esto, un administrador (tiene
        # `admin.usuarios.crear`) podía dar de alta un usuario con el rol
        # `superadmin` — la lista completa de permisos — y usarlo. Va ANTES de
        # tocar cualquier estado (lápidas, `self.usuarios`).
        if 'superadmin' in (roles or []):
            if not self.es_superadmin(self._usuario_actual()):
                raise ValueError('Solo un superadmin puede asignar el rol superadmin')

        if roles:
            for rol in roles:
                if rol not in self.roles:
                    raise ValueError(f"El rol {rol} no existe")
        
        # Recrear un usuario que estaba borrado: la lápida se descarta, si no
        # `_datos_para_guardar` la reenviaría y el alta nunca persistiría.
        self.lapidas.pop(username, None)
        
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
    
    @_reversible
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
    
    @_reversible
    def editar_usuario(self, username: str, **kwargs) -> bool:
        if username not in self.usuarios:
            raise ValueError(f"El usuario {username} no existe")
        
        usuario = self.usuarios[username]
        
        # ✅ No permitir modificar al superadmin
        if usuario.es_superadmin:
            raise ValueError("No puedes modificar al superadmin")

        # El rol superadmin no se puede asignar sin ser superadmin: si no, un
        # administrador con `admin.usuarios.editar` podía escalar privilegios
        # (la API de admin recibe `roles` del cuerpo). El endpoint además filtra
        # las claves, así que `es_superadmin` no es editable por esa vía.
        if 'roles' in kwargs and 'superadmin' in (kwargs['roles'] or []):
            if not self.es_superadmin(self._usuario_actual()):
                raise ValueError('Solo un superadmin puede asignar el rol superadmin')

        # Defensa en profundidad: la API bloquea `es_superadmin` por whitelist, pero
        # un caller interno (o un endpoint nuevo que reenvíe el cuerpo) podía
        # saltarla. Mismo criterio que el guard del rol: sin ser superadmin, no.
        if 'es_superadmin' in kwargs:
            if not self.es_superadmin(self._usuario_actual()):
                raise ValueError('Solo un superadmin puede cambiar es_superadmin')
        
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
    
    @_reversible
    def eliminar_usuario(self, username: str) -> bool:
        if username not in self.usuarios:
            raise ValueError(f"El usuario {username} no existe")
        
        usuario = self.usuarios[username]
        
        if usuario.es_superadmin:
            raise ValueError("No se puede eliminar al superadmin")
        
        self.lapidas[username] = config_central.marcar_lapida(
            usuario.to_dict(), self._usuario_actual())
        del self.usuarios[username]
        self._guardar_usuarios()
        return True
    
    @_reversible
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
    
    @_reversible
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
    
    @_reversible
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
            
            self._guardar_sin_bloquear('el intento de acceso')
            return None
        
        usuario.intentos_fallidos = 0
        usuario.ultimo_acceso = datetime.now().isoformat()
        self._guardar_sin_bloquear('el último acceso')
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

    def paises_permitidos(self, username: str):
        """Nombres de país que este usuario puede operar, o None si son todos.

        Traduce `bases_permitidas` (ids de base) a los nombres de país que usa
        VENTAS_MANUALES. Es la única traducción del sistema: antes vivía duplicada
        dentro del servicio de consolidado. Fail-closed: lista vacía = sin países.
        """
        if username not in self.usuarios:
            return []
        usuario = self.usuarios[username]
        if usuario.es_superadmin or '*' in (usuario.bases_permitidas or []):
            return None
        from config import BASES_DISPONIBLES
        paises = []
        for base in (usuario.bases_permitidas or []):
            info = BASES_DISPONIBLES.get(base)
            if info and info.get('sigla') in _SIGLA_A_PAIS:
                paises.append(_SIGLA_A_PAIS[info['sigla']])
        return sorted(set(paises))

    def puede_gestionar_ventas_de(self, username: str, pais: str) -> bool:
        """¿Este usuario puede BORRAR una venta manual de ese país?

        Regla (17/09/2026, pedido del usuario): el superadmin y el rol
        `administrador` pueden con todas; el resto, solo con las de sus países
        habilitados. Es fail-closed: sin países permitidos, no puede ninguna.
        """
        if username not in self.usuarios:
            return False
        usuario = self.usuarios[username]
        if usuario.es_superadmin or 'administrador' in (usuario.roles or []):
            return True
        permitidos = self.paises_permitidos(username)
        if permitidos is None:
            return True
        return (pais or '') in permitidos

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

    def recargar_si_cambio(self, forzar: bool = False) -> bool:
        """Recarga del almacén si el sello cambió (spec §6.3).

        Throttle: consulta el sello como mucho una vez cada CENTRAL_RELOAD_SEG
        segundos, así se puede llamar en cada request sin costo.
        """
        ahora = time.monotonic()
        if not forzar and (ahora - self._ultimo_chequeo) < self._reload_seg:
            return False
        self._ultimo_chequeo = ahora

        sello = config_central.leer_sello(carpeta=self.carpeta_central)
        if sello is None:
            # `leer_sello` devuelve None tanto si el sello FALTA (modo local o
            # almacén todavía sin sello: no hay nada que recargar) como si el
            # `sello.json` está ilegible. Un sello roto por un conflicto de
            # OneDrive congelaba la propagación en todas las PCs hasta la próxima
            # escritura: si el archivo existe y no se puede leer, se recarga.
            if not config_central.sello_ilegible(self.carpeta_central):
                return False
        elif sello == self._sello_actual:
            return False

        print(f'[INFO] Almacén central cambió (sello {str(sello)[:8]}): recargando usuarios/roles')
        self._cargar_datos()
        return True

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
                "base_default": u.base_default,
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
            "base_default": usuario.base_default,
            "usar_sso": usuario.usar_sso,
            "es_usuario_prueba": usuario.es_usuario_prueba,
            "permisos": self.obtener_permisos_usuario(username)
        }
    
    @_reversible
    def crear_rol(self, rol_id: str, nombre: str, descripcion: str, 
                 permisos: List[str], nivel: int = 0, color: str = "#6c757d") -> bool:
        if rol_id in self.roles:
            raise ValueError(f"El rol {rol_id} ya existe")

        # Recrear un rol que estaba borrado: la lápida se descarta, si no
        # `_roles_para_guardar` la reenviaría y el merge conservaría el registro
        # borrado (`m == b` → gana el disco): el rol nuevo no se escribiría nunca
        # aunque en memoria quedara vivo. Mismo criterio que en `crear_usuario`.
        self.lapidas_roles.pop(rol_id, None)

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
    
    @_reversible
    def editar_rol(self, rol_id: str, **kwargs) -> bool:
        if rol_id not in self.roles:
            raise ValueError(f"El rol {rol_id} no existe")
        
        if rol_id in ["superadmin"]:
            raise ValueError("No se puede editar el rol superadmin")
        
        self.roles[rol_id].update(kwargs)
        self._guardar_roles()
        return True
    
    @_reversible
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
        
        # La lápida la sintetiza `guardar()`: el rol estaba en la base del merge y ya
        # no viene en el estado deseado, así el borrado se propaga a las otras PCs.
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

    @_reversible
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
    
    @_reversible
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