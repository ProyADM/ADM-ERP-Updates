# modules/shared/relanzar.py
# ============================================================
# RELANZADO DE LA APP (auto-reinicio tras una actualizacion)
# ============================================================
# Por que existe este modulo:
#   Reiniciar la app desde dentro del propio proceso NO funciona de forma
#   confiable: el hijo queda atado al arbol de procesos del padre (y en Windows
#   muere con el), y si el cwd es el de un modulo, config.py no encuentra
#   .env.local y el proceso nuevo aborta al arrancar.
#
# La forma robusta es lanzar un proceso DESPRENDIDO (nueva sesion / detached)
# que: espera a que el PID actual muera, limpia estado efimero y arranca la app
# con el MISMO mecanismo que usa el instalador (Iniciar_ADM-ERP.vbs, que ya
# contempla "ya hay un app.py corriendo" y abre el navegador).
#
# Uso desde app.py:
#     from modules.shared.relanzar import lanzar_relanzador
#     lanzar_relanzador(install_dir, app_dir=raiz_de_la_app_que_corre,
#                       motivo='actualizacion')
#
# DOS RAICES DISTINTAS, CON ROLES DISTINTOS:
#   `install_dir` = a donde el updater ESCRIBIO los archivos (sale del
#       registro). Es la app que tiene que volver: el relanzador arranca ESA
#       raiz y limpia el `__pycache__`/`flask_session` de ESA raiz. Es el
#       `--install-dir` y el `cwd` del proceso desprendido.
#   `app_dir` = la raiz de la app EN EJECUCION. Se usa SOLO para BUSCAR el
#       script del relanzador (su `modules/shared/relanzar_app.py` es el codigo
#       que conoce este arbol), no para decidir que app reiniciar.
#
# EL RELANZADOR TIENE QUE ESTAR EN UN ARBOL QUE VIAJE AL CLIENTE:
#   vivia en `scripts/relanzar_app.py`, pero `scripts/` esta excluido del canal
#   (publicar_release.py) y el instalador tampoco lo copia: en una instalacion
#   real ese archivo NO EXISTE, asi que el auto-reinicio posterior a una
#   actualizacion fallaba en silencio y la app nueva solo corria si alguien
#   reiniciaba a mano. Ahora vive en `modules/shared/relanzar_app.py` (que si
#   viaja) y se resuelve con `resolver_relanzador`.
# ============================================================

import os
import subprocess
import sys

VBS_ARRANQUE = 'Iniciar_ADM-ERP.vbs'
RELANZADOR_NOMBRE = 'relanzar_app.py'

# Raiz de la app que corre, derivada de este archivo:
#   <raiz>/modules/shared/relanzar.py -> tres niveles arriba. Es el default de
#   `app_dir` en las funciones de abajo; app.py le pasa la suya (la calcula de
#   su propio `__file__`) para que quede explicito y no dependa de como se
#   importo este modulo.
_APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def candidatos_relanzador(app_dir, install_dir, nombre=RELANZADOR_NOMBRE):
    """Rutas donde puede estar el script del relanzador, en orden de preferencia:
      1. `<app_dir>/modules/shared/relanzar_app.py`
      2. `<install_dir>/modules/shared/relanzar_app.py`
      3. `<install_dir>/scripts/relanzar_app.py`      (compatibilidad)

    El 1 va primero porque es el script del arbol que esta corriendo: es el
    codigo que conoce este arbol (el que viaja con el canal). En un cliente las
    dos raices coinciden.

    OJO: esta funcion NO decide que app hay que reiniciar. Eso lo decide el
    updater con `install_dir` (ver `lanzar_relanzador`). Aca solo se elige QUE
    SCRIPT ejecutar.

    Es PURA: no toca el disco salvo `os.path.join`.
    """
    return [
        os.path.join(app_dir, 'modules', 'shared', nombre),
        os.path.join(install_dir, 'modules', 'shared', nombre),
        os.path.join(install_dir, 'scripts', nombre),
    ]


def resolver_relanzador(app_dir, install_dir, existe=None):
    """Elige el script del relanzador a ejecutar: `(script, detalle)`.

    Gana el PRIMERO que existe (ver `candidatos_relanzador`). Si no existe
    ninguno, `script` es None y `detalle` enumera TODAS las rutas probadas: es
    lo que termina en el estado de la actualizacion y en el log, asi el proximo
    diagnostico dice *por que* no se pudo reiniciar en vez de dejar solo un
    "no existe <ruta>".

    Devuelve SOLO el script: la raiz que hay que reiniciar no sale de aca (sale
    del updater, `install_dir`). Ver el comentario de `lanzar_relanzador`.
    """
    if existe is None:
        existe = os.path.exists
    probadas = candidatos_relanzador(app_dir, install_dir)
    for script in probadas:
        if existe(script):
            return script, f'encontrado {script}'
    detalle = ('no existe el relanzador en ninguna de estas rutas: '
               + '; '.join(probadas))
    return None, detalle


def _pythonw() -> str:
    """pythonw.exe (sin consola) si existe; si no, el interprete actual."""
    exe = sys.executable or 'python'
    candidato = os.path.join(os.path.dirname(exe), 'pythonw.exe')
    return candidato if os.path.exists(candidato) else exe


def lanzar_relanzador(install_dir: str, puerto: int = 5000, espera: float = 1.5,
                      motivo: str = 'manual', version: str = None,
                      app_dir: str = None, existe=None, popen=None):
    r"""Lanza el relanzador desprendido. Devuelve (ok, detalle).

    No mata el proceso actual: de eso se encarga el propio relanzador (espera a
    que este PID desaparezca). El llamador debe terminar el proceso despues de
    invocar esta funcion.

    `version` es la version a la que se esta actualizando: el relanzador la deja
    en su archivo de resultado, para que el aviso al usuario diga a cual.

    `install_dir` es la raiz que dice el updater (el destino de los ARCHIVOS,
    que sale del registro) y es SIEMPRE la que se reinicia: `--install-dir` y el
    `cwd` del proceso desprendido. Es la app que el updater acaba de actualizar,
    asi que es la que tiene que volver (y de la que hay que limpiar
    `__pycache__`/`flask_session`).

    `app_dir` es la raiz de la app EN EJECUCION y se usa SOLO para buscar el
    script (el del arbol que corre primero). Default: la raiz derivada de este
    archivo.

    POR QUE NO SE USA LA RAIZ DEL SCRIPT (esto estaba mal antes):
    la version anterior pasaba como `--install-dir` la raiz del script elegido.
    Eso conflaciona "donde esta el script" con "que app hay que reiniciar" y se
    rompe cuando el proceso que aplica la actualizacion NO es el del arbol
    destino. Caso real medido (E2E del usuario, 23/09/2026): el disparo importo
    `app.py` del ARBOL DE DESARROLLO (el runtime portatil tiene un
    `python313._pth` con la linea `..`, que le agrega ese directorio al
    `sys.path` y hace que gane su `app.py` sobre el del cwd), asi que `app_dir`
    era el arbol de desarrollo, el relanzador arranco ahi (log en
    `AppUnificado\logs\relanzamientos.log`) y la app actualizada -la del cliente-
    nunca volvio. Que app tiene que volver no depende de quien importo el modulo:
    depende de donde se escribieron los archivos.

    `existe` y `popen` existen para poder testear sin tocar el disco ni lanzar
    procesos reales.
    """
    if app_dir is None:
        app_dir = _APP_DIR
    script, detalle = resolver_relanzador(app_dir, install_dir, existe)
    if script is None:
        return False, detalle

    flags = 0
    if os.name == 'nt':
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

    cmd = [
        _pythonw(), script,
        '--pid', str(os.getpid()),
        # SIEMPRE la raiz del updater: es la app que se acaba de actualizar, la
        # que tiene que volver y de la que hay que limpiar el estado efimero.
        '--install-dir', install_dir,
        '--puerto', str(puerto),
        '--espera', str(espera),
        '--motivo', motivo,
    ]
    if version:
        cmd += ['--version', str(version)]

    if popen is None:
        popen = subprocess.Popen
    try:
        with open(os.devnull, 'wb') as devnull:
            popen(
                cmd,
                # El cwd tambien es la raiz del updater: el relanzador arranca
                # `app.py` de ahi (y si el cwd fuera el arbol que corre, el
                # proceso nuevo no encontraria el `app.py` actualizado).
                cwd=install_dir,
                stdin=devnull,
                stdout=devnull,
                stderr=devnull,
                creationflags=flags,
                close_fds=True,
            )
        return True, f'relanzador lanzado ({script})'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'
