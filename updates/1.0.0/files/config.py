# config.py
# ============================================================
# CONFIGURACIÓN - SIDESYS ERP
# ============================================================
# Carga configuraciones desde .env (normal o encriptado)
# ============================================================

import os
import sys
import base64
from dotenv import load_dotenv

# ============================================================
# FUNCIONES PARA DESENCRIPTAR .env EN MEMORIA
# ============================================================

# Salt usado SOLO para leer archivos cifrados ANTES del cambio a
# salt aleatorio por archivo (retrocompatibilidad). NO usar al cifrar.
SALT_LEGACY = b'sidesys_erp_master_salt_2026'

def _salt_desde_meta(meta):
    """Obtiene el salt de los metadatos (base64). Si no está, usa legacy."""
    salt_b64 = meta.get('salt')
    if salt_b64:
        try:
            return base64.urlsafe_b64decode(salt_b64)
        except Exception:
            pass
    return SALT_LEGACY

def derivar_clave_maestra(password: str, salt: bytes = None) -> bytes:
    """
    Deriva la clave de encriptación de la clave maestra.

    salt=None conserva el salt fijo SOLO como compatibilidad de lectura
    con archivos cifrados antes del cambio. Al cifrar archivos nuevos se
    debe generar y persistir un salt aleatorio por archivo.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    
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

def obtener_clave_maestra():
    """
    Obtiene la clave maestra desde variable de entorno o archivo.

    🔴 NO genera claves automáticamente ni usa fallback hardcodeado:
    si no existe, lanza error con instrucciones.
    """
    # Primero intentar desde variable de entorno
    key = os.environ.get('SIDESYS_MASTER_KEY')
    if key:
        return key
    
    # Segundo, intentar desde archivo de configuración
    key_file = os.path.join(os.path.dirname(__file__), '.master.key')
    if os.path.exists(key_file):
        with open(key_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    # No hay clave → error claro (nunca un fallback hardcodeado)
    raise RuntimeError(
        "❌ No se encontró clave maestra.\n"
        "   Define SIDESYS_MASTER_KEY en variables de entorno\n"
        "   O crea un archivo .master.key con la clave de esta instalación."
    )

def cargar_env_encriptado(env_file):
    """
    Carga un archivo .env encriptado en memoria
    """
    try:
        from cryptography.fernet import Fernet
        import json
        
        # Obtener clave maestra
        password = obtener_clave_maestra()
        
        # Leer archivo encriptado (metadatos + datos)
        with open(env_file, 'rb') as f:
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
        
        # Cargar en variables de entorno
        import io
        from dotenv import load_dotenv
        
        env_content = decrypted.decode('utf-8')
        load_dotenv(stream=io.StringIO(env_content))
        
        print(f"[INFO] Configuración cargada desde: {env_file} (encriptado)")
        print(f"   Algoritmo: {meta.get('algorithm', 'AES-256')}")
        return True
        
    except Exception as e:
        print(f"❌ Error al cargar configuración encriptada: {e}")
        return False

# ============================================================
# CARGA DE CONFIGURACIÓN - CORREGIDO
# ============================================================

# Buscar .env.local en el directorio actual
ENV_FILE = ".env.local"

# ============================================================
# INTENTAR CARGAR .env.local ENCRIPTADO
# ============================================================
PROGRAM_DATA = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
SIDESYS_DIR = os.path.join(PROGRAM_DATA, "SidesysERP")
ENV_ENCRYPTED_FILE = os.path.join(SIDESYS_DIR, ".env.local")

# Si existe el archivo encriptado en ProgramData, cargarlo
if os.path.exists(ENV_ENCRYPTED_FILE):
    if cargar_env_encriptado(ENV_ENCRYPTED_FILE):
        print(f"[INFO] Configuración cargada desde: {ENV_ENCRYPTED_FILE}")
    else:
        print("[ERROR] No se pudo cargar configuración encriptada")
        print("   Verifica que el archivo .env.local en ProgramData sea válido")
        sys.exit(1)

# ============================================================
# SI NO HAY ENCRIPTADO, USAR .env.local NORMAL (DESARROLLO)
# ============================================================
elif os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE)
    print(f"[INFO] Configuración cargada desde: {ENV_FILE} (modo desarrollo)")

else:
    print("❌ ERROR: No se encontró .env.local")
    print("   Copia .env.example a .env.local y completa con tus credenciales")
    print("   O asegúrate de que el archivo encriptado esté en ProgramData")
    sys.exit(1)

# ============================================================
# FUNCIÓN PARA VALIDAR VARIABLES REQUERIDAS - CORREGIDO
# ============================================================

def get_required_env(key):
    """Obtiene una variable de entorno requerida. Si no existe, termina la ejecución."""
    value = os.environ.get(key)
    if value is None:
        print(f"❌ ERROR: Variable de entorno {key} no definida")
        print("   Asegúrate de tener todas las variables necesarias en tu configuración")
        print(f"   Ejecuta: echo %{key}% para verificar")
        sys.exit(1)
    return value

def get_env(key, default=None):
    """Obtiene una variable de entorno con valor por defecto."""
    return os.environ.get(key, default)

# ============================================================
# VALIDACIÓN DE VARIABLES CRÍTICAS - NUEVO
# ============================================================

# Verificar que las variables críticas existan
CRITICAL_VARS = ['SQL_SERVER', 'SQL_DATABASE', 'SQL_USERNAME', 'SQL_PASSWORD']
for var in CRITICAL_VARS:
    get_required_env(var)

# Verificar que la contraseña no esté vacía
SQL_PASSWORD = os.environ.get('SQL_PASSWORD', '')
if not SQL_PASSWORD or SQL_PASSWORD == '':
    print("❌ ERROR: SQL_PASSWORD no puede estar vacía")
    sys.exit(1)

# ============================================================
# CONFIGURACIÓN DE BASES DE DATOS
# ============================================================

print("[INFO] Cargando configuración de bases de datos...")

SQL_SERVER = get_required_env("SQL_SERVER")
SQL_DATABASE = get_required_env("SQL_DATABASE")
SQL_USERNAME = get_required_env("SQL_USERNAME")
SQL_PASSWORD = get_required_env("SQL_PASSWORD")
SQL_SERVER_PLATAFORMA = get_env("SQL_SERVER_PLATAFORMA", SQL_SERVER)

# C8: cifrado en tránsito hacia SQL Server (Encrypt). Default 'no' para no
# romper drivers legacy ({SQL Server}) que no reconocen el keyword Encrypt.
# Activar con SQL_ENCRYPT=yes (idealmente migrando a ODBC Driver 18 + cert de
# CA real; con cert self-signed mantener TrustServerCertificate=yes).
SQL_ENCRYPT_ACTIVO = get_env("SQL_ENCRYPT", "no").strip().lower() in ('1', 'yes', 'true', 'on')

print(f"[INFO] SQL_SERVER = {SQL_SERVER}")
print(f"[INFO] SQL_DATABASE = {SQL_DATABASE}")
print(f"[INFO] SQL_USERNAME = {SQL_USERNAME}")
# 🔴 NUNCA imprimir contraseñas en logs

# ============================================================
# BASES DISPONIBLES
# ============================================================

BASES_DISPONIBLES = {
    "plataforma_ur": {
        "label": "Uruguay",
        "sigla": "UY",
        "server": get_env("UY_SERVER", SQL_SERVER),
        "user": get_env("UY_USER", SQL_USERNAME),
        "password": get_env("UY_PASS", SQL_PASSWORD),
        "division": 6,
        "sucursal": 1
    },
    "plataforma_rd": {
        "label": "República Dominicana",
        "sigla": "RD",
        "server": get_env("RD_SERVER", SQL_SERVER),
        "user": get_env("RD_USER", SQL_USERNAME),
        "password": get_env("RD_PASS", SQL_PASSWORD),
        "division": 5,
        "sucursal": 5,
        # sucursal empresa (MOST_SUCURSAL_EMP → SIST_SUEM): en RD la impresora es
        # 5 pero la empresa es 4 (DOMINICANA); sin esto el ajuste/transferencia
        # de stock rompe la FK SUEM_R05.
        "sucursal_emp": 4
    },
    "plataforma_hn": {
        "label": "Honduras",
        "sigla": "HN",
        "server": get_env("HN_SERVER", SQL_SERVER),
        "user": get_env("HN_USER", SQL_USERNAME),
        "password": get_env("HN_PASS", SQL_PASSWORD),
        "division": 10,
        "sucursal": 1
    },
    "plataforma_gt": {
        "label": "Guatemala",
        "sigla": "GT",
        "server": get_env("GT_SERVER", SQL_SERVER),
        "user": get_env("GT_USER", SQL_USERNAME),
        "password": get_env("GT_PASS", SQL_PASSWORD),
        "division": 7,
        "sucursal": 8
    },
    "plataforma_co": {
        "label": "Colombia",
        "sigla": "CO",
        "server": get_env("CO_SERVER", SQL_SERVER),
        "user": get_env("CO_USER", SQL_USERNAME),
        "password": get_env("CO_PASS", SQL_PASSWORD),
        "division": 9,
        "sucursal": 9
    },
    "plataforma_pe": {
        "label": "Perú",
        "sigla": "PE",
        "server": get_env("PE_SERVER", SQL_SERVER),
        "user": get_env("PE_USER", SQL_USERNAME),
        "password": get_env("PE_PASS", SQL_PASSWORD),
        "division": 12,
        "sucursal": 1
    },
    "plataforma_py": {
        "label": "Paraguay",
        "sigla": "PY",
        "server": get_env("PY_SERVER", SQL_SERVER),
        "user": get_env("PY_USER", SQL_USERNAME),
        "password": get_env("PY_PASS", SQL_PASSWORD),
        "division": 11,
        "sucursal": 7
    },
    "plataforma_ec": {
        "label": "Ecuador",
        "sigla": "EC",
        "server": get_env("EC_SERVER", SQL_SERVER),
        "user": get_env("EC_USER", SQL_USERNAME),
        "password": get_env("EC_PASS", SQL_PASSWORD),
        "division": 8,
        "sucursal": 1
    },
    "plataforma_mx": {
        "label": "México",
        "sigla": "MX",
        "server": get_env("MX_SERVER", SQL_SERVER),
        "user": get_env("MX_USER", SQL_USERNAME),
        "password": get_env("MX_PASS", SQL_PASSWORD),
        "division": 4,
        "sucursal": 4
    },
    "plataforma_cr": {
        "label": "Costa Rica",
        "sigla": "CR",
        "server": get_env("CR_SERVER", SQL_SERVER),
        "user": get_env("CR_USER", SQL_USERNAME),
        "password": get_env("CR_PASS", SQL_PASSWORD),
        "division": 6,
        "sucursal": 7
    },
    "plataforma": {
        "label": "Argentina",
        "sigla": "AR",
        "server": get_env("AR_SERVER", SQL_SERVER_PLATAFORMA),
        "user": get_env("AR_USER", SQL_USERNAME),
        "password": get_env("AR_PASS", SQL_PASSWORD),
        "sociedades": {
            "sidesys": {"label": "Sidesys", "division": 1, "sucursal": 1},
            "advansur": {"label": "Advansur", "division": 2, "sucursal": 1},
        },
    },
}

BASE_DEFAULT = SQL_DATABASE if SQL_DATABASE in BASES_DISPONIBLES else "plataforma_rd"
SOCIEDAD_DEFAULT = "sidesys"

print(f"[INFO] BASE_DEFAULT = {BASE_DEFAULT}")
print(f"[INFO] SOCIEDAD_DEFAULT = {SOCIEDAD_DEFAULT}")

# ============================================================
# BASES PARA COTIZACIONES (CxP)
# ============================================================

BASES_COTI = {
    "GT": "plataforma_gt",
    "HN": "plataforma_hn",
    "RD": "plataforma_rd",
    "UY": "plataforma_ur",
    "CO": "plataforma_co",
    "PE": "plataforma_pe",
    "PY": "plataforma_py",
    "EC": "plataforma_ec",
    "MX": "plataforma_mx",
    "CR": "plataforma_cr",
    "AR": "plataforma",
}

# ============================================================
# TESSERACT
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TESSERACT_PATH = os.path.join(BASE_DIR, "tesseract", "tesseract.exe")

# ============================================================
# CATEGORÍAS DE ARTÍCULOS
# ============================================================

CATEGORIAS_ARTICULO = {
    "-": {"nombre": "No disponible", "con_partidas_default": False},
    "001": {"nombre": "Cables", "con_partidas_default": False},
    "002": {"nombre": "Kioscos", "con_partidas_default": True},
    "003": {"nombre": "Impresoras", "con_partidas_default": True},
    "004": {"nombre": "Cabezales", "con_partidas_default": True},
    "005": {"nombre": "Memoria", "con_partidas_default": True},
    "006": {"nombre": "Garantía Anual", "con_partidas_default": False},
    "007": {"nombre": "Tablet", "con_partidas_default": True},
    "008": {"nombre": "Botones", "con_partidas_default": True},
    "009": {"nombre": "Licencias", "con_partidas_default": False},
    "010": {"nombre": "Monitores", "con_partidas_default": True},
    "011": {"nombre": "Gastos Asociados", "con_partidas_default": False},
    "012": {"nombre": "Repuestos", "con_partidas_default": True},
    "013": {"nombre": "Televisores", "con_partidas_default": True},
    "014": {"nombre": "Mini PC", "con_partidas_default": True},
}

CUENTAS_POR_ORIGEN = {
    "local": {"arts": "1106", "compra": "1106", "venta": "410101"},
    "exterior": {"arts": "110701", "compra": "110701", "venta": "410101"},
}

# ============================================================
# COLUMNAS PARA UY
# ============================================================
_UY_COLS = {
    "ZF": [1],
    "FABRICA": [6, 8],
    "TRANSITO": [7, 10, 14, 9, 13, 11, 12],
}
_BASES_CONSOLIDADO = [b for b in BASES_DISPONIBLES if b != "plataforma_ur"]

print("[INFO] Configuración cargada correctamente")
print("=" * 60)