# modules/reportes/services/pendiente_cobro_service.py
# ============================================================
# SERVICIO: PENDIENTE DE COBRO
# ============================================================
#
# DOS LECTURAS DEL MISMO INFORME
# ------------------------------
# 1) SIN fecha (o con la fecha de HOY): el informe de siempre. Toma el saldo ACTUAL de
#    cada cuota del mayor (`CCOB_VCTC.VCTC_SAL_*`) y la antiguedad contra `GETDATE()`.
#    Este camino NO cambio: es el que ya estaba en produccion.
#
# 2) CON una fecha ANTERIOR a hoy ("pendiente al 31/08/2026"): el saldo de cada cuota A
#    ESA FECHA. El mayor guarda solo el saldo ACTUAL, asi que se reconstruye anclado en
#    el y sumando lo que se aplico DESPUES del corte:
#
#        saldo al corte = saldo actual + suma(aplicado DESPUES del corte)
#
#    Es equivalente a `importe de la cuota - lo aplicado hasta el corte`, porque el
#    mayor cumple `importe - lo aplicado = saldo actual`: medido el 02/10/2026 sobre las
#    10.330 cuotas de `plataforma_rd`, 0 diferencias (probe
#    `_investigacion_gt/481_probe_corte_cobranza.py`, salida en
#    `481_salida_corte_cobranza.txt`).
#
#    Las aplicaciones son los recibos de cobro (`CCOB_ARCC` + cabecera `CCOB_RCCL`), las
#    ordenes de pago (`CCOB_AOPC` + `CCOB_OPCL`) y los documentos (`CCOB_DCCB` +
#    `CCOB_CCCB`), cada una con la FECHA DE EMISION de su cabecera y ligada a la cuota
#    por `*_CTACTE_VCTC` + `*_RENGLON_VCTC`.
#
#    Ademas, mirando una fecha pasada: (a) solo entran los comprobantes EMITIDOS hasta
#    el corte (uno del 11/09 no existia al 31/08), y (b) entran TAMBIEN las cuotas que
#    HOY tienen saldo 0 (se cobraron despues del corte, pero a esa fecha estaban
#    pendientes): por eso la consulta del corte NO filtra por saldo actual != 0.
# ============================================================

import datetime
import logging

import pandas as pd

from .utils import get_db_connection, get_db_connection_base, limpiar_datos
from modules.reportes.config_clientes import get_clientes_forzados_ps, get_clientes_forzados_dl

logger = logging.getLogger(__name__)

# Aplicaciones de cobranza de las cuotas de la division, con la fecha de emision de su
# cabecera. La sucursal de la cabecera se llama `*_SUCURSAL_IMP`; los documentos dados de
# baja (`*_FECHA_BAJA`) no cuentan.
SQL_APLICACIONES = """
SELECT a.ARCC_CTACTE_VCTC AS Ctacte, a.ARCC_RENGLON_VCTC AS Renglon,
       r.RCCL_FECHA_EMI AS Fecha,
       a.ARCC_IMP_APL_ORI AS AplicadoOrigen, a.ARCC_IMP_APL_LOC AS AplicadoLocal
FROM CCOB_ARCC a
INNER JOIN CCOB_RCCL r
   ON r.RCCL_DIVISION_RCCL = a.ARCC_DIVISION_RCCL
  AND r.RCCL_SUCURSAL_IMP = a.ARCC_SUCURSAL_RCCL
  AND r.RCCL_TIPO_REC = a.ARCC_TIPO_RCCL
  AND r.RCCL_NUMERO_RCCL = a.ARCC_NUMERO_RCCL
WHERE r.RCCL_FECHA_BAJA IS NULL AND r.RCCL_FECHA_EMI IS NOT NULL
  AND a.ARCC_CTACTE_VCTC IN (SELECT CTEC_CTACTE_CTEC FROM CCOB_CTEC WHERE CTEC_DIVISION = ?)
UNION ALL
SELECT a.AOPC_CTACTE_VCTC, a.AOPC_RENGLON_VCTC,
       o.OPCL_FECHA_EMI,
       a.AOPC_IMP_APL_ORI, a.AOPC_IMP_APL_LOC
FROM CCOB_AOPC a
INNER JOIN CCOB_OPCL o
   ON o.OPCL_DIVISION_OPCL = a.AOPC_DIVISION_OPCL
  AND o.OPCL_SUCURSAL_IMP = a.AOPC_SUCURSAL_OPCL
  AND o.OPCL_TIPO_OPCL = a.AOPC_TIPO_OPCL
  AND o.OPCL_NUMERO_OPCL = a.AOPC_NUMERO_OPCL
WHERE o.OPCL_FECHA_BAJA IS NULL AND o.OPCL_FECHA_EMI IS NOT NULL
  AND a.AOPC_CTACTE_VCTC IN (SELECT CTEC_CTACTE_CTEC FROM CCOB_CTEC WHERE CTEC_DIVISION = ?)
UNION ALL
SELECT a.DCCB_CTACTE_VCTC, a.DCCB_RENGLON_VCTC,
       b.CCCB_FECHA_EMI,
       a.DCCB_IMP_APL_ORI, a.DCCB_IMP_APL_LOC
FROM CCOB_DCCB a
INNER JOIN CCOB_CCCB b
   ON b.CCCB_DIVISION_CCCB = a.DCCB_DIVISION_CCCB
  AND b.CCCB_SUCURSAL_IMP = a.DCCB_SUCURSAL_CCCB
  AND b.CCCB_TIPO_CCCB = a.DCCB_TIPO_CCCB
  AND b.CCCB_NUMERO_CCCB = a.DCCB_NUMERO_CCCB
WHERE b.CCCB_FECHA_BAJA IS NULL AND b.CCCB_FECHA_EMI IS NOT NULL
  AND a.DCCB_CTACTE_VCTC IN (SELECT CTEC_CTACTE_CTEC FROM CCOB_CTEC WHERE CTEC_DIVISION = ?)
"""


def _normalizar_fecha(valor):
    """'AAAA-MM-DD' (o `date`/`datetime`) -> `date`; cualquier otra cosa -> None."""
    if valor in (None, ''):
        return None
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    try:
        return datetime.datetime.strptime(str(valor).strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        logger.warning(f"Pendiente de cobro: fecha de corte invalida, se ignora: {valor!r}")
        return None


def _signo(row):
    return -1.0 if str(row.get('Signo') or '').strip().upper() == 'H' else 1.0


def _pesos(row, saldo_local, ps_list, dl_list):
    """El `PESOS` del informe, aplicado al saldo que se le pase (mismas reglas que el SQL)."""
    nombre = str(row.get('Cliente') or '')
    cotiz = row.get('Cotizacion_Comprobante')
    dia = row.get('Cotizacion_Dia')
    c = 0.0 if pd.isna(cotiz) else float(cotiz)
    d = 0.0 if pd.isna(dia) else float(dia)
    if nombre in ps_list:
        return saldo_local
    if nombre not in dl_list and str(row.get('TipoCliente') or '').strip() != '5' and c != d:
        return saldo_local
    return 0.0


def _dolares(row, saldo_origen, ps_list, dl_list):
    """El `DOLARES` del informe aplicado al saldo que se le pase. El saldo que llega YA
    viene con el signo del comprobante aplicado (lo aplica el SQL): no se repite."""
    nombre = str(row.get('Cliente') or '')
    cotiz = row.get('Cotizacion_Comprobante')
    dia = row.get('Cotizacion_Dia')
    c = 0.0 if pd.isna(cotiz) else float(cotiz)
    d = 0.0 if pd.isna(dia) else float(dia)
    if nombre in dl_list:
        return saldo_origen
    if nombre not in ps_list and (str(row.get('TipoCliente') or '').strip() == '5' or c == d):
        return saldo_origen
    return 0.0


def _query_informe(ps_list, dl_list, corte=None):
    """La consulta del informe. Con `corte` (una fecha anterior a hoy) cambia SOLO tres
    cosas: la fecha contra la que se mide la antiguedad, el filtro de saldo (entran las
    cuotas que hoy estan en 0) y el filtro de emision (solo lo emitido hasta el corte).
    Devuelve (sql, params_extra) — los `?` van siempre DESPUES del `?` de la division,
    salvo los de la antiguedad, que van en el SELECT y por eso van primero."""
    signo_sql = """
            CASE 
                WHEN c.CTEC_SIGNO = 'D' THEN 1
                WHEN c.CTEC_SIGNO = 'H' THEN -1
                ELSE 1
            END
        """
    if corte is None:
        fecha_aging = 'GETDATE()'
        filtro_saldo = 'AND (v.VCTC_SAL_ORI IS NOT NULL AND v.VCTC_SAL_ORI != 0)'
        filtro_emision = ''
    else:
        # La fecha va como TEXTO ISO con `CAST(? AS DATE)`: el driver ODBC viejo no puede
        # bindear un `date` de Python (falla con HYC00 "SQLBindParameter", medido el
        # 02/10/2026) y asi la conversion la hace SQL Server.
        fecha_aging = 'CAST(? AS DATE)'
        filtro_saldo = 'AND v.VCTC_SAL_ORI IS NOT NULL'
        filtro_emision = 'AND CAST(c.CTEC_FECHA_EMI AS DATE) <= CAST(? AS DATE)'

    return f"""
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
            c.CTEC_CTACTE_CTEC AS Ctacte,
            v.VCTC_RENGLON_VCTC AS Renglon,
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
                WHEN DATEDIFF(DAY, c.CTEC_FECHA_EMI, {fecha_aging}) > 90 THEN '> 90 días'
                WHEN DATEDIFF(DAY, c.CTEC_FECHA_EMI, {fecha_aging}) > 30 THEN '>30 días y <= 90 días'
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
          {filtro_saldo}
          {filtro_emision}
        ORDER BY cl.CLIE_NOMBRE ASC, c.CTEC_FECHA_EMI ASC
        """


def _aplicar_corte(df, aplicaciones, corte, ps_list, dl_list):
    """Cambia los saldos del informe por los de esa fecha y recalcula PESOS, DOLARES y
    `Saldo_*` sobre ellos. `Rango_Dias` ya viene medido contra el corte desde el SQL."""
    aplicaciones = aplicaciones.copy()
    aplicaciones['Fecha'] = pd.to_datetime(aplicaciones['Fecha']).dt.date
    aplicaciones['Clave'] = list(zip(
        pd.to_numeric(aplicaciones['Ctacte'], errors='coerce').fillna(0).astype('int64'),
        pd.to_numeric(aplicaciones['Renglon'], errors='coerce').fillna(0).astype('int64')))
    # `limpiar_datos` puede haber dejado las claves como texto: se convierten igual.
    df = df.copy()
    df['Clave'] = list(zip(
        pd.to_numeric(df['Ctacte'], errors='coerce').fillna(0).astype('int64'),
        pd.to_numeric(df['Renglon'], errors='coerce').fillna(0).astype('int64')))

    posteriores = aplicaciones[aplicaciones['Fecha'] > corte]
    extra_ori = posteriores.groupby('Clave')['AplicadoOrigen'].sum().to_dict()
    extra_loc = posteriores.groupby('Clave')['AplicadoLocal'].sum().to_dict()

    ajustadas = []
    for _, row in df.iterrows():
        clave = row['Clave']
        fila = row.copy()
        # El `Saldo_*` del SQL ya viene con el signo del comprobante aplicado (los
        # comprobantes 'H' van en negativo): lo que se suma entra con ESE signo.
        signo = _signo(fila)
        fila['Saldo_Origen'] = float(fila['Saldo_Origen']) + signo * float(extra_ori.get(clave, 0.0))
        fila['Saldo_Local'] = float(fila['Saldo_Local']) + signo * float(extra_loc.get(clave, 0.0))
        # Ya cobrado ANTES del corte: no estaba pendiente a esa fecha.
        if abs(float(fila['Saldo_Origen'])) < 0.005 and abs(float(fila['Saldo_Local'])) < 0.005:
            continue
        fila['PESOS'] = _pesos(fila, float(fila['Saldo_Local']), ps_list, dl_list)
        fila['DOLARES'] = _dolares(fila, float(fila['Saldo_Origen']), ps_list, dl_list)
        ajustadas.append(fila)
    if not ajustadas:
        return df.iloc[0:0].drop(columns=['Clave'], errors='ignore')
    return pd.DataFrame(ajustadas).drop(columns=['Clave'], errors='ignore')


def _armar_detalle(df):
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
    return detalle


def obtener_pendiente_cobro(base_override=None, sociedad_override=None, fecha_corte=None):
    """El informe de hoy (sin `fecha_corte`) o el pendiente AL CORTE indicado."""
    try:
        if base_override:
            conn, division = get_db_connection_base(base_override, sociedad_override)
        else:
            conn, division = get_db_connection()

        clientes_ps = get_clientes_forzados_ps(division) if 'get_clientes_forzados_ps' in globals() else []
        clientes_dl = get_clientes_forzados_dl(division) if 'get_clientes_forzados_dl' in globals() else []

        ps_list = list(clientes_ps or [])
        dl_list = list(clientes_dl or [])
        ps_sql = "', '".join(ps_list) if ps_list else "''"
        dl_sql = "', '".join(dl_list) if dl_list else "''"

        corte = _normalizar_fecha(fecha_corte)
        hoy = datetime.date.today()
        # La fecha de HOY (o una futura) no cambia nada: sale el informe de siempre.
        usa_corte = corte is not None and corte < hoy

        query = _query_informe(ps_sql, dl_sql, corte if usa_corte else None)
        if usa_corte:
            # Orden de los `?`: los DOS de la antiguedad (van en el SELECT), el de la
            # division y el del filtro de emision. La fecha va como texto ISO (ver
            # `_query_informe`). El chequeo de abajo evita que un cambio futuro en el SQL
            # rompa con "parameter markers" (paso el 02/10/2026, dos veces).
            corte_iso = corte.strftime('%Y-%m-%d')
            params = [corte_iso, corte_iso, division, corte_iso]
            marcas = query.count('?')
            if marcas != len(params):
                raise ValueError(
                    f"la consulta del corte tiene {marcas} marcas (?) y se le pasaron "
                    f"{len(params)} parametros")
            df = pd.read_sql(query, conn, params=params)
            aplicaciones = pd.read_sql(SQL_APLICACIONES, conn,
                                       params=[division, division, division])
        else:
            df = pd.read_sql(query, conn, params=[division])
            aplicaciones = None
        conn.close()

        df = df.replace([float('inf'), float('-inf')], 0)
        df = df.fillna(0)
        df = limpiar_datos(df)

        if usa_corte:
            df = _aplicar_corte(df, aplicaciones, corte, ps_list, dl_list)

        detalle = _armar_detalle(df)

        return {
            'success': True,
            'data': detalle,
            'total_registros': len(detalle),
            'fecha_corte': corte.strftime('%Y-%m-%d') if usa_corte else None
        }

    except Exception as e:
        logger.error(f"Error en pendiente_cobro_service: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e), 'data': [], 'total_registros': 0}
