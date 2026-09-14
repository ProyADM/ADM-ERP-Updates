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
#     lanzar_relanzador(motivo='actualizacion')
# ============================================================

import os
import subprocess
import sys

VBS_ARRANQUE = 'Iniciar_ADM-ERP.vbs'


def _pythonw() -> str:
    """pythonw.exe (sin consola) si existe; si no, el interprete actual."""
    exe = sys.executable or 'python'
    candidato = os.path.join(os.path.dirname(exe), 'pythonw.exe')
    return candidato if os.path.exists(candidato) else exe


def lanzar_relanzador(install_dir: str, puerto: int = 5000, espera: float = 1.5,
                      motivo: str = 'manual'):
    """Lanza el relanzador desprendido. Devuelve (ok, detalle).

    No mata el proceso actual: de eso se encarga el propio relanzador (espera a
    que este PID desaparezca). El llamador debe terminar el proceso despues de
    invocar esta funcion.
    """
    script = os.path.join(install_dir, 'scripts', 'relanzar_app.py')
    if not os.path.exists(script):
        return False, f'no existe {script}'

    flags = 0
    if os.name == 'nt':
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

    cmd = [
        _pythonw(), script,
        '--pid', str(os.getpid()),
        '--install-dir', install_dir,
        '--puerto', str(puerto),
        '--espera', str(espera),
        '--motivo', motivo,
    ]

    try:
        with open(os.devnull, 'wb') as devnull:
            subprocess.Popen(
                cmd,
                cwd=install_dir,
                stdin=devnull,
                stdout=devnull,
                stderr=devnull,
                creationflags=flags,
                close_fds=True,
            )
        return True, 'relanzador lanzado'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'
