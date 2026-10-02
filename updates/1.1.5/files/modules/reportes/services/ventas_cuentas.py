# modules/reportes/services/ventas_cuentas.py
# ============================================================
# DEFINICIÓN ÚNICA DE "VENTAS" PARA LOS REPORTES DE VENTAS
# (Ventas Globales = consolidado_total, Ventas por País = consolidado_pais)
# ============================================================
# Fuente: las LÍNEAS DEL ASIENTO (SIST_RASI) imputadas a las cuentas de venta.
#
#   * Sin filtro de subdiario: entran TODOS los comprobantes que toquen las
#     cuentas de venta (facturas, notas de crédito/débito, ajustes), no sólo
#     el subdiario 'VTA'.
#   * Intercompany excluida: por tipo de cliente ('5') O por nombre
#     ('%SIDESYS%'). Se evalúa a nivel ASIENTO: si alguna cuenta corriente del
#     asiento es intercompany, se excluye el asiento completo.
#   * El importe sale de la línea 410101/410102 (no de las líneas analíticas
#     de SIST_AASI), con el signo contable: debe positivo, haber negativo.
#
# Verificado contra el mayor del ERP (CONT_TOTM): el total de estas líneas
# coincide al centavo con el saldo de 410101 + 410102 en las 11 bases.
# ============================================================

CUENTAS_VENTA = ('410101', '410102')
TIPO_CLIENTE_INTERCOMPANY = '5'
PATRON_INTERCOMPANY_NOMBRE = '%SIDESYS%'


def cuentas_sql():
    """Lista de cuentas lista para un IN (...) (valores internos, no de usuario)."""
    return ", ".join(f"'{c}'" for c in CUENTAS_VENTA)


def join_ventas():
    """Cabecera del asiento + su línea, uniendo también por DIVISIÓN.

    La división importa: en Argentina conviven las divisiones 1 y 2 en la misma
    base, y unir sólo por número de asiento puede mezclar renglones.
    """
    return """
        FROM SIST_CASI c
        INNER JOIN SIST_RASI r
                ON r.RASI_DIVISION = c.CASI_DIVISION
               AND r.RASI_ASIENTO = c.CASI_ASIENTO
    """


def filtro_intercompany():
    """Exclusión de intercompany (tipo 5 O nombre SIDESYS) por asiento."""
    return """
          AND NOT EXISTS (
              SELECT 1 FROM CCOB_RACC ra
              INNER JOIN CCOB_CTEC ct ON ra.RACC_CTACTE_CTEC = ct.CTEC_CTACTE_CTEC
              INNER JOIN CCOB_CLIE cl ON ct.CTEC_CLIENTE = cl.CLIE_CLIENTE
              WHERE ra.RACC_ASIENTO = c.CASI_ASIENTO
                AND (cl.CLIE_TIPO_CLI = ? OR cl.CLIE_NOMBRE LIKE ?))
    """


def param_intercompany():
    """Parámetros de filtro_intercompany(), en orden."""
    return [TIPO_CLIENTE_INTERCOMPANY, PATRON_INTERCOMPANY_NOMBRE]


def apply_cliente(alias='cli'):
    """Nombre del cliente del asiento. OUTER APPLY TOP 1: nunca multiplica filas
    (un asiento puede tener más de una cuenta corriente)."""
    return f"""
        OUTER APPLY (
            SELECT TOP 1 cl.CLIE_NOMBRE AS CLIE_NOMBRE
            FROM CCOB_RACC ra
            INNER JOIN CCOB_CTEC ct ON ra.RACC_CTACTE_CTEC = ct.CTEC_CTACTE_CTEC
            INNER JOIN CCOB_CLIE cl ON ct.CTEC_CLIENTE = cl.CLIE_CLIENTE
            WHERE ra.RACC_ASIENTO = c.CASI_ASIENTO
            ORDER BY ra.RACC_CTACTE_CTEC
        ) {alias}
    """


def apply_analitica(alias='an'):
    """Centro de costo / CC cliente desde la imputación analítica del asiento
    (CONT_IMAE). Si el asiento no tiene líneas analíticas quedan NULL; se
    prioriza el renglón analítico que corresponde a la línea de venta."""
    return f"""
        OUTER APPLY (
            SELECT TOP 1 i.IMAE_DESCRIPCION2 AS CC_CLIENTE,
                         i.IMAE_DESCRIPCION3 AS CENTRO_COSTO
            FROM SIST_AASI a
            INNER JOIN CONT_IMAE i
                    ON i.IMAE_MAESTRO = a.AASI_MAESTRO
                   AND i.IMAE_INSTANCIA = a.AASI_INSTANCIA
            WHERE a.AASI_DIVISION = c.CASI_DIVISION
              AND a.AASI_ASIENTO = c.CASI_ASIENTO
            ORDER BY CASE WHEN a.AASI_RENGLON_ASI = r.RASI_RENGLON THEN 0 ELSE 1 END
        ) {alias}
    """


def importe_con_signo(columna):
    """Importe con signo contable (debe positivo, haber negativo). `columna` es
    un nombre de columna interno (RASI_IMP_LOC / RASI_IMP_CON / RASI_IMP_ORI)."""
    return f"CASE WHEN r.RASI_SIGNO = 'D' THEN -r.{columna} ELSE r.{columna} END"


def rango_fechas(anio):
    """Rango [desde, hasta) para filtrar por CASI_FECHA usando índices en lugar
    de YEAR(CASI_FECHA) = ?."""
    return (f"{int(anio)}-01-01", f"{int(anio) + 1}-01-01")


def a_usd(importe_local, importe_conversion, cotizacion=None, es_ecuador=False):
    """Regla ÚNICA de conversión a USD de los informes de ventas.

    La usan Ventas Globales (por mes y país) y Ventas por País (por comprobante),
    así los dos muestran el mismo número para el mismo país/año.

      * Ecuador: su moneda local ya es USD -> se usa tal cual.
      * Con cotización del mes (> 0): importe local / cotización.
      * Sin cotización: el importe de conversión del comprobante; si es 0, el local.

    Los dos importes deben venir CON SIGNO contable (debe negativo, haber
    positivo): dividir cada línea por la cotización del mes da el mismo total que
    dividir el acumulado del mes, que es lo que hace Ventas Globales.
    """
    try:
        local = float(importe_local or 0)
    except (TypeError, ValueError):
        local = 0.0
    if es_ecuador:
        return local
    try:
        cot = float(cotizacion) if cotizacion is not None else 0.0
    except (TypeError, ValueError):
        cot = 0.0
    if cot > 0:
        return local / cot
    try:
        conversion = float(importe_conversion or 0)
    except (TypeError, ValueError):
        conversion = 0.0
    return conversion if conversion != 0 else local
