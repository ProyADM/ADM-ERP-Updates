# modules/reportes/services/utils.py
# ============================================================
# UTILIDADES PARA REPORTES
# ============================================================

import pyodbc
import pandas as pd
import logging
import os
from datetime import datetime, timedelta
from config import SQL_SERVER, SQL_USERNAME, SQL_PASSWORD, BASES_DISPONIBLES, SQL_ENCRYPT_ACTIVO
from modules.shared.database import get_db_context

logger = logging.getLogger(__name__)

# ============================================================
# VENTAS MANUALES: BASE CANÓNICA FIJA EN EL CÓDIGO (23/09/2026)
# ============================================================
# La tabla VENTAS_MANUALES guarda las ventas de TODOS los países, así que no
# puede vivir "en la base activa": si vivía ahí, cargar una venta de México
# estando parado en RD la guardaba en la base equivocada (bug real: una venta de
# RD quedó dentro de la base Argentina) y el Consolidado Total la perdía según
# desde dónde se mirara.
#
# El 17/09/2026 se arregló que TODAS las operaciones ignoraran la base activa,
# pero la canónica se resolvía con el `BASE_DEFAULT` de CADA instalación (sale
# del `.env.local` de cada PC). Una PC con otro default escribía en OTRA tabla y
# sus ventas dejaban de verse desde el resto: el mismo bug, en silencio y sólo
# con un warning en el log.
#
# Ahora la canónica es una CONSTANTE DEL CÓDIGO
# (`ventas_manuales_base.BASE_CANONICA_VENTAS_MANUALES` = 'plataforma_rd'), igual
# en todas las instalaciones y sin tocar ningún `.env.local`. La decisión vive en
# el módulo puro `ventas_manuales_base.resolver()` y depende de si es lectura o
# escritura:
#   · ESCRIBIR sin acceso a la canónica -> `ErrorBaseVentasManuales` con el
#     `MENSAJE_SIN_PERMISO` (nunca más una venta en una tabla que los demás no
#     ven);
#   · LEER sin acceso -> cae a la base de antes CON AVISO en el log (leer sigue
#     funcionando).
# `VENTAS_MANUALES_BASE` (variable de entorno) queda como override explícito de
# despliegue para mover la canónica de servidor; `BASE_DEFAULT` ya no decide nada
# acá (sigue con su semántica en el resto de la app).

class ErrorBaseVentasManuales(RuntimeError):
    """La operación de ESCRITURA no puede usar la base canónica de ventas manuales.

    Se levanta cuando el usuario no alcanza `BASE_CANONICA_VENTAS_MANUALES` y la
    operación es de escritura: el mensaje (`MENSAJE_SIN_PERMISO`) llega tal cual a
    la pantalla, porque los servicios devuelven `{'success': False, 'error':
    str(e)}` y las rutas hacen `jsonify(resultado)`.
    """


def base_ventas_manuales(para_escritura=False):
    """Nombre de la base donde vive VENTAS_MANUALES (ver bloque de arriba).

    Junta los datos de acá (entorno, permisos de la sesión, `config.BASE_DEFAULT` y
    el catálogo `config.BASES_DISPONIBLES`) y delega la DECISIÓN en el módulo puro
    `ventas_manuales_base.resolver()`: acá se conecta, allá se decide. El aviso del
    resolver va al log; si es escritura y vuelve error, se levanta
    `ErrorBaseVentasManuales` para que no se guarde nada.
    """
    from config import BASE_DEFAULT as _BASE_DEFAULT, BASES_DISPONIBLES
    from . import ventas_manuales_base

    # Bases permitidas del usuario de la sesión, si hay sesión (None = todas).
    permitidas = None
    try:
        from modules.shared.decorators import bases_permitidas_actuales
        permitidas = bases_permitidas_actuales()
    except Exception:
        permitidas = None

    # El CATÁLOGO lo pasa el llamador: el módulo puro no importa `config` (si lo
    # importara, un cwd sin `.env.local` lo haría morir con `SystemExit`, que no
    # es `Exception`). Acá `config` ya está importado arriba, así que es gratis.
    base, error, aviso = ventas_manuales_base.resolver(
        permitidas, _BASE_DEFAULT,
        override=os.environ.get('VENTAS_MANUALES_BASE'),
        escritura=para_escritura,
        catalogo=BASES_DISPONIBLES)

    if aviso:
        logger.warning(aviso)
    if error:
        logger.error('Ventas manuales: %s' % error)
        raise ErrorBaseVentasManuales(error)
    return base


def get_db_connection_ventas_manuales(para_escritura=False):
    """Conexión a la base CANÓNICA de ventas manuales (ignora la base activa).

    `para_escritura=True` en crear/borrar/importar/asegurar la tabla: ahí no se
    acepta una base sustituta (ver `base_ventas_manuales`).
    """
    base = base_ventas_manuales(para_escritura=para_escritura)
    return get_db_connection_base(base)


# ============================================================
# CONEXIONES A BASE DE DATOS
# ============================================================

def get_db_connection():
    """Obtiene conexión a la base activa (contexto)"""
    try:
        server, database, division, sucursal = get_db_context()
        logger.info(f"Conectando a: {server} / {database} / División: {division}")
        conn = pyodbc.connect(
            'DRIVER={SQL Server};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={SQL_USERNAME};'
            f'PWD={SQL_PASSWORD};'
            'TrustServerCertificate=yes;'
            + ('Encrypt=yes;' if SQL_ENCRYPT_ACTIVO else '')
            + 'Timeout=10;'
            + 'Connect Timeout=10;'
        )
        return conn, division
    except Exception as e:
        # Detalle completo SOLO al log; el cliente recibe mensaje genérico.
        logger.error(f"Error de conexión: {e}")
        raise RuntimeError("Error de conexión a la base de datos")

def _validar_base_solicitada(database, sociedad=None):
    """
    Valida que la base pedida exista en la whitelist BASES_DISPONIBLES
    (evita inyección en connection string / SSRF por el parámetro base).
    Para Argentina (plataforma) valida también la sociedad.
    Retorna el dict de info de la base.
    """
    info = BASES_DISPONIBLES.get(database)
    if info is None:
        raise RuntimeError(
            f"Base de datos no permitida: '{database}'. "
            f"Bases válidas: {', '.join(BASES_DISPONIBLES.keys())}"
        )
    if database == 'plataforma':
        sociedades = info.get('sociedades', {})
        sociedad_efectiva = sociedad or 'sidesys'
        if sociedad_efectiva not in sociedades:
            raise RuntimeError(
                f"Sociedad no permitida para la base '{database}': '{sociedad_efectiva}'. "
                f"Sociedades válidas: {', '.join(sociedades.keys())}"
            )
    return info

def get_db_connection_base(database, sociedad=None):
    """
    Obtiene conexión a una base específica.
    Retorna (conn, division)
    """
    try:
        info = _validar_base_solicitada(database, sociedad)
        server = info.get("server") or SQL_SERVER

        # Si es Argentina y no se especificó sociedad, usar sidesys
        if database == 'plataforma' and not sociedad:
            sociedad = 'sidesys'

        # Calcular división
        division = 5  # valor por defecto
        if database == 'plataforma' and sociedad:
            sociedades = info.get('sociedades', {})
            soc_info = sociedades.get(sociedad)
            if soc_info:
                division = soc_info.get('division', 1)
        else:
            division = info.get('division', 5)

        conn = pyodbc.connect(
            'DRIVER={SQL Server};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={SQL_USERNAME};'
            f'PWD={SQL_PASSWORD};'
            'TrustServerCertificate=yes;'
            + ('Encrypt=yes;' if SQL_ENCRYPT_ACTIVO else '')
            + 'Timeout=10;'
            + 'Connect Timeout=10;'
        )
        return conn, division
    except RuntimeError:
        # Base/sociedad no permitida: mensaje seguro, propagar tal cual.
        logger.warning(f"Intento de conexión a base no permitida: {database}")
        raise
    except Exception as e:
        # Detalle completo SOLO al log; el cliente recibe mensaje genérico.
        logger.error(f"Error de conexión a {database}: {e}")
        raise RuntimeError("Error de conexión a la base de datos")

# ============================================================
# LIMPIEZA DE DATOS (DataFrames)
# ============================================================

def limpiar_datos(df):
    """Limpia un DataFrame de valores no válidos y convierte tipos"""
    if df.empty:
        return df
    df = df.replace([float('inf'), float('-inf')], None)
    df = df.where(pd.notnull(df), None)
    for col in df.select_dtypes(include=['float64', 'float32', 'int64', 'int32']).columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df[col] = df[col].where(pd.notnull(df[col]), 0)
    for col in df.select_dtypes(include=['datetime64', 'datetime64[ns]']).columns:
        df[col] = df[col].astype(str)
    return df

# ============================================================
# COTIZACIÓN POR MES (para conversión de moneda local a USD)
# ============================================================

def obtener_cotizacion_por_mes(anio, mes, base_referencia='plataforma_rd'):
    """
    Obtiene la cotización DL→PS más reciente hasta el último día del mes dado,
    en la base de referencia (por defecto RD). 
    Si no hay cotización en ese mes, busca la última disponible anterior.
    Retorna el valor de cotización (float) o None si no hay.
    """
    try:
        # Último día del mes
        if mes == 12:
            ultimo_dia = datetime(anio, mes, 31)
        else:
            ultimo_dia = datetime(anio, mes + 1, 1) - timedelta(days=1)
        fecha_limite = ultimo_dia.strftime('%Y-%m-%d')

        # Conectar a la base de referencia
        conn, _ = get_db_connection_base(base_referencia)
        cursor = conn.cursor()

        query = """
            SELECT TOP 1 COTI_COTIZACION 
            FROM SIST_COTI 
            WHERE COTI_MONEDA1 = 'DL' AND COTI_MONEDA2 = 'PS'
              AND COTI_FECHA <= ?
            ORDER BY COTI_FECHA DESC
        """
        cursor.execute(query, (fecha_limite,))
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            valor = float(row[0])
            logger.info(f"Cotización para {anio}-{mes:02d}: {valor} (última <= {fecha_limite})")
            return valor
        else:
            logger.warning(f"No se encontró cotización para {anio}-{mes:02d} (hasta {fecha_limite})")
            return None

    except Exception as e:
        logger.error(f"Error obteniendo cotización para {anio}-{mes:02d}: {e}")
        return None

# ============================================================
# ASEGURAR TABLA VENTAS_MANUALES (en la base activa)
# ============================================================

def asegurar_tabla_ventas_manuales(para_escritura=False):
    """Crea la tabla VENTAS_MANUALES en la base CANÓNICA (no en la activa).

    `para_escritura=True` cuando la llama una operación de escritura: el chequeo
    de tabla de una escritura tiene que usar la misma base que la escritura (y
    fallar igual si no se alcanza la canónica). Las lecturas la llaman con
    `False`, así pueden seguir cayendo a la base anterior con aviso.
    """
    try:
        conn, _ = get_db_connection_ventas_manuales(para_escritura=para_escritura)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM sys.objects 
            WHERE object_id = OBJECT_ID(N'[dbo].[VENTAS_MANUALES]') AND type in (N'U')
        """)
        existe = cursor.fetchone()[0] > 0

        if not existe:
            cursor.execute("""
                CREATE TABLE VENTAS_MANUALES (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    base NVARCHAR(50) NOT NULL,
                    sociedad NVARCHAR(50) NULL,
                    anio INT NOT NULL,
                    mes INT NOT NULL,
                    pais NVARCHAR(100) NOT NULL,
                    centro_costo NVARCHAR(100) NULL,
                    importe_usd DECIMAL(18,2) NOT NULL DEFAULT 0,
                    importe_ps DECIMAL(18,2) NOT NULL DEFAULT 0,
                    fecha_registro DATE NOT NULL,
                    comentario NVARCHAR(255) NULL,
                    usuario NVARCHAR(100) NOT NULL,
                    fecha_creacion DATETIME DEFAULT GETDATE()
                )
                CREATE INDEX IX_VENTAS_MANUALES_BaseAnioMes ON VENTAS_MANUALES (base, anio, mes)
                CREATE INDEX IX_VENTAS_MANUALES_Pais ON VENTAS_MANUALES (pais)
            """)
            conn.commit()
            logger.info("✅ Tabla VENTAS_MANUALES creada")
        else:
            # Verificar columnas
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'VENTAS_MANUALES' AND COLUMN_NAME = 'importe'
            """)
            if cursor.fetchone()[0] > 0:
                cursor.execute("ALTER TABLE VENTAS_MANUALES DROP COLUMN importe")
                logger.info("✅ Columna 'importe' eliminada")

            columnas_existentes = []
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'VENTAS_MANUALES'")
            for row in cursor.fetchall():
                columnas_existentes.append(row[0].lower())

            columnas_requeridas = {
                'sociedad': 'NVARCHAR(50) NULL',
                'centro_costo': 'NVARCHAR(100) NULL',
                'importe_usd': 'DECIMAL(18,2) NOT NULL DEFAULT 0',
                'importe_ps': 'DECIMAL(18,2) NOT NULL DEFAULT 0'
            }
            for col, tipo in columnas_requeridas.items():
                if col not in columnas_existentes:
                    cursor.execute(f"ALTER TABLE VENTAS_MANUALES ADD {col} {tipo}")
                    logger.info(f"✅ Columna {col} agregada")

            conn.commit()
            logger.info("✅ Tabla VENTAS_MANUALES verificada")

        conn.close()
    except ErrorBaseVentasManuales:
        # No hay acceso a la canónica: no es "no se pudo asegurar la tabla", es el
        # error de permiso. Se propaga tal cual para que el usuario vea el mensaje
        # y el log no quede con un warning engañoso encima del error real.
        raise
    except Exception as e:
        logger.warning(f"⚠️ No se pudo asegurar la tabla VENTAS_MANUALES: {e}")