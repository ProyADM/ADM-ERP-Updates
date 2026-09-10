# modules/reportes/services/utils.py
# ============================================================
# UTILIDADES PARA REPORTES
# ============================================================

import pyodbc
import pandas as pd
import logging
from datetime import datetime, timedelta
from config import SQL_SERVER, SQL_USERNAME, SQL_PASSWORD, BASES_DISPONIBLES, SQL_ENCRYPT_ACTIVO
from modules.shared.database import get_db_context

logger = logging.getLogger(__name__)

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

def asegurar_tabla_ventas_manuales():
    """Crea o actualiza la tabla VENTAS_MANUALES en la base activa"""
    try:
        conn, _ = get_db_connection()
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
    except Exception as e:
        logger.warning(f"⚠️ No se pudo asegurar la tabla VENTAS_MANUALES: {e}")