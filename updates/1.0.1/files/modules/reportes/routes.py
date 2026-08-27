# modules/reportes/routes.py - VERSIÓN CORREGIDA
# ============================================================
# REPORTES - SIDESYS ERP (CONSULTAS PARAMETRIZADAS)
# ============================================================

from flask import Blueprint, jsonify, request, g
import pyodbc
import pandas as pd
import logging
from config import SQL_SERVER, SQL_USERNAME, SQL_PASSWORD, BASES_DISPONIBLES
from modules.shared.database import get_db_context
from modules.reportes.config_clientes import (
    get_clientes_forzados_ps, 
    get_clientes_forzados_dl,
    get_tipo_cliente_excluir,
    get_clientes_excluir_consolidado
)
import traceback
import sys
from datetime import datetime

reportes_bp = Blueprint('reportes', __name__)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Obtener conexión a la base de datos usando el contexto activo"""
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
        )
        return conn, division
    except Exception as e:
        logger.error(f"Error de conexión: {e}")
        raise

def get_db_connection_base(database, sociedad=None):
    """Obtener conexión a una base específica"""
    try:
        info = BASES_DISPONIBLES.get(database, {})
        server = info.get("server") or SQL_SERVER
        
        if database == 'plataforma' and not sociedad:
            sociedad = 'sidesys'
        
        division = 5
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
        )
        return conn, division
    except Exception as e:
        logger.error(f"Error de conexión: {e}")
        raise

def limpiar_datos(df):
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
# REPORTE: AÑOS DISPONIBLES
# ============================================================

@reportes_bp.route('/reportes/anos', methods=['GET'])
def get_anos_disponibles():
    try:
        base_param = request.args.get('base')
        sociedad_param = request.args.get('sociedad')
        if base_param:
            conn, division = get_db_connection_base(base_param, sociedad_param)
        else:
            conn, division = get_db_connection()
        
        cursor = conn.cursor()
        # 🔴 CORREGIDO: Consulta parametrizada
        cursor.execute("""
            SELECT DISTINCT YEAR(COFF_FECHA_EST_FC) AS ANIO
            FROM dbo.ACCT_COFF
            WHERE COFF_FECHA_EST_FC IS NOT NULL
              AND YEAR(COFF_FECHA_EST_FC) >= 2020
            ORDER BY ANIO DESC
        """)
        anos = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not anos:
            ano_actual = datetime.now().year
            anos = [ano_actual, ano_actual - 1, ano_actual - 2, ano_actual - 3, ano_actual - 4]
        
        return jsonify({'success': True, 'anos': anos})
    except Exception as e:
        logger.error(f"Error en get_anos_disponibles: {e}")
        return jsonify({'success': False, 'error': str(e), 'anos': []}), 500

# ============================================================
# REPORTE: CONTRATOS (PENDIENTE DE FACTURAR) - CORREGIDO
# ============================================================

@reportes_bp.route('/reportes/contratos', methods=['POST'])
def get_reporte_contratos():
    """Reporte de Pendiente de Facturar"""
    try:
        data = request.get_json() or {}
        anio = data.get('anio')
        mes = data.get('mes')
        base_override = data.get('base')
        sociedad_override = data.get('sociedad')
        
        if base_override:
            conn, division = get_db_connection_base(base_override, sociedad_override)
        else:
            conn, division = get_db_connection()
        
        # 🔴 CORREGIDO: Consulta parametrizada
        query = """
        SELECT 
            CONCAT(ca.COCA_TIPO_TCAC, '-', ca.COCA_NUMERO_COCA) AS CONTRATO,
            COALESCE(ci.IMAE_DESCRIPCION2, ci.IMAE_DESCRIPCION1, 'SIN CLIENTE') AS CLIENTE,
            COALESCE(ci.IMAE_DESCRIPCION3, 'SIN CONCEPTO') AS CENTRO_COSTO,
            COALESCE(cd.CODF_MONEDA, 'SIN MONEDA') AS MONEDA,
            YEAR(cf.COFF_FECHA_EST_FC) AS ANIO,
            MONTH(cf.COFF_FECHA_EST_FC) AS MES,
            SUM(cp.COCP_CANTIDAD * cp.COCP_PRECIO_ORI) AS IMPORTE
        FROM dbo.ACCT_COFF cf
        INNER JOIN dbo.ACCT_COCA ca ON cf.COFF_NUMINT_COCA = ca.COCA_NUMINT_COCA
        INNER JOIN dbo.ACCT_COCP cp ON cf.COFF_NUMINT_COCA = cp.COCP_NUMINT_COCA
        INNER JOIN dbo.ACCT_CODF cd ON ca.COCA_NUMINT_COCA = cd.CODF_NUMINT_COCA
        LEFT JOIN dbo.CONT_IMAE ci ON cp.COCP_MAESTRO = ci.IMAE_MAESTRO AND cp.COCP_INSTANCIA = ci.IMAE_INSTANCIA
        WHERE cd.CODF_DIVISION = ?
          AND cf.COFF_DIVISION_CVCL IS NULL
          AND cf.COFF_FECHA_EST_FC >= ISNULL(cp.COCP_FECHA_VIG_DES, '2001-01-01')
          AND cf.COFF_FECHA_EST_FC <= ISNULL(cp.COCP_FECHA_VIG_HAS, '2050-12-31')
          AND (cd.CODF_FECHA_SUS_DES IS NULL OR cd.CODF_FECHA_SUS_DES > cf.COFF_FECHA_EST_FC)
          AND (cd.CODF_FECHA_SUS_HAS IS NULL OR cd.CODF_FECHA_SUS_HAS < cf.COFF_FECHA_EST_FC)
          AND cp.COCP_CANTIDAD IS NOT NULL
          AND cp.COCP_PRECIO_ORI IS NOT NULL
          AND (ci.IMAE_DESCRIPCION1 IS NOT NULL OR ci.IMAE_DESCRIPCION2 IS NOT NULL)
        """
        params = [division]
        if anio:
            query += " AND YEAR(cf.COFF_FECHA_EST_FC) = ?"
            params.append(int(anio))
        if mes:
            query += " AND MONTH(cf.COFF_FECHA_EST_FC) = ?"
            params.append(int(mes))
        
        query += """
        GROUP BY ca.COCA_TIPO_TCAC, ca.COCA_NUMERO_COCA, ci.IMAE_DESCRIPCION1, ci.IMAE_DESCRIPCION2, ci.IMAE_DESCRIPCION3, cd.CODF_MONEDA, YEAR(cf.COFF_FECHA_EST_FC), MONTH(cf.COFF_FECHA_EST_FC)
        HAVING SUM(cp.COCP_CANTIDAD * cp.COCP_PRECIO_ORI) <> 0
        ORDER BY CLIENTE, CONTRATO, ANIO, MES
        """
        
        # 🔴 CORREGIDO: Usar params en read_sql
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        df = limpiar_datos(df)
        
        total_importe = float(df['IMPORTE'].sum()) if not df.empty and 'IMPORTE' in df.columns and df['IMPORTE'].notna().any() else 0
        total_registros = len(df)
        
        resumen = []
        if not df.empty and 'ANIO' in df.columns and 'MES' in df.columns:
            resumen_df = df.groupby(['ANIO', 'MES']).agg({'IMPORTE': 'sum', 'CONTRATO': 'count'}).reset_index()
            resumen_df.columns = ['ANIO', 'MES', 'TOTAL_IMPORTE', 'CANTIDAD_CONTRATOS']
            for _, row in resumen_df.iterrows():
                resumen.append({
                    'ANIO': int(row['ANIO']), 'MES': int(row['MES']),
                    'TOTAL_IMPORTE': float(row['TOTAL_IMPORTE']), 'CANTIDAD_CONTRATOS': int(row['CANTIDAD_CONTRATOS'])
                })
        
        detalle = df.to_dict(orient='records') if not df.empty else []
        columnas = ['CONTRATO', 'CLIENTE', 'CENTRO_COSTO', 'MONEDA', 'ANIO', 'MES', 'IMPORTE']
        
        return jsonify({
            'success': True, 'data': detalle, 'columnas': columnas,
            'total_registros': total_registros, 'total_importe': total_importe, 'resumen': resumen
        })
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error en contratos: {error_msg}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': error_msg, 'data': [], 'columnas': [], 'total_registros': 0, 'total_importe': 0, 'resumen': []}), 500

# ============================================================
# REPORTE: PENDIENTE DE COBRO - CORREGIDO
# ============================================================

@reportes_bp.route('/reportes/pendiente_cobro', methods=['GET'])
def get_pendiente_cobro():
    """Reporte de saldos pendientes de cobro por cliente"""
    try:
        base_override = request.args.get('base')
        sociedad_override = request.args.get('sociedad')
        
        if base_override:
            conn, division = get_db_connection_base(base_override, sociedad_override)
        else:
            conn, division = get_db_connection()
        
        clientes_ps = get_clientes_forzados_ps(division) if 'get_clientes_forzados_ps' in globals() else []
        clientes_dl = get_clientes_forzados_dl(division) if 'get_clientes_forzados_dl' in globals() else []
        
        ps_list = "', '".join(clientes_ps) if clientes_ps else "''"
        dl_list = "', '".join(clientes_dl) if clientes_dl else "''"
        
        signo_sql = """
            CASE 
                WHEN c.CTEC_SIGNO = 'D' THEN 1
                WHEN c.CTEC_SIGNO = 'H' THEN -1
                ELSE 1
            END
        """
        
        # 🔴 CORREGIDO: Consulta parametrizada
        query = f"""
        WITH CotizacionDia AS (
            SELECT 
                CAST(COTI_FECHA AS DATE) AS Fecha,
                COTI_COTIZACION AS Cotizacion
            FROM (
                SELECT 
                    COTI_FECHA,
                    COTI_COTIZACION,
                    ROW_NUMBER() OVER (PARTITION BY CAST(COTI_FECHA AS DATE) ORDER BY COTI_FECHA DESC) AS rn
                FROM SIST_COTI
                WHERE COTI_MONEDA1 = 'DL' AND COTI_MONEDA2 = 'PS'
            ) t
            WHERE rn = 1
        )
        SELECT 
            cl.CLIE_NOMBRE AS Cliente,
            cl.CLIE_TIPO_CLI AS TipoCliente,
            c.CTEC_SIGNO AS Signo,
            c.CTEC_FECHA_EMI AS Fecha,
            vcc.CVCC_TIPO_CVCL + '-' + CAST(vcc.CVCC_NUMERO_CVCL AS VARCHAR) AS Comprobante,
            CASE 
                WHEN cl.CLIE_NOMBRE IN ('{ps_list}') THEN 'PS'
                WHEN cl.CLIE_NOMBRE IN ('{dl_list}') THEN 'DL'
                WHEN cl.CLIE_TIPO_CLI = '5' THEN 'DL'
                WHEN c.CTEC_COTIZACION = cd.Cotizacion THEN 'DL'
                ELSE 'PS'
            END AS Moneda,
            c.CTEC_COTIZACION AS Cotizacion_Comprobante,
            cd.Cotizacion AS Cotizacion_Dia,
            ISNULL(v.VCTC_SAL_ORI, 0) * ({signo_sql}) AS Saldo_Origen,
            ISNULL(v.VCTC_SAL_LOC, 0) * ({signo_sql}) AS Saldo_Local,
            CASE 
                WHEN cl.CLIE_NOMBRE IN ('{ps_list}') THEN ISNULL(v.VCTC_SAL_LOC, 0) * ({signo_sql})
                WHEN cl.CLIE_NOMBRE NOT IN ('{dl_list}') 
                     AND cl.CLIE_TIPO_CLI != '5' 
                     AND ISNULL(c.CTEC_COTIZACION, 0) != ISNULL(cd.Cotizacion, 0) THEN ISNULL(v.VCTC_SAL_LOC, 0) * ({signo_sql})
                ELSE 0 
            END AS PESOS,
            CASE 
                WHEN cl.CLIE_NOMBRE IN ('{dl_list}') THEN ISNULL(v.VCTC_SAL_ORI, 0) * ({signo_sql})
                WHEN cl.CLIE_NOMBRE NOT IN ('{ps_list}') 
                     AND (cl.CLIE_TIPO_CLI = '5' OR ISNULL(c.CTEC_COTIZACION, 0) = ISNULL(cd.Cotizacion, 0)) THEN ISNULL(v.VCTC_SAL_ORI, 0) * ({signo_sql})
                ELSE 0 
            END AS DOLARES,
            CASE 
                WHEN DATEDIFF(DAY, c.CTEC_FECHA_EMI, GETDATE()) > 90 THEN '> 90 días'
                WHEN DATEDIFF(DAY, c.CTEC_FECHA_EMI, GETDATE()) > 30 THEN '>30 días y <= 90 días'
                ELSE '=< 30 días'
            END AS Rango_Dias,
            ISNULL(g.GCTC_OBSERVACION, '') AS Observacion
        FROM CCOB_CTEC c
        INNER JOIN CCOB_CLIE cl ON c.CTEC_CLIENTE = cl.CLIE_CLIENTE
        LEFT JOIN CCOB_CVCC vcc ON c.CTEC_CTACTE_CTEC = vcc.CVCC_CTACTE_CTEC
        LEFT JOIN CCOB_VCTC v ON c.CTEC_CTACTE_CTEC = v.VCTC_CTACTE_CTEC
        LEFT JOIN CCOB_GCTC g ON c.CTEC_CTACTE_CTEC = g.GCTC_CTACTE_CTEC
        LEFT JOIN CotizacionDia cd ON CAST(c.CTEC_FECHA_EMI AS DATE) = cd.Fecha
        WHERE c.CTEC_DIVISION = ?
          AND (v.VCTC_SAL_ORI IS NOT NULL AND v.VCTC_SAL_ORI != 0)
        ORDER BY cl.CLIE_NOMBRE ASC, c.CTEC_FECHA_EMI ASC
        """
        
        # 🔴 CORREGIDO: Usar params en read_sql
        df = pd.read_sql(query, conn, params=[division])
        conn.close()
        
        df = df.replace([float('inf'), float('-inf')], 0)
        df = df.fillna(0)
        df = limpiar_datos(df)
        
        detalle = []
        for _, row in df.iterrows():
            fecha_val = row.get('Fecha')
            if pd.isna(fecha_val) or fecha_val is None:
                fecha_str = ''
            elif hasattr(fecha_val, 'strftime'):
                fecha_str = fecha_val.strftime('%Y-%m-%d')
            else:
                fecha_str = str(fecha_val)
            
            detalle.append({
                'Cliente': str(row.get('Cliente', '')),
                'TipoCliente': str(row.get('TipoCliente', '')),
                'Signo': str(row.get('Signo', '')),
                'Fecha': fecha_str,
                'Comprobante': str(row.get('Comprobante', '')),
                'Moneda': str(row.get('Moneda', '')),
                'Cotizacion_Comprobante': float(row.get('Cotizacion_Comprobante', 0)) if pd.notna(row.get('Cotizacion_Comprobante', 0)) else 0,
                'Cotizacion_Dia': float(row.get('Cotizacion_Dia', 0)) if pd.notna(row.get('Cotizacion_Dia', 0)) else 0,
                'Saldo_Origen': float(row.get('Saldo_Origen', 0)) if pd.notna(row.get('Saldo_Origen', 0)) else 0,
                'Saldo_Local': float(row.get('Saldo_Local', 0)) if pd.notna(row.get('Saldo_Local', 0)) else 0,
                'PESOS': float(row.get('PESOS', 0)) if pd.notna(row.get('PESOS', 0)) else 0,
                'DOLARES': float(row.get('DOLARES', 0)) if pd.notna(row.get('DOLARES', 0)) else 0,
                'Rango_Dias': str(row.get('Rango_Dias', '')),
                'Observacion': str(row.get('Observacion', ''))
            })
        
        return jsonify({'success': True, 'data': detalle, 'total_registros': len(detalle)})
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error en pendiente_cobro: {error_msg}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': error_msg, 'data': [], 'total_registros': 0}), 500

# ============================================================
# REPORTE: CONSOLIDADO VENTAS POR PAÍS - CORREGIDO (CON PARÁMETROS)
# ============================================================

@reportes_bp.route('/reportes/consolidado_ventas_pais', methods=['GET'])
def get_consolidado_ventas_pais():
    """Ventas consolidadas por país - con parámetros"""
    try:
        base_override = request.args.get('base')
        sociedad_override = request.args.get('sociedad')
        
        anio_param = request.args.get('anio')
        if anio_param:
            try:
                anio = int(anio_param)
            except ValueError:
                anio = 2026
        else:
            anio = 2026
        
        if base_override:
            conn, division = get_db_connection_base(base_override, sociedad_override)
        else:
            conn, division = get_db_connection()
        
        paises_excluir = [
            'SIDESYS COLOMBIA', 'SIDESYS COSTA RICA', 'SIDESYS ECUADOR',
            'SIDESYS GUATEMALA', 'SIDESYS HONDURAS', 'SIDESYS MEXICO', 'SIDESYS PARAGUAY'
        ]
        
        # ✅ CORREGIDO: Usar placeholders para la cláusula NOT IN
        placeholders = ','.join(['?'] * len(paises_excluir))
        
        query = f"""
        SELECT 
            a.AASI_DIVISION,
            a.AASI_IMP_LOC AS IMPORTE_LOCAL,
            a.AASI_IMP_CON AS IMPORTE_CONVERSION,
            a.AASI_SIGNO,
            MAX(c.CASI_FECHA) AS FECHA,
            MAX(i.IMAE_DESCRIPCION2) AS CC_CLIENTE,
            MAX(i.IMAE_DESCRIPCION3) AS CENTRO_COSTO,
            MAX(r.RASI_CUENTA) AS CUENTA_CONTABLE,
            MAX(c.CASI_SUBDIARIO) AS SUBDIARIO,
            MAX(cl.CLIE_NOMBRE) AS CLIE_NOMBRE,
            YEAR(MAX(c.CASI_FECHA)) AS AÑO,
            MONTH(MAX(c.CASI_FECHA)) AS MES,
            CASE 
                WHEN a.AASI_SIGNO = 'D' THEN -a.AASI_IMP_CON 
                WHEN a.AASI_SIGNO = 'H' THEN a.AASI_IMP_CON 
                ELSE a.AASI_IMP_CON 
            END AS IMPORTE_DL,
            'República Dominicana' AS PAIS
        FROM SIST_AASI a
        LEFT JOIN CONT_IMAE i ON a.AASI_MAESTRO = i.IMAE_MAESTRO AND a.AASI_INSTANCIA = i.IMAE_INSTANCIA
        LEFT JOIN SIST_RASI r ON a.AASI_ASIENTO = r.RASI_ASIENTO
        LEFT JOIN SIST_CASI c ON a.AASI_ASIENTO = c.CASI_ASIENTO
        LEFT JOIN CCOB_RACC ra ON c.CASI_ASIENTO = ra.RACC_ASIENTO
        LEFT JOIN CCOB_CTEC ct ON ra.RACC_CTACTE_CTEC = ct.CTEC_CTACTE_CTEC
        LEFT JOIN CCOB_CLIE cl ON ct.CTEC_CLIENTE = cl.CLIE_CLIENTE
        WHERE a.AASI_DIVISION = ?
          AND r.RASI_CUENTA = '410101'
          AND c.CASI_SUBDIARIO = 'VTA'
          AND cl.CLIE_NOMBRE NOT IN ({placeholders})
          AND YEAR(c.CASI_FECHA) = ?
        GROUP BY 
            a.AASI_DIVISION,
            a.AASI_IMP_LOC,
            a.AASI_IMP_CON,
            a.AASI_SIGNO,
            a.AASI_ASIENTO,
            a.AASI_RENGLON_ASI,
            a.AASI_RENGLON_APE,
            CASE 
                WHEN a.AASI_SIGNO = 'D' THEN -a.AASI_IMP_CON 
                WHEN a.AASI_SIGNO = 'H' THEN a.AASI_IMP_CON 
                ELSE a.AASI_IMP_CON 
            END
        ORDER BY MAX(c.CASI_FECHA) DESC
        """
        
        # ✅ CORREGIDO: Parámetros completos con los países a excluir
        params = [division] + paises_excluir + [anio]
        
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return jsonify({
                'success': True,
                'data': [],
                'resumen_cliente': [],
                'resumen_centro': [],
                'resumen_subdiario': [],
                'totales': {
                    'total_local': 0,
                    'total_usd': 0,
                    'total_dl': 0,
                    'total_registros': 0,
                    'anio': anio
                }
            })
        
        df = limpiar_datos(df)
        df['CC_CLIENTE'] = df['CC_CLIENTE'].fillna('SIN CLIENTE')
        df['CENTRO_COSTO'] = df['CENTRO_COSTO'].fillna('SIN CENTRO')
        df['CLIE_NOMBRE'] = df['CLIE_NOMBRE'].fillna('SIN NOMBRE')
        df['SUBDIARIO'] = df['SUBDIARIO'].fillna('SIN SUBDIARIO')
        
        resumen_cliente = df.groupby('CLIE_NOMBRE').agg({
            'IMPORTE_LOCAL': 'sum',
            'IMPORTE_CONVERSION': 'sum',
            'IMPORTE_DL': 'sum',
            'AASI_DIVISION': 'count'
        }).reset_index()
        resumen_cliente.columns = ['Cliente', 'Total_Local', 'Total_USD', 'Total_DL', 'Transacciones']
        resumen_cliente = resumen_cliente.sort_values('Total_DL', ascending=False)
        
        resumen_centro = df.groupby('CENTRO_COSTO').agg({
            'IMPORTE_LOCAL': 'sum',
            'IMPORTE_CONVERSION': 'sum',
            'IMPORTE_DL': 'sum',
            'AASI_DIVISION': 'count'
        }).reset_index()
        resumen_centro.columns = ['Centro_Costo', 'Total_Local', 'Total_USD', 'Total_DL', 'Transacciones']
        resumen_centro = resumen_centro.sort_values('Total_DL', ascending=False)
        
        resumen_subdiario = df.groupby('SUBDIARIO').agg({
            'IMPORTE_LOCAL': 'sum',
            'IMPORTE_CONVERSION': 'sum',
            'IMPORTE_DL': 'sum',
            'AASI_DIVISION': 'count'
        }).reset_index()
        resumen_subdiario.columns = ['Subdiario', 'Total_Local', 'Total_USD', 'Total_DL', 'Transacciones']
        resumen_subdiario = resumen_subdiario.sort_values('Total_DL', ascending=False)
        
        detalle = []
        for _, row in df.iterrows():
            fecha_val = row.get('FECHA')
            if pd.isna(fecha_val) or fecha_val is None:
                fecha_str = ''
            elif hasattr(fecha_val, 'strftime'):
                fecha_str = fecha_val.strftime('%Y-%m-%d')
            else:
                fecha_str = str(fecha_val)
            
            detalle.append({
                'Division': int(row.get('AASI_DIVISION', 0)) if pd.notna(row.get('AASI_DIVISION', 0)) else 0,
                'Pais': str(row.get('PAIS', 'República Dominicana')),
                'Cliente': str(row.get('CC_CLIENTE', 'SIN CLIENTE')),
                'NombreCliente': str(row.get('CLIE_NOMBRE', 'SIN NOMBRE')),
                'CentroCosto': str(row.get('CENTRO_COSTO', 'SIN CENTRO')),
                'CuentaContable': str(row.get('CUENTA_CONTABLE', 'SIN CUENTA')),
                'Fecha': fecha_str,
                'Anio': int(row.get('AÑO', 0)) if pd.notna(row.get('AÑO', 0)) else 0,
                'Mes': int(row.get('MES', 0)) if pd.notna(row.get('MES', 0)) else 0,
                'Signo': str(row.get('AASI_SIGNO', '')),
                'Subdiario': str(row.get('SUBDIARIO', 'SIN SUBDIARIO')),
                'Importe_Local': float(row.get('IMPORTE_LOCAL', 0)) if pd.notna(row.get('IMPORTE_LOCAL', 0)) else 0,
                'Importe_Conversion': float(row.get('IMPORTE_CONVERSION', 0)) if pd.notna(row.get('IMPORTE_CONVERSION', 0)) else 0,
                'Importe_DL': float(row.get('IMPORTE_DL', 0)) if pd.notna(row.get('IMPORTE_DL', 0)) else 0
            })
        
        total_local = float(df['IMPORTE_LOCAL'].sum()) if not df.empty else 0
        total_usd = float(df['IMPORTE_CONVERSION'].sum()) if not df.empty else 0
        total_dl = float(df['IMPORTE_DL'].sum()) if not df.empty else 0
        
        return jsonify({
            'success': True,
            'data': detalle,
            'resumen_cliente': resumen_cliente.to_dict(orient='records'),
            'resumen_centro': resumen_centro.to_dict(orient='records'),
            'resumen_subdiario': resumen_subdiario.to_dict(orient='records'),
            'totales': {
                'total_local': total_local,
                'total_usd': total_usd,
                'total_dl': total_dl,
                'total_registros': len(df),
                'anio': anio
            }
        })
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ ERROR: {error_msg}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': error_msg,
            'data': [],
            'resumen_cliente': [],
            'resumen_centro': [],
            'resumen_subdiario': [],
            'totales': {
                'total_local': 0,
                'total_usd': 0,
                'total_dl': 0,
                'total_registros': 0,
                'anio': anio if 'anio' in locals() else 2026
            }
        }), 500

# ============================================================
# REPORTE: CONSOLIDADO VENTAS GLOBAL - CORREGIDO
# ============================================================

@reportes_bp.route('/reportes/consolidado_ventas_global', methods=['GET'])
def get_consolidado_ventas_global():
    """Ventas consolidadas de todas las bases (excluye intercompany)"""
    try:
        data_global = []
        tipos_excluir = get_tipo_cliente_excluir()
        
        # ✅ CORREGIDO: Usar placeholders para la cláusula NOT IN
        if tipos_excluir:
            placeholders = ','.join(['?'] * len(tipos_excluir))
        else:
            placeholders = ''
        
        for db_name in BASES_DISPONIBLES.keys():
            try:
                conn, _ = get_db_connection_base(db_name)
                
                # ✅ CORREGIDO: Consulta con parámetros
                if tipos_excluir:
                    query = f"""
                    SELECT 
                        COUNT(*) AS Transacciones,
                        ISNULL(SUM(CTEC_IMP_TOT_LOC), 0) AS Total
                    FROM CCOB_CTEC c
                    INNER JOIN CCOB_CLIE cl ON c.CTEC_CLIENTE = cl.CLIE_CLIENTE
                    WHERE c.CTEC_FECHA_EMI >= DATEADD(YEAR, -1, GETDATE())
                      AND cl.CLIE_TIPO_CLI NOT IN ({placeholders})
                    """
                    df = pd.read_sql(query, conn, params=tipos_excluir)
                else:
                    query = """
                    SELECT 
                        COUNT(*) AS Transacciones,
                        ISNULL(SUM(CTEC_IMP_TOT_LOC), 0) AS Total
                    FROM CCOB_CTEC c
                    INNER JOIN CCOB_CLIE cl ON c.CTEC_CLIENTE = cl.CLIE_CLIENTE
                    WHERE c.CTEC_FECHA_EMI >= DATEADD(YEAR, -1, GETDATE())
                    """
                    df = pd.read_sql(query, conn)
                conn.close()
                
                if not df.empty:
                    info = BASES_DISPONIBLES.get(db_name, {})
                    sigla = info.get('sigla', db_name)
                    if db_name == 'plataforma':
                        sigla = 'AR'
                    
                    total = float(df.iloc[0]['Total']) if pd.notna(df.iloc[0]['Total']) else 0
                    transacciones = int(df.iloc[0]['Transacciones']) if pd.notna(df.iloc[0]['Transacciones']) else 0
                    
                    data_global.append({
                        'Base': db_name,
                        'Sigla': sigla,
                        'Transacciones': transacciones,
                        'Total': total
                    })
            except Exception as inner_e:
                logger.warning(f"No se pudo consultar la base global {db_name}: {inner_e}")
                continue
        
        return jsonify({'success': True, 'data': data_global, 'total_registros': len(data_global)})
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error en consolidado_ventas_global: {error_msg}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': error_msg, 'data': [], 'total_registros': 0}), 500

# ============================================================
# REPORTE: AÑOS DISPONIBLES PARA VENTAS
# ============================================================

@reportes_bp.route('/reportes/anos_ventas', methods=['GET'])
def get_anos_ventas():
    """Obtener años disponibles para el reporte de ventas"""
    try:
        base_override = request.args.get('base')
        sociedad_override = request.args.get('sociedad')
        
        if base_override:
            conn, division = get_db_connection_base(base_override, sociedad_override)
        else:
            conn, division = get_db_connection()
        
        # 🔴 CORREGIDO: Consulta parametrizada
        query = """
        SELECT DISTINCT YEAR(AASI_FECHA_REF) AS ANIO
        FROM SIST_AASI
        WHERE AASI_DIVISION = ?
          AND AASI_FECHA_REF IS NOT NULL
        ORDER BY ANIO DESC
        """
        
        df = pd.read_sql(query, conn, params=[division])
        conn.close()
        
        anos_bd = df['ANIO'].tolist() if not df.empty else []
        ano_actual = datetime.now().year
        anos_futuros = [ano_actual + 1, ano_actual, ano_actual - 1]
        todos_anos = list(set(anos_bd + anos_futuros))
        todos_anos.sort(reverse=True)
        
        anos_filtrados = []
        for anio in todos_anos:
            if anio >= 2025:
                anos_filtrados.append(anio)
        
        if not anos_filtrados:
            anos_filtrados = [2027, 2026, 2025]
        
        anio_default = 2026
        
        logger.info(f"📅 Años disponibles: {anos_filtrados}")
        logger.info(f"📅 Año por defecto: {anio_default}")
        
        return jsonify({
            'success': True,
            'anos': anos_filtrados,
            'anio_default': anio_default
        })
    except Exception as e:
        logger.error(f"Error en get_anos_ventas: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'anos': [2027, 2026, 2025],
            'anio_default': 2026
        }), 500