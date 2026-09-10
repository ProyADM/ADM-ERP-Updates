# modules/shared/dashboard.py
# ============================================================
# DASHBOARD - STOCK + VENTAS (ordenadas por número DESC) + CONTRATOS
# ============================================================

from flask import Blueprint, jsonify, g
from modules.shared.database import run_sql
from datetime import datetime
import logging

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')
logger = logging.getLogger(__name__)

@dashboard_bp.route('/actividad', methods=['GET'])
def obtener_actividad():
    try:
        actividad = []
        resumen = {'stock': 0, 'ventas': 0, 'contratos': 0, 'total': 0}

        # 1. Stock
        try:
            stock_sql = """
                SELECT TOP 10
                    m.MOST_MOVSTO_MOST AS id,
                    m.MOST_FECHA_EMI AS fecha,
                    'STOCK' AS tipo,
                    CONCAT(
                        'Artículo: ', ISNULL(a.ARTS_NOMBRE, 'N/A'),
                        ' | Depósito: ', ISNULL(d.DPOS_NOMBRE, 'N/A'),
                        ' | ', 
                        CASE 
                            WHEN md.MOSD_SIGNO = 'E' THEN 'Entrada'
                            WHEN md.MOSD_SIGNO = 'S' THEN 'Salida'
                            ELSE 'Transferencia'
                        END,
                        ' | Cantidad: ', CAST(md.MOSD_CANT_ING AS VARCHAR)
                    ) AS descripcion,
                    '📦' AS icono
                FROM STOC_MOST m
                INNER JOIN STOC_MOSD md ON m.MOST_MOVSTO_MOST = md.MOSD_MOVSTO_MOST
                LEFT JOIN STOC_ARTS a ON md.MOSD_ARTICULO = a.ARTS_ARTICULO
                LEFT JOIN STOC_DPOS d ON md.MOSD_DEPOSITO = d.DPOS_DEPOSITO
                WHERE m.MOST_FECHA_EMI IS NOT NULL
                ORDER BY m.MOST_FECHA_EMI DESC
            """
            stock = run_sql(stock_sql)
            for item in stock:
                actividad.append({
                    'id': item['id'],
                    'fecha': item['fecha'].isoformat() if item['fecha'] else None,
                    'tipo': 'STOCK',
                    'descripcion': item['descripcion'] or 'Movimiento de stock',
                    'icono': '📦'
                })
            resumen['stock'] = len(stock)
        except Exception as e:
            logger.warning(f"Error en stock: {e}")

        # 2. Ventas agrupadas (último mes, ordenadas por número DESC)
        try:
            division = getattr(g, 'division', 5)
            ventas_sql = """
                SELECT TOP 10
                    MAX(c.CTEC_CTACTE_CTEC) AS id,
                    MAX(c.CTEC_FECHA_EMI) AS fecha,
                    'VENTA' AS tipo,
                    CONCAT(
                        'Comprobante(s): ',
                        STUFF((
                            SELECT DISTINCT ' / ' + vcc2.CVCC_TIPO_CVCL
                            FROM CCOB_CVCC vcc2
                            WHERE vcc2.CVCC_NUMERO_CVCL = vcc.CVCC_NUMERO_CVCL
                              AND vcc2.CVCC_TIPO_CVCL IN ('CAE', 'CEB', 'FAA', 'FAE', 'FBE', 'MEA', 'MEB')
                            FOR XML PATH('')
                        ), 1, 3, ''),
                        ' | Nro: ', CAST(vcc.CVCC_NUMERO_CVCL AS VARCHAR),
                        ' | Cliente: ', ISNULL(MAX(cl.CLIE_NOMBRE), 'N/A'),
                        ' | Total: ', FORMAT(SUM(c.CTEC_IMP_TOT_ORI), 'N2'),
                        ' | ', MAX(c.CTEC_MONEDA)
                    ) AS descripcion,
                    '💰' AS icono
                FROM CCOB_CTEC c
                INNER JOIN CCOB_CLIE cl ON c.CTEC_CLIENTE = cl.CLIE_CLIENTE
                INNER JOIN CCOB_CVCC vcc ON c.CTEC_CTACTE_CTEC = vcc.CVCC_CTACTE_CTEC
                WHERE c.CTEC_DIVISION = ?
                  AND c.CTEC_CLIENTE IS NOT NULL
                  AND c.CTEC_FECHA_EMI IS NOT NULL
                  AND c.CTEC_IMP_TOT_ORI IS NOT NULL
                  AND cl.CLIE_TIPO_CLI != '5'
                  AND vcc.CVCC_TIPO_CVCL IN ('CAE', 'CEB', 'FAA', 'FAE', 'FBE', 'MEA', 'MEB')
                  AND vcc.CVCC_NUMERO_CVCL IS NOT NULL
                  AND c.CTEC_FECHA_EMI >= DATEADD(MONTH, -1, GETDATE())
                GROUP BY vcc.CVCC_NUMERO_CVCL, cl.CLIE_CLIENTE
                HAVING SUM(c.CTEC_IMP_TOT_ORI) <> 0
                ORDER BY vcc.CVCC_NUMERO_CVCL DESC
            """
            ventas = run_sql(ventas_sql, params=[division])
            for item in ventas:
                actividad.append({
                    'id': item['id'],
                    'fecha': item['fecha'].isoformat() if item['fecha'] else None,
                    'tipo': 'VENTA',
                    'descripcion': item['descripcion'] or 'Venta registrada',
                    'icono': '💰'
                })
            resumen['ventas'] = len(ventas)
        except Exception as e:
            logger.warning(f"Error en ventas agrupadas: {e}")

        # 3. Contratos pendientes
        try:
            division = getattr(g, 'division', 5)
            contratos_sql = """
                SELECT TOP 10
                    ca.COCA_NUMINT_COCA AS id,
                    ca.COCA_FECHA_ALTA AS fecha,
                    'CONTRATO' AS tipo,
                    CONCAT(
                        'Contrato ', ca.COCA_TIPO_TCAC, '-', CAST(ca.COCA_NUMERO_COCA AS VARCHAR),
                        ' | Cliente: ', ISNULL(MAX(ci.IMAE_DESCRIPCION2), ISNULL(MAX(ci.IMAE_DESCRIPCION1), 'N/A'))
                    ) AS descripcion,
                    '📋' AS icono
                FROM ACCT_COCA ca
                INNER JOIN ACCT_COFF cf ON ca.COCA_NUMINT_COCA = cf.COFF_NUMINT_COCA
                INNER JOIN ACCT_COCP cp ON cf.COFF_NUMINT_COCA = cp.COCP_NUMINT_COCA
                INNER JOIN ACCT_CODF cd ON ca.COCA_NUMINT_COCA = cd.CODF_NUMINT_COCA
                LEFT JOIN CONT_IMAE ci ON cp.COCP_MAESTRO = ci.IMAE_MAESTRO AND cp.COCP_INSTANCIA = ci.IMAE_INSTANCIA
                WHERE cd.CODF_DIVISION = ?
                  AND cf.COFF_DIVISION_CVCL IS NULL
                  AND cf.COFF_FECHA_EST_FC >= ISNULL(cp.COCP_FECHA_VIG_DES, '2001-01-01')
                  AND cf.COFF_FECHA_EST_FC <= ISNULL(cp.COCP_FECHA_VIG_HAS, '2050-12-31')
                  AND (cd.CODF_FECHA_SUS_DES IS NULL OR cd.CODF_FECHA_SUS_DES > cf.COFF_FECHA_EST_FC)
                  AND (cd.CODF_FECHA_SUS_HAS IS NULL OR cd.CODF_FECHA_SUS_HAS < cf.COFF_FECHA_EST_FC)
                  AND cp.COCP_CANTIDAD IS NOT NULL AND cp.COCP_PRECIO_ORI IS NOT NULL
                  AND (ci.IMAE_DESCRIPCION1 IS NOT NULL OR ci.IMAE_DESCRIPCION2 IS NOT NULL)
                GROUP BY ca.COCA_NUMINT_COCA, ca.COCA_TIPO_TCAC, ca.COCA_NUMERO_COCA, ca.COCA_FECHA_ALTA
                HAVING SUM(cp.COCP_CANTIDAD * cp.COCP_PRECIO_ORI) <> 0
                ORDER BY ca.COCA_FECHA_ALTA DESC
            """
            contratos = run_sql(contratos_sql, params=[division])
            for item in contratos:
                actividad.append({
                    'id': item['id'],
                    'fecha': item['fecha'].isoformat() if item['fecha'] else None,
                    'tipo': 'CONTRATO',
                    'descripcion': item['descripcion'] or 'Contrato pendiente',
                    'icono': '📋'
                })
            resumen['contratos'] = len(contratos)
        except Exception as e:
            logger.warning(f"Error en contratos: {e}")

        actividad.sort(key=lambda x: x['fecha'] or '', reverse=True)
        resumen['total'] = len(actividad)

        return jsonify({
            'success': True,
            'data': actividad,
            'resumen': resumen,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error en dashboard/actividad: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500