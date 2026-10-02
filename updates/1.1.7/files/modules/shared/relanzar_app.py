# modules/shared/relanzar_app.py
# ============================================================
# RELANZADOR EXTERNO DE LA APP (proceso desprendido)
# ============================================================
# Lo lanza la app (modules/shared/relanzar.py) justo antes de terminar, tanto
# en el auto-reinicio posterior a una actualizacion como en /api/reiniciar.
#
# Vive en modules/shared/ y NO en scripts/ a proposito: `scripts/` esta excluido
# del canal de actualizaciones y el instalador tampoco lo copia, asi que un
# relanzador que viviera ahi no llegaba a ninguna instalacion (por eso el
# auto-reinicio posterior a una actualizacion nunca ocurria en la PC cliente).
# `modules/` si viaja: entra al manifiesto del canal y lo copia el instalador.
#
# Hace, en orden:
#   1. Espera a que el PID anterior desaparezca (o lo fuerza tras el timeout).
#   2. Libera el puerto si quedo un proceso zombie.
#   3. Limpia estado efimero: flask_session (para no arrastrar sesiones contra
#      codigo nuevo) y __pycache__ (para que no quede bytecode viejo).
#   4. Arranca la app con el MISMO mecanismo del instalador
#      (Iniciar_ADM-ERP.vbs). Si no esta, usa app.py directo sin consola.
#
# REGLA DE LAS DOS PASADAS DE LIMPIEZA (fix 1.1.4, incidente del 24/09/2026)
# -------------------------------------------------------------------------
# La sesion se borra ANTES de arrancar y NUNCA despues. El motivo es concreto:
# al arrancar, la app nueva crea su carpeta de sesiones (cachelib la crea en su
# `__init__`, `cachelib/file.py:78`, sobre `SESSION_FILE_DIR`), asi que una
# segunda pasada de limpieza DESPUES del arranque le borra la carpeta al proceso
# que esta corriendo. Desde ahi ninguna sesion se puede guardar y la app queda
# sin poder iniciar sesion: `POST /api/auth/login` responde 200 y el
# `GET /api/auth/current_user` inmediato responde 401, en bucle, con
# `FileNotFoundError: 'flask_session\tmpXXXX.__wz_cache'` por request.
#
# Eso es exactamente lo que paso en produccion al aplicarse 1.1.3 (m = 1, el log
# del incidente tiene DOS lineas "Limpiado: 9 carpeta(s) de cache/sesion", la
# segunda con la app ya escuchando en el puerto). Por eso la pasada posterior al
# arranque limpia SOLO `__pycache__` (`sesiones=False`) y el mensaje del log dice
# QUE borro, para que un diagnostico futuro no tenga que adivinar.
#
# Registrar en logs/relanzamientos.log para poder diagnosticar en la PC cliente.
# ============================================================

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time

VBS_ARRANQUE = 'Iniciar_ADM-ERP.vbs'
ESPERA_ARRANQUE_SEG = 45


def _ruta_resultado(install_dir):
    """Archivo donde el relanzador deja su veredicto.

    Va en ProgramData (NO en {app}, que se reescribe al actualizar) y junto al
    `update_status.json` que escribe la app. Así, cuando la app nueva arranca,
    puede leer si el reinicio salió bien y —si no— **avisar en pantalla** en vez
    de quedarse para siempre en "reiniciando". Eso fue exactamente lo que pasó el
    17/09/2026: la app no arrancaba y no había forma de verlo.
    """
    pdata = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
    return os.path.join(pdata, 'SidesysERP', 'relanzamiento_resultado.json')


def guardar_resultado(install_dir, ok, motivo, version=None, esperados=None):
    """Deja el veredicto del relanzamiento (best-effort, nunca lanza)."""
    try:
        import json
        ruta = _ruta_resultado(install_dir)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump({
                'ok': bool(ok),
                'motivo': motivo,
                'version': version,
                'esperados': esperados,
                'dir': install_dir,
                'timestamp': time.time(),
            }, f)
    except Exception as e:
        print(f'⚠️ no se pudo escribir el resultado del relanzamiento: {e}', flush=True)


def log(install_dir, mensaje):
    linea = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {mensaje}"
    # Se imprime SIEMPRE primero: si el archivo no se puede escribir (por ejemplo
    # porque el proceso padre cerró los handles al salir con os._exit), el error
    # no se pierde en silencio.
    print(linea, flush=True)
    try:
        logs = os.path.join(install_dir, 'logs')
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, 'relanzamientos.log'), 'a',
                  encoding='utf-8') as f:
            f.write(linea + '\n')
    except Exception as e:
        print(f'{linea} | ⚠️ no se pudo escribir el log: {e}', flush=True)


def pid_vivo(pid):
    """True si el proceso existe. En Windows usa tasklist (no requiere permisos)."""
    if pid <= 0:
        return False
    if os.name == 'nt':
        try:
            r = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                               capture_output=True, text=True, timeout=15)
            salida = (r.stdout or '').strip()
            return str(pid) in salida
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def esperar_salida(pid, timeout, install_dir):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not pid_vivo(pid):
            log(install_dir, f'PID {pid} termino tras {time.time() - t0:.1f}s')
            return True
        time.sleep(0.5)
    log(install_dir, f'PID {pid} sigue vivo tras {timeout}s: se fuerza el cierre')
    try:
        subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                       capture_output=True, timeout=20)
    except Exception as e:
        log(install_dir, f'No se pudo forzar el cierre: {e}')
    time.sleep(1.0)
    return False


def liberar_puerto(puerto, install_dir, pid_anterior=None, intentos=20):
    """Espera (y si hace falta libera) el puerto antes de arrancar la app nueva.

    El proceso anterior ya deberia haber terminado; esto cubre el caso de que el
    sistema tarde en liberar el socket. Si el puerto lo ocupa OTRO proceso, no se
    toca (matar procesos ajenos es peor que esperar).
    """
    for intento in range(intentos):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.6)
            if s.connect_ex(('127.0.0.1', puerto)) != 0:
                return True
        log(install_dir,
            f'Puerto {puerto} todavia ocupado (intento {intento + 1}/{intentos})')
        if os.name == 'nt':
            try:
                r = subprocess.run(
                    ['netstat', '-ano', '-p', 'TCP'], capture_output=True,
                    text=True, timeout=20)
                pids = set()
                for linea in (r.stdout or '').splitlines():
                    partes = linea.split()
                    if (len(partes) >= 5 and partes[3] == 'LISTENING'
                            and partes[1].endswith(f':{puerto}')):
                        pids.add(partes[4])
                for pid in pids:
                    if pid in ('0', str(os.getpid())):
                        continue
                    # No matar procesos ajenos al problema: si el PID que ocupa
                    # el puerto NO es el de la app anterior (por ejemplo, un
                    # visor/consumidor de ese puerto), matarlo no ayuda y puede
                    # romper otra cosa.
                    if pid_anterior and pid != str(pid_anterior):
                        log(install_dir, f'El puerto {puerto} lo ocupa el PID {pid}, '
                                         f'distinto del anterior ({pid_anterior}): '
                                         f'no se toca')
                        continue
                    log(install_dir, f'Cerrando proceso {pid} que ocupa el puerto')
                    subprocess.run(['taskkill', '/F', '/PID', pid],
                                   capture_output=True, timeout=20)
            except Exception as e:
                log(install_dir, f'No se pudo liberar el puerto: {e}')
        time.sleep(1.0)
    return False


def _borrar_con_reintentos(ruta, intentos=8, pausa=0.4):
    """Borra un directorio reintentando: en Windows el proceso recien terminado
    puede seguir reteniendo handles unos instantes (rmtree falla en silencio)."""
    for i in range(intentos):
        if not os.path.isdir(ruta):
            return True
        shutil.rmtree(ruta, ignore_errors=True)
        if not os.path.isdir(ruta):
            return True
        time.sleep(pausa)
    return not os.path.isdir(ruta)


def limpiar_estado(install_dir, log_fn, sesiones=True):
    """Borra estado efimero: sesiones de Flask y bytecode cacheado.

    `sesiones=False` borra SOLO `__pycache__` y NO toca `flask_session`. Es la
    forma que tiene la pasada POSTERIOR al arranque de no borrarle la carpeta de
    sesiones al proceso que ya esta corriendo (ver la regla de las dos pasadas en
    el docstring del modulo: es el fix del incidente de 1.1.3). La pasada PREVIA
    al arranque va con el valor por defecto (`sesiones=True`): ahi si tiene
    sentido, porque la app todavia no arranco y no se quieren arrastrar sesiones
    contra codigo nuevo.

    Es una LIMPIEZA de cortesia (Python ya invalida el bytecode por fecha del
    fuente): si algo queda tomado, no se considera un fallo del relanzado.

    OJO: NO se desciende en `python\\` (el runtime portatil de la instalacion).
    Ahi vive el PAQUETE `python\\Lib\\site-packages\\flask_session`, que no tiene
    nada que ver con la carpeta de sesiones de la app: al borrarlo, la app nueva
    moria al arrancar con `ImportError: cannot import name 'Session' from
    'flask_session'` y el reinicio posterior a una actualizacion dejaba al
    usuario sin aplicacion (es uno de los caminos que terminan en la
    "ADVERTENCIA: la app no respondio en el puerto" del propio relanzador).
    """
    cache = 0
    sesion = 0
    for root, dirs, files in os.walk(install_dir):
        for d in list(dirs):
            if d == '__pycache__':
                if _borrar_con_reintentos(os.path.join(root, d)):
                    cache += 1
            elif d == 'flask_session' and sesiones:
                if _borrar_con_reintentos(os.path.join(root, d)):
                    sesion += 1
        dirs[:] = [d for d in dirs
                   if d not in ('__pycache__', 'flask_session', 'logs',
                                'tesseract', 'data', 'python')]
    if cache or sesion:
        # El mensaje dice QUE se borro: el del incidente decia "cache/sesion" en
        # las dos pasadas y por eso el diagnostico tuvo que deducir cual de las
        # dos se habia llevado la carpeta de sesiones de la app viva.
        log_fn(f'Limpiado: {cache} carpeta(s) de __pycache__ y '
               f'{sesion} carpeta(s) de flask_session')
    else:
        log_fn('Nada que limpiar' + ('' if sesiones else ' (sesiones: no)'))


def arrancar(install_dir, puerto, log_fn, version=None):
    vbs = os.path.join(install_dir, VBS_ARRANQUE)
    if os.path.exists(vbs):
        log_fn(f'Arrancando con {VBS_ARRANQUE}')
        subprocess.Popen(['wscript.exe', vbs], cwd=install_dir, close_fds=True)
    else:
        # Sin .vbs: arrancar directo. Se prioriza el PYTHON PORTATIL de la
        # instalacion ({app}\python\), que es lo que lleva el instalador para no
        # depender de Python en la PC; si no esta, el interprete actual.
        exe = os.path.join(install_dir, 'python', 'pythonw.exe')
        if not os.path.exists(exe):
            exe = os.path.join(install_dir, 'python', 'python.exe')
        if not os.path.exists(exe):
            exe = sys.executable or 'python'
            pythonw = os.path.join(os.path.dirname(exe), 'pythonw.exe')
            if os.path.exists(pythonw):
                exe = pythonw
        log_fn(f'Sin {VBS_ARRANQUE}: arrancando {exe} app.py directo')
        flags = 0
        if os.name == 'nt':
            flags = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP
        with open(os.devnull, 'wb') as devnull:
            subprocess.Popen([exe, 'app.py'], cwd=install_dir,
                             stdin=devnull, stdout=devnull, stderr=devnull,
                             creationflags=flags, close_fds=True)

    # Verificar que levanto. Si no responde en el plazo, se deja constancia del
    # motivo en el archivo de resultado (antes solo iba al log, que podia no
    # escribirse y dejaba el reinicio sin explicacion).
    t0 = time.time()
    while time.time() - t0 < ESPERA_ARRANQUE_SEG:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.6)
            if s.connect_ex(('127.0.0.1', puerto)) == 0:
                segundos = time.time() - t0
                log_fn(f'App escuchando en el puerto {puerto} tras {segundos:.1f}s')
                # Segunda pasada de limpieza: el proceso viejo, al terminar,
                # puede haber reescrito __pycache__ despues de la primera.
                # `sesiones=False` es EL FIX de 1.1.4: la app nueva ya esta
                # arriba y ya creo su carpeta de sesiones; borrarsela en este
                # momento la dejaba sin poder guardar ninguna sesion (login 200 +
                # current_user 401 en bucle). El borrado de sesiones vive SOLO en
                # la pasada previa al arranque (`main()`).
                limpiar_estado(install_dir, log_fn, sesiones=False)
                guardar_resultado(install_dir, True,
                                  f'app escuchando en el puerto {puerto} '
                                  f'tras {segundos:.1f}s', version=version)
                return True
        time.sleep(1.0)

    motivo = (f'la app no respondio en el puerto {puerto} tras '
              f'{ESPERA_ARRANQUE_SEG}s. Revisá logs\\app.log y el Diagnóstico; '
              f'también se puede abrir a mano con el acceso directo.')
    log_fn('ADVERTENCIA: ' + motivo)
    guardar_resultado(install_dir, False, motivo, version=version)
    return False


def main():
    ap = argparse.ArgumentParser(description='Relanzador externo de ADM-ERP')
    ap.add_argument('--pid', type=int, required=True,
                    help='PID del proceso anterior que debe terminar')
    ap.add_argument('--install-dir', required=True)
    ap.add_argument('--puerto', type=int, default=5000)
    ap.add_argument('--espera', type=float, default=1.5,
                    help='Segundos a esperar antes de empezar a chequear el PID')
    ap.add_argument('--motivo', default='manual')
    ap.add_argument('--timeout-pid', type=float, default=30.0)
    ap.add_argument('--version', default=None,
                    help='Version a la que se esta actualizando (para el aviso)')
    args = ap.parse_args()

    install_dir = os.path.abspath(args.install_dir)
    log_fn = lambda m: log(install_dir, f'[{args.motivo}] {m}')

    log_fn(f'Relanzador iniciado (pid anterior={args.pid}, dir={install_dir}, '
           f'puerto={args.puerto}, version={args.version})')

    try:
        if args.espera > 0:
            time.sleep(args.espera)

        esperar_salida(args.pid, args.timeout_pid, install_dir)
        liberar_puerto(args.puerto, install_dir, pid_anterior=args.pid)
        # Pasada PREVIA al arranque: aca SI se borran las sesiones (la app nueva
        # todavia no arranco y no queremos arrastrar sesiones contra codigo
        # nuevo). Es la UNICA pasada que puede tocar `flask_session`.
        limpiar_estado(install_dir, log_fn, sesiones=True)
        ok = arrancar(install_dir, args.puerto, log_fn, version=args.version)
        return 0 if ok else 1
    except Exception as e:
        # Cualquier falla inesperada queda registrada: sin esto el reinicio se
        # quedaba sin explicacion y la app en "reiniciando" para siempre.
        import traceback
        motivo = f'error inesperado del relanzador: {type(e).__name__}: {e}'
        log_fn(motivo)
        log_fn(traceback.format_exc())
        guardar_resultado(install_dir, False, motivo, version=args.version)
        return 1


if __name__ == '__main__':
    # `main()` ya registra su propio resultado; este try/except cubre fallas al
    # parsear argumentos o cualquier cosa anterior a tener `install_dir`.
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f'Error en el relanzador: {type(e).__name__}: {e}', flush=True)
        sys.exit(1)
