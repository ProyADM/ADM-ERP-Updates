# modules/shared/config_central.py
# ============================================================
# ALMACÉN CENTRAL DE USUARIOS Y ROLES - SIDESYS ERP
# ============================================================
# Única puerta al almacén: resuelve la carpeta sincronizada, lee, escribe
# (atómico + sello), mergea por registro, cachea localmente y audita.
#
# ⚠️ NO importa config.py a propósito: config.py termina en sys.exit(1) si
#    falta .env.local, y este módulo tiene que poder importarse en pruebas
#    offline. Los ajustes se leen de os.environ con los mismos defaults.
# ============================================================

import copy
import json
import os
import uuid
from datetime import datetime, timedelta

NOMBRE_USUARIOS = 'usuarios.json'
NOMBRE_ROLES = 'roles.json'
NOMBRE_SELLO = 'sello.json'
NOMBRE_AUDITORIA = 'auditoria.jsonl'
PREFIJO_CONFLICTOS = 'conflictos_'
DIAS_LAPIDA = 90

RELOAD_SEG_DEFAULT = 15


class AlmacenNoDisponible(RuntimeError):
    """El almacén central está configurado pero no se puede escribir."""


# ============================================================
# RUTAS
# ============================================================

def base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _destino_apartado(ruta):
    """Primer sufijo LIBRE para apartar un archivo: `<ruta>.archivo`, `.archivo2`, …

    Nunca pisa un apartado anterior (ni un archivo ni un directorio): el
    `os.remove`/`os.replace` sobre un directorio daba IsADirectoryError (un OSError
    que solo se avisaba) y el archivo quedaba en su lugar, así que el `os.makedirs`
    posterior volvía a tumbar el arranque. Con el primer sufijo libre el apartado
    siempre funciona y no se pierde el apartado previo.
    """
    destino = ruta + '.archivo'
    n = 1
    while os.path.exists(destino):
        n += 1
        destino = f'{ruta}.archivo{n}'
    return destino


def _apartar_si_es_archivo(ruta):
    """Un archivo con el nombre de una carpeta que necesitamos (residuo de algo)
    tumbaba el arranque con FileExistsError fuera de todo try: se aparta."""
    try:
        if os.path.exists(ruta) and not os.path.isdir(ruta):
            destino = _destino_apartado(ruta)
            os.replace(ruta, destino)
            print(f'[WARN] config_central: {os.path.basename(ruta)} era un archivo; '
                  f'se apartó a {os.path.basename(destino)}')
    except OSError as e:
        print(f'[WARN] config_central: no se pudo apartar {ruta}: {e}')


def data_dir() -> str:
    d = os.path.join(base_dir(), 'data')
    _apartar_si_es_archivo(d)
    os.makedirs(d, exist_ok=True)
    return d


def cache_dir() -> str:
    d = os.path.join(data_dir(), 'cache_central')
    _apartar_si_es_archivo(d)
    os.makedirs(d, exist_ok=True)
    return d


def ajustes() -> dict:
    try:
        reload_seg = int(os.environ.get('CENTRAL_RELOAD_SEG') or RELOAD_SEG_DEFAULT)
    except ValueError:
        reload_seg = RELOAD_SEG_DEFAULT
    return {
        # expandvars: el .env de despliegue (el que se cifra como erp.env.encrypted) es
        # COMPARTIDO entre PCs y la raíz de OneDrive es por equipo, así que CENTRAL_DIR se
        # escribe como %OneDriveCommercial%\Sidesys\ADM-ERP\config y cada PC resuelve la suya.
        'central_dir': os.path.expandvars(os.environ.get('CENTRAL_DIR') or '').strip() or None,
        'reload_seg': max(1, reload_seg),
        'strict': (os.environ.get('CENTRAL_STRICT') or 'no').strip().lower()
                  in ('1', 'yes', 'true', 'on'),
    }


def detectar_onedrive():
    """%OneDriveCommercial%\\Sidesys\\ADM-ERP\\config (con %OneDrive% como respaldo)."""
    base = os.environ.get('OneDriveCommercial') or os.environ.get('OneDrive')
    if not base:
        return None
    return os.path.join(base, 'Sidesys', 'ADM-ERP', 'config')


def resolver_central_dir(carpeta=None):
    if carpeta:
        return carpeta
    return ajustes()['central_dir'] or detectar_onedrive()


def carpeta_utilizable(carpeta) -> bool:
    if not carpeta or not os.path.isdir(carpeta):
        return False
    try:
        prueba = os.path.join(carpeta, '.escritura_test')
        with open(prueba, 'w', encoding='utf-8') as f:
            f.write('ok')
        os.remove(prueba)
        return True
    except OSError:
        return False


# ============================================================
# LECTURA / ESCRITURA
# ============================================================

def leer_json(ruta, default=None):
    try:
        if not os.path.exists(ruta):
            return default
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        print(f'[WARN] config_central: no se pudo leer {ruta}: {e}')
        return default


def escribir_atomico(ruta, datos):
    """Escribe <ruta>.tmp y lo mueve con os.replace (atómico en el mismo volumen)."""
    tmp = ruta + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    os.replace(tmp, ruta)


def leer_sello(carpeta=None):
    carpeta = resolver_central_dir(carpeta)
    if not carpeta:
        return None
    datos = leer_json(os.path.join(carpeta, NOMBRE_SELLO), None)
    if isinstance(datos, dict):
        return datos.get('sello')
    return None


def sello_ilegible(carpeta=None) -> bool:
    """True si en el almacén hay un `sello.json` que no se puede leer.

    `leer_sello` devuelve None tanto si el sello falta (no hay nada que
    recargar) como si el archivo está corrupto. La diferencia importa para la
    propagación: un `sello.json` roto por un conflicto de OneDrive la congela en
    todas las PCs hasta la próxima escritura, así que en ese caso hay que
    recargar igual (lo trata `recargar_si_cambio`).
    """
    destino = resolver_central_dir(carpeta)
    if not destino:
        return False
    ruta = os.path.join(destino, NOMBRE_SELLO)
    if not os.path.exists(ruta):
        return False
    datos = leer_json(ruta, None)
    return not (isinstance(datos, dict) and datos.get('sello'))


def escribir_sello(carpeta, escritor):
    sello = uuid.uuid4().hex
    escribir_atomico(os.path.join(carpeta, NOMBRE_SELLO), {
        'sello': sello,
        'ultima_escritura': datetime.now().isoformat(),
        'escritor': escritor or 'sistema',
    })
    return sello


# ============================================================
# ESTADO EN MEMORIA (lo último que se leyó del almacén)
# ============================================================
# Es la "base" del merge de tres vías: permite distinguir lo que cambió otra PC
# de lo que quedó igual mientras editábamos.
_ultimo = {'usuarios': {}, 'roles': {}, 'sello': None, 'carpeta': None}


def reiniciar_estado():
    """Solo para pruebas: olvida lo último leído."""
    _ultimo.update({'usuarios': {}, 'roles': {}, 'sello': None, 'carpeta': None})


def ultimo_escrito() -> dict:
    """Lo que quedó en el almacén (o en data/, en modo local) en el último
    `cargar`/`guardar`: es la base del merge y el espejo de lo escrito.

    La usa `GestorUsuarios` para refrescar la `revision` de sus objetos en
    memoria después de guardar: si no, un registro creado o editado en esta
    sesión seguiría sin revisión y el merge lo vería "cambiado" siempre.

    Devuelve una COPIA PROFUNDA: es un accesor público a la base del merge, y
    quien lo reciba no puede mutar el estado interno de este módulo."""
    return copy.deepcopy(_ultimo)


def _recordar(carpeta, usuarios, roles, sello=None):
    """Snapshot base del merge. Copia profunda: el caller puede mutar lo que
    recibió sin alterar la base (si no, el merge vería 'sin cambios')."""
    _ultimo.update({'usuarios': copy.deepcopy(usuarios), 'roles': copy.deepcopy(roles),
                    'sello': sello, 'carpeta': carpeta})


def _rutas_locales(local_dir=None):
    d = local_dir or data_dir()
    return os.path.join(d, NOMBRE_USUARIOS), os.path.join(d, NOMBRE_ROLES)


def _leer_locales(local_dir=None):
    ru, rr = _rutas_locales(local_dir)
    return leer_json(ru, {}) or {}, leer_json(rr, {}) or {}


def _leer_json_estado(ruta):
    """Devuelve (datos, estado) con estado en {'ok', 'falta', 'corrupto'}.

    Necesario para distinguir "el archivo no está" de "el archivo está roto":
    el spec §7 manda apartar el corrupto como .corrupto y NO sobreescribirlo.
    """
    if not os.path.exists(ruta):
        return None, 'falta'
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f), 'ok'
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, 'corrupto'
    except OSError as e:
        print(f'[WARN] config_central: no se pudo leer {ruta}: {e}')
        return None, 'falta'


def _apartar_corruptos(carpeta):
    """Mueve los JSON rotos del almacén a .corrupto (spec §7)."""
    apartados = []
    for nombre in (NOMBRE_USUARIOS, NOMBRE_ROLES):
        ruta = os.path.join(carpeta, nombre)
        if _leer_json_estado(ruta)[1] != 'corrupto':
            continue
        destino = ruta + '.corrupto'
        try:
            if os.path.exists(destino):
                os.remove(destino)
            os.replace(ruta, destino)
            apartados.append(destino)
            print(f'[WARN] config_central: {nombre} corrupto → {nombre}.corrupto')
        except OSError as e:
            print(f'[WARN] config_central: no se pudo apartar {nombre}: {e}')
    return apartados


def _guardar_cache(usuarios, roles, cache_dir=None):
    try:
        # globals(): el parámetro `cache_dir` tapa el nombre de la función cache_dir().
        d = cache_dir or globals()['cache_dir']()
        escribir_atomico(os.path.join(d, NOMBRE_USUARIOS), usuarios)
        escribir_atomico(os.path.join(d, NOMBRE_ROLES), roles)
    except OSError as e:
        print(f'[WARN] config_central: no se pudo actualizar la caché local: {e}')


def _cargar_cache(cache_dir=None):
    d = cache_dir or globals()['cache_dir']()
    return (leer_json(os.path.join(d, NOMBRE_USUARIOS), None),
            leer_json(os.path.join(d, NOMBRE_ROLES), None))


def _respaldar_locales(local_dir=None):
    """Backup .pre-central.json de los JSON locales (idempotente, nunca pisa uno existente)."""
    ru, rr = _rutas_locales(local_dir)
    for ruta in (ru, rr):
        if not os.path.exists(ruta):
            continue
        backup = ruta.replace('.json', '.pre-central.json')
        if os.path.exists(backup):
            continue
        try:
            with open(ruta, 'r', encoding='utf-8') as fo, \
                 open(backup, 'w', encoding='utf-8') as fd:
                fd.write(fo.read())
        except (OSError, UnicodeDecodeError) as e:
            print(f'[WARN] config_central: backup {backup} falló: {e}')


def _sembrar(destino, local_dir=None, usuarios=None, roles=None):
    """Completa desde data/ lo que falte en el almacén (siembra inicial o reparación).

    Devuelve (usuarios, roles) completos. Deja backup .pre-central.json y sello.
    """
    locales_u, locales_r = _leer_locales(local_dir)
    repuestos = []
    if not usuarios and locales_u:
        usuarios = locales_u
        repuestos.append(NOMBRE_USUARIOS)
    if not roles and locales_r:
        roles = locales_r
        repuestos.append(NOMBRE_ROLES)
    if not repuestos:
        return usuarios or {}, roles or {}
    _respaldar_locales(local_dir)
    escribir_atomico(os.path.join(destino, NOMBRE_USUARIOS), usuarios or {})
    escribir_atomico(os.path.join(destino, NOMBRE_ROLES), roles or {})
    if not leer_sello(destino):
        escribir_sello(destino, 'siembra')
    print(f'[INFO] config_central: almacén completado desde data/: {repuestos}')
    return usuarios or {}, roles or {}


def _estado_base(carpeta):
    return {
        'ruta': carpeta,
        'modo': 'local',
        'accesible': False,
        'degradado': False,
        'sello': None,
        'escritor': None,
        'ultima_escritura': None,
        'ultima_lectura': None,
        'mensaje': '',
    }


def _es_explicito(carpeta=None):
    """¿El almacén está configurado a propósito (env o override de prueba)?

    Distingue "este equipo nunca fue aprovisionado" (autodetección que no
    encuentra carpeta → comportamiento local, spec §4) de "el almacén está
    configurado y no se puede acceder" (degradado + escritura bloqueada, §7/§12).
    """
    return bool(ajustes()['central_dir'] or carpeta)


def cargar(carpeta=None, _local_dir=None, _cache_dir=None):
    """Devuelve (usuarios, roles, estado). Ver secciones 6 y 7 del spec."""
    a = ajustes()
    destino = resolver_central_dir(carpeta)
    est = _estado_base(destino)

    if destino and carpeta_utilizable(destino):
        usuarios, est_u = _leer_json_estado(os.path.join(destino, NOMBRE_USUARIOS))
        roles, est_r = _leer_json_estado(os.path.join(destino, NOMBRE_ROLES))

        if 'corrupto' in (est_u, est_r):
            _apartar_corruptos(destino)
            cache_u, cache_r = _cargar_cache(_cache_dir)
            usuarios, roles = cache_u or {}, cache_r or {}
            est.update({
                'modo': 'degradado',
                'degradado': True,
                'mensaje': ('Hay archivos corruptos en el almacén: se apartaron como '
                            '.corrupto (no se sobreescribieron) y se sigue con la última '
                            'copia buena.'),
                'ultima_lectura': datetime.now().isoformat(),
            })
            _recordar(destino, usuarios, roles)
            return usuarios, roles, est

        if not usuarios or not roles:
            usuarios, roles = _sembrar(destino, _local_dir, usuarios, roles)
        usuarios, roles = usuarios or {}, roles or {}
        sello_datos = leer_json(os.path.join(destino, NOMBRE_SELLO), {}) or {}
        est.update({
            'modo': 'central',
            'accesible': True,
            'sello': sello_datos.get('sello'),
            'escritor': sello_datos.get('escritor'),
            'ultima_escritura': sello_datos.get('ultima_escritura'),
            'ultima_lectura': datetime.now().isoformat(),
        })
        if usuarios or roles:
            _guardar_cache(usuarios, roles, _cache_dir)
        _recordar(destino, usuarios, roles, est['sello'])
        return usuarios, roles, est

    if destino and a['strict'] and _es_explicito(carpeta):
        raise RuntimeError(
            f'Almacén central no accesible y CENTRAL_STRICT=yes: {destino}')

    if destino and _es_explicito(carpeta):
        cache_u, cache_r = _cargar_cache(_cache_dir)
        usuarios, roles = cache_u or {}, cache_r or {}
        if not usuarios or not roles:
            locales_u, locales_r = _leer_locales(_local_dir)
            usuarios = usuarios or locales_u
            roles = roles or locales_r
            origen = 'data/ local (copia incompleta)'
        else:
            origen = 'la última copia buena local'
        est.update({
            'modo': 'degradado',
            'degradado': True,
            'mensaje': (f'Almacén central no accesible: se usa {origen}. '
                        'La administración de usuarios queda deshabilitada.'),
            'ultima_lectura': datetime.now().isoformat(),
        })
        _recordar(destino, usuarios, roles)
        return usuarios, roles, est

    # Sin almacén configurado (o autodetectado y todavía inexistente): local.
    est['mensaje'] = est['mensaje'] or (
        'Sin almacén central aprovisionado: configuración local (data/).')
    usuarios, roles = _leer_locales(_local_dir)
    est['ultima_lectura'] = datetime.now().isoformat()
    _recordar(destino, usuarios, roles)
    return usuarios, roles, est


def estado(carpeta=None):
    """Estado actual del almacén (vuelve a leer el almacén)."""
    _, _, est = cargar(carpeta)
    return est


# ============================================================
# RESPALDO Y SIEMBRA MANUAL (spec §4)
# ============================================================

def exportar(destino, carpeta=None):
    """Respaldo manual: un JSON con usuarios y roles juntos (spec §4)."""
    usuarios, roles, est = cargar(carpeta)
    if not usuarios or not roles:
        # Un respaldo a medias es peor que ninguno: importar `{"usuarios": {},
        # "roles": {...}}` sintetiza una lápida por cada usuario del destino y
        # borra la configuración. La guarda es simétrica a la de `importar`.
        raise ValueError('No hay configuración para exportar (usuarios o roles vacíos)')
    paquete = {
        'exportado': datetime.now().isoformat(),
        'origen': est.get('ruta'),
        'sello': est.get('sello'),
        # Sin el modo, un respaldo hecho en degradado (caché o data/ viejo) no se
        # distingue de uno hecho contra el almacén central.
        'modo': est.get('modo'),
        'usuarios': usuarios,
        'roles': roles,
    }
    escribir_atomico(destino, paquete)
    return destino


def importar(origen, cambiado_por='importacion', carpeta=None):
    """Siembra manual desde un respaldo. Valida la forma antes de escribir."""
    paquete = leer_json(origen, None)
    if not isinstance(paquete, dict) or 'usuarios' not in paquete or 'roles' not in paquete:
        raise ValueError('El archivo no tiene el formato de un respaldo de configuración')
    if not isinstance(paquete['usuarios'], dict) or not isinstance(paquete['roles'], dict):
        raise ValueError('usuarios/roles del respaldo no son diccionarios')
    if not paquete['usuarios'] or not paquete['roles']:
        # Importar una mitad vacía no es "no hacer nada": el merge sintetiza una
        # lápida por cada registro de la base y borraría la configuración de todas
        # las PCs. El caso real es el camino degradado, que puede exportar
        # `{"usuarios": {}, "roles": {...}}`. Por eso se exigen las DOS mitades.
        raise ValueError(
            'El respaldo está incompleto (usuarios o roles vacíos): no se importa '
            'para no borrar la configuración')
    sello = guardar(paquete['usuarios'], paquete['roles'],
                    cambiado_por=cambiado_por, carpeta=carpeta)
    return len(paquete['usuarios']), len(paquete['roles']), sello


# ============================================================
# GUARDADO: MERGE DE TRES VÍAS, REVISIÓN POR REGISTRO Y LÁPIDAS
# ============================================================
# `guardar` recibe el estado deseado completo. La base del merge es lo último
# que leyó `cargar` (`_ultimo`) y "suyo" es lo que hay en el disco ahora: así se
# distingue mi cambio del de otra PC. Los borrados viajan como lápida
# (`eliminado: True`) y se podan a los DIAS_LAPIDA.

def _clave(rec):
    return json.dumps(rec, sort_keys=True, ensure_ascii=False)


def marcar_lapida(registro, quien):
    """Convierte un registro en lápida: el borrado se propaga a las otras PCs.

    Tolerante a un registro que no sea dict (una entrada editada a mano en el
    almacén): `dict(registro)` lanzaba ValueError desde el arranque/login, fuera
    de todo try. La base se COPIA igual: el dict del caller no se muta."""
    lapida = dict(registro if isinstance(registro, dict) else {})
    lapida['eliminado'] = True
    lapida['revision'] = datetime.now().isoformat()
    lapida['modificado_por'] = quien or 'sistema'
    return lapida


def _podar_lapidas(datos, dias=DIAS_LAPIDA):
    corte = (datetime.now() - timedelta(days=dias)).isoformat()
    return {k: v for k, v in datos.items()
            if not (isinstance(v, dict) and v.get('eliminado')
                    and (v.get('revision') or '') < corte)}


def _merge_tres(base, mio, suyo, etiqueta, conflictos):
    """Merge por registro (sección 5 del spec).

    - Si yo no lo toqué y el otro sí → gana el otro.
    - Si el otro no lo tocó y yo sí → gana el mío.
    - Si los dos lo tocaron distinto → gana la `revision` mayor y el perdedor
      se guarda en conflictos_<fecha>_<escritor>.json (no se pierde nada). Si las
      dos revisiones son iguales no hay "mayor": gana la del disco (no se pisa la
      escritura ajena) y lo mío queda en el archivo de conflictos.
    """
    resultado = {}
    for k in set(base) | set(mio) | set(suyo):
        b, m, s = base.get(k), mio.get(k), suyo.get(k)
        if _clave(m) == _clave(b):
            elegido = s if s is not None else m
        elif _clave(s) == _clave(b):
            elegido = m
        else:
            # `or ''`: un registro sin revisión (o con `revision: null`, que es lo
            # que manda el gestor para un registro recién creado) no puede romper
            # la comparación con None.
            rev_m = ((m or {}).get('revision') or '') if isinstance(m, dict) else ''
            rev_s = ((s or {}).get('revision') or '') if isinstance(s, dict) else ''
            elegido, perdedor = (m, s) if rev_m > rev_s else (s, m)
            if perdedor is not None and _clave(perdedor) != _clave(elegido):
                conflictos.append({'tabla': etiqueta, 'clave': k,
                                   'descartado': perdedor, 'elegido': elegido})
        if elegido is not None:
            resultado[k] = elegido
    return resultado


def _estampar(base, suyo, resultado, quien):
    """Marca revision/modificado_por en lo que yo cambié y no vino del otro."""
    ahora = datetime.now().isoformat()
    for k, rec in resultado.items():
        if not isinstance(rec, dict):
            continue
        if _clave(rec) == _clave(base.get(k)):
            continue
        if _clave(rec) == _clave(suyo.get(k)):
            continue                      # vino del otro: se respeta su revisión
        rec['revision'] = ahora
        rec['modificado_por'] = quien or 'sistema'
    return resultado


def _slug(texto):
    limpio = ''.join(c if (c.isalnum() or c in '-_') else '_' for c in str(texto or ''))
    return limpio[:24] or 'desconocido'


def _registrar_conflictos(carpeta, conflictos, escritor):
    if not conflictos:
        return None
    nombre = f'{PREFIJO_CONFLICTOS}{datetime.now().strftime("%Y%m%d")}_{_slug(escritor)}.json'
    ruta = os.path.join(carpeta, nombre)
    previos = leer_json(ruta, []) or []
    previos.extend(conflictos)
    try:
        escribir_atomico(ruta, previos)
        print(f'[WARN] config_central: {len(conflictos)} conflicto(s) guardados en {nombre}')
        return ruta
    except OSError as e:
        print(f'[WARN] config_central: no se pudieron registrar los conflictos: {e}')
        return None


def guardar(usuarios, roles, cambiado_por='sistema', carpeta=None, _cache_dir=None,
            _local_dir=None):
    """Escribe el almacén con merge de tres vías. Devuelve el sello nuevo."""
    destino = resolver_central_dir(carpeta)

    if not destino or not (carpeta_utilizable(destino) or _es_explicito(carpeta)):
        # Sin almacén aprovisionado (o sin CENTRAL_DIR): comportamiento local actual.
        ru, rr = _rutas_locales(_local_dir)
        usuarios = _podar_lapidas(dict(usuarios or {}))
        roles = _podar_lapidas(dict(roles or {}))
        try:
            escribir_atomico(ru, usuarios)
            escribir_atomico(rr, roles)
            _guardar_cache(usuarios, roles, _cache_dir)
        except OSError as e:
            # El camino local tampoco puede tumbar el arranque (el singleton se
            # construye al importar): data/ sin permiso o bloqueado se reporta
            # como almacén no disponible (aviso en arranque/login, 503 en admin).
            raise AlmacenNoDisponible(
                f'No se pudo escribir la configuración local: {e}')
        _recordar(None, usuarios, roles)
        return ''

    if not carpeta_utilizable(destino):
        raise AlmacenNoDisponible(
            f'El almacén central no está accesible ({destino}): el cambio no se guardó.')
    conflicto = _ultimo['carpeta'] == destino
    base_u = _ultimo['usuarios'] if conflicto else {}
    base_r = _ultimo['roles'] if conflicto else {}
    disco_u = leer_json(os.path.join(destino, NOMBRE_USUARIOS), {}) or {}
    disco_r = leer_json(os.path.join(destino, NOMBRE_ROLES), {}) or {}

    # Un registro que la base conocía y que ya no viene en el estado deseado es un
    # borrado: se convierte en lápida para que se propague. Si no, otra PC con la
    # base vieja lo resucitaría al guardar (y sin conflicto). El flujo normal manda
    # los borrados ya con lápida (marcar_lapida), así que esto es la red de seguridad.
    usuarios_in = dict(usuarios or {})
    roles_in = dict(roles or {})
    for k, rec in base_u.items():
        if k not in usuarios_in:
            usuarios_in[k] = marcar_lapida(rec, cambiado_por)
    for k, rec in base_r.items():
        if k not in roles_in:
            roles_in[k] = marcar_lapida(rec, cambiado_por)

    conflictos = []
    final_u = _merge_tres(base_u, usuarios_in, disco_u, 'usuarios', conflictos)
    final_r = _merge_tres(base_r, roles_in, disco_r, 'roles', conflictos)
    final_u = _estampar(base_u, disco_u, final_u, cambiado_por)
    final_r = _estampar(base_r, disco_r, final_r, cambiado_por)
    final_u = _podar_lapidas(final_u)
    final_r = _podar_lapidas(final_r)

    try:
        escribir_atomico(os.path.join(destino, NOMBRE_USUARIOS), final_u)
        escribir_atomico(os.path.join(destino, NOMBRE_ROLES), final_r)
        sello = escribir_sello(destino, cambiado_por)
    except OSError as e:
        raise AlmacenNoDisponible(
            f'El almacén central no se pudo escribir ({destino}): '
            f'el cambio no se guardó. {e}')
    _registrar_conflictos(destino, conflictos, cambiado_por)
    _guardar_cache(final_u, final_r, _cache_dir)
    _recordar(destino, final_u, final_r, sello)
    return sello


# ============================================================
# AUDITORÍA (spec §7: nunca interrumpe la operación)
# ============================================================
# Un evento = una línea JSON (jsonl). Se intenta el almacén y, si no se puede
# escribir, se cae al data/ local (así la promesa de "nunca interrumpe" no
# depende de que el almacén sea escribible). Reemplaza al data/auditoria.log que
# se leía y nunca se escribía (hallazgo 13.1 #2).

def _rutas_auditoria(carpeta=None, _local_dir=None):
    """Rutas candidatas en orden: el almacén (si está resuelto) y luego data/ local.

    El dedup es por ruta NORMALIZADA (normcase+abspath): el mismo directorio
    escrito distinto (barra final, ".", mayúsculas en Windows) no debe quedar dos
    veces o el mismo archivo se leería dos veces y los eventos saldrían duplicados.
    """
    candidatas = []
    destino = resolver_central_dir(carpeta)
    if destino:
        candidatas.append(os.path.join(destino, NOMBRE_AUDITORIA))
    candidatas.append(os.path.join(_local_dir or data_dir(), NOMBRE_AUDITORIA))
    rutas = []
    vistas = set()
    for ruta in candidatas:
        clave = os.path.normcase(os.path.abspath(ruta))
        if clave in vistas:
            continue
        vistas.add(clave)
        rutas.append(ruta)
    return rutas


def ruta_auditoria(carpeta=None, _local_dir=None):
    """Primera ruta candidata (ver _rutas_auditoria)."""
    return _rutas_auditoria(carpeta, _local_dir)[0]


def auditar(evento, carpeta=None, _local_dir=None):
    """Agrega una línea JSON al log. NUNCA interrumpe la operación (spec §7)."""
    try:
        evento = dict(evento or {})
        evento.setdefault('fecha', datetime.now().isoformat())
        linea = json.dumps(evento, ensure_ascii=False) + '\n'
        fallo = None
        for ruta in _rutas_auditoria(carpeta, _local_dir):
            try:
                with open(ruta, 'a', encoding='utf-8') as f:
                    f.write(linea)
                return
            except OSError as e:
                fallo = e
        print(f'[WARN] config_central: auditoría falló ({fallo}); la operación sigue')
    except (OSError, TypeError, ValueError) as e:
        print(f'[WARN] config_central: auditoría falló ({e}); la operación sigue')


def leer_auditoria(dias=7, limite=100, carpeta=None, _local_dir=None):
    """Lee TODAS las rutas candidatas (almacén + fallback local), mezcla, ordena
    por fecha y recién ahí filtra por días y recorta a los `limite` últimos."""
    limite = max(0, int(limite))
    corte = (datetime.now() - timedelta(days=max(1, dias))).isoformat()
    eventos = []
    for ruta in _rutas_auditoria(carpeta, _local_dir):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                for linea in f:
                    try:
                        ev = json.loads(linea)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(ev, dict):
                        continue
                    fecha = ev.get('fecha')
                    if not isinstance(fecha, str) or fecha < corte:
                        continue
                    eventos.append(ev)
        except FileNotFoundError:
            continue
        except OSError as e:
            print(f'[WARN] config_central: no se pudo leer la auditoría ({ruta}): {e}')
            continue
    eventos.sort(key=lambda ev: ev.get('fecha') or '')
    return [] if not limite else eventos[-limite:]
