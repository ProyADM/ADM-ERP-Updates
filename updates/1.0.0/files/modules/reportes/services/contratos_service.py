# modules/reportes/services/contratos_service.py
# ============================================================
# SERVICIO: REPORTE DE CONTRATOS PENDIENTES DE FACTURAR
# ============================================================

import pandas as pd
import logging
from .utils import get_db_connection, get_db_connection_base, limpiar_datos

logger = logging.getLogger(__name__)

def obtener_reporte_contratos(anio=None, mes=None, base_override=None, sociedad_override=None):
    """
    Retorna dict con:
        - data: lista de registros
        - columnas: nombres de columnas
        - total_registros, total_importe, resumen (agrupado por año/mes)
    """
    try:
        if base_override:
            conn, division = get_db_connection_base(base_override, sociedad_override)
        else:
            conn, division = get_db_connection()

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
                    'ANIO': int(row['ANIO']),
                    'MES': int(row['MES']),
                    'TOTAL_IMPORTE': float(row['TOTAL_IMPORTE']),
                    'CANTIDAD_CONTRATOS': int(row['CANTIDAD_CONTRATOS'])
                })

        detalle = df.to_dict(orient='records') if not df.empty else []
        columnas = ['CONTRATO', 'CLIENTE', 'CENTRO_COSTO', 'MONEDA', 'ANIO', 'MES', 'IMPORTE']

        return {
            'success': True,
            'data': detalle,
            'columnas': columnas,
            'total_registros': total_registros,
            'total_importe': total_importe,
            'resumen': resumen
        }

    except Exception as e:
        logger.error(f"Error en contratos_service: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'data': [],
            'columnas': [],
            'total_registros': 0,
            'total_importe': 0,
            'resumen': []
        }