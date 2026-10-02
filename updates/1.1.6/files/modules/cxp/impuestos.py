# modules/cxp/impuestos.py
# ============================================================
# IMPUESTOS ESPECIALES DE GUATEMALA (IDP Y TURISMO) - PARTE PURA
# ============================================================
# Vive aca y no en `parser.py` porque el parser importa `config`, `pdfplumber` y
# `pytesseract` a nivel de modulo: un test no lo puede cargar sin `.env.local` y
# la config de la app. Este modulo solo usa la stdlib (`re`).
import re

# Impuestos especiales de Guatemala: el IDP del combustible y el turismo del
# hospedaje. NO son IVA: van dentro del bruto (guia de cuentas, "Modificacion
# Base Imponible"). El parser los separa para poder calcular la base imponible.
PATRONES_ESPECIAL = (
    r'IMPUESTO\s+IDP\s*[:\s]\s*([\d,.]+)',
    r'IDP\s*\(?Q?\)?\s*[:\s]\s*([\d,.]+)',
    # El rotulo del hospedaje es TURISMO ("TURISMO", "TURISMO HOSPEDAJE"): la
    # palabra suelta HOSPEDAJE es la descripcion del servicio y trae el importe
    # de la linea, no el impuesto. Los typos del OCR van como alternativas
    # literales (TURSNMO = I leida como N, TURISM0 = O leida como cero) y no
    # como clase de caracteres: la clase no puede cubrir la I que el OCR se
    # come (`TUR[SN0]MO` matchea TURSNMO y TURNMO, pero "TURISMO" tiene una I
    # entre la R y la S, asi que esa clase nunca lo matcheo). Una clase mas
    # suelta como `TUR\w{0,2}[MN][0O]` seria peor: agarra "turno".
    r'(?:TURISMO|TURSNMO|TURISM0)\s*(?:HOSPEDAJE)?[\s:]\s*([\d,.]+)',
)


def _monto(texto):
    """Importe del texto del rotulo, con el formato local (coma decimal).

    Los importes de estos impuestos son chicos (Q5,26 / Q12,29), asi que una
    coma sola es siempre el separador decimal y nunca el de miles: "12,29" son
    12,29 y no 1229.
    """
    try:
        t = str(texto).strip()
        if ',' in t and '.' in t:
            t = t.replace('.', '').replace(',', '.')   # 1.234,56
        elif ',' in t:
            t = t.replace(',', '.')                    # 12,29
        return float(t)
    except (TypeError, ValueError):
        return None


def detectar_impuesto_especial(texto):
    """Importe del impuesto especial (IDP o turismo) tal como aparece en la factura.

    Gana el PRIMER PATRON de `PATRONES_ESPECIAL`, en el orden de la tupla, que
    tenga coincidencia (no el rotulo que aparece primero en el texto) y de ese
    patron se toma su primer importe. Los patrones se solapan a proposito (una
    linea "IMPUESTO IDP: 4,67" la agarran el patron del IDP y el generico) y
    sumarlos contaba dos veces el mismo impuesto. Por eso, con
    "IDP (Q) 5.26 ... IMPUESTO IDP: 4.67" gana el patron 2 y devuelve 4.67, y
    con "HOSPEDAJE 999.00 TURISMO 12.29" (ya sin el patron suelto de HOSPEDAJE)
    devuelve 12.29.
    """
    t = texto or ''
    for patron in PATRONES_ESPECIAL:
        m = re.search(patron, t, re.I)
        if m:
            valor = _monto(m.group(1))
            if valor:
                return round(valor, 2)
    return 0.0


def detectar_tipo(texto):
    """(tipo, aviso). Sin la leyenda NO se asume FCP: queda sin definir."""
    t = texto or ''
    # La leyenda real viene en singular ("SUIETO A PAGO TRIMESTRAL", factura n.1
    # de la rendicion: el OCR lee SUIETO por SUJETO) o en plural ("SUJETO A PAGOS
    # TRIMESTRALES ISR"). El patron acepta las dos formas.
    if re.search(r'SU[IJ]ETO[S]?\s+A\s+PAGOS?\s+TRIMESTRAL(?:ES)?', t, re.I):
        return 'FCP', ''
    if re.search(r'NO\s+GENERA\s+(DERECHO\s+A\s+)?CR[EÉ]DITO\s+FISCAL', t, re.I):
        return 'FCC', ''
    return '', 'sin leyenda de tipo: elegi FCP o FCC'


def calcular_impuestos(texto, total, iva_explicito=None, tipo=None):
    """(base, iva, bruto, especial) de la factura, o None si no hay datos.

    Regla (guia de cuentas + confirmacion del usuario 19/09/2026):
      - Sin tipo ('', que es lo que devuelve `detectar_tipo` cuando la factura no
        trae la leyenda): NO se calcula IVA. No se puede saber si es FCP o FCC,
        asi que no se inventa nada: iva 0, bruto = total, base = total - especial.
        La pantalla le pide al operador que elija FCP o FCC y se recalcula.
      - FCC: el total es el bruto y el IVA es 0 (el impuesto especial no se separa).
      - FCP: base = (total - especial) / 1.12; iva = total - especial - base;
             bruto = base + especial.
    """
    tipo = tipo if tipo is not None else detectar_tipo(texto)[0]
    total = float(total or 0)
    if total <= 0:
        return None
    especial = round(float(detectar_impuesto_especial(texto)), 2)
    if tipo == 'FCC':
        return {'imp_especial': 0.0, 'base_imponible': total, 'imp_bruto': total,
                'imp_iva': 0.0, 'tasa_iva': 0}
    if not tipo:
        # Sin leyenda de tipo: ni IVA ni base calculados (punto 6 de la spec).
        if especial >= total:
            especial = 0.0
        return {'imp_especial': especial, 'base_imponible': round(total - especial, 2),
                'imp_bruto': total, 'imp_iva': 0.0, 'tasa_iva': 0}
    if especial and especial >= total:
        especial = 0.0            # el dato no puede ser mayor que la factura: se ignora
    subtotal = total - especial
    base = round(subtotal / 1.12, 2)
    iva = round(subtotal - base, 2)
    if iva_explicito and iva_explicito > 0:
        # El IVA impreso manda: se recalcula la base para que la suma cierre.
        iva = round(float(iva_explicito), 2)
        base = round(subtotal - iva, 2)
    return {'imp_especial': especial, 'base_imponible': base,
            'imp_bruto': round(base + especial, 2), 'imp_iva': iva, 'tasa_iva': 12}
