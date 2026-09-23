# app.py
# ============================================================
# SIDESYS ERP - APLICACIÓN PRINCIPAL (CON PANEL ADMIN Y UPDATER)
# ============================================================

import os
import sys
import time
import subprocess
import threading
import json
import hashlib
import shutil
import winreg
from flask import Flask, send_from_directory, jsonify, request, g, session
from flask_cors import CORS
from flask_session import Session
import secrets

# ============================================================
# CONSOLA UTF-8 (evita UnicodeEncodeError al arrancar desde consola)
# ============================================================
# Windows arranca Python con la code page del sistema (cp1252/cp850 en español)
# y `print()` de CUALQUIER emoji del código revienta el arranque con
# UnicodeEncodeError. Caso real y medido: app.py:156 (`⚠️ No se encontró ruta de
# instalación en el registro...`) tumbaba la app al ejecutarla desde una consola
# (iniciar.bat o `python app.py`). El .vbs no se ve afectado porque usa pythonw
# (stdout=None y print() es no-op), pero el resto de los caminos sí.
# Se reconfigura ANTES de importar config/modulos: algunos imprimen al importarse.
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ============================================================
# LOGGING PERSISTENTE (imprescindible para diagnosticar en la PC destino)
# ============================================================
# Sin esto, `logger.warning/error` de los módulos no tiene handler: con la app
# lanzada por el .vbs (pythonw, SIN consola) el mensaje se pierde. Síntoma real:
# el ERP devuelve "Error de conexión a la base de datos" (database.py:177
# esconde a propósito el detalle de pyodbc) y NO queda rastro en ningún lado,
# así que no se puede saber si falló la red, el driver ODBC o las credenciales.
# Escribe en logs/app.log (y en la consola cuando existe).
def _configurar_logging():
    import logging
    from logging.handlers import RotatingFileHandler
    try:
        carpeta_logs = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(carpeta_logs, exist_ok=True)
        destino = os.path.join(carpeta_logs, 'app.log')
    except OSError:
        destino = None

    formato = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    raiz = logging.getLogger()
    if not raiz.handlers:
        raiz.setLevel(logging.INFO)
        if destino:
            try:
                archivo = RotatingFileHandler(
                    destino, maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8')
                archivo.setFormatter(formato)
                raiz.addHandler(archivo)
            except OSError:
                pass
        # Bajo pythonw no hay stderr útil: solo agregar consola si existe.
        if sys.stderr is not None:
            consola = logging.StreamHandler()
            consola.setFormatter(formato)
            raiz.addHandler(consola)
    return destino


LOG_FILE = _configurar_logging()
print(f"[INFO] Log de la aplicación: {LOG_FILE}")

# ============================================================
# CONFIGURACIÓN DE SESIÓN SEGURA
# ============================================================
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
SECRET_KEY = os.environ.get('SESSION_SECRET_KEY')

if not SECRET_KEY:
    if FLASK_ENV == 'production':
        raise ValueError(
            "❌ SESSION_SECRET_KEY es OBLIGATORIA en producción.\n"
            "   Define SESSION_SECRET_KEY en .env.production"
        )
    SECRET_KEY = secrets.token_hex(32)
    print(f"[WARN] No se encontró SESSION_SECRET_KEY en .env, usando clave generada temporalmente")
    print(f"[WARN] Las sesiones se reiniciarán al reiniciar el servidor")

# ============================================================
# VERSIÓN DE LA APLICACIÓN
# ============================================================
# Fuente de verdad: el archivo VERSION en la raiz de la app (lo escribe el
# release). Si no existe (dev), se usa el fallback. No hardcodear la version:
# terminaba desalineada con el instalador y con version.txt.
def _leer_version_base(default="1.0.0"):
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION"),
                  "r", encoding="utf-8") as f:
            v = f.read().strip()
            return v or default
    except OSError:
        return default


APP_VERSION = _leer_version_base()
APP_PORT = int(os.environ.get("APP_PORT", "5000"))  # lo usa el relanzador
# Canal de actualizaciones. Override por entorno para pruebas de staging o para
# apuntar a un canal propio: SIDESYS_UPDATE_URL debe terminar en '/' o en el
# nombre de archivo del metadato.
_CANAL_DEFECTO = "https://raw.githubusercontent.com/ProyADM/ADM-ERP-Updates/main/"
_CANAL = (os.environ.get("SIDESYS_UPDATE_URL") or _CANAL_DEFECTO).rstrip("/") + "/"
VERSION_URL = _CANAL + "version.json"
UPDATE_URL = _CANAL + "updates/"

# ============================================================
# VERIFICACIÓN DE FIRMA DEL CANAL DE ACTUALIZACIÓN (C5)
# ============================================================
def _verificar_metadato_firmado(url, etiqueta):
    """Descarga <url> y su sidecar firmado <url>.sig y verifica la firma Ed25519.

    Fail-closed (C5): si falta el .sig, la firma no valida o hay cualquier
    error de red/parseo, devuelve (None, mensaje). Nunca se confía en un
    metadato (version.json / manifest.json) sin firma válida.
    """
    try:
        import requests
        from modules.shared.update_firma import verificar_firma
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        contenido = resp.content
        resp_sig = requests.get(url + '.sig', timeout=10)
        resp_sig.raise_for_status()
        if not verificar_firma(contenido, resp_sig.text):
            return None, (f"[WARN] {etiqueta} ignorado: firma inválida o .sig faltante "
                          f"(canal comprometido o release sin firmar)")
        return contenido, None
    except Exception as e:
        return None, f"[WARN] No se pudo verificar {etiqueta}: {e}"

# ============================================================
# FUNCIÓN PARA OBTENER LA RUTA DE INSTALACIÓN REAL
# ============================================================
def obtener_ruta_instalacion():
    """Ruta real de la instalación: variable de entorno > registro > carpeta de la app.

    `SIDESYS_INSTALL_DIR` sirve para pruebas (redirige el updater a un sandbox sin
    tocar la instalación real de la PC) y para despliegues con rutas no estándar.
    El registro lo escribe el instalador (HKCU\\Software\\Sidesys\\ADM-ERP).
    """
    override = os.environ.get("SIDESYS_INSTALL_DIR")
    if override and os.path.isdir(override):
        print(f"📂 Ruta de instalación (SIDESYS_INSTALL_DIR): {override}")
        return override
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Sidesys\ADM-ERP")
        path, _ = winreg.QueryValueEx(key, "InstallPath")
        winreg.CloseKey(key)
        if os.path.isdir(path):
            print(f"📂 Ruta de instalación detectada: {path}")
            return path
    except WindowsError:
        pass
    fallback = os.path.dirname(os.path.abspath(__file__))
    print(f"⚠️ No se encontró ruta de instalación en el registro, usando: {fallback}")
    return fallback

# ============================================================
# IMPORTAR BLUEPRINTS
# ============================================================
from modules.stock import stock_bp
from modules.cxp import cxp_bp
from modules.cotizaciones import cotizaciones_bp
from modules.shared.routes import shared_bp
from modules.shared.database import set_contexto_base
from modules.reportes import reportes_bp
from config import BASE_DEFAULT, SOCIEDAD_DEFAULT, BASES_DISPONIBLES
from modules.shared.dashboard import dashboard_bp
from modules.shared.auth import auth_bp
from modules.shared.auth_windows import get_current_windows_user, validar_sesion
from modules.shared.admin_api import admin_bp
from modules.shared.usuarios import get_gestor_usuarios
from modules.shared.decorators import requiere_admin, requiere_superadmin
from modules.shared.relanzar import lanzar_relanzador
from modules.shared import update_politica

# ============================================================
# FUNCIONES DE ACTUALIZACIÓN (INTEGRADAS DIRECTAMENTE)
# ============================================================

PROGRAM_DATA = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
UPDATE_DIR = os.path.join(PROGRAM_DATA, "SidesysERP", "updates")
BACKUP_DIR = os.path.join(PROGRAM_DATA, "SidesysERP", "backups")
VERSION_FILE = os.path.join(PROGRAM_DATA, "SidesysERP", "version.txt")
UPDATE_STATUS_FILE = os.path.join(PROGRAM_DATA, "SidesysERP", "update_status.json")
# Lo escribe el relanzador al terminar: si el reinicio no logro levantar la app,
# aca queda el motivo para poder AVISAR en pantalla (antes el estado se quedaba
# en "reiniciando" para siempre y el usuario no tenia forma de saber que hacer).
RELANZAMIENTO_RESULTADO_FILE = os.path.join(PROGRAM_DATA, "SidesysERP",
                                            "relanzamiento_resultado.json")
# Bandera de RESCATE: se escribe SOLO cuando `lanzar_relanzador` no pudo
# lanzar nada (el relanzador no esta en ningun arbol conocido), o sea cuando
# la actualizacion quedo aplicada en disco pero el proceso viejo sigue vivo.
# Significa "hay una actualizacion aplicada esperando un reinicio REAL". La
# borra la app al arrancar (el reinicio ya ocurrio) y la miran los lanzadores
# (`iniciar.bat`, `installer/Iniciar_ADM-ERP.vbs`) para NO tomar el atajo de
# "ya hay algo escuchando en el puerto -> abrir el navegador y salir", que era
# justo lo que dejaba al usuario trabado con el codigo viejo.
REINICIO_PENDIENTE_FILE = os.path.join(PROGRAM_DATA, "SidesysERP",
                                       "reinicio_pendiente.flag")
# Un solo aplicador a la vez. La actualizacion se puede disparar casi al mismo
# tiempo desde el hilo de arranque (`aplicar_actualizacion_al_inicio`) y desde el
# clic de un admin (`/api/download_update`, `/api/update/install`): el aviso de
# "hay versión nueva" sale a los 5 s, justo cuando arranca el automatico. Sin este
# candado los dos escribirian el MISMO `UPDATE_DIR` y podrian lanzar DOS
# relanzadores (o dejar archivos a medio copiar encima de la app).
_LOCK_ACTUALIZACION = threading.Lock()

def leer_estado_actualizacion():
    """Estado del updater que dejo el arranque anterior ({} si no hay o no se
    puede leer): lo usa la guarda anti-bucle y el panel de diagnostico."""
    try:
        if os.path.exists(UPDATE_STATUS_FILE):
            with open(UPDATE_STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f) or {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ No se pudo leer el estado de actualización: {e}")
    return {}


def resolver_resultado_relanzamiento():
    """Convierte el veredicto del relanzador en el estado de actualización.

    Se llama UNA vez al arrancar y devuelve True si este arranque es el posterior
    a una actualizacion (el que NO debe volver a aplicar sola la misma version).
    Si la app ya esta corriendo, el reinicio salio bien (aunque el relanzador no
    haya llegado a escribir nada): en ese caso, un estado que quedo en
    'reiniciando' pasa a 'completado'.

    Tambien cierra el estado terminal del caso espejo: si el relanzador dejo
    escrito que fallo (`error: relanzamiento`) pero NOSOTROS estamos corriendo la
    version que se habia instalado, el reinicio si funciono (el usuario abrio la
    app a mano, o el relanzador se equivoco al juzgar) y el estado no puede
    quedar diciendo "la ultima actualizacion falló (relanzamiento)" para siempre:
    sin esto, esa frase se leia en Administración → Diagnóstico durante semanas.
    """
    try:
        estado_previo = leer_estado_actualizacion()
        estado = estado_previo.get('estado')
        version = estado_previo.get('version')

        if estado == 'error' and estado_previo.get('error') == 'relanzamiento':
            # La version instalada es la fuente de verdad del cliente.
            if version and version == obtener_version_actual():
                guardar_estado_actualizacion(
                    'completado',
                    f'Actualización a {version} aplicada. El reinicio automático '
                    f'no se pudo confirmar: la aplicación arrancó de forma manual.',
                    version=version)
                print(f'✅ Actualización a {version} ya estaba aplicada '
                      f'(requirió inicio manual)')
            # Este arranque NO viene de un reinicio del updater: la aplicación
            # automática puede volver a evaluar la version (si el estado se
            # cerro, `decidir_aplicacion` igual no la va a reintentar porque el
            # disco ya esta al dia: `check_actualizaciones` dice que no hay nada).
            return False

        if estado != 'reiniciando':
            return False

        resultado = None
        if os.path.exists(RELANZAMIENTO_RESULTADO_FILE):
            try:
                with open(RELANZAMIENTO_RESULTADO_FILE, 'r', encoding='utf-8') as f:
                    resultado = json.load(f) or {}
            except (json.JSONDecodeError, OSError):
                resultado = None
            # Se borra DESPUES de leerlo: si quedaba un `ok: false` viejo, el
            # proximo relanzamiento lo volvia a leer como si fuera su veredicto y
            # gastaba uno de los 3 intentos por un fallo que ya no aplica.
            try:
                os.remove(RELANZAMIENTO_RESULTADO_FILE)
            except OSError as e:
                print(f'⚠️ No se pudo borrar el resultado del relanzamiento: {e}')

        if resultado and resultado.get('ok') is False:
            guardar_estado_actualizacion(
                'error',
                'La actualización se instaló pero la aplicación no volvió a '
                'arrancar: ' + str(resultado.get('motivo') or 'motivo desconocido'),
                version=version, error='relanzamiento')
            print('⚠️ El reinicio posterior a la actualización falló: '
                  + str(resultado.get('motivo')))
        else:
            guardar_estado_actualizacion(
                'completado',
                f'Actualización a {version} aplicada y aplicación reiniciada.' if version
                else 'Actualización aplicada y aplicación reiniciada.',
                version=version)
            print(f'✅ Actualización a {version} confirmada (la app arrancó bien)'
                  if version else '✅ Actualización confirmada')
        return True
    except Exception as e:
        print(f'⚠️ No se pudo resolver el resultado del relanzamiento: {e}')
        return False

def guardar_estado_actualizacion(estado, mensaje='', version=None, error=None,
                                 archivos=0, origen=None):
    """Persiste el estado del update.

    La forma la decide `update_politica.estado_a_guardar` (fusiona con lo que
    ya estaba: conserva `intentos` y `aplicada_en`). `origen` en None conserva
    el anterior, asi el estado que escribe `resolver_resultado_relanzamiento`
    no pierde que la actualizacion fue automatica.
    """
    try:
        os.makedirs(os.path.dirname(UPDATE_STATUS_FILE), exist_ok=True)
        datos = update_politica.estado_a_guardar(
            leer_estado_actualizacion(), estado, version=version, mensaje=mensaje,
            error=error, archivos=archivos, origen=origen)
        with open(UPDATE_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f)
    except Exception as e:
        print(f"⚠️ No se pudo escribir el estado de actualización: {e}")

def obtener_version_actual():
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("Versión:"):
                        return line.split(":")[1].strip()
        except:
            pass
    return APP_VERSION

def guardar_version(version):
    os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Versión: {version}\n")
        f.write(f"Actualizado: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

def comparar_versiones(v1: str, v2: str) -> int:
    def parse_version(v):
        v = v.replace('v', '').strip()
        parts = v.split('.')
        while len(parts) < 3:
            parts.append('0')
        return [int(p) for p in parts[:3]]
    v1_parts = parse_version(v1)
    v2_parts = parse_version(v2)
    for i in range(3):
        if v1_parts[i] < v2_parts[i]:
            return -1
        elif v1_parts[i] > v2_parts[i]:
            return 1
    return 0

def check_actualizaciones():
    try:
        # C5: solo se confía en un version.json con firma válida.
        contenido, error = _verificar_metadato_firmado(VERSION_URL, 'version.json')
        if contenido is None:
            print(error)
            return False, None
        try:
            version_info = json.loads(contenido.decode('utf-8'))
        except Exception as e:
            print(f"[WARN] version.json corrupto: {e}")
            return False, None

        version_remota = version_info.get('version', '0.0.0')
        # version_actual sale de version.txt (vive en ProgramData) y refleja lo
        # que hay realmente en disco; APP_VERSION es el valor leido al arrancar
        # y NO cambia tras aplicar una actualizacion.
        version_actual = obtener_version_actual()

        # C5 - frescura: la firma garantiza autenticidad, no frescura. Si esta
        # instalacion es anterior a la version MINIMA que declara el release, se
        # avisa. La actualizacion SE SIGUE OFRECIENDO (bloquearla aca dejaria a
        # esa PC sin forma de llegar a la version nueva); el limite duro se
        # aplica al instalar (ver verificar_y_actualizar).
        min_version = version_info.get('min_version')
        if min_version:
            try:
                if comparar_versiones(version_actual, str(min_version)) < 0:
                    msg = (f"Esta instalación ({version_actual}) es anterior a la mínima "
                           f"recomendada ({min_version}). Se recomienda la instalación "
                           f"completa.")
                    print(f"[WARN] {msg}")
                    version_info['aviso_version_minima'] = msg
            except Exception as e:
                print(f"[WARN] min_version ilegible ({min_version}): {e}")

        if comparar_versiones(version_actual, version_remota) < 0:
            return True, version_info
        return False, version_info
    except Exception as e:
        print(f"[WARN] No se pudo verificar actualizaciones: {e}")
        return False, None

def descargar_archivos_diferenciales(version_info):
    try:
        import requests
        version_remota = version_info.get('version')
        manifest_url = version_info.get('manifest_url')
        files_url = version_info.get('files_url')
        deleted_url = version_info.get('deleted_url')

        if not manifest_url or not files_url:
            success, archivos = descargar_actualizacion_completa(version_info)
            return success, archivos, []

        print(f"📥 Descargando manifest de versión {version_remota}...")
        # C5: el manifest viaja firmado; sin firma válida no se procesa.
        contenido_manifest, error = _verificar_metadato_firmado(manifest_url, 'manifest.json')
        if contenido_manifest is None:
            print(error)
            return False, [], []
        try:
            manifest_remoto = json.loads(contenido_manifest.decode('utf-8'))
        except Exception as e:
            print(f"[WARN] manifest.json corrupto: {e}")
            return False, [], []

        archivos_eliminar = []
        if deleted_url:
            try:
                resp_del = requests.get(deleted_url, timeout=10)
                resp_del.raise_for_status()
                archivos_eliminar = resp_del.json() or []
            except Exception as e:
                print(f"⚠️ No se pudo obtener deleted.json: {e}")

        archivos_actualizar = []
        app_dir = obtener_ruta_instalacion()

        for file_path, info_remoto in manifest_remoto.items():
            hash_remoto = info_remoto.get('hash')
            if not hash_remoto:
                # El manifest viene firmado, pero sin hash no hay verificación
                # posible: fail-closed (no se pisa el archivo a ciegas).
                print(f"   ✗ {file_path} sin hash en el manifest: se omite")
                continue
            local_path = os.path.join(app_dir, file_path)
            if os.path.exists(local_path):
                with open(local_path, 'rb') as f:
                    local_hash = hashlib.sha256(f.read()).hexdigest()
                if hash_remoto != local_hash:
                    archivos_actualizar.append(file_path)
            else:
                archivos_actualizar.append(file_path)

        if not archivos_actualizar:
            print("✅ No hay archivos que actualizar")
            return True, [], archivos_eliminar

        print(f"📥 Descargando {len(archivos_actualizar)} archivos modificados...")
        archivos_descargados = []
        total_archivos = len(archivos_actualizar)
        for idx, file_path in enumerate(archivos_actualizar, start=1):
            file_path_normalized = file_path.replace('\\', '/')
            file_url = f"{files_url.rstrip('/')}/{file_path_normalized}"
            # BUG HISTORICO: aca se usaba `info_remoto`, la variable que quedaba
            # del bucle de comparacion (el ULTIMO archivo del manifest), asi que
            # se validaba el hash de otro archivo y TODA actualizacion abortaba
            # con "Hash invalido". Se busca la entrada del archivo que se baja.
            info_remoto = manifest_remoto.get(file_path)
            if not info_remoto:
                print(f"   ✗ {file_path} no está en el manifest firmado: se aborta")
                return False, [], []
            guardar_estado_actualizacion(
                'descargando',
                f'Descargando archivo {idx}/{total_archivos}: {file_path_normalized}',
                version=version_remota
            )
            try:
                response = requests.get(file_url, timeout=30)
                response.raise_for_status()
                contenido = response.content
                # C5: verificar SHA-256 contra el manifest firmado antes de guardar.
                hash_esperado = info_remoto.get('hash')
                if not hash_esperado or hashlib.sha256(contenido).hexdigest() != hash_esperado:
                    print(f"   ✗ Hash inválido en {file_path}: se aborta la actualización "
                          f"(url={file_url} http={response.status_code} "
                          f"len={len(contenido)} esperado={hash_esperado})")
                    return False, [], []
                temp_file = os.path.join(UPDATE_DIR, file_path)
                os.makedirs(os.path.dirname(temp_file), exist_ok=True)
                with open(temp_file, 'wb') as f:
                    f.write(contenido)
                archivos_descargados.append({
                    'path': file_path,
                    'size': len(contenido)
                })
                print(f"   ✓ {file_path} ({len(contenido)} bytes)")
            except Exception as e:
                print(f"   ✗ Error descargando {file_path}: {e}")
                return False, [], []

        return True, archivos_descargados, archivos_eliminar

    except Exception as e:
        print(f"❌ Error en descarga diferencial: {e}")
        return False, [], []

def descargar_actualizacion_completa(version_info):
    try:
        import requests, zipfile
        download_url = version_info.get('download_url')
        if not download_url:
            return False, []
        print(f"📥 Descargando actualización completa...")
        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()
        zip_path = os.path.join(UPDATE_DIR, f"update_{version_info['version']}.zip")
        os.makedirs(UPDATE_DIR, exist_ok=True)
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print("📦 Extrayendo archivos...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(UPDATE_DIR)
        os.remove(zip_path)
        return True, []
    except Exception as e:
        print(f"❌ Error descargando actualización completa: {e}")
        return False, []

def instalar_actualizacion_diferencial(archivos_eliminar=None):
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, timestamp)
        os.makedirs(backup_path, exist_ok=True)

        app_dir = obtener_ruta_instalacion()

        # Backup de archivos existentes
        for root, dirs, files in os.walk(app_dir):
            for file in files:
                if file.endswith(('.py', '.js', '.css', '.html', '.json', '.txt')):
                    src = os.path.join(root, file)
                    rel = os.path.relpath(src, app_dir)
                    dst = os.path.join(backup_path, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

        print(f"📁 Backup creado en: {backup_path}")

        # Copiar archivos desde UPDATE_DIR a app_dir
        archivos_copiados = 0
        for root, dirs, files in os.walk(UPDATE_DIR):
            for file in files:
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, UPDATE_DIR)
                dst_file = os.path.join(app_dir, rel_path)
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                shutil.copy2(src_file, dst_file)
                archivos_copiados += 1

        print(f"✅ {archivos_copiados} archivos copiados correctamente")

        # 🔴 DESACTIVADO: No borrar archivos automáticamente
        # archivos_borrados = 0
        # for rel_path in (archivos_eliminar or []):
        #     target = os.path.join(app_dir, rel_path)
        #     if os.path.exists(target):
        #         try:
        #             os.remove(target)
        #             archivos_borrados += 1
        #             print(f"   🗑️ Eliminado: {rel_path}")
        #         except Exception as e:
        #             print(f"   ⚠️ No se pudo eliminar {rel_path}: {e}")
        # if archivos_borrados:
        #     print(f"✅ {archivos_borrados} archivo(s) obsoleto(s) eliminados")

        limpiar_archivos_temporales()
        return True

    except Exception as e:
        print(f"❌ Error instalando actualización: {e}")
        restaurar_backup()
        return False

def restaurar_backup():
    try:
        backups = sorted([d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d))])
        if backups:
            last_backup = os.path.join(BACKUP_DIR, backups[-1])
            app_dir = obtener_ruta_instalacion()
            print(f"🔄 Restaurando backup: {last_backup}")
            for root, dirs, files in os.walk(last_backup):
                for file in files:
                    src = os.path.join(root, file)
                    rel = os.path.relpath(src, last_backup)
                    dst = os.path.join(app_dir, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
            print("✅ Backup restaurado correctamente")
            return True
    except Exception as e:
        print(f"❌ Error restaurando backup: {e}")
        return False

def verificar_y_actualizar(origen='manual'):
    """Aplica la actualizacion disponible. UN solo aplicador a la vez.

    El hilo automatico del arranque y el clic de un admin pueden coincidir (el
    aviso de "hay versión nueva" sale a los 5 s, justo cuando arranca el
    automatico). El que llega segundo NO instala y NO escribe estado: el que esta
    aplicando es el dueno del estado y de `UPDATE_DIR`, y pisarlo dejaria el
    estado mintiendo (o perderia el `reiniciando` que espera la app nueva).
    """
    if not _LOCK_ACTUALIZACION.acquire(blocking=False):
        print("⚠️ Ya hay una actualización en curso: se omite este disparo")
        return None
    try:
        return _aplicar_actualizacion(origen)
    finally:
        _LOCK_ACTUALIZACION.release()


def _aplicar_actualizacion(origen='manual'):
    # Primer estado ANTES de verificar. `check_actualizaciones()` es un ida y
    # vuelta por HTTP y el panel consulta /api/update/status cada segundo: sin
    # esto, mientras se verifica todavia se ve el `completado` de la
    # actualizacion anterior, el panel lo toma como final ("Instalada. Reiniciá la
    # aplicación") y deja de seguir el progreso de ESTA. Se escribe adentro del
    # aplicador (con el candado tomado): es el dueno del estado.
    guardar_estado_actualizacion('descargando', 'Verificando actualización...',
                                 origen=origen)
    print("🔍 Verificando actualizaciones...")
    hay_actualizacion, version_info = check_actualizaciones()
    if not hay_actualizacion:
        print("✅ Ya tienes la última versión")
        # Estado terminal: no puede quedar en 'descargando' para siempre.
        guardar_estado_actualizacion('sin_actualizacion', 'Ya tienes la última versión',
                                     origen=origen)
        limpiar_archivos_temporales()
        return None
    if not version_info:
        print("⚠️ No se pudo obtener información de versiones")
        guardar_estado_actualizacion('error', 'No se pudo obtener información de versiones',
                                     error='canal', origen=origen)
        limpiar_archivos_temporales()
        return None

    version_remota = version_info.get('version')
    print(f"\n📢 Nueva versión disponible: {version_remota}")
    print(f"   Versión actual: {obtener_version_actual()}")
    print(f"   Fecha: {version_info.get('release_date', 'N/A')}")
    print()
    print("   Cambios:")
    for cambio in version_info.get('changelog', []):
        print(f"   • {cambio}")
    if version_info.get('aviso_version_minima'):
        print()
        print(f"   ⚠️ {version_info['aviso_version_minima']}")
    print()

    print("\n📥 Descargando actualización...")
    guardar_estado_actualizacion('descargando', 'Iniciando descarga...',
                                version=version_remota, origen=origen)

    archivos_eliminar = []
    archivos_descargados = []
    if version_info.get('manifest_url'):
        success, archivos_descargados, archivos_eliminar = \
            descargar_archivos_diferenciales(version_info)
    else:
        # C5: el canal legacy ZIP (sin manifest_url, sin firma por archivo) no se soporta.
        print("⚠️ versión remota sin manifest_url: canal ZIP legacy no soportado, se omite")
        guardar_estado_actualizacion('error', 'Canal ZIP legacy no soportado',
                                     version=version_remota, error='canal',
                                     origen=origen)
        limpiar_archivos_temporales()
        return None

    if not success:
        print("❌ Error al descargar la actualización")
        guardar_estado_actualizacion('error', 'Falló la descarga',
                                     version=version_remota, error='descarga',
                                     origen=origen)
        limpiar_archivos_temporales()
        return None

    print("\n🔄 Instalando actualización...")
    guardar_estado_actualizacion('instalando', 'Copiando archivos e instalando...',
                                 version=version_remota, origen=origen)
    if not instalar_actualizacion_diferencial(archivos_eliminar):
        print("❌ Error al instalar la actualización")
        guardar_estado_actualizacion('error', 'Falló la instalación',
                                     version=version_remota, error='instalacion',
                                     origen=origen)
        limpiar_archivos_temporales()
        return None

    guardar_version(version_remota)
    limpiar_archivos_temporales()
    limpiar_backups_viejos()

    # ¿Hace falta relanzar? Lo decide la politica con lo que REALMENTE se bajo:
    # un `.py` obliga aunque el canal diga que no; sin `.py` manda el canal y, si
    # no se bajo nada, no hay nada que reiniciar. El camino MANUAL (el clic de un
    # admin) reinicia siempre, que es lo que el usuario pidio.
    reiniciar = True
    if origen == 'automatica':
        reiniciar = update_politica.necesita_reinicio(
            version_info.get('requires_restart'), archivos_descargados)

    if not reiniciar:
        guardar_estado_actualizacion(
            'aplicada_sin_reinicio',
            f'Actualización a {version_remota} aplicada sin reiniciar '
            f'(sólo cambió pantalla).',
            version=version_remota, archivos=len(archivos_descargados),
            origen=origen)
        print(f"✅ Actualización a {version_remota} aplicada sin reiniciar")
        return version_info

    guardar_estado_actualizacion(
        'reiniciando',
        'Actualización instalada. Reiniciando la aplicación...',
        version=version_remota, origen=origen)
    print(f"\n✅ Actualización a versión {version_remota} instalada")

    # Auto-reinicio: el codigo nuevo ya esta en disco, pero este proceso sigue
    # ejecutando el viejo en memoria. El relanzador es un proceso desprendido
    # que espera a que este PID muera y arranca la app de nuevo.
    # Dos raices distintas y a proposito:
    #   install_dir = donde van los ARCHIVOS (sale del registro, R4: no se toca).
    #   app_dir     = la raiz de la app EN EJECUCION (este archivo), que es la
    #                 que hay que volver a arrancar. El relanzador se busca ahi
    #                 primero; si el updater apunta a otra carpeta (esta PC), se
    #                 relanza la app que corre y no la instalada.
    install_dir = obtener_ruta_instalacion()
    app_dir = os.path.dirname(os.path.abspath(__file__))
    ok, detalle = lanzar_relanzador(install_dir, puerto=APP_PORT,
                                    motivo='actualizacion',
                                    version=version_remota, app_dir=app_dir)
    if ok:
        print(f"🔁 Reiniciando con la versión {version_remota}...")
        guardar_estado_actualizacion(
            'reiniciando',
            f'Reiniciando con la versión {version_remota}...',
            version=version_remota, origen=origen)
        # Dar tiempo a que el frontend lea el estado antes de cortar.
        time.sleep(1.5)
        os._exit(0)
    else:
        print(f"⚠️ No se pudo lanzar el relanzador ({detalle}). "
              f"Reiniciá la aplicación manualmente para aplicar los cambios.")
        # R2: la bandera es la red de seguridad. El relanzador no pudo arrancar
        # nada, asi que el proceso viejo sigue vivo con el codigo viejo; la
        # bandera hace que los lanzadores maten ese proceso y arranquen de nuevo
        # en vez de tomar el atajo de "el puerto ya escucha -> abrir navegador".
        escribir_bandera_reinicio(version=version_remota, detalle=detalle)
        guardar_estado_actualizacion(
            'completado',
            'Actualización instalada. Reiniciá la aplicación para aplicarla.',
            version=version_remota, origen=origen)
    return version_info

def escribir_bandera_reinicio(version=None, detalle=None):
    """Deja `REINICIO_PENDIENTE_FILE`: hay un reinicio que NO se pudo lanzar.

    Best-effort y nunca lanza: si no se puede escribir, el unico efecto es que
    los lanzadores no ven la bandera (se pierde el rescate, no la app).
    """
    try:
        os.makedirs(os.path.dirname(REINICIO_PENDIENTE_FILE), exist_ok=True)
        with open(REINICIO_PENDIENTE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'version': version,
                'detalle': str(detalle or ''),
                'hora': time.strftime('%Y-%m-%d %H:%M:%S'),
            }, f)
        return True
    except Exception as e:
        print(f"⚠️ No se pudo escribir la bandera de reinicio: {e}")
        return False


def borrar_bandera_reinicio():
    """Borra la bandera al arrancar: si la app llego hasta aca, el reinicio
    pendiente ya ocurrio. Nunca revienta el arranque."""
    try:
        if os.path.exists(REINICIO_PENDIENTE_FILE):
            os.remove(REINICIO_PENDIENTE_FILE)
            print('🧹 Bandera de reinicio pendiente borrada (la app ya arrancó)')
    except OSError as e:
        print(f'⚠️ No se pudo borrar la bandera de reinicio: {e}')


def limpiar_backups_viejos(maximo=5):
    """Conserva los `maximo` backups mas nuevos del updater.

    Antes se hacia un backup por actualizacion y sin nadie mirando: se
    acumulaban ~1 MB por update para siempre.
    """
    try:
        if not os.path.isdir(BACKUP_DIR):
            return []
        sobrantes = update_politica.backups_a_borrar(os.listdir(BACKUP_DIR), maximo)
        for nombre in sobrantes:
            ruta = os.path.join(BACKUP_DIR, nombre)
            if os.path.isdir(ruta):
                shutil.rmtree(ruta, ignore_errors=True)
        if sobrantes:
            print(f"🧹 Backups viejos borrados: {len(sobrantes)}")
        return sobrantes
    except Exception as e:
        print(f"⚠️ No se pudieron limpiar los backups: {e}")
        return []

def aplicar_actualizacion_al_inicio(arranque_por_actualizacion=False, demora=5):
    """Aplica sola la actualizacion disponible al arrancar, sin clic.

    Corre una vez, unos segundos despues de levantar (la app vive mientras el
    navegador este abierto: hay un arranque por apertura). La firma Ed25519 y
    el hash por archivo son el control de seguridad; el clic nunca lo fue.
    Devuelve la version aplicada o None.
    """
    time.sleep(max(0, demora))
    # `version_remota` se define ANTES del try: si algo falla antes de saber cuál
    # es la versión, el estado de error tiene que poder decir "no sé de cuál".
    version_remota = None
    try:
        estado_previo = leer_estado_actualizacion()
        hay, version_info = check_actualizaciones()
        version_remota = (version_info or {}).get('version') if hay else None
        aplicar, motivo = update_politica.decidir_aplicacion(
            version_remota, estado_previo, arranque_por_actualizacion)
        if not aplicar:
            print(f"[UPDATER] No se aplica automáticamente ({motivo})")
            return None
        print(f"[UPDATER] Aplicando {version_remota} automáticamente al inicio")
        return verificar_y_actualizar(origen='automatica')
    except Exception as e:
        print(f"[UPDATER] Error en la aplicación automática: {e}")
        # Con `version` la politica cuenta el intento de ESA version: sin esto,
        # una falla fuera de los caminos de descarga/instalacion (por ejemplo
        # `guardar_version` con el disco lleno) dejaba `intentos` vacio y la app
        # reintentaba sola en cada arranque, para siempre.
        guardar_estado_actualizacion('error', f'Error en la aplicación automática: {e}',
                                     version=version_remota, error='excepcion',
                                     origen='automatica')
        return None

def limpiar_archivos_temporales():
    try:
        if os.path.exists(UPDATE_DIR):
            for item in os.listdir(UPDATE_DIR):
                item_path = os.path.join(UPDATE_DIR, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
        print("🧹 Archivos temporales limpiados")
    except Exception as e:
        print(f"⚠️ Error limpiando archivos: {e}")

# ============================================================
# MONITOREO DEL NAVEGADOR (la app vive mientras el navegador este abierto)
# ============================================================
def hay_actualizacion_en_curso():
    """¿Hay una actualizacion aplicandose en ESTE proceso?

    Es el candado del aplicador (`_LOCK_ACTUALIZACION`), no el estado en disco:
    lo que importa es si `instalar_actualizacion_diferencial` esta copiando
    archivos AHORA, y `os._exit` no levanta nada, asi que `restaurar_backup()`
    no llegaria a correr nunca.
    """
    return _LOCK_ACTUALIZACION.locked()


def esperar_fin_de_actualizacion(pausa=2.0, maximo=1800.0, dormir=time.sleep,
                                 en_curso=None):
    """Espera a que termine la actualizacion en vuelo. True si ya no hay ninguna.

    Devuelve False solo si se agoto `maximo` (el candado no se suelta): en ese
    caso el proceso igual se apaga, porque si no el server quedaria vivo para
    siempre con el navegador cerrado.
    """
    en_curso = en_curso or hay_actualizacion_en_curso
    esperado = 0.0
    while en_curso():
        if esperado >= maximo:
            return False
        dormir(pausa)
        esperado += pausa
    return True


def monitorear_navegador(app_port=APP_PORT, psutil_mod=None,
                         dormir=time.sleep, salir=os._exit, en_curso=None):
    """Cierra la app cuando se cierra el navegador que la abrio.

    GUARDA (importante): la aplicacion automatica corre en ESTE proceso a los
    ~5 s de arrancar, asi que ahora cerrar el navegador dentro de esa ventana
    es algo que pasa sin que nadie haga clic. `os._exit` no levanta ninguna
    excepcion: si se corta en medio de `instalar_actualizacion_diferencial` el
    `except` que llama a `restaurar_backup()` NUNCA corre y la PC queda con el
    arbol a medio copiar (y quizas una app que no importa). Tampoco se sale
    mientras el estado es `reiniciando`: ahi el relanzador esta esperando que
    muera ESTE PID y le corresponde al aplicador cortar (con su `os._exit(0)`
    despues del `sleep(1.5)`) para que el frontend llegue a leer el estado.
    """
    psutil_mod = psutil_mod or __import__('psutil')
    dormir(3)
    navegadores = ["chrome.exe", "firefox.exe", "msedge.exe", "brave.exe"]
    pid_navegador = None
    for proc in psutil_mod.process_iter(['pid', 'name']):
        if proc.info['name'].lower() in navegadores:
            try:
                for conn in proc.net_connections():
                    if conn.laddr.port == app_port:
                        pid_navegador = proc.info['pid']
                        break
            except Exception:
                pass
            if pid_navegador:
                break
    if not pid_navegador:
        return
    print(f"[INFO] Monitoreando navegador (PID: {pid_navegador})")
    while True:
        try:
            psutil_mod.Process(pid_navegador)
            dormir(3)
        except psutil_mod.NoSuchProcess:
            if not esperar_fin_de_actualizacion(dormir=dormir, en_curso=en_curso):
                print("[WARN] La actualización no terminó en el tiempo máximo: "
                      "se cierra igual")
            print("[INFO] Navegador cerrado. Deteniendo servidor...")
            salir(0)
            return

# ============================================================
# CREAR APLICACIÓN FLASK
# ============================================================
app = Flask(__name__, static_folder="frontend", static_url_path="")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
# Ruta real de instalacion (registro HKCU -> fallback a la raiz de la app):
# la usa /api/reiniciar para lanzar el relanzador en el lugar correcto.
app.config['APP_INSTALL_DIR'] = obtener_ruta_instalacion()

app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'sidesys_'

Session(app)

ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000').split(',')
CORS(app, supports_credentials=True, origins=ALLOWED_ORIGINS)

# ============================================================
# MIDDLEWARE DE CONTEXTO DE BASE
# ============================================================
def _usuario_puede_acceder_base(user_data, base):
    """¿El usuario autenticado tiene permitido operar sobre esta base?
    C4 (fail-closed): lista vacía/ausente = SIN acceso. Solo superadmin,
    bases_permitidas=['*'] o membresía explícita habilitan."""
    if not user_data:
        return False
    if user_data.get('es_superadmin'):
        return True
    bases = user_data.get('bases_permitidas') or []
    if '*' in bases:
        return True
    return base in bases

def _path_no_requiere_base(path):
    """Endpoints que NO operan sobre bases de datos de países (sesión/admin):
    no se les exige una base autorizada."""
    return path.startswith('/api/auth/') or path.startswith('/api/admin/')

@app.before_request
def _resolver_base_activa():
    """Resuelve la base de trabajo SOLO con sesión válida y base autorizada.

    Sin sesión (o con sesión inválida) no se confía en el header X-Base:
    se usa siempre BASE_DEFAULT. Con sesión, un X-Base explícito que no esté
    entre las bases permitidas del usuario se rechaza con 403 (fail-closed).
    Sin X-Base, la base por defecto se usa solo si el usuario puede operarla;
    en APIs de datos se rechaza para que el cliente envíe una base permitida.
    """
    # Config central (Etapa 1): si otra PC cambió usuarios/roles, se aplica acá.
    # El throttle vive en el gestor (CENTRAL_RELOAD_SEG): a lo sumo un stat por request.
    try:
        if get_gestor_usuarios().recargar_si_cambio():
            _refrescar_sesion_desde_gestor()
    except Exception as e:
        app.logger.warning(f"No se pudo recargar la configuración central: {e}")

    sociedad = request.headers.get("X-Sociedad")

    # 1) Sin sesión → contexto por defecto, ignorar X-Base por completo.
    if 'username' not in session:
        set_contexto_base(BASE_DEFAULT, sociedad)
        return None

    # 2) Sesión presente pero JWT inválido/expirado → no confiar en ella
    #    (validar_sesion limpia la sesión en ese caso).
    success, _ = validar_sesion()
    if not success:
        set_contexto_base(BASE_DEFAULT, sociedad)
        return None

    # 3) Con sesión válida: resolver user_data (cacheada en sesión por el SSO).
    username = session.get('username')
    user_data = session.get('user_data')
    if not user_data or user_data.get('username') != username:
        user_data = obtener_datos_usuario_completo(username)

    base_pedida = request.headers.get("X-Base")
    if base_pedida is None:
        # Sin header: base por defecto.
        base = BASE_DEFAULT
        if not _usuario_puede_acceder_base(user_data, base):
            if request.path.startswith('/api/') and not _path_no_requiere_base(request.path):
                return jsonify({
                    'error': f'Base "{base}" no autorizada para este usuario. Enviá X-Base con una base permitida.',
                    'code': 'BASE_FORBIDDEN'
                }), 403
    elif base_pedida in BASES_DISPONIBLES and _usuario_puede_acceder_base(user_data, base_pedida):
        base = base_pedida
    else:
        return jsonify({
            'error': f'Base "{base_pedida}" no autorizada para este usuario',
            'code': 'BASE_FORBIDDEN'
        }), 403

    set_contexto_base(base, sociedad)
    return None

# ============================================================
# FUNCIONES DE GESTIÓN DE ROLES Y PERMISOS
# ============================================================
def obtener_datos_usuario_completo(username):
    """C4: única fuente de verdad = GestorUsuarios (usuarios.json + roles.json).
    Antes esta función leía los JSON crudos por duplicado y asumía
    bases_permitidas=['*'] cuando faltaba la clave (inconsistente con el
    gestor, que usa []). El gestor ya resuelve rol/permisos/superadmin."""
    gestor = get_gestor_usuarios()
    return gestor.datos_usuario_completo(username)

def _refrescar_sesion_desde_gestor():
    """Tras una recarga del almacén central, actualiza la copia cacheada en la
    sesión para que la autorización por base no quede vieja hasta el re-login."""
    username = session.get('username')
    if not username:
        return
    user_data = obtener_datos_usuario_completo(username)
    if not user_data:
        session.clear()
        return
    session['rol'] = user_data['rol']
    session['es_superadmin'] = user_data['es_superadmin']
    session['permisos'] = user_data['permisos']
    session['user_data'] = user_data

# ============================================================
# MIDDLEWARE DE AUTENTICACIÓN
# ============================================================
@app.before_request
def _verificar_autenticacion():
    rutas_publicas = [
        '/api/auth/login', '/api/auth/login_sso',
        '/api/auth/check', '/api/auth/logout',
        '/frontend/', '/app.js', '/style.css', '/favicon.ico',
        '/api/test', '/api/__version', '/api/version'
    ]
    es_ruta_publica = False
    for ruta in rutas_publicas:
        if request.path.startswith(ruta):
            es_ruta_publica = True
            break
    if request.path == '/':
        es_ruta_publica = True

    if 'username' in session:
        success, _ = validar_sesion()
        if success:
            return None
        else:
            session.clear()

    if not request.path.startswith('/api/auth'):
        # C4: SSO automático SOLO en la misma máquina (localhost) y SOLO si el
        # usuario Windows ya está dado de alta (existe en el gestor) y está
        # activo. Antes se auto-creaba la sesión del usuario del proceso para
        # CUALQUIER request de la LAN (cualquiera heredaba la identidad del
        # usuario que corre la app). Desconocidos/remotos → 401 + login
        # explícito (/api/auth/login valida credenciales reales).
        if request.remote_addr in ('127.0.0.1', '::1'):
            username = get_current_windows_user()
            if username:
                try:
                    gestor = get_gestor_usuarios()
                    usuario_obj = gestor.usuarios.get(username)
                    if usuario_obj and usuario_obj.activo and not usuario_obj.bloqueado:
                        user_data = gestor.datos_usuario_completo(username)
                        if user_data:
                            from modules.shared.auth_windows import crear_sesion
                            session['username'] = username
                            session['rol'] = user_data['rol']
                            session['es_superadmin'] = user_data['es_superadmin']
                            session['permisos'] = user_data['permisos']
                            session['user_data'] = user_data
                            crear_sesion(username, user_data['rol'])
                        if request.path == '/' or es_ruta_publica:
                            return None
                except Exception as e:
                    print(f"[WARN] SSO automático falló: {e}")

    if es_ruta_publica or request.path == '/':
        return None

    if request.path.startswith('/api/') and not request.path.startswith('/api/auth/'):
        return jsonify({
            'error': 'No autenticado',
            'code': 'UNAUTHORIZED',
            'login_url': '/'
        }), 401

# ============================================================
# REGISTRAR BLUEPRINTS
# ============================================================
app.register_blueprint(stock_bp, url_prefix='/api')
app.register_blueprint(cxp_bp, url_prefix='/api')
app.register_blueprint(cotizaciones_bp, url_prefix='/api/cotizaciones')
app.register_blueprint(shared_bp, url_prefix='/api')
app.register_blueprint(reportes_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(dashboard_bp)

# ============================================================
# RUTAS PRINCIPALES
# ============================================================
@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")

@app.route("/style.css")
def serve_css():
    return send_from_directory("frontend", "style.css")

@app.route("/app.js")
def serve_app_js():
    return send_from_directory("frontend", "app.js")

@app.route("/frontend/modules/<path:filename>")
def serve_modules(filename):
    return send_from_directory("frontend/modules", filename)

@app.route("/frontend/templates/<path:filename>")
def serve_templates(filename):
    return send_from_directory("frontend/templates", filename)

@app.route("/frontend/css/<path:filename>")
def serve_css_files(filename):
    return send_from_directory("frontend/css", filename)

# ============================================================
# API - USUARIO ACTUAL
# ============================================================
@app.route("/api/auth/current_user", methods=['GET'])
def api_current_user():
    if 'username' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    username = session['username']
    user_data = obtener_datos_usuario_completo(username)
    if not user_data:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    return jsonify({
        'success': True,
        'user': user_data,
        'session': {
            'username': session.get('username'),
            'rol': session.get('rol'),
            'es_superadmin': session.get('es_superadmin', False)
        }
    })

# ============================================================
# API - VERSIÓN
# ============================================================
@app.route("/api/__version")
def api_version():
    try:
        h1 = hashlib.md5(open(__file__, "rb").read()).hexdigest()[:8]
        h2 = hashlib.md5(open(os.path.join(os.path.dirname(__file__), "frontend/index.html"), "rb").read()).hexdigest()[:8]
        h3 = hashlib.md5(open(os.path.join(os.path.dirname(__file__), "frontend/style.css"), "rb").read()).hexdigest()[:8]
        return jsonify({"version": h1 + h2 + h3})
    except Exception as e:
        return jsonify({"version": "unknown", "error": str(e)})

@app.route("/api/version")
def api_version_info():
    return jsonify({
        'version': obtener_version_actual(),
        'check_url': VERSION_URL,
        'app_version': APP_VERSION
    })

@app.route("/api/check_update")
def api_check_update():
    # Mismos campos de decision que `/api/update/notification` (mismo
    # `check_actualizaciones`, misma forma): dos contratos distintos para el mismo
    # dato hacian que un consumidor nuevo leyera `undefined` donde el otro tenia
    # un booleano. `force_update` significa "no puede esperar al proximo arranque"
    # y `requires_restart`, "hay que relanzar la app".
    try:
        hay, version_info = check_actualizaciones()
        if hay and version_info:
            return jsonify({
                'has_update': True,
                'version': version_info.get('version'),
                'release_date': version_info.get('release_date'),
                'changelog': version_info.get('changelog', []),
                'current_version': obtener_version_actual(),
                'force_update': bool(version_info.get('force_update')),
                'requires_restart': bool(version_info.get('requires_restart'))
            })
        else:
            return jsonify({
                'has_update': False,
                'message': 'Ya tienes la última versión',
                'current_version': obtener_version_actual()
            })
    except Exception as e:
        return jsonify({
            'has_update': False,
            'error': str(e),
            'message': 'Error al verificar actualizaciones'
        }), 500

@app.route("/api/download_update", methods=['POST'])
@requiere_admin
def api_download_update():
    try:
        hay, version_info = check_actualizaciones()
        if not hay or not version_info:
            return jsonify({
                'success': False,
                'message': 'No hay actualizaciones disponibles'
            }), 400

        def update_thread():
            try:
                print(f"[UPDATER] Iniciando actualización a versión {version_info['version']}")
                verificar_y_actualizar()
            except Exception as e:
                print(f"[UPDATER] Error en hilo de actualización: {e}")
                guardar_estado_actualizacion('error', str(e), version=version_info.get('version'), error='excepcion')

        thread = threading.Thread(target=update_thread)
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Actualización iniciada en segundo plano',
            'version': version_info.get('version'),
            'status': 'downloading'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Error al iniciar la actualización'
        }), 500

# ============================================================
# API - NOTIFICACIÓN DE ACTUALIZACIÓN
# ============================================================
@app.route('/api/update/notification', methods=['GET'])
def api_update_notification():
    try:
        hay, version_info = check_actualizaciones()
        if hay and version_info:
            return jsonify({
                'has_update': True,
                'version': version_info.get('version'),
                'release_date': version_info.get('release_date'),
                'changelog': version_info.get('changelog', []),
                'url': '/api/download_update',
                # Criticidad: si el release se publico con --critico, el
                # frontend SI muestra el pop-up (no puede esperar al proximo
                # arranque). El resto se aplica sola y en silencio.
                'force_update': bool(version_info.get('force_update')),
                'requires_restart': bool(version_info.get('requires_restart')),
                # C5 - frescura: aviso informativo (no bloquea la actualizacion)
                'aviso': version_info.get('aviso_version_minima')
            })
        return jsonify({
            'has_update': False,
            'message': 'No hay actualizaciones disponibles'
        })
    except Exception as e:
        return jsonify({
            'has_update': False,
            'error': str(e)
        }), 500

# ============================================================
# API - UPDATE (NUEVOS ENDPOINTS)
# ============================================================
@app.route('/api/update/check', methods=['GET'])
def api_update_check():
    return api_check_update()

@app.route('/api/update/install', methods=['POST'])
@requiere_admin
def api_update_install():
    # SIN pre-escritura de estado: si el clic cae mientras el automatico esta
    # aplicando, `verificar_y_actualizar` no lo deja entrar (candado) y este
    # 'descargando' pisaria el 'reiniciando'/'aplicada_sin_reinicio' —con su
    # `origen` y su `aplicada_en`— que la app nueva necesita leer. El estado lo
    # escribe el aplicador cuando realmente arranca (`_aplicar_actualizacion`).
    return api_download_update()

@app.route('/api/update/status', methods=['GET'])
def api_update_status():
    if not os.path.exists(UPDATE_STATUS_FILE):
        return jsonify({'estado': 'sin_actualizacion'})
    try:
        with open(UPDATE_STATUS_FILE, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({'estado': 'error', 'error': str(e)}), 500

# NOTA C4: /api/reiniciar vive en modules/shared/routes.py (con @requiere_superadmin).
# La copia duplicada que había acá en app.py se eliminó: quedaba shadoweada según
# el orden de registro de rutas y no tenía control de permisos.

@app.route('/favicon.ico')
def favicon():
    return '', 204

# ============================================================
# CABECERAS DE SEGURIDAD (C9) - CSP FUERTE
# ============================================================
# script-src 'self' (sin inline ni eval): todo el JS vive en archivos propios.
# style-src permite 'unsafe-inline' porque el HTML usa style="" inline.
# El index.html NO debe contener <script> inline ni onclick= (usar data-onclick).
@app.after_request
def aplicar_cabeceras_seguridad(response):
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "media-src 'self' blob:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'no-referrer')
    return response

# ============================================================
# API - TEST
# ============================================================
@app.route("/api/test")
def test_api():
    return jsonify({
        "status": "ok",
        "message": "API funcionando correctamente",
        "authenticated": 'username' in session,
        "version": obtener_version_actual()
    })

# ============================================================
# API - DEBUG STOCK
# ============================================================
@app.route('/api/debug/stock', methods=['GET'])
@requiere_superadmin
def debug_stock():
    try:
        from modules.shared.database import run_sql
        info = {
            'db_server': getattr(g, 'db_server', 'NO SETEADO'),
            'db_database': getattr(g, 'db_database', 'NO SETEADO'),
            'division': getattr(g, 'division', 'NO SETEADO'),
            'sucursal': getattr(g, 'sucursal', 'NO SETEADO'),
            'authenticated_user': session.get('username'),
            'rol': session.get('rol', 'usuario'),
            'es_superadmin': session.get('es_superadmin', False),
            'permisos': session.get('permisos', [])
        }
        rows = run_sql("SELECT TOP 1 ARTS_ARTICULO FROM STOC_ARTS")
        info['consulta_ok'] = True
        info['resultado'] = 'ok' if rows else 'vacio'
        return jsonify(info)
    except Exception as e:
        return jsonify({
            'error': 'Ocurrió un error en la base de datos.',
            'details': str(e)
        }), 500

# ============================================================
# MANEJO DE ERRORES
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Recurso no encontrado"}), 404

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({
        "error": "No autenticado",
        "code": "UNAUTHORIZED",
        "login_url": "/"
    }), 401

@app.errorhandler(403)
def forbidden(e):
    return jsonify({
        "error": "No tienes permiso para acceder a este recurso",
        "code": "FORBIDDEN"
    }), 403

# ============================================================
# FUNCIÓN PARA VERIFICAR ACTUALIZACIONES EN SEGUNDO PLANO
# ============================================================
def verificar_actualizaciones_fondo():
    try:
        time.sleep(5)
        print("\n🔍 Verificando actualizaciones en segundo plano...")
        hay, version_info = check_actualizaciones()
        if hay and version_info:
            version_actual = obtener_version_actual()
            version_nueva = version_info.get('version', '0.0.0')
            print(f"\n📢 NUEVA VERSIÓN DISPONIBLE: {version_nueva}")
            print(f"   Versión actual: {version_actual}")
            print(f"   Fecha: {version_info.get('release_date', 'N/A')}")
            print()
            print("   Cambios:")
            for cambio in version_info.get('changelog', []):
                print(f"   • {cambio}")
            print()
            print("   Visita /api/download_update para instalar automáticamente")
            print("=" * 60)
            update_info_file = os.path.join(PROGRAM_DATA, "SidesysERP", "update_available.json")
            os.makedirs(os.path.dirname(update_info_file), exist_ok=True)
            with open(update_info_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': version_nueva,
                    'release_date': version_info.get('release_date'),
                    'changelog': version_info.get('changelog', []),
                    'detected_at': time.time()
                }, f, indent=2)
    except Exception as e:
        print(f"[WARN] Error verificando actualizaciones en fondo: {e}")

# ============================================================
# EJECUCIÓN
# ============================================================
if __name__ == "__main__":
    # NOTA: `psutil` ya no se importa aca. El unico consumidor era el monitor del
    # navegador, que ahora vive a nivel de modulo y lo importa el mismo (asi se
    # puede testear pasandole un doble). Importarlo aca sin usarlo solo servia
    # para reventar el arranque si faltaba el paquete, aunque el monitor no
    # llegara a correr.
    os.makedirs(UPDATE_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # R2: si quedaba una bandera de reinicio pendiente, este arranque ES el
    # reinicio que faltaba (lo haya disparado el usuario, `iniciar.bat` o el
    # .vbs): se borra ANTES de agendar la aplicacion automatica. Nunca revienta
    # el arranque (best-effort).
    borrar_bandera_reinicio()

    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    if FLASK_ENV == 'production' and debug_mode:
        print("[WARN] ⚠️ DEBUG activado en producción - DESACTIVANDO")
        debug_mode = False

    # ============================================================
    # CONFIGURACIÓN DE BIND / TLS (C8)
    # ============================================================
    # C8: por defecto la app escucha SOLO en 127.0.0.1. Para uso multi-PC en
    # LAN hay que setear APP_HOST=0.0.0.0 explícitamente (idealmente con TLS).
    app_host = os.environ.get('APP_HOST', '127.0.0.1')
    app_port = APP_PORT  # ya validado al definir la constante (linea 40)
    tls_cert = os.environ.get('APP_TLS_CERT', '').strip()
    tls_key = os.environ.get('APP_TLS_KEY', '').strip()
    tls_activo = bool(tls_cert and tls_key)
    if bool(tls_cert) != bool(tls_key):
        print("❌ APP_TLS_CERT y APP_TLS_KEY deben definirse JUNTOS (cert PEM + key PEM)")
        sys.exit(1)
    if app_host not in ('127.0.0.1', 'localhost', '::1') and not tls_activo:
        print(f"[WARN] ⚠️ Escuchando en {app_host}:{app_port} SIN TLS: el tráfico va en claro por la LAN.")
        print("       Para cifrarlo definí APP_TLS_CERT/APP_TLS_KEY (o usá un reverse proxy con TLS).")
    esquema = 'https' if tls_activo else 'http'

    print("=" * 60)
    print("  SIDESYS ERP - MODO DESARROLLO")
    print("=" * 60)
    print(f"  Versión: {APP_VERSION}")
    print(f"  SECRET_KEY: {SECRET_KEY[:10]}...")
    print(f"  Sesiones expiran en: {app.config['PERMANENT_SESSION_LIFETIME']} segundos")
    print("  Autenticación de Windows: ACTIVADA")
    print("  Panel de Administración: ACTIVADO")
    print("  Sistema de Actualizaciones: ACTIVADO")
    print(f"  Entorno: {FLASK_ENV}")
    print(f"  DEBUG: {debug_mode}")
    print(f"  Bind: {app_host}:{app_port} ({esquema})")
    if tls_activo:
        print(f"  TLS: activo (cert={tls_cert})")
    print("=" * 60)
    print()

    # La app ya esta levantando: si el estado habia quedado en 'reiniciando'
    # (auto-reinicio posterior a una actualizacion), aca se confirma —o se avisa
    # que fallo—. Va ANTES del chequeo en segundo plano para que el frontend lea
    # el estado final y no uno intermedio. Devuelve si este arranque es el
    # posterior a una actualizacion: entonces la version ya se aplico y no hay
    # que volver a aplicarla sola.
    arranque_por_actualizacion = resolver_resultado_relanzamiento()

    thread = threading.Thread(target=verificar_actualizaciones_fondo)
    thread.daemon = True
    thread.start()

    # Aplicacion automatica: sin pop-up, sin clic y solo al arrancar.
    hilo_update = threading.Thread(
        target=aplicar_actualizacion_al_inicio,
        kwargs={'arranque_por_actualizacion': arranque_por_actualizacion})
    hilo_update.daemon = True
    hilo_update.start()

    # El monitor vive arriba, a nivel de modulo (`monitorear_navegador`): es el
    # que decide si puede cortar el proceso, y esa decision tiene que poder
    # testearse sin arrancar el server.
    threading.Thread(target=monitorear_navegador,
                     kwargs={'app_port': app_port}, daemon=True).start()

    ssl_ctx = (tls_cert, tls_key) if tls_activo else None
    print(f"🚀 Servidor disponible en {esquema}://localhost:{app_port}")
    app.run(
        host=app_host,
        port=app_port,
        debug=debug_mode,
        threaded=True,
        ssl_context=ssl_ctx
    )