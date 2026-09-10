# modules/reportes/services/pendiente_cobro_service.py
# ============================================================
# SERVICIO: PENDIENTE DE COBRO
# ============================================================

import pandas as pd
import logging
from .utils import get_db_connection, get_db_connection_base, limpiar_datos
from modules.reportes.config_clientes import get_clientes_forzados_ps, get_clientes_forzados_dl

logger = logging.getLogger(__name__)

def obtener_pendiente_cobro(base_override=None, sociedad_override=None):
    try:
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

        return {'success': True, 'data': detalle, 'total_registros': len(detalle)}

    except Exception as e:
        logger.error(f"Error en pendiente_cobro_service: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e), 'data': [], 'total_registros': 0}