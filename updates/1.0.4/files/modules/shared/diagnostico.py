# modules/shared/diagnostico.py
# ============================================================
# DIAGNÓSTICO DEL SISTEMA (vista "🩺 Diagnóstico" del panel)
# ============================================================
# Responde "¿por qué no anda / no actualiza?" con dos capas:
#
#   1. CHEQUEOS EN VIVO: ¿el servidor SQL responde en cada base? ¿el canal de
#      actualizaciones se puede consultar y su firma valida? ¿de dónde lee esta
#      PC los usuarios? ¿queda espacio en disco?
#   2. ERRORES RECIENTES: qué se quejó la app últimamente, leído de `logs/app.log`
#      (que ya rota solo: 2 MB × 3 backups = 8 MB como máximo).
#
# Todo es SOLO LECTURA. Los detalles técnicos que hoy solo existen en el log
# (por ejemplo el error real de pyodbc, que `database.py` esconde a propósito en
# la respuesta al cliente) se muestran acá para el administrador.
#
# ⚠️ NO se devuelven cadenas de conexión, usuarios ni contraseñas de SQL: de
#    pyodbc se informa la CLASE de error (timeout, login, driver) y su mensaje.
#
# ⚠️ APRENDIZAJE DEL ENTORNO (16-17/09/2026): DOS comprobaciones de este módulo
#    dan FALSO POSITIVO si se corren DENTRO del sandbox del asistente:
#      1. la conexión ODBC falla con "Error de seguridad de SSL (18)" en TODAS
#         las bases, y
#      2. la escritura en la carpeta del almacén falla con "Acceso denegado"
#         (lo que además hace que `config_central` informe modo `degradado`).
#    Fuera del sandbox, con la MISMA carpeta y el mismo proceso: SQL conecta,
#    `carpeta_utilizable` da True y el modo es `central`.
#    El bloque SQL y el de permisos SOLO son válidos cuando los pide el servidor
#    real (la app, fuera del sandbox), no en una corrida de prueba.

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# Cuántas líneas del log se leen por pedido. Es un tope de trabajo, no de
# exactitud: 4000 líneas cubren de sobra una sesión de diagnóstico y evitan que
# un log grande haga lento el panel.
MAX_LINEAS_LOG = 4000
MAX_BYTES_COLA = 2 * 1024 * 1024          # 2 MB: se lee el final, no el archivo entero
MAX_ERRORES_DEVUELTOS = 40                # grupos distintos que se muestran
MAX_LARGO_MENSAJE = 1500                  # recorte defensivo por mensaje
MAX_LARGO_DETALLE = 4000                  # detalle técnico copiable
ESPERA_SQL_SEG = 6                        # timeout de conexión por base
ESPERA_MAX_CHEQUEOS_SEG = 20              # tope total de la tanda de sondas

_SEV_ORDEN = {'ERROR': 0, 'CRITICAL': 0, 'WARNING': 1, 'INFO': 2}

# El formato lo fija `_configurar_logging()` en app.py:
#   2026-09-16 18:08:51 [ERROR] modules.shared.database: [SQL ERROR de conexión] ...
_RE_NIVEL = re.compile(
    r'^(?P<fecha>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+'
    r'\[(?P<nivel>[A-Z]+)\]\s+'
    r'(?P<logger>[^:]+):\s?(?P<msg>.*)$'
)
_RE_GRUPO = re.compile(r'([A-Za-z_][A-Za-z0-9_.]*):')


# ============================================================
# UBICACIONES
# ============================================================

def carpeta_logs():
    """`<app>/logs`, la misma que usa `_configurar_logging()`."""
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(raiz, 'logs')


def archivos_log():
    """Los log existentes, del más NUEVO al más viejo (incluye los rotados)."""
    carpeta = carpeta_logs()
    candidatos = []
    try:
        for nombre in os.listdir(carpeta):
            if nombre == 'app.log' or (nombre.startswith('app.log.') and nombre[8:].isdigit()):
                ruta = os.path.join(carpeta, nombre)
                if os.path.isfile(ruta):
                    candidatos.append(ruta)
    except OSError:
        return []

    def sufijo(ruta):
        cola = os.path.basename(ruta)[len('app.log'):]
        return int(cola[1:]) if cola.startswith('.') and cola[1:].isdigit() else -1

    return sorted(candidatos, key=sufijo)


# ============================================================
# LECTURA DEL LOG
# ============================================================

def _cola_texto(ruta, max_bytes=MAX_BYTES_COLA):
    """Últimos `max_bytes` del archivo, decodificados con tolerancia.

    Se lee la cola y no el archivo completo: es un log rotado, pero puede tener
    megabytes y el panel tiene que responder rápido.
    """
    try:
        with open(ruta, 'rb') as f:
            f.seek(0, os.SEEK_END)
            tamano = f.tell()
            desde = max(0, tamano - max_bytes)
            f.seek(desde)
            datos = f.read()
        texto = datos.decode('utf-8', errors='replace')
        if desde > 0:
            # La primera línea puede haber quedado cortada al medio.
            corte = texto.find('\n')
            if corte >= 0:
                texto = texto[corte + 1:]
        return texto
    except OSError:
        return ''


def leer_lineas_log(max_lineas=MAX_LINEAS_LOG, archivo=None):
    """Últimas `max_lineas` líneas del log (o de un archivo puntual).

    Devuelve una lista de `{linea, nivel, fecha, logger, mensaje}`; las líneas sin
    cabecera reconocible (los tracebacks) se adjuntan a la entrada anterior como
    continuación, para que el detalle técnico no pierda el stack.
    """
    rutas = [archivo] if archivo else archivos_log()
    if not rutas:
        return []

    # Se completa desde el más nuevo hacia atrás hasta juntar las líneas pedidas.
    lineas = []
    for ruta in rutas:
        texto = _cola_texto(ruta)
        if not texto:
            continue
        lineas = texto.splitlines() + lineas
        if len(lineas) >= max_lineas:
            break
    lineas = lineas[-max_lineas:]

    entradas = []
    for linea in lineas:
        m = _RE_NIVEL.match(linea)
        if m:
            entradas.append({
                'linea': linea,
                'fecha': m.group('fecha'),
                'nivel': m.group('nivel'),
                'logger': m.group('logger').strip(),
                'mensaje': m.group('msg').strip(),
            })
        elif entradas:
            # Continuación (traceback): se pega al mensaje de la entrada anterior.
            entradas[-1]['linea'] += '\n' + linea
            if len(entradas[-1]['mensaje']) < MAX_LARGO_MENSAJE:
                entradas[-1]['mensaje'] = (entradas[-1]['mensaje'] + '\n' +
                                           linea.strip())[:MAX_LARGO_MENSAJE]
    return entradas


# ============================================================
# AGRUPACIÓN DE ERRORES
# ============================================================

def _categoria(entrada):
    """Etiqueta legible del problema: `[SQL ERROR de conexión] reportes_db` → SQL ERROR…"""
    msg = entrada.get('mensaje') or ''
    corchete = msg.find(']')
    if msg.startswith('[') and corchete > 0 and corchete < 80:
        return msg[1:corchete].strip()
    m = _RE_GRUPO.search(msg)
    if m:
        return m.group(1).strip()
    logger = (entrada.get('logger') or '').split('.')[-1]
    return logger or 'General'


def _clave_grupo(entrada):
    """Clave de agrupación: categoría + la parte estable del mensaje.

    Los números, rutas y valores variables se normalizan para que el mismo error
    caiga siempre en el mismo grupo (si no, cada intento sería un grupo nuevo).
    """
    msg = entrada.get('mensaje') or ''
    normal = re.sub(r'\d+', '#', msg.splitlines()[0])
    normal = re.sub(r'\s+', ' ', normal).strip()[:120]
    return _categoria(entrada) + '|' + normal


def errores_agrupados(entradas, horas=24, min_veces=1):
    """Agrupa los ERROR/WARNING de las últimas `horas`, del más frecuente al más viejo."""
    limite = datetime.now() - timedelta(hours=max(1, int(horas)))
    grupos = {}

    for e in entradas:
        nivel = (e.get('nivel') or '').upper()
        if nivel not in ('ERROR', 'CRITICAL', 'WARNING'):
            continue
        try:
            cuando = datetime.strptime(e.get('fecha') or '', '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        if cuando < limite:
            continue

        clave = _clave_grupo(e)
        g = grupos.get(clave)
        if g is None:
            g = {
                'categoria': _categoria(e),
                'nivel': nivel,
                'mensaje': (e.get('mensaje') or '')[:MAX_LARGO_MENSAJE],
                'logger': e.get('logger'),
                'veces': 0,
                'primera': e.get('fecha'),
                'ultima': e.get('fecha'),
                'detalle': '',
            }
            grupos[clave] = g
        g['veces'] += 1
        g['ultima'] = e.get('fecha')
        if len(g['detalle']) < MAX_LARGO_DETALLE:
            g['detalle'] = (g['detalle'] + e.get('linea', '') + '\n')[:MAX_LARGO_DETALLE]
        # El nivel más grave manda: un error nunca queda tapado por un warning.
        if _SEV_ORDEN.get(nivel, 9) < _SEV_ORDEN.get(g['nivel'], 9):
            g['nivel'] = nivel

    lista = [g for g in grupos.values() if g['veces'] >= max(1, int(min_veces))]
    lista.sort(key=lambda g: (g['ultima'] or ''), reverse=True)
    lista.sort(key=lambda g: g['veces'], reverse=True)
    return lista[:MAX_ERRORES_DEVUELTOS]


# ============================================================
# CHEQUEOS EN VIVO
# ============================================================

def _clasificar_error_sql(e):
    """Traduce el error crudo de pyodbc a una causa probable, SIN datos sensibles."""
    texto = '%s' % (e,)
    bajo = texto.lower()
    try:
        import pyodbc
        if isinstance(e, pyodbc.InterfaceError) or 'data source name not found' in bajo \
                or 'driver' in bajo and 'not found' in bajo:
            return 'driver ODBC', texto[:400]
        if isinstance(e, pyodbc.OperationalError):
            if 'timeout' in bajo or 'hyt00' in bajo or 'hyt01' in bajo:
                return 'timeout (red/VPN o servidor saturado)', texto[:400]
            if 'login failed' in bajo or '18456' in bajo:
                return 'credenciales rechazadas', texto[:400]
            if 'ssl' in bajo or 'encrypt' in bajo:
                return 'TLS/cifrado (driver sin soporte de Encrypt)', texto[:400]
            return 'conexión (red/VPN, servidor caído o instancia)', texto[:400]
    except ImportError:
        pass
    if 'timeout' in bajo:
        return 'timeout', texto[:400]
    return 'inesperado', texto[:400]


def _probar_base(base, espera):
    """`SELECT 1` con timeout corto, reportando la CAUSA REAL de la falla.

    Se conecta directo con pyodbc en vez de usar `run_sql` por un motivo concreto:
    la app convierte cualquier falla de conexión en un genérico "Error de conexión
    a la base de datos" (`database.py:177`) y manda el detalle de pyodbc SOLO al
    log. Para diagnosticar hace falta ese detalle, así que acá se captura el error
    crudo y se CLASIFICA: red/timeout, credenciales, driver o TLS.

    Nunca se devuelven usuario ni contraseña: solo el servidor y la clase de error.
    """
    inicio = time.time()
    try:
        from config import BASES_DISPONIBLES, SQL_ENCRYPT_ACTIVO
    except Exception as e:
        return {'base': base, 'etiqueta': base, 'ok': False, 'ms': 0,
                'causa': 'no se pudo leer la configuración', 'detalle': '%s' % e}

    cfg = BASES_DISPONIBLES.get(base) or {}
    servidor = cfg.get('server') or ''
    etiqueta = cfg.get('sigla') or cfg.get('label') or base

    resultado = {'base': base, 'etiqueta': etiqueta, 'servidor': servidor}
    conexion = None
    try:
        import pyodbc
        cadena = (
            'DRIVER={SQL Server};'
            'SERVER=%s;' % servidor +
            'DATABASE=%s;' % base +
            'UID=%s;' % (cfg.get('user') or '') +
            'PWD=%s;' % (cfg.get('password') or '') +
            'TrustServerCertificate=yes;' +
            ('Encrypt=yes;' if SQL_ENCRYPT_ACTIVO else '')
        )
        conexion = pyodbc.connect(cadena, timeout=espera)
        cursor = conexion.cursor()
        cursor.execute('SELECT 1 AS ok')
        cursor.fetchall()
        resultado.update({'ok': True, 'ms': int((time.time() - inicio) * 1000)})
    except Exception as e:
        causa, detalle = _clasificar_error_sql(e)
        resultado.update({'ok': False, 'ms': int((time.time() - inicio) * 1000),
                          'causa': causa, 'detalle': detalle})
    finally:
        if conexion is not None:
            try:
                conexion.close()
            except Exception:
                pass
    resultado.setdefault('ms', int((time.time() - inicio) * 1000))
    return resultado


def probar_bases(bases, espera=ESPERA_SQL_SEG, paralelo=6):
    """Prueba varias bases EN PARALELO: en serie, 11 bases × 6 s = 66 s de espera."""
    resultados = []
    if not bases:
        return resultados
    # `shutdown(wait=False)` para que un cuelgue de una sonda no retenga el
    # request: el tope de tiempo manda y lo que falte se informa como timeout.
    pool = ThreadPoolExecutor(max_workers=max(1, min(paralelo, len(bases))))
    try:
        futuros = {pool.submit(_probar_base, b, espera): b for b in bases}
        try:
            for futuro in as_completed(futuros, timeout=ESPERA_MAX_CHEQUEOS_SEG):
                resultados.append(futuro.result())
        except Exception:
            # Lo que no llegó a tiempo se informa como timeout, no se omite.
            hechos = {r['base'] for r in resultados}
            for base in futuros.values():
                if base not in hechos:
                    resultados.append({'base': base, 'ok': False, 'ms': None,
                                       'causa': 'timeout del chequeo', 'detalle': ''})
    finally:
        pool.shutdown(wait=False)
    orden = {b: i for i, b in enumerate(bases)}
    resultados.sort(key=lambda r: orden.get(r['base'], 999))
    return resultados


def estado_permisos_carpeta(rutas):
    """¿Se puede ESCRIBIR de verdad en cada carpeta? Y si no, por qué.

    Es el chequeo que faltaba: el 16/09/2026 la carpeta del almacén quedó de solo
    lectura en OneDrive (una regla de DENEGACIÓN de `DeleteSubdirectoriesAndFiles`
    heredada desde `Sidesys`). La app lo detecta —`carpeta_utilizable` da False y el
    panel queda en modo `degradado`, sin poder guardar— pero el motivo no se veía
    en ningún lado. Acá se prueba la operación REAL (crear un `.tmp` y renombrarlo
    con `os.replace`, que es exactamente lo que hace `escribir_atomico`) y se
    informa el atributo de la carpeta y las reglas de DENEGACIÓN que la afectan.
    """
    salida = []
    for etiqueta, ruta in rutas:
        if not ruta:
            continue
        item = {'etiqueta': etiqueta, 'ruta': ruta}
        if not os.path.isdir(ruta):
            item.update({'ok': False, 'motivo': 'la carpeta no existe'})
            salida.append(item)
            continue

        prueba_tmp = os.path.join(ruta, '.diagnostico_prueba.tmp')
        prueba_final = os.path.join(ruta, '.diagnostico_prueba.json')
        estado = None
        try:
            with open(prueba_tmp, 'w', encoding='utf-8') as f:
                f.write('{}')
            os.replace(prueba_tmp, prueba_final)
            estado = (True, 'pudo crear y renombrar un archivo de prueba')
        except OSError as e:
            estado = (False, '%s (errno %s)' % (e.strerror or e, e.errno))
        finally:
            # Limpieza best-effort: con la carpeta bloqueada el borrado también
            # falla, y ahí se avisa que puede quedar un residuo.
            try:
                if os.path.exists(prueba_tmp):
                    os.remove(prueba_tmp)
                if os.path.exists(prueba_final):
                    os.remove(prueba_final)
                item['residuo'] = False
            except OSError:
                item['residuo'] = os.path.exists(prueba_tmp) or os.path.exists(prueba_final)

        item['ok'] = estado[0]
        item['motivo'] = estado[1]
        if not estado[0]:
            item['causas'] = _causas_escritura(ruta)
        salida.append(item)
    return salida


def _causas_escritura(ruta):
    """Pistas de por qué no se puede escribir: atributos y DENYs de la ACL."""
    pistas = []
    try:
        import stat
        attrs = os.stat(ruta).st_file_attributes
        if attrs & stat.FILE_ATTRIBUTE_READONLY:
            pistas.append('la carpeta tiene el atributo "solo lectura"')
    except Exception:
        pass
    try:
        import subprocess
        # Se pregunta por TODAS las reglas de denegación que alcanzan la carpeta
        # (incluidas las heredadas de las carpetas superiores).
        cmd = ['powershell', '-NoProfile', '-Command',
               "(Get-Acl -LiteralPath '%s').Access | "
               "Where-Object { $_.AccessControlType -eq 'Deny' } | "
               "ForEach-Object { $_.IdentityReference.ToString() + ' -> ' + "
               "$_.FileSystemRights.ToString() + $(if ($_.IsInherited) { ' (heredada)' } "
               "else { ' (propia)' }) }" % ruta]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15,
                              encoding='utf-8', errors='replace')
        for linea in (proc.stdout or '').splitlines():
            texto = linea.strip()
            if texto:
                pistas.append('regla de DENEGACIÓN: ' + texto)
    except Exception as e:
        pistas.append('no se pudieron leer los permisos: %s' % e)
    if not pistas:
        pistas.append('no se identificó la causa; probar con permisos de administrador')
    return pistas


def estado_disco(rutas):
    """Espacio libre en las rutas relevantes (la instalación y el almacén)."""
    salida = []
    vistas = set()
    for etiqueta, ruta in rutas:
        if not ruta:
            continue
        destino = ruta if os.path.isdir(ruta) else os.path.dirname(ruta)
        if not destino or destino in vistas:
            continue
        vistas.add(destino)
        try:
            uso = os.statvfs(destino) if hasattr(os, 'statvfs') else None
            if uso is None:
                import shutil
                total, usado, libre = shutil.disk_usage(destino)
            else:
                total = uso.f_blocks * uso.f_frsize
                libre = uso.f_bavail * uso.f_frsize
                usado = total - libre
            salida.append({
                'etiqueta': etiqueta,
                'ruta': destino,
                'libre_mb': int(libre / (1024 * 1024)),
                'total_mb': int(total / (1024 * 1024)),
                'libre_pct': int(round(100.0 * libre / total)) if total else None,
            })
        except Exception as e:
            salida.append({'etiqueta': etiqueta, 'ruta': destino, 'error': str(e)[:200]})
    return salida


def estado_canal_actualizaciones():
    """¿Se puede consultar el canal firmado y qué dice? Nunca lanza.

    Incluye la version INSTALADA (`version.txt` de ProgramData, la marca real de
    lo que corre esta PC): así el panel responde "¿está al día?" sin tener que
    abrir archivos a mano.
    """
    try:
        from app import check_actualizaciones, _CANAL
    except Exception as e:
        return {'ok': False, 'motivo': 'no se pudo importar el updater: %s' % e}

    version_instalada = None
    try:
        from app import obtener_version_actual
        version_instalada = obtener_version_actual()
    except Exception:
        pass

    try:
        hay, info = check_actualizaciones()
        if hay and info:
            return {'ok': True, 'canal': _CANAL, 'hay_novedad': True,
                    'version_instalada': version_instalada,
                    'version_remota': info.get('version'),
                    'release_date': info.get('release_date'),
                    'aviso': info.get('aviso_version_minima')}
        return {'ok': True, 'canal': _CANAL, 'hay_novedad': False,
                'version_instalada': version_instalada}
    except Exception as e:
        return {'ok': False, 'canal': _CANAL,
                'version_instalada': version_instalada, 'motivo': '%s' % e}


def estado_almacen():
    """Modo del almacén de usuarios/permisos de esta PC (central/local/degradado)."""
    try:
        from . import config_central
        est = config_central.estado() or {}
        return {'modo': est.get('modo'), 'accesible': est.get('accesible'),
                'ruta': est.get('ruta'), 'sello': est.get('sello'),
                'escritor': est.get('escritor'),
                'ultima_escritura': est.get('ultima_escritura'),
                'mensaje': est.get('mensaje')}
    except Exception as e:
        return {'modo': 'desconocido', 'mensaje': 'no se pudo consultar el almacén: %s' % e}


def resumen_alerta(horas=72, desde=None):
    """Insignia de la pestaña Diagnóstico: cuántos problemas hay para mirar.

    Es LIVIANO a propósito (solo lee el log; no sondea el SQL ni el canal de
    actualizaciones): lo consulta el panel cada pocos minutos para el contador
    del menú lateral.

    `desde` (ISO 'YYYY-MM-DDTHH:MM:SS' o 'YYYY-MM-DD HH:MM:SS') es la marca de la
    última vez que esa PC abrió la pestaña: así el contador cuenta solo lo NUEVO
    y se limpia cuando el administrador entra a mirar. Cuenta GRUPOS de error, no
    líneas: un error repetido 23 veces es UN problema.
    """
    entradas = leer_lineas_log()
    limite = datetime.now() - timedelta(hours=max(1, int(horas)))
    grupos = errores_agrupados(entradas, horas=max(1, int(horas)))

    momento_desde = None
    if desde:
        for formato in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
            try:
                momento_desde = datetime.strptime(desde.strip()[:19], formato)
                break
            except (ValueError, AttributeError):
                continue

    nuevos = 0
    for g in grupos:
        try:
            ultima = datetime.strptime(g.get('ultima') or '', '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        if ultima < limite:
            continue
        if momento_desde is None or ultima > momento_desde:
            nuevos += 1

    graves = sum(1 for g in grupos if (g.get('nivel') or '') in ('ERROR', 'CRITICAL'))
    return {
        'generado': datetime.now().isoformat(timespec='seconds'),
        'desde': desde,
        'horas': max(1, int(horas)),
        'nuevos': nuevos,
        'total': len(grupos),
        'graves': graves,
        'fuente': 'log',
    }


def informe(bases=None, horas=24):
    """Informe completo del panel: chequeos en vivo + errores recientes."""
    bases = list(bases or [])
    entradas = leer_lineas_log()

    informe_sql = probar_bases(bases)
    caidas = [r for r in informe_sql if not r.get('ok')]

    almacen = estado_almacen()
    raiz_app = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rutas = [
        ('Instalación', raiz_app),
        ('Almacén de usuarios', almacen.get('ruta')),
    ]

    return {
        'generado': datetime.now().isoformat(timespec='seconds'),
        'sql': {
            'bases': informe_sql,
            'total': len(informe_sql),
            'caidas': len(caidas),
        },
        'canal': estado_canal_actualizaciones(),
        'almacen': almacen,
        'permisos': estado_permisos_carpeta(rutas),
        'disco': estado_disco(rutas),
        'errores': errores_agrupados(entradas, horas=horas),
        'log': {
            'archivos': [os.path.basename(r) for r in archivos_log()],
            'lineas_leidas': len(entradas),
        },
    }
