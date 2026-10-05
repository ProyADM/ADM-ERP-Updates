# modules/shared/update_respaldo.py
# ============================================================
# RESPALDO DEL UPDATER: QUE SE COPIA ANTES DE PISAR UN ARCHIVO
# ============================================================
# `instalar_actualizacion_diferencial` (app.py) respalda la instalacion ANTES de
# copiar los archivos nuevos: si algo sale mal, `restaurar_backup()` vuelve atras.
#
# POR QUE VIVE ACA Y NO EN app.py:
#   - es stdlib puro (`os`/`shutil`), asi que se testea sin app, sin config y sin
#     red (mismo criterio que `update_politica.py` y `update_firma.py`);
#   - viaja por el canal (`modules/shared/`) como el resto de la logica del updater.
#
# QUE SE RESPALDA (medido el 03/10/2026): SOLO lo que el canal puede cambiar. El
# respaldo anterior recorria el arbol ENTERO y copiaba, entre otras cosas, todo lo
# publicable que hay bajo `python\` -- **3.400 archivos** medidos en el clon del E2E,
# cuyo `python\` es la copia del runtime real del proyecto (176 MB) -- en CADA
# actualizacion, contra **102** del respaldo nuevo (34x menos). Y el canal NUNCA toca
# `python\` (lo instala el .exe: es el invariante del esquema de actualizaciones).
# Ademas de inutil y lento, ese recorrido es el candidato mas firme al `WinError 3`
# del pendiente (recorrer site-packages mientras algo se mueve, con rutas largas).
import os
import shutil

# Extensiones que el canal puede publicar (`scripts/publicar_release.py`,
# `EXTENSIONES`). El respaldo tiene que cubrir EXACTAMENTE eso: si el canal puede
# pisar un archivo, tiene que poder restaurarlo. OJO: `VERSION` (sin extension) NO
# viaja por el canal --verificado contra el `manifest.json` publicado--; la verdad
# de version en runtime es `version.txt` de PROGRAMDATA, que escribe el updater.
# Hay un test que compara las dos tuplas (`tests/test_updater_respaldo.py`): si una
# cambia sin la otra, se pone rojo.
EXTENSIONES_RESPALDO = ('.py', '.js', '.css', '.html', '.json', '.txt', '.vbs')

# Carpetas que NO se respaldan:
#   python/        runtime portatil: lo instala el .exe, el canal no lo toca
#   tesseract/     idem (OCR)
#   logs/          crece solo; no es codigo de la app
#   flask_session/ sesiones: no se restauran (el relanzador las limpia a proposito)
#   data/          datos del usuario / cache del almacen central
#   __pycache__    bytecode
#   updates/, backups/  del propio updater (hoy viven en PROGRAMDATA, pero
#                  excluirlos es gratis y evita una copia recursiva si alguna vez
#                  se apunta el respaldo adentro del arbol)
CARPETAS_SIN_RESPALDO = ('python', 'tesseract', 'logs', 'flask_session', 'data',
                         '__pycache__', 'updates', 'backups')


def rutas_a_respaldar(app_dir):
    """Rutas RELATIVAS (con barra normal) de lo que hay que respaldar.

    Decide sin copiar: recorre y devuelve la lista, ordenada para que el respaldo
    sea reproducible y los tests deterministas. Es lo que se testea sin tocar el
    disco de una instalacion.
    """
    rutas = []
    for root, dirs, files in os.walk(app_dir):
        # `dirs[:] = ...` es lo que hace que `os.walk` NO descienda: sin esto
        # seguiria entrando en `python\Lib\site-packages` y descartando archivo por
        # archivo (que es justo el costo que este modulo elimina).
        dirs[:] = sorted(d for d in dirs if d not in CARPETAS_SIN_RESPALDO)
        for nombre in sorted(files):
            if not nombre.endswith(EXTENSIONES_RESPALDO):
                continue
            rel = os.path.relpath(os.path.join(root, nombre), app_dir)
            rutas.append(rel.replace('\\', '/'))
    return sorted(rutas)


def copiar_respaldo(app_dir, backup_path, log=None):
    """Copia al respaldo lo que decide `rutas_a_respaldar`. Devuelve cuantos copio.

    NO es best-effort a proposito: si un archivo no se puede copiar, la excepcion
    sube y `instalar_actualizacion_diferencial` restaura el backup y aborta la
    actualizacion (un respaldo incompleto no es un respaldo).
    """
    copiados = 0
    for rel in rutas_a_respaldar(app_dir):
        partes = rel.split('/')
        src = os.path.join(app_dir, *partes)
        dst = os.path.join(backup_path, *partes)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copiados += 1
    if log:
        log(f'📁 Backup creado en: {backup_path} ({copiados} archivo(s))')
    return copiados
