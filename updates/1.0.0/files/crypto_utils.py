# crypto_utils.py
# ============================================================
# UTILIDADES DE ENCRIPTACIÓN CON CLAVE MAESTRA - SIDESYS ERP
# ============================================================
# 🔑 CLAVE MAESTRA ÚNICA - Reutilizable en TODAS las PCs
#    GENERACIÓN AUTOMÁTICA EN EL PRIMER ARRANQUE
# ============================================================

import os
import base64
import hashlib
import json
import secrets
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ============================================================
# CONFIGURACIÓN DE LA CLAVE MAESTRA
# ============================================================

# Archivo donde se guarda la clave maestra (ignorado por git)
MASTER_KEY_FILE = os.path.join(os.path.dirname(__file__), '.master.key')

# Salt usado SOLO para leer archivos cifrados ANTES del cambio a
# salt aleatorio por archivo (retrocompatibilidad). NO usar al cifrar.
SALT_LEGACY = b'sidesys_erp_master_salt_2026'


def _generar_salt(tamano: int = 16) -> bytes:
    """Genera un salt aleatorio para cifrar un archivo nuevo."""
    return os.urandom(tamano)


def _salt_desde_meta(meta):
    """Obtiene el salt de los metadatos (base64). Si no está, usa legacy."""
    salt_b64 = meta.get('salt')
    if salt_b64:
        try:
            return base64.urlsafe_b64decode(salt_b64)
        except Exception:
            pass
    return SALT_LEGACY


def _generar_y_guardar_clave_maestra():
    """
    Genera una clave maestra aleatoria y la guarda.
    🔴 Esta función SOLO se invoca EXPLÍCITAMENTE por CLI (--generate-key),
    NUNCA automáticamente en el arranque.
    
    RETURNS: La clave generada
    """
    # Generar clave aleatoria de 32 caracteres (segura)
    nueva_clave = secrets.token_urlsafe(32)
    
    # Guardar en archivo .master.key (ignorado por git)
    try:
        with open(MASTER_KEY_FILE, 'w', encoding='utf-8') as f:
            f.write(nueva_clave)
        # Asegurar que solo el usuario actual pueda leer el archivo
        try:
            os.chmod(MASTER_KEY_FILE, 0o600)  # Solo lectura/escritura para el propietario
        except:
            pass  # En Windows no funciona chmod, ignorar
        print(f"🔑 CLAVE MAESTRA GENERADA")
        print(f"   Guardada en: {MASTER_KEY_FILE}")
        print(f"   ⚠️ NO COMPARTAS ESTE ARCHIVO")
        print(f"   ℹ️ Si necesitas la clave, consulta el archivo .master.key")
    except Exception as e:
        print(f"⚠️ No se pudo guardar la clave en archivo: {e}")
    
    # También intentar guardar en variable de entorno del sistema (opcional)
    try:
        import subprocess
        subprocess.run(
            ['setx', 'SIDESYS_MASTER_KEY', nueva_clave],
            capture_output=True,
            timeout=5
        )
        print(f"   ✅ Clave también guardada en variable de entorno SIDESYS_MASTER_KEY")
    except Exception:
        pass
    
    return nueva_clave


def obtener_clave_maestra():
    """
    Obtiene la clave maestra desde variable de entorno o archivo.
    🔴 NO genera claves automáticamente ni usa fallback: si no existe,
    lanza un error con instrucciones.
    
    RETURNS: La clave maestra como string
    """
    # Primero intentar desde variable de entorno
    key = os.environ.get('SIDESYS_MASTER_KEY')
    if key:
        return key
    
    # Segundo, intentar desde archivo de configuración
    if os.path.exists(MASTER_KEY_FILE):
        try:
            with open(MASTER_KEY_FILE, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key:
                    return key
        except Exception as e:
            print(f"⚠️ Error al leer .master.key: {e}")
    
    # No hay clave → error claro (nunca auto-generar en silencio)
    raise RuntimeError(
        "❌ No se encontró clave maestra.\n"
        "   Define SIDESYS_MASTER_KEY en variables de entorno\n"
        "   O crea un archivo .master.key con la clave de esta instalación."
    )


def obtener_clave_maestra_segura():
    """
    Obtiene la clave maestra SIN generar una nueva si no existe.
    Útil cuando se quiere verificar si la clave está configurada.
    
    RETURNS: La clave maestra o None si no existe
    """
    # Intentar desde variable de entorno
    key = os.environ.get('SIDESYS_MASTER_KEY')
    if key:
        return key
    
    # Intentar desde archivo
    if os.path.exists(MASTER_KEY_FILE):
        try:
            with open(MASTER_KEY_FILE, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key:
                    return key
        except:
            pass
    
    return None

# ============================================================
# FUNCIONES DE ENCRIPTACIÓN CON CLAVE MAESTRA
# ============================================================

def derivar_clave_maestra(password: str, salt: bytes = None) -> bytes:
    """
    Deriva una clave de encriptación a partir de la clave maestra.

    salt=None conserva el salt fijo SOLO como compatibilidad de lectura
    con archivos cifrados antes del cambio. Al cifrar archivos nuevos se
    debe generar y persistir un salt aleatorio por archivo.
    """
    if salt is None:
        salt = SALT_LEGACY
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encriptar_archivo(archivo_origen: str, archivo_destino: str, password: str = None):
    """
    Encripta un archivo usando la clave maestra.

    Cada archivo usa un salt aleatorio propio, persistido en los
    metadatos del archivo cifrado (para poder desencriptarlo después).
    """
    if password is None:
        password = obtener_clave_maestra()
    
    # Salt aleatorio por archivo (nunca el fijo legacy al cifrar)
    salt = _generar_salt()
    key = derivar_clave_maestra(password, salt)
    fernet = Fernet(key)
    
    # Leer archivo
    with open(archivo_origen, 'rb') as f:
        data = f.read()
    
    # Encriptar
    encrypted = fernet.encrypt(data)
    
    # Guardar metadatos (incluye el salt usado)
    meta = {
        'encrypted_with': 'SidesysERP-MasterKey',
        'timestamp': datetime.now().isoformat(),
        'algorithm': 'AES-256-Fernet',
        'version': '2.0',
        'salt': base64.urlsafe_b64encode(salt).decode('ascii')
    }
    
    # Guardar archivo con metadatos
    with open(archivo_destino, 'wb') as f:
        # Guardar metadatos primero
        meta_json = json.dumps(meta).encode()
        f.write(len(meta_json).to_bytes(4, 'big'))
        f.write(meta_json)
        f.write(encrypted)
    
    print(f"✅ Archivo encriptado con clave maestra: {archivo_destino}")
    print(f"   Algoritmo: AES-256 (Fernet)")
    print(f"   ℹ️ Este archivo funciona en CUALQUIER PC")
    return archivo_destino


def desencriptar_archivo(archivo_origen: str, archivo_destino: str, password: str = None) -> bool:
    """
    Desencripta un archivo usando la clave maestra

    Usa el salt guardado en los metadatos si existe (archivos v2);
    si no (archivos v1 legacy), usa el salt fijo de compatibilidad.
    RETURNS: True si éxito, False si falla
    """
    try:
        if password is None:
            password = obtener_clave_maestra()
        
        # Leer archivo (metadatos + datos)
        with open(archivo_origen, 'rb') as f:
            # Leer metadatos
            meta_len = int.from_bytes(f.read(4), 'big')
            meta_json = f.read(meta_len)
            meta = json.loads(meta_json)
            
            # Leer datos encriptados
            encrypted_data = f.read()
        
        # Derivar clave con el salt del archivo (o legacy si es antiguo)
        key = derivar_clave_maestra(password, _salt_desde_meta(meta))
        fernet = Fernet(key)
        
        # Desencriptar
        decrypted = fernet.decrypt(encrypted_data)
        
        # Guardar
        with open(archivo_destino, 'wb') as f:
            f.write(decrypted)
        
        print(f"✅ Archivo desencriptado: {archivo_destino}")
        print(f"   Algoritmo: {meta.get('algorithm', 'AES-256')}")
        return True
        
    except Exception as e:
        print(f"❌ Error al desencriptar: {e}")
        return False


def encriptar_env(env_file: str, output_file: str = None, password: str = None):
    """
    Encripta un archivo .env con la clave maestra
    """
    if output_file is None:
        output_file = env_file + '.encrypted'
    
    return encriptar_archivo(env_file, output_file, password)


def desencriptar_env(encrypted_file: str, output_file: str = None, password: str = None):
    """
    Desencripta un archivo .env.encrypted
    """
    if output_file is None:
        output_file = encrypted_file.replace('.encrypted', '')
    
    return desencriptar_archivo(encrypted_file, output_file, password)

# ============================================================
# GENERAR .ENV DE EJEMPLO
# ============================================================

def generar_env_ejemplo():
    """Genera un archivo .env de ejemplo"""
    env_content = """# ============================================================
# SIDESYS ERP - CONFIGURACIÓN DE BASE DE DATOS
# ============================================================
# 🔴 COMPLETA ESTE ARCHIVO CON TUS CREDENCIALES
#    LUEGO ENCRÍPTALO CON: python crypto_utils.py --encrypt .env
# ============================================================

# ============================================================
# CONFIGURACIÓN DE BASES DE DATOS
# ============================================================
SQL_SERVER=192.168.0.172,1433
SQL_DATABASE=plataforma_rd
SQL_USERNAME=tu_usuario
SQL_PASSWORD=tu_contraseña
SQL_SERVER_PLATAFORMA=192.168.0.172,1433

# ============================================================
# CONFIGURACIÓN POR PAÍS (Usa las mismas credenciales)
# ============================================================
UY_SERVER=192.168.0.172,1433
UY_USER=tu_usuario
UY_PASS=tu_contraseña

RD_SERVER=192.168.0.172,1433
RD_USER=tu_usuario
RD_PASS=tu_contraseña

HN_SERVER=192.168.0.172,1433
HN_USER=tu_usuario
HN_PASS=tu_contraseña

GT_SERVER=192.168.0.172,1433
GT_USER=tu_usuario
GT_PASS=tu_contraseña

CO_SERVER=192.168.0.172,1433
CO_USER=tu_usuario
CO_PASS=tu_contraseña

PE_SERVER=192.168.0.172,1433
PE_USER=tu_usuario
PE_PASS=tu_contraseña

PY_SERVER=192.168.0.172,1433
PY_USER=tu_usuario
PY_PASS=tu_contraseña

EC_SERVER=192.168.0.172,1433
EC_USER=tu_usuario
EC_PASS=tu_contraseña

MX_SERVER=192.168.0.172,1433
MX_USER=tu_usuario
MX_PASS=tu_contraseña

CR_SERVER=192.168.0.172,1433
CR_USER=tu_usuario
CR_PASS=tu_contraseña

AR_SERVER=192.168.0.172,1433
AR_USER=tu_usuario
AR_PASS=tu_contraseña

# ============================================================
# CONFIGURACIÓN DE SEGURIDAD (GENERADO AUTOMÁTICAMENTE)
# ============================================================
FLASK_DEBUG=False

# ============================================================
# 🔴 CLAVE MAESTRA - OBLIGATORIA (NO se genera automáticamente)
# ============================================================
# Debe ser ÚNICA por instalación/despliegue y guardarse fuera del repo.
# Opción A - variable de entorno (recomendada):
#   setx SIDESYS_MASTER_KEY "TuClaveUnicaLargaYSegura"
# Opción B - archivo .master.key (creado con --generate-key o a mano).
# Generar una clave aleatoria:
#   python crypto_utils.py --generate-key
"""
    
    with open('.env.ejemplo', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("✅ Archivo .env.ejemplo creado")
    print("   📝 Edita este archivo con tus credenciales")
    print("   🔑 Define SIDESYS_MASTER_KEY (única por instalación) o crea .master.key")
    print("   🔐 Luego ejecuta: python crypto_utils.py --encrypt .env.ejemplo")
    return '.env.ejemplo'

# ============================================================
# FUNCIÓN PARA MOSTRAR LA CLAVE MAESTRA
# ============================================================

def mostrar_clave_maestra():
    """
    Muestra la clave maestra actual (útil para auditoría)
    """
    key = obtener_clave_maestra_segura()
    if key:
        print("\n" + "=" * 60)
        print("  🔑 CLAVE MAESTRA ACTUAL")
        print("=" * 60)
        print(f"  {key}")
        print("=" * 60)
        print()
        print("  📁 Archivo: .master.key")
        print("  ⚠️ GUARDA ESTA CLAVE EN UN LUGAR SEGURO")
        print("  ⚠️ NO LA COMPARTAS")
        return key
    else:
        print("\n⚠️ No hay clave maestra configurada.")
        print("   Defínela con SIDESYS_MASTER_KEY (única por instalación)")
        print("   o genérala con: python crypto_utils.py --generate-key")
        return None

# ============================================================
# INTERFAZ DE LÍNEA DE COMANDOS
# ============================================================

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Utilidades de encriptación con clave maestra')
    parser.add_argument('--encrypt', help='Encripta un archivo .env')
    parser.add_argument('--decrypt', help='Desencripta un archivo .env.encrypted')
    parser.add_argument('--generate', action='store_true', help='Genera archivo .env de ejemplo')
    parser.add_argument('--output', help='Archivo de salida (opcional)')
    parser.add_argument('--password', help='Clave maestra (opcional)')
    parser.add_argument('--show-key', action='store_true', help='Muestra la clave maestra actual')
    parser.add_argument('--generate-key', action='store_true', help='Genera una nueva clave maestra')
    
    args = parser.parse_args()
    
    if args.show_key:
        mostrar_clave_maestra()
        sys.exit(0)
    
    if args.generate_key:
        print("🔑 Generando nueva clave maestra...")
        nueva_clave = _generar_y_guardar_clave_maestra()
        print(f"\n✅ Nueva clave generada: {nueva_clave}")
        print(f"   Guardada en: {MASTER_KEY_FILE}")
        sys.exit(0)
    
    if args.generate:
        generar_env_ejemplo()
        sys.exit(0)
    
    if args.encrypt:
        encriptar_env(args.encrypt, args.output, args.password)
        sys.exit(0)
    
    if args.decrypt:
        desencriptar_env(args.decrypt, args.output, args.password)
        sys.exit(0)
    
    print("""
    ============================================================
    UTILIDADES DE ENCRIPTACIÓN CON CLAVE MAESTRA - SIDESYS ERP
    ============================================================
    
    Uso:
    
    1. (Recomendado) Definir la clave maestra ÚNICA por instalación:
       setx SIDESYS_MASTER_KEY "TuClaveUnicaLargaYSegura"
       O generar y guardar en .master.key:
       python crypto_utils.py --generate-key
    
    2. Generar archivo .env de ejemplo:
       python crypto_utils.py --generate
    
    3. Encriptar archivo .env (con la clave maestra definida):
       python crypto_utils.py --encrypt .env.ejemplo
    
    4. Desencriptar archivo:
       python crypto_utils.py --decrypt .env.encrypted
    
    5. Ver la clave maestra actual:
       python crypto_utils.py --show-key
    
    6. Usar contraseña personalizada (no recomendado en producción):
       python crypto_utils.py --encrypt .env --password "MiClaveSegura"
    
    🔑  La clave maestra NO se genera automáticamente: debe definirse
        por instalación (SIDESYS_MASTER_KEY o .master.key).
    🔐  Cada archivo cifrado usa un salt aleatorio propio.
    📁  .master.key NO se sube a Git.
    ============================================================
    """)