# modules/cxp/servicio_comprobantes.py
# ============================================================
# Capa unica de comprobantes de CxP (Etapa 2). Modulo PURO: solo stdlib y el
# plan de cuentas de `cuentas.py`. No importa Flask, pyodbc, config ni
# database, asi que se testea sin app y sin base (los tests lo cargan por
# ruta: tests/cargar_servicio.py::cargar_cxp).
#
# Toda operacion arma UN lote SQL con SET XACT_ABORT ON + transaccion +
# guardas RAISERROR('CXP_...|mensaje') + verificacion de la invariante de
# totales (CONT_TOTM/CONT_TOTD) antes del COMMIT.
#
# Los valores de pais NO estan en el cuerpo del SQL: salen de
# PARAMETROS_CXP[ctx.base]. Hoy hay UNA sola entrada (Guatemala): cualquier
# otra base se rechaza con CXP_VAL_BASE y no escribe nada (fail-closed).
# ============================================================

import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP

from cuentas import CUENTAS

PREFIJO_VAL = 'CXP_VAL_'
PREFIJO_INT = 'CXP_INT_'

# Las columnas de importe medidas son DECIMAL(14,2): 12 digitos enteros. La spec
# pide <= 15 como cota, pero 13 digitos moririan como overflow de SQL (500) en
# vez de salir como 400 con codigo.
MAX_DIGITOS_IMPORTE = 12
# CTEP_COTIZACION es DECIMAL(14,5): 9 digitos enteros.
MAX_DIGITOS_COTIZACION = 9
# SIST_RASI.RASI_CUENTA es varchar(15): ahi van la cuenta de gasto y la del
# proveedor.
MAX_LARGO_CUENTA = 15
# SIST_RASI.RASI_DESCRIPCION y SIST_CASI.CASI_COMENTARIO son varchar(30).
MAX_LARGO_DESCRIPCION = 30

CENTAVOS = Decimal('0.01')

# Regla de duplicados: 0 = misma fecha exacta (el duplicado real -doble clic,
# reintento, archivo cargado dos veces- es del mismo dia).
DIAS_VENTANA_DUPLICADO = 0

# Numerador del ERP del asiento ("ultimo numero asiento unificador", medido:
# 91.088 en GT al 18/09/2026).
NUMERADOR_ASIENTO_ID = 23

# Tipos de comprobante que carga la APLICACION (la UI solo ofrece estos dos,
# `frontend/modules/cxp/render.js:140-141`). El patron de la columna
# (CDPR_TIPO_CDPR varchar(3)) acepta cualquier codigo de 3 caracteres, pero este
# circuito NO escribe el arbol `COMP_*`: un `FMR` (lo genera el ERP) que entrara
# por aca dejaria comprobante, cuenta corriente y asiento escritos sin ese arbol,
# o sea un comprobante a medias. Se rechaza con CXP_VAL_TIPO.
TIPOS_ALTA = ('FCP', 'FCC')

# Tolerancia del IVA contra la tasa declarada (redondeo al centavo del PDF).
TOLERANCIA_IVA = Decimal('0.05')

# Patrones de los codigos, acotados al largo de la columna medida.
PATRON_COND_PAGO = r'^[A-Z0-9_\-]{1,3}$'     # CTEP_COND_PAGO varchar(3)
PATRON_MONEDA = r'^[A-Z]{2,3}$'              # CTEP_MONEDA varchar(3)
PATRON_TIPO = r'^[A-Z0-9]{1,3}$'             # CDPR_TIPO_CDPR varchar(3)
PATRON_CUENTA = r'^[0-9A-Z\-\.]{1,15}$'      # RASI_CUENTA varchar(15)
PATRON_CCO = r'^[0-9A-Z\-\.]{1,9}$'          # SIST_AASI.AASI_INSTANCIA varchar(9)

# Parametros por base (spec 4.8). Una sola entrada cargada: Guatemala es la
# unica base donde CxP escribe. Habilitar otro pais es agregar su entrada
# medida, no tocar el camino de escritura.
PARAMETROS_CXP = {
    'plataforma_gt': {
        'pais': 'GT',
        'cuenta_iva': '110401001',
        'descripcion_iva': 'IVA 12% GUATEMALA',
        'tasa_iva': 12,
        'cuenta_prov_local': '210101001',
        'cuenta_prov_extranjera': '210101002',
        'origen': 'CPCV',
        'subdiario': 'CPA',
        'localidad_eventual': 'Guatemala',
        'cuentas_gasto': CUENTAS,   # hoy, la lista de cuentas.py (plan de cuentas de Guatemala)
    },
}

# Mensajes (una sola fuente: los tests verifican el codigo y el operador lee el
# texto).
MENSAJE_CLAVE_INVALIDA = "Clave de idempotencia invalida."
MENSAJE_CLAVE_REUTILIZADA = ("La clave de idempotencia ya fue usada con otro contenido: "
                             "reenviá la operación con una clave nueva.")
MENSAJE_MOTIVO = "El motivo es obligatorio para eliminar un comprobante."
MENSAJE_CLIENTE_VIEJO = ("Recargá la pantalla (Ctrl+F5) e intentá de nuevo: la baja identifica "
                         "el comprobante por su número interno, no por el Nro. DTE del PDF.")


class ErrorValidacion(Exception):
    """Error de datos o de negocio: el endpoint responde 400 con `codigo`."""

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


class ErrorServicio(Exception):
    """Error de integridad/estado: el endpoint responde 409 con `codigo` y, si
    el error trae datos extra (p.ej. la lista de bloqueos de una baja), con
    `datos`."""

    def __init__(self, codigo, mensaje, datos=None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.datos = datos or {}


class Contexto:
    """Base activa, division del comprobante y usuario (auditoria)."""

    __slots__ = ('base', 'division', 'usuario')

    def __init__(self, base, division, usuario=''):
        self.base = str(base or '')
        self.division = int(division)
        self.usuario = str(usuario or '')


def lit(valor):
    """Literal SQL. Misma semantica que `_sql_literal` de shared/database.py (no
    se importa de ahi porque ese modulo arrastra Flask)."""
    if valor is None:
        return 'NULL'
    if isinstance(valor, bool):
        return '1' if valor else '0'
    if isinstance(valor, (int, Decimal)):
        return str(valor)
    if isinstance(valor, float):
        return repr(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def num(valor, decimales=2):
    """Importe normalizado a texto para el SQL (cantidad fija de decimales)."""
    if valor in (None, ''):
        return 'NULL'
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ErrorValidacion(PREFIJO_VAL + 'IMPORTE', 'El importe no es un numero valido.')
    if not numero.is_finite():
        raise ErrorValidacion(PREFIJO_VAL + 'IMPORTE', 'El importe tiene que ser finito.')
    return str(numero.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP))


def parametros_cxp(ctx):
    """Parametros de la base activa o CXP_VAL_BASE (fail-closed: sin entrada, no
    se escribe)."""
    parametros = PARAMETROS_CXP.get(ctx.base)
    if parametros is None:
        raise ErrorValidacion(
            PREFIJO_VAL + 'BASE',
            "El módulo de Cuentas a Pagar todavía no está habilitado para la base '" +
            str(ctx.base) + "': no se cargó ningún comprobante.")
    return parametros


# ============================================================
# VALIDACION DE FORMA (spec 4.2)
# ============================================================

def validar_fecha(valor, campo, obligatoria=False, codigo=None):
    codigo = codigo or (PREFIJO_VAL + 'FECHA')
    if valor in (None, ''):
        if obligatoria:
            raise ErrorValidacion(codigo, "El campo '" + campo + "' es obligatorio (formato AAAA-MM-DD).")
        return None
    try:
        return date.fromisoformat(str(valor).strip()).isoformat()
    except (TypeError, ValueError):
        raise ErrorValidacion(codigo, "El campo '" + campo + "' tiene que tener formato AAAA-MM-DD.")


def validar_entero(valor, campo, codigo=None, positivo=False):
    codigo = codigo or (PREFIJO_VAL + 'ENTERO')
    if isinstance(valor, bool):
        raise ErrorValidacion(codigo, "El campo '" + campo + "' tiene que ser un numero entero.")
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ErrorValidacion(codigo, "El campo '" + campo + "' tiene que ser un numero entero.")
    if positivo and numero <= 0:
        raise ErrorValidacion(codigo, "El campo '" + campo + "' tiene que ser mayor que cero.")
    return numero


def validar_importe(valor, campo, obligatorio=False, default=0, codigo=None,
                    max_digitos=MAX_DIGITOS_IMPORTE, decimales=2):
    codigo = codigo or (PREFIJO_VAL + 'IMPORTE')
    if valor in (None, ''):
        if obligatorio:
            raise ErrorValidacion(codigo, "El campo '" + campo + "' es obligatorio.")
        valor = default
    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ErrorValidacion(codigo, "El campo '" + campo + "' tiene que ser un numero.")
    if not numero.is_finite():
        raise ErrorValidacion(codigo, "El campo '" + campo + "' tiene que ser un numero finito.")
    if numero < 0:
        raise ErrorValidacion(codigo, "El campo '" + campo + "' no puede ser negativo.")
    if numero.to_integral_value(rounding=ROUND_DOWN) >= Decimal(10) ** max_digitos:
        raise ErrorValidacion(codigo, "El campo '" + campo + "' admite hasta " +
                              str(max_digitos) + " digitos enteros.")
    return numero.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


def validar_codigo(valor, campo, patron, default=None, obligatoria=False, codigo=None):
    codigo = codigo or (PREFIJO_VAL + 'CODIGO')
    if valor in (None, ''):
        if obligatoria:
            raise ErrorValidacion(codigo, "El campo '" + campo + "' es obligatorio.")
        return default
    limpio = str(valor).strip().upper()
    if not re.fullmatch(patron, limpio):
        raise ErrorValidacion(codigo, "El campo '" + campo + "' no es valido: " + limpio)
    return limpio


def validar_renglones(renglones, cuenta_gasto=None, cco_codigo=None, bruto=None):
    """Renglones de gasto. Sin `renglones` se acepta el atajo actual del alta
    (`cuenta_gasto` + `cco_codigo` del cuerpo -> un solo renglon por el bruto).
    Todos los renglones son de DEBE: un importe positivo en una cuenta de gasto
    es un debito (el unico signo que el alta sabe expresar)."""
    codigo = PREFIJO_VAL + 'RENGLON'
    if not renglones:
        if cuenta_gasto:
            renglones = [{'cuenta': cuenta_gasto, 'importe': bruto, 'cco': cco_codigo}]
    if not isinstance(renglones, (list, tuple)) or not renglones:
        raise ErrorValidacion(codigo, "El comprobante tiene que tener al menos un renglon de gasto.")
    normalizados = []
    for numero, renglon in enumerate(renglones, start=1):
        if not isinstance(renglon, dict):
            raise ErrorValidacion(codigo, "El renglon " + str(numero) + " no es un objeto.")
        cuenta = validar_codigo(renglon.get('cuenta'), 'cuenta del renglon ' + str(numero),
                                PATRON_CUENTA, codigo=codigo)
        if cuenta is None:
            raise ErrorValidacion(codigo, "El renglon " + str(numero) + " no tiene cuenta contable.")
        importe = validar_importe(renglon.get('importe'), 'importe del renglon ' + str(numero),
                                  obligatorio=True, codigo=codigo)
        if importe <= 0:
            raise ErrorValidacion(codigo, "El importe del renglon " + str(numero) +
                                  " tiene que ser mayor que cero.")
        signo = str(renglon.get('signo') or 'D').strip().upper()
        if signo != 'D':
            raise ErrorValidacion(codigo, "El renglon " + str(numero) +
                                  " solo admite signo 'D' (debe): el alta no carga renglones al haber.")
        cco = str(renglon.get('cco') or '').strip().upper()
        if cco and not re.fullmatch(PATRON_CCO, cco):
            raise ErrorValidacion(codigo, "El centro de costo del renglon " + str(numero) + " no es valido.")
        normalizados.append({
            'cuenta': cuenta,
            'importe': importe,
            'descripcion': str(renglon.get('descripcion') or '').strip()[:MAX_LARGO_DESCRIPCION],
            'cco': cco,
            'signo': 'D',
        })
    return normalizados


def validar_eventual(eventual):
    """Proveedor eventual (CPAG_NCTP): el nombre, el CUIT y la localidad se
    recortan al largo de la columna medida."""
    if not eventual:
        return None
    if not isinstance(eventual, dict):
        raise ErrorValidacion(PREFIJO_VAL + 'CODIGO', "Los datos del proveedor eventual no son un objeto.")
    return {
        'nombre': str(eventual.get('nombre') or '').strip()[:90],       # NCTP_NOMBRE varchar(90)
        'nit': str(eventual.get('nit') or '').strip()[:15],             # NCTP_CUIT varchar(15)
        'domicilio': str(eventual.get('domicilio') or '').strip()[:60],  # NCTP_DOMICILIO varchar(60)
        'localidad': str(eventual.get('localidad') or '').strip()[:50],  # NCTP_LOCALIDAD varchar(50)
    }


def cuenta_del_proveedor(parametros, datos, moneda):
    """Cuenta contable del proveedor: la del cuerpo si vino; si no, la de la
    tabla de parametros de la base (local o extranjera)."""
    cuenta = str(datos.get('cuenta_prov') or '').strip()
    if cuenta:
        return validar_codigo(cuenta, 'cuenta_prov', PATRON_CUENTA)
    eventual = datos.get('eventual')
    if eventual:
        localidad = str((eventual or {}).get('localidad') or '').strip().upper()
        propias = (str(parametros['pais']).strip().upper(),
                   str(parametros['localidad_eventual']).strip().upper(), '')
        if moneda == 'DL' and localidad not in propias:
            return parametros['cuenta_prov_extranjera']
    return parametros['cuenta_prov_local']


def importes_locales(bruto, iva, total, moneda, cotizacion, especial=Decimal('0')):
    """Importes locales del comprobante. En quetzales (PS) no hay conversion: la
    cotizacion es 1 y el importe local es el del documento. `especial` es el
    impuesto especial (IDP/turismo) y `base_loc` sale por resta, para que
    bruto_loc = base_loc + especial_loc se cumpla exacto."""
    if moneda == 'PS':
        return {'bruto_loc': bruto, 'iva_loc': iva, 'total_loc': total,
                'especial_loc': especial, 'base_loc': bruto - especial,
                'cotizacion_conv': Decimal('1')}
    bruto_loc = (bruto * cotizacion).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    total_loc = (total * cotizacion).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    especial_loc = (especial * cotizacion).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return {'bruto_loc': bruto_loc, 'iva_loc': total_loc - bruto_loc, 'total_loc': total_loc,
            'especial_loc': especial_loc, 'base_loc': bruto_loc - especial_loc,
            'cotizacion_conv': cotizacion}


def validar_alta(ctx, datos):
    """Valida la FORMA del alta y devuelve el diccionario normalizado (lo usan
    `sql_alta` y los tests). No escribe ni consulta nada: la existencia del
    proveedor y los duplicados son guardas del lote."""
    if not isinstance(datos, dict):
        raise ErrorValidacion(PREFIJO_VAL + 'ENTERO', 'El cuerpo del alta tiene que ser un objeto JSON.')
    parametros = parametros_cxp(ctx)
    division = validar_entero(ctx.division, 'division', positivo=True)
    tipo_comp = validar_codigo(datos.get('tipo_comp', 'FCP'), 'tipo_comp', PATRON_TIPO, default='FCP')
    # El patron de la columna acepta cualquier codigo de 3 caracteres, pero este
    # circuito solo sabe escribir los tipos que carga la aplicacion (ver
    # TIPOS_ALTA): cualquier otro seria un comprobante a medias.
    if tipo_comp not in TIPOS_ALTA:
        raise ErrorValidacion(
            PREFIJO_VAL + 'TIPO',
            "El tipo de comprobante '" + tipo_comp + "' no lo carga la aplicacion: "
            "solo se aceptan " + ' y '.join(TIPOS_ALTA) + ".")
    proveedor = validar_entero(datos.get('proveedor_id'), 'proveedor_id',
                               codigo=PREFIJO_VAL + 'PROVEEDOR', positivo=True)
    fecha = validar_fecha(datos.get('fecha'), 'fecha', obligatoria=True)
    fecha_vto = validar_fecha(datos.get('fecha_vto'), 'fecha_vto') or fecha
    if fecha_vto < fecha:
        raise ErrorValidacion(PREFIJO_VAL + 'FECHA',
                              "La fecha de vencimiento (" + fecha_vto +
                              ") no puede ser anterior a la fecha del comprobante (" + fecha + ").")
    bruto = validar_importe(datos.get('imp_bruto'), 'imp_bruto', obligatorio=True)
    iva = validar_importe(datos.get('imp_iva', 0), 'imp_iva')
    tasa = validar_importe(datos.get('tasa_iva', parametros['tasa_iva']), 'tasa_iva',
                           default=Decimal(str(parametros['tasa_iva'])),
                           max_digitos=3)
    # Impuesto especial (IDP del combustible, turismo del hospedaje): no es IVA y
    # va DENTRO del bruto (el bruto es lo que se distribuye en los renglones y lo
    # que guarda CTEP_IMP_BRU_ORI). La base imponible del IVA es el bruto menos el
    # especial; en un FCC el total es el bruto y el IVA es cero, asi que un
    # especial ahi seria inventar una base que el ERP no va a usar.
    especial = validar_importe(datos.get('imp_especial', 0), 'imp_especial')
    if especial < 0:
        raise ErrorValidacion(PREFIJO_VAL + 'IMPORTE',
                              "El impuesto especial (" + str(especial) + ") no puede ser negativo.")
    if especial and tasa == 0:
        raise ErrorValidacion(PREFIJO_VAL + 'IMPORTE',
                              "El impuesto especial (" + str(especial) + ") no corresponde a un "
                              "comprobante sin IVA: en un FCC el total es el bruto y el IVA es cero.")
    # La guarda de arriba esta atada a la TASA, asi que no alcanza para el FCC: un
    # payload incoherente que declare `FCC` con tasa 12 e IVA (o con especial) la
    # pasaba, y `lineas_asiento` le escribia un DEBITO a la cuenta de IVA: un
    # credito fiscal fantasma en un comprobante que no genera credito. La regla del
    # FCC es "el total es el bruto, el IVA es cero y no se separa nada", asi que
    # ninguno de los tres campos puede venir distinto de cero. Se miran los tres
    # por separado: con la tasa sola, un `imp_iva` > 0 sin tasa declarada seguiria
    # entrando.
    if tipo_comp == 'FCC' and (tasa != 0 or iva != 0 or especial != 0):
        raise ErrorValidacion(PREFIJO_VAL + 'IMPORTE',
                              "Un FCC (pequeno contribuyente) no lleva IVA ni impuesto especial: "
                              "el total es el bruto. Se recibio tasa_iva " + str(tasa) +
                              ", imp_iva " + str(iva) + " e imp_especial " + str(especial) +
                              "; los tres tienen que ser 0. Si la factura lleva IVA, cargala como FCP.")
    if especial >= bruto:
        raise ErrorValidacion(PREFIJO_VAL + 'IMPORTE',
                              "El impuesto especial (" + str(especial) + ") tiene que ser menor que el "
                              "bruto (" + str(bruto) + "): si no, la base imponible queda en cero o menos.")
    base_imponible = (bruto - especial).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    moneda = validar_codigo(datos.get('moneda', 'PS'), 'moneda', PATRON_MONEDA, default='PS')
    cotizacion = validar_importe(datos.get('cotizacion', 1), 'cotizacion', default=Decimal('1'),
                                 max_digitos=MAX_DIGITOS_COTIZACION, decimales=5)
    if moneda == 'PS':
        cotizacion = Decimal('1')
    # Se verifica sobre el valor YA normalizado (y despues del forzado de PS): una
    # cotizacion 0 en moneda extranjera dividia por cero mas abajo
    # (decimal.InvalidOperation, o sea un 500 opaco sin `codigo` en vez del 400
    # que corresponde). El quantize a 5 decimales tambien atrapa los valores que
    # la columna CTEP_COTIZACION guardaria como 0.
    if moneda != 'PS' and cotizacion <= 0:
        raise ErrorValidacion(PREFIJO_VAL + 'IMPORTE',
                              "La cotizacion (" + str(cotizacion) + ") tiene que ser mayor que cero "
                              "cuando la moneda no es PS: se recibio la moneda " + moneda + ".")
    cond_pago = validar_codigo(datos.get('cond_pago', '00'), 'cond_pago', PATRON_COND_PAGO, default='00')
    ref_prov = str(datos.get('ref_prov') or '').strip()[:15]     # CDPR_REF_PROV varchar(15)
    descripcion = str(datos.get('descripcion') or '').strip()[:MAX_LARGO_DESCRIPCION]
    renglones = validar_renglones(datos.get('renglones'), datos.get('cuenta_gasto'),
                                  datos.get('cco_codigo'), bruto)
    total = (bruto + iva).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    locales = importes_locales(bruto, iva, total, moneda, cotizacion, especial)
    proveedor_nombre = str(datos.get('proveedor_nombre') or '').strip()[:MAX_LARGO_DESCRIPCION]
    return {
        'division': division,
        'tipo_comp': tipo_comp,
        'proveedor': proveedor,
        'proveedor_nombre': proveedor_nombre,
        'cuenta_prov': cuenta_del_proveedor(parametros, datos, moneda),
        'fecha': fecha,
        'fecha_vto': fecha_vto,
        'ref_prov': ref_prov,
        'descripcion': descripcion,
        'cond_pago': cond_pago,
        'moneda': moneda,
        'cotizacion': cotizacion,
        'cotizacion_conv': locales['cotizacion_conv'],
        'tasa_iva': tasa,
        'imp_bruto': bruto,
        'imp_especial': especial,
        'base_imponible': base_imponible,
        'imp_iva': iva,
        'imp_total': total,
        'imp_bruto_loc': locales['bruto_loc'],
        'imp_especial_loc': locales['especial_loc'],
        'imp_base_loc': locales['base_loc'],
        'imp_iva_loc': locales['iva_loc'],
        'imp_total_loc': locales['total_loc'],
        'iva_con': (locales['iva_loc'] / locales['cotizacion_conv']).quantize(CENTAVOS, rounding=ROUND_HALF_UP),
        'prov_con': (locales['total_loc'] / locales['cotizacion_conv']).quantize(CENTAVOS, rounding=ROUND_HALF_UP),
        'renglones': renglones,
        'eventual': validar_eventual(datos.get('eventual')),
    }


# ============================================================
# DUPLICADOS (spec 4.3)
# ============================================================

def condicion_duplicado(datos):
    """Condicion SQL del duplicado: mismo tipo que se esta cargando, mismo
    proveedor, mismo importe total, misma fecha y -si la ref del proveedor que se
    esta cargando no esta vacia- la misma ref. La moneda entra en la comparacion
    porque el importe total esta en la moneda del documento: comparar totales de
    monedas distintas bloquearia dos facturas legitimamente distintas.

    El tipo NO se clava en 'FCP': sale del request y la app carga FCP y FCC
    (`TIPOS_ALTA`). Con el literal clavado, un alta FCC no se bloqueaba nunca
    contra un FCC ya cargado. Cualquier otro tipo (el `FMR` incluido, que el ERP
    genera con su arbol `COMP_*`) no llega hasta aca: `validar_alta` lo rechaza
    con `CXP_VAL_TIPO`.

    `datos` es el diccionario NORMALIZADO de `validar_alta`."""
    fecha = 'CONVERT(date, ' + lit(datos['fecha']) + ', 23)'
    condiciones = [
        'c.CDPR_TIPO_CDPR = ' + lit(datos['tipo_comp']),
        'c.CDPR_DIVISION_CDPR = ' + str(datos['division']),
        'c.CDPR_PROVEEDOR = ' + str(datos['proveedor']),
        'c.CDPR_FECHA_BAJA IS NULL',
        'c.CDPR_FECHA_EMI >= ' + fecha,
        'c.CDPR_FECHA_EMI < DATEADD(DAY, ' + str(DIAS_VENTANA_DUPLICADO + 1) + ', ' + fecha + ')',
        't.CTEP_IMP_TOT_ORI = ' + num(datos['imp_total']),
        't.CTEP_MONEDA = ' + lit(datos['moneda']),
    ]
    if datos['ref_prov']:
        condiciones.append('c.CDPR_REF_PROV = ' + lit(datos['ref_prov']))
    return ' AND '.join(condiciones)


def sql_duplicado(ctx, datos):
    """Guarda de duplicados: si ya existe un comprobante igual, levanta
    CXP_VAL_DUPLICADO mostrando el existente (tipo, numero, fecha, importe,
    proveedor y ref) para que el operador lo verifique. No escribe nada.

    Va DENTRO de la transaccion y antes de cualquier INSERT: un pre-chequeo
    aparte seria check-then-act y dos POST simultaneos pasarian los dos. El orden
    de las guardas del lote es division -> proveedor -> duplicado."""
    return f"""
DECLARE @dup VARCHAR(400);
SELECT TOP 1 @dup = 'CXP_VAL_DUPLICADO|Ya existe el comprobante ' + c.CDPR_TIPO_CDPR + ' '
        + CAST(CAST(c.CDPR_NUMERO_CDPR AS INT) AS VARCHAR(20))
        + ' del ' + CONVERT(VARCHAR(10), c.CDPR_FECHA_EMI, 120)
        + ' por ' + CAST(t.CTEP_IMP_TOT_ORI AS VARCHAR(30)) + ' ' + t.CTEP_MONEDA
        + ' del proveedor ' + CAST(c.CDPR_PROVEEDOR AS VARCHAR(20))
        + ' (ref. ' + ISNULL(NULLIF(LTRIM(RTRIM(c.CDPR_REF_PROV)), ''), 'sin referencia') + ').'
  FROM CPAG_CDPR c
  JOIN CPAG_RCCP r
    ON r.RCCP_DIVISION_CDPR = c.CDPR_DIVISION_CDPR
   AND r.RCCP_TIPO_CDPR = c.CDPR_TIPO_CDPR
   AND r.RCCP_NUMERO_CDPR = c.CDPR_NUMERO_CDPR
  JOIN CPAG_CTEP t ON r.RCCP_CTACTE_CTEP = t.CTEP_CTACTE_CTEP
 WHERE {condicion_duplicado(datos)}
 ORDER BY c.CDPR_NUMERO_CDPR DESC;
IF @dup IS NOT NULL
BEGIN
    -- RAISERROR interpreta los % del mensaje y la ref del proveedor es texto
    -- del usuario: se duplican antes de levantarlo.
    SET @dup = REPLACE(@dup, '%', '%%');
    RAISERROR(@dup, 16, 1);
END
"""


# ============================================================
# COHERENCIA CONTABLE DEL ALTA (spec 4.6)
# ============================================================

def verificar_iva(datos):
    """El IVA cargado tiene que coincidir con la tasa declarada SOBRE LA BASE
    IMPONIBLE (bruto menos impuesto especial), con la tolerancia del redondeo al
    centavo del documento (0,05). En las facturas sin impuesto especial la base y
    el bruto coinciden, asi que el control es el mismo de siempre."""
    base = datos['base_imponible']
    esperado = (base * datos['tasa_iva'] / Decimal(100)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    if abs(datos['imp_iva'] - esperado) > TOLERANCIA_IVA:
        raise ErrorValidacion(
            PREFIJO_VAL + 'IVA',
            "El IVA cargado (" + str(datos['imp_iva']) + ") no coincide con la tasa " +
            str(datos['tasa_iva']) + "% de la base (" + str(base) + "): esperado " +
            str(esperado) + ". La base es el bruto (" + str(datos['imp_bruto']) +
            ") menos el impuesto especial (" + str(datos['imp_especial']) + ").")


def renglones_con_residual(datos):
    """Reparte el residual del redondeo en el ULTIMO renglon (mecanismo actual)
    y rechaza el residual negativo: antes eso escribia un renglon negativo en
    silencio. Devuelve los renglones con `importe_loc` e `importe_con`."""
    conv = datos['cotizacion_conv']
    # El alta ya rechaza la cotizacion <= 0 cuando la moneda no es PS, pero esta
    # funcion es publica: sin esta guarda, un llamador que no lo sepa se come
    # una division por cero (InvalidOperation, o sea un 500 sin `codigo`).
    if conv <= 0:
        raise ErrorValidacion(
            PREFIJO_VAL + 'IMPORTE',
            "La cotizacion (" + str(conv) + ") tiene que ser mayor que cero para "
            "convertir los importes a moneda local.")
    renglones = [dict(renglon) for renglon in datos['renglones']]
    if datos['moneda'] == 'PS':
        locales = [renglon['importe'] for renglon in renglones]
    else:
        locales = [(renglon['importe'] * datos['cotizacion']).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
                   for renglon in renglones]
    suma = sum(locales, Decimal('0.00'))
    residual = (datos['imp_bruto_loc'] - suma).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    if residual < 0:
        raise ErrorValidacion(
            PREFIJO_VAL + 'RESIDUAL',
            "Los renglones suman " + str(suma) + " y el bruto del comprobante es " +
            str(datos['imp_bruto_loc']) + ": sobran " + str(-residual) +
            ". Corregí los importes (no se escribe un renglon negativo).")
    locales[-1] = locales[-1] + residual
    for renglon, importe_loc in zip(renglones, locales):
        renglon['importe_loc'] = importe_loc
        renglon['importe_con'] = (importe_loc / conv).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return renglones


# ============================================================
# FRAGMENTOS DEL LOTE DEL ALTA
# ============================================================

def lineas_asiento(datos, parametros, renglones):
    """Lineas del asiento (SIST_RASI): IVA (renglon 1, si hay), un renglon por
    renglon de gasto (desde el 2) y el proveedor al final (H). `ori` queda en 0:
    es lo que escribe hoy la app."""
    lineas = []
    if datos['imp_iva'] > 0:
        lineas.append({'renglon': 1, 'cuenta': parametros['cuenta_iva'], 'loc': datos['imp_iva_loc'],
                       'con': datos['iva_con'], 'ori': Decimal('0.00'), 'signo': 'D',
                       'descripcion': parametros['descripcion_iva'][:MAX_LARGO_DESCRIPCION],
                       'editable': 0, 'fija': 1, 'cco': ''})
    for indice, renglon in enumerate(renglones):
        lineas.append({'renglon': indice + 2, 'cuenta': renglon['cuenta'],
                       'loc': renglon['importe_loc'], 'con': renglon['importe_con'],
                       'ori': Decimal('0.00'), 'signo': 'D', 'descripcion': renglon['descripcion'],
                       'editable': 1, 'fija': 0, 'cco': renglon['cco']})
    lineas.append({'renglon': len(renglones) + 2, 'cuenta': datos['cuenta_prov'],
                   'loc': datos['imp_total_loc'], 'con': datos['prov_con'],
                   'ori': Decimal('0.00'), 'signo': 'H', 'descripcion': datos['proveedor_nombre'],
                   'editable': 0, 'fija': 1, 'cco': ''})
    return lineas


def _cierre_try_catch():
    return """
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
"""


def verificar_division(division):
    """La division tiene que EXISTIR: el servicio NO crea divisiones (spec 4.1.1).

    El `asegurar_division` anterior (`routes.py:32-52`) hacia
    `INSERT INTO SIST_DIVI (DIVI_DIVISION, DIVI_DESCRIPCION, DIVI_ABREVIATURA)`,
    pero `SIST_DIVI` no tiene esas dos ultimas columnas y tiene SEIS NOT NULL sin
    default (`DIVI_DIVISION`, `DIVI_NOMBRE`, `DIVI_UTILIZABLE`, `DIVI_DEFAULT`,
    `DIVI_SUCURSAL_SICO`, `DIVI_REQ_CERTIF_DEP`): ese INSERT fallaba SIEMPRE y
    nadie lo notaba porque la division 7 ya existe y el helper se tragaba la
    excepcion. Una division inexistente se rechaza sin escribir nada y se crea
    desde el ERP.

    El numero se normaliza con `validar_entero` (y tiene que ser positivo, igual
    que la division del alta) antes de interpolarlo: la funcion es publica y no
    depende de que el llamador lo haya validado."""
    division = validar_entero(division, 'division', positivo=True)
    return f"""
IF NOT EXISTS (SELECT 1 FROM SIST_DIVI WHERE DIVI_DIVISION = {division})
    RAISERROR('{PREFIJO_VAL}DIVISION|La division {division} no existe en esta base: creala desde el ERP antes de cargar comprobantes.', 16, 1);
"""


def _guarda_proveedor(proveedor):
    """El proveedor tiene que existir y estar vigente. La app lee el maestro de
    proveedores de `CPAG_PROV` (es la tabla que usa /api/proveedores)."""
    return f"""
IF NOT EXISTS (SELECT 1 FROM CPAG_PROV WHERE PROV_PROVEEDOR = {proveedor} AND PROV_FECHA_BAJA IS NULL)
    RAISERROR('{PREFIJO_VAL}PROVEEDOR|El proveedor {proveedor} no existe o esta dado de baja.', 16, 1);
"""


def _numeracion(ctx, datos):
    """Todas las reservas de numero, DENTRO de la transaccion y con el bloqueo
    tomado hasta el final (UPDLOCK + HOLDLOCK).

    El UPDATE del contador del ERP NO escribe `NUSI_ULT_ACTUALIZACION_USUARIO`:
    esa columna tiene la FK `USUA_R106` contra `SEGU_USUA.USUA_USUARIO`
    (habilitada) y el usuario de la aplicacion es el del SSO de Windows, que no
    es un usuario del ERP. Medido el 18/09/2026: `pmolina` NO existe en
    `SEGU_USUA` y **0 de 50 filas** de `SIST_NUSI` tienen esa columna con valor
    (el ERP nunca la escribe). La corrida del E2E del 19/09/2026 fallo con el 547
    `USUA_R106` justo por esto. `NUSI_ULT_ACTUALIZACION_FYH` no tiene FK y se
    sigue actualizando."""
    return f"""
DECLARE @ctacte INT, @nro_cdpr DECIMAL(18,0), @nro_asi INT;
SELECT @ctacte = ISNULL(MAX(CTEP_CTACTE_CTEP), 0) + 1 FROM CPAG_CTEP WITH (UPDLOCK, HOLDLOCK);
SELECT @nro_cdpr = ISNULL(MAX(CDPR_NUMERO_CDPR), 0) + 1 FROM CPAG_CDPR WITH (UPDLOCK, HOLDLOCK)
 WHERE CDPR_DIVISION_CDPR = {datos['division']} AND CDPR_TIPO_CDPR = {lit(datos['tipo_comp'])};
UPDATE SIST_NUSI WITH (UPDLOCK, HOLDLOCK)
   SET NUSI_ULTIMO_NUMERO = ISNULL(NUSI_ULTIMO_NUMERO, 0) + 1,
       NUSI_ULT_ACTUALIZACION_FYH = GETDATE()
 WHERE NUSI_NUMERADOR_ID = {NUMERADOR_ASIENTO_ID};
IF @@ROWCOUNT = 0
    RAISERROR('{PREFIJO_INT}NUMERADOR|Falta el numerador {NUMERADOR_ASIENTO_ID} (ultimo numero de asiento unificador) en esta base: no se puede numerar el asiento.', 16, 1);
SELECT @nro_asi = NUSI_ULTIMO_NUMERO FROM SIST_NUSI WHERE NUSI_NUMERADOR_ID = {NUMERADOR_ASIENTO_ID};
IF @ctacte IS NULL OR @nro_cdpr IS NULL OR @nro_asi IS NULL
    RAISERROR('{PREFIJO_INT}NUMERADOR|No se pudo reservar el numero de cuenta corriente, de comprobante o de asiento.', 16, 1);
"""


def _insertar_cdpr(datos):
    """El comprobante. `CDPR_ORIGEN` es varchar(2) y la app siempre escribio '1'
    ahi (el origen del circuito 'CPCV' va en `SIST_CASI.CASI_ORIGEN`, cuyo largo
    es 4): se conserva el valor actual."""
    fecha = 'CONVERT(date, ' + lit(datos['fecha']) + ', 23)'
    return f"""
INSERT INTO CPAG_CDPR (
    CDPR_DIVISION_CDPR, CDPR_TIPO_CDPR, CDPR_NUMERO_CDPR,
    CDPR_FECHA_EMI, CDPR_FECHA_PROV, CDPR_FECHA_REC,
    CDPR_PROVEEDOR, CDPR_REF_PROV, CDPR_ES_DIF_CAMBIO, CDPR_ES_PROVISION,
    CDPR_ORIGEN, CDPR_CLASIF_CVCO_1, CDPR_IMP_FISCAL, CDPR_CPBTE_FCE
) VALUES (
    {datos['division']}, {lit(datos['tipo_comp'])}, @nro_cdpr,
    {fecha}, {fecha}, {fecha},
    {datos['proveedor']}, {lit(datos['ref_prov'])}, 0, 0,
    '1', '03', 0, 0
);
"""


def _insertar_ctep(datos):
    fecha = 'CONVERT(date, ' + lit(datos['fecha']) + ', 23)'
    return f"""
INSERT INTO CPAG_CTEP (
    CTEP_CTACTE_CTEP, CTEP_DIVISION, CTEP_ORIGEN, CTEP_PROVEEDOR, CTEP_FECHA_EMI,
    CTEP_COND_PAGO, CTEP_SIGNO, CTEP_DESCRIPCION, CTEP_MONEDA, CTEP_COTIZACION,
    CTEP_IMP_BRU_ORI, CTEP_IMP_BRU_LOC, CTEP_IMP_TOT_ORI, CTEP_IMP_TOT_LOC, CTEP_ES_DIF_CAMBIO
) VALUES (
    @ctacte, {datos['division']}, '1', {datos['proveedor']}, {fecha},
    {lit(datos['cond_pago'])}, 'H', {lit(datos['descripcion'])}, {lit(datos['moneda'])}, {num(datos['cotizacion'], 5)},
    {num(datos['imp_bruto'])}, {num(datos['imp_bruto_loc'])}, {num(datos['imp_total'])}, {num(datos['imp_total_loc'])}, 0
);
"""


def _insertar_rccp(datos):
    return f"""
INSERT INTO CPAG_RCCP (RCCP_CTACTE_CTEP, RCCP_DIVISION_CDPR, RCCP_TIPO_CDPR, RCCP_NUMERO_CDPR)
VALUES (@ctacte, {datos['division']}, {lit(datos['tipo_comp'])}, @nro_cdpr);
"""


def _insertar_vctp(datos):
    """Una sola cuota con saldo = total (limitacion conocida y fuera de esta
    etapa: los planes de cuota multiple no entran)."""
    fecha_vto = 'CONVERT(date, ' + lit(datos['fecha_vto']) + ', 23)'
    return f"""
INSERT INTO CPAG_VCTP (
    VCTP_CTACTE_CTEP, VCTP_RENGLON_VCTP, VCTP_FECHA_VTO, VCTP_FECHA_VTO_FIN, VCTP_NUM_CUOTA,
    VCTP_IMP_ORI, VCTP_IMP_LOC, VCTP_SAL_ORI, VCTP_SAL_LOC
) VALUES (
    @ctacte, 1, {fecha_vto}, {fecha_vto}, 1,
    {num(datos['imp_total'])}, {num(datos['imp_total_loc'])},
    {num(datos['imp_total'])}, {num(datos['imp_total_loc'])}
);
"""


def _insertar_casi(datos, parametros):
    return f"""
INSERT INTO SIST_CASI (
    CASI_DIVISION, CASI_ASIENTO, CASI_ORIGEN, CASI_FECHA, CASI_SUBDIARIO,
    CASI_COTIZACION, CASI_COMENTARIO
) VALUES (
    {datos['division']}, @nro_asi, {lit(parametros['origen'])},
    CONVERT(date, {lit(datos['fecha'])}, 23), {lit(parametros['subdiario'])},
    {num(datos['cotizacion'], 5)}, {lit(datos['descripcion'])}
);
"""


def _insertar_rasi(datos, lineas):
    partes = []
    for linea in lineas:
        partes.append(f"""
INSERT INTO SIST_RASI (
    RASI_DIVISION, RASI_ASIENTO, RASI_RENGLON,
    RASI_CUENTA, RASI_IMP_LOC, RASI_IMP_CON, RASI_IMP_ORI,
    RASI_SIGNO, RASI_CANTIDAD, RASI_DESCRIPCION, RASI_EDITABLE, RASI_FIJA
) VALUES (
    {datos['division']}, @nro_asi, {linea['renglon']},
    {lit(linea['cuenta'])}, {num(linea['loc'])}, {num(linea['con'])}, {num(linea['ori'])},
    {lit(linea['signo'])}, 0, {lit(linea['descripcion'])}, {linea['editable']}, {linea['fija']}
);""")
    return '\n'.join(partes)


def _insertar_aasi(datos, lineas):
    """`SIST_AASI` NO tiene numeracion propia: `AASI_ASIENTO` ES el numero de
    asiento contable, el mismo que `SIST_CASI.CASI_ASIENTO` y
    `SIST_RASI.RASI_ASIENTO`.

    Medido el 18/09/2026 (`_investigacion_gt/134_aasi_y_cardinalidades.py`):
    `SIST_AASI` tiene la FK `RASI_R01` habilitada hacia `SIST_RASI` por
    (AASI_DIVISION, AASI_ASIENTO, AASI_RENGLON_ASI); los valores de
    `AASI_ASIENTO` llegan a 91.087 en GT (los de `CASI_ASIENTO` a 91.088; en RD
    130.723 vs 130.725), hay 29.728 filas hijas en GT y 56.695 en RD, y 0 filas
    de `AASI` sin su `RASI`. El `MAX(AASI_ASIENTO) + 1` por division que habia
    aca era una creencia heredada: la fila o reventaba contra la FK (547) o
    quedaba colgada de un asiento ajeno, y la baja (que borra y verifica por
    `AASI_ASIENTO`) no la veia."""
    partes = []
    for linea in lineas:
        if not linea['cco']:
            continue
        partes.append(f"""
INSERT INTO SIST_AASI (
    AASI_DIVISION, AASI_ASIENTO, AASI_RENGLON_ASI, AASI_RENGLON_APE,
    AASI_MAESTRO, AASI_INSTANCIA,
    AASI_IMP_LOC, AASI_IMP_CON, AASI_IMP_ORI, AASI_SIGNO, AASI_CANTIDAD
) VALUES (
    {datos['division']}, @nro_asi, {linea['renglon']}, 1,
    'CCO', {lit(linea['cco'])},
    {num(linea['loc'])}, {num(linea['con'])}, {num(linea['ori'])}, {lit(linea['signo'])}, 0
);""")
    return '\n'.join(partes)


def _insertar_rasp(datos):
    return f"""
INSERT INTO CPAG_RASP (RASP_DIVISION, RASP_ASIENTO, RASP_CTACTE_CTEP)
VALUES ({datos['division']}, @nro_asi, @ctacte);
"""


def _insertar_ictp(datos):
    """Impuesto del comprobante: solo para FCP con IVA (igual que hoy).

    `ICTP_IMP_GRA_ORI`/`ICTP_IMP_GRA_LOC` llevan la BASE imponible (bruto menos
    impuesto especial), no el bruto: el invariante medido de la tabla es
    `ICTP_IMP_GRA x ICTP_TASA/100 = ICTP_IMPUESTO` (314 de 316 filas de 2026). En
    las facturas sin impuesto especial base y bruto coinciden, asi que el cambio
    no altera nada de lo ya cargado."""
    if not (datos['tipo_comp'] == 'FCP' and datos['imp_iva'] > 0):
        return ''
    return f"""
INSERT INTO CPAG_ICTP (
    ICTP_CTACTE_CTEP, ICTP_IMPUESTO, ICTP_CATEGORIA_IMP,
    ICTP_IMP_GRA_ORI, ICTP_IMP_GRA_LOC, ICTP_IMPUESTO_ORI, ICTP_IMPUESTO_LOC,
    ICTP_FACTOR_IMP, ICTP_TASA, ICTP_ES_IVA, ICTP_PRORRATEA_IVA_CRFIS, ICTP_POR_COMP_IVA_CRFIS
) VALUES (
    @ctacte, 'IVP', 'P12',
    {num(datos['base_imponible'])}, {num(datos['imp_base_loc'])},
    {num(datos['imp_iva'])}, {num(datos['imp_iva_loc'])},
    1.00000, {num(datos['tasa_iva'])}, 1, 0, 100.00
);
"""


def _insertar_nctp(datos):
    """Datos del proveedor eventual (CPAG_NCTP). `NCTP_CONDICION_IVA` y
    `NCTP_UTILIZABLE` son NOT NULL: se conservan los valores que ya escribia la
    app."""
    eventual = datos['eventual']
    if not eventual:
        return ''
    return f"""
INSERT INTO CPAG_NCTP (
    NCTP_CTACTE_CTEP, NCTP_NOMBRE, NCTP_DOMICILIO, NCTP_LOCALIDAD, NCTP_CUIT,
    NCTP_CONDICION_IVA, NCTP_UTILIZABLE
) VALUES (
    @ctacte, {lit(eventual['nombre'])}, {lit(eventual['domicilio'])},
    {lit(eventual['localidad'])}, {lit(eventual['nit'])}, 'RI', 1
);
"""


def _sumas_por_cuenta(lineas):
    """Suma, por cuenta, las columnas LOC/ORI/CON separadas en debe y haber."""
    agrupado = {}
    for linea in lineas:
        acumulado = agrupado.setdefault(linea['cuenta'], {
            'debe_loc': Decimal('0.00'), 'haber_loc': Decimal('0.00'),
            'debe_ori': Decimal('0.00'), 'haber_ori': Decimal('0.00'),
            'debe_con': Decimal('0.00'), 'haber_con': Decimal('0.00')})
        prefijo = 'debe_' if linea['signo'] == 'D' else 'haber_'
        acumulado[prefijo + 'loc'] += linea['loc']
        acumulado[prefijo + 'ori'] += linea['ori']
        acumulado[prefijo + 'con'] += linea['con']
    return agrupado


def _upsert_totm(division, cuenta, anio, mes, sumas):
    return f"""
UPDATE CONT_TOTM WITH (UPDLOCK, HOLDLOCK)
   SET TOTM_DEBE_LOC = TOTM_DEBE_LOC + {num(sumas['debe_loc'])},
       TOTM_HABER_LOC = TOTM_HABER_LOC + {num(sumas['haber_loc'])},
       TOTM_DEBE_ORI = TOTM_DEBE_ORI + {num(sumas['debe_ori'])},
       TOTM_HABER_ORI = TOTM_HABER_ORI + {num(sumas['haber_ori'])},
       TOTM_DEBE_CON = TOTM_DEBE_CON + {num(sumas['debe_con'])},
       TOTM_HABER_CON = TOTM_HABER_CON + {num(sumas['haber_con'])}
 WHERE TOTM_DIVISION = {division} AND TOTM_CUENTA = {lit(cuenta)}
   AND TOTM_ANO = {anio} AND TOTM_MES = {mes};
IF @@ROWCOUNT = 0
    INSERT INTO CONT_TOTM (TOTM_DIVISION, TOTM_CUENTA, TOTM_ANO, TOTM_MES,
        TOTM_DEBE_LOC, TOTM_HABER_LOC, TOTM_DEBE_ORI, TOTM_HABER_ORI,
        TOTM_DEBE_CON, TOTM_HABER_CON, TOTM_DEBE_CAN, TOTM_HABER_CAN)
    VALUES ({division}, {lit(cuenta)}, {anio}, {mes},
        {num(sumas['debe_loc'])}, {num(sumas['haber_loc'])},
        {num(sumas['debe_ori'])}, {num(sumas['haber_ori'])},
        {num(sumas['debe_con'])}, {num(sumas['haber_con'])}, 0, 0);
"""


def _upsert_totd(division, cuenta, subdiario, fecha, sumas):
    """Medido el 18/09/2026: 0 filas de CONT_TOTD con hora en GT y RD
    (`_investigacion_gt/132_mediciones_lote_b.py`), asi que la igualdad exacta
    `TOTD_FECHA = <fecha>` es correcta; si alguna vez apareciera una con hora,
    aca va `CONVERT(date, ...)` (misma nota en `verificacion_totales`)."""
    fecha_sql = 'CONVERT(date, ' + lit(fecha) + ', 23)'
    return f"""
UPDATE CONT_TOTD WITH (UPDLOCK, HOLDLOCK)
   SET TOTD_DEBE_LOC = TOTD_DEBE_LOC + {num(sumas['debe_loc'])},
       TOTD_HABER_LOC = TOTD_HABER_LOC + {num(sumas['haber_loc'])},
       TOTD_DEBE_ORI = TOTD_DEBE_ORI + {num(sumas['debe_ori'])},
       TOTD_HABER_ORI = TOTD_HABER_ORI + {num(sumas['haber_ori'])},
       TOTD_DEBE_CON = TOTD_DEBE_CON + {num(sumas['debe_con'])},
       TOTD_HABER_CON = TOTD_HABER_CON + {num(sumas['haber_con'])}
 WHERE TOTD_DIVISION = {division} AND TOTD_CUENTA = {lit(cuenta)}
   AND TOTD_SUBDIARIO = {lit(subdiario)} AND TOTD_FECHA = {fecha_sql};
IF @@ROWCOUNT = 0
    INSERT INTO CONT_TOTD (TOTD_DIVISION, TOTD_CUENTA, TOTD_SUBDIARIO, TOTD_FECHA,
        TOTD_DEBE_LOC, TOTD_HABER_LOC, TOTD_DEBE_ORI, TOTD_HABER_ORI,
        TOTD_DEBE_CON, TOTD_HABER_CON, TOTD_DEBE_CAN, TOTD_HABER_CAN)
    VALUES ({division}, {lit(cuenta)}, {lit(subdiario)}, {fecha_sql},
        {num(sumas['debe_loc'])}, {num(sumas['haber_loc'])},
        {num(sumas['debe_ori'])}, {num(sumas['haber_ori'])},
        {num(sumas['debe_con'])}, {num(sumas['haber_con'])}, 0, 0);
"""


def _claves_totales_alta(datos, parametros, lineas):
    anio = int(datos['fecha'][0:4])
    mes = int(datos['fecha'][5:7])
    cuentas = sorted({linea['cuenta'] for linea in lineas})
    filas_m = ', '.join('(' + lit(cuenta) + ', ' + str(anio) + ', ' + str(mes) + ')'
                        for cuenta in cuentas)
    filas_d = ', '.join('(' + lit(cuenta) + ', ' + lit(parametros['subdiario']) +
                        ', CONVERT(date, ' + lit(datos['fecha']) + ', 23))' for cuenta in cuentas)
    return f"""
DECLARE @claves_m TABLE (cuenta VARCHAR(15), anio INT, mes INT);
DECLARE @claves_d TABLE (cuenta VARCHAR(15), subdiario VARCHAR(3), fecha DATE);
INSERT INTO @claves_m (cuenta, anio, mes) VALUES {filas_m};
INSERT INTO @claves_d (cuenta, subdiario, fecha) VALUES {filas_d};
"""


def _totales_alta(datos, parametros, lineas):
    """Mantiene CONT_TOTM (cuenta/ano/mes) y CONT_TOTD (cuenta/fecha/subdiario)
    sumando las columnas LOC/ORI/CON (debe y haber)."""
    anio = int(datos['fecha'][0:4])
    mes = int(datos['fecha'][5:7])
    partes = []
    for cuenta, sumas in sorted(_sumas_por_cuenta(lineas).items()):
        partes.append(_upsert_totm(datos['division'], cuenta, anio, mes, sumas))
        partes.append(_upsert_totd(datos['division'], cuenta, parametros['subdiario'],
                                   datos['fecha'], sumas))
    return '\n'.join(partes)


def verificacion_totales(division, tabla_m, tabla_d):
    """Verifica CONT_TOTM/CONT_TOTD contra la suma de los asientos para las
    claves cargadas en las variables de tabla `tabla_m` (cuenta, anio, mes) y
    `tabla_d` (cuenta, subdiario, fecha). Va DESPUES de mantener los totales y
    ANTES del COMMIT: es lo que descarta el doble conteo del caso Guatemala.

    Medido el 18/09/2026: 0 filas de CONT_TOTD con hora en GT y RD
    (`_investigacion_gt/132_mediciones_lote_b.py`), asi que comparar
    `TOTD_FECHA = k.fecha` exacto es correcto; si alguna vez apareciera una con
    hora, aca va `CONVERT(date, ...)` (misma nota en `_upsert_totd`)."""
    return f"""
DECLARE @msg_tot VARCHAR(400) = NULL;
SELECT TOP 1 @msg_tot = 'CXP_INT_TOTALES|CONT_TOTM de la cuenta ' + k.cuenta
        + ' (' + CAST(k.mes AS VARCHAR(2)) + '/' + CAST(k.anio AS VARCHAR(4))
        + '): el ERP guarda debe/haber ' + CAST(ISNULL(m.TOTM_DEBE_LOC, 0) AS VARCHAR(30))
        + '/' + CAST(ISNULL(m.TOTM_HABER_LOC, 0) AS VARCHAR(30))
        + ' y los asientos suman ' + CAST(s.debe_loc AS VARCHAR(30))
        + '/' + CAST(s.haber_loc AS VARCHAR(30)) + '.'
  FROM {tabla_m} k
  LEFT JOIN CONT_TOTM m
    ON m.TOTM_DIVISION = {division} AND m.TOTM_CUENTA = k.cuenta
   AND m.TOTM_ANO = k.anio AND m.TOTM_MES = k.mes
  OUTER APPLY (
      SELECT ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_LOC ELSE 0 END), 0) AS debe_loc,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_LOC ELSE 0 END), 0) AS haber_loc,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_ORI ELSE 0 END), 0) AS debe_ori,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_ORI ELSE 0 END), 0) AS haber_ori,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_CON ELSE 0 END), 0) AS debe_con,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_CON ELSE 0 END), 0) AS haber_con
        FROM SIST_RASI r
        JOIN SIST_CASI c ON c.CASI_DIVISION = r.RASI_DIVISION AND c.CASI_ASIENTO = r.RASI_ASIENTO
       WHERE c.CASI_DIVISION = {division}
         AND YEAR(c.CASI_FECHA) = k.anio AND MONTH(c.CASI_FECHA) = k.mes
         AND r.RASI_CUENTA = k.cuenta
  ) s
 WHERE m.TOTM_CUENTA IS NULL
    OR m.TOTM_DEBE_LOC <> s.debe_loc OR m.TOTM_HABER_LOC <> s.haber_loc
    OR m.TOTM_DEBE_ORI <> s.debe_ori OR m.TOTM_HABER_ORI <> s.haber_ori
    OR m.TOTM_DEBE_CON <> s.debe_con OR m.TOTM_HABER_CON <> s.haber_con;
IF @msg_tot IS NOT NULL
    RAISERROR(@msg_tot, 16, 1);
SET @msg_tot = NULL;
SELECT TOP 1 @msg_tot = 'CXP_INT_TOTALES|CONT_TOTD de la cuenta ' + k.cuenta
        + ' (' + CONVERT(VARCHAR(10), k.fecha, 120) + ' ' + k.subdiario
        + '): el ERP guarda debe/haber ' + CAST(ISNULL(d.TOTD_DEBE_LOC, 0) AS VARCHAR(30))
        + '/' + CAST(ISNULL(d.TOTD_HABER_LOC, 0) AS VARCHAR(30))
        + ' y los asientos suman ' + CAST(s.debe_loc AS VARCHAR(30))
        + '/' + CAST(s.haber_loc AS VARCHAR(30)) + '.'
  FROM {tabla_d} k
  LEFT JOIN CONT_TOTD d
    ON d.TOTD_DIVISION = {division} AND d.TOTD_CUENTA = k.cuenta
   AND d.TOTD_SUBDIARIO = k.subdiario AND d.TOTD_FECHA = k.fecha
  OUTER APPLY (
      SELECT ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_LOC ELSE 0 END), 0) AS debe_loc,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_LOC ELSE 0 END), 0) AS haber_loc,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_ORI ELSE 0 END), 0) AS debe_ori,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_ORI ELSE 0 END), 0) AS haber_ori,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_CON ELSE 0 END), 0) AS debe_con,
             ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_CON ELSE 0 END), 0) AS haber_con
        FROM SIST_RASI r
        JOIN SIST_CASI c ON c.CASI_DIVISION = r.RASI_DIVISION AND c.CASI_ASIENTO = r.RASI_ASIENTO
       WHERE c.CASI_DIVISION = {division}
         AND CONVERT(date, c.CASI_FECHA) = k.fecha AND c.CASI_SUBDIARIO = k.subdiario
         AND r.RASI_CUENTA = k.cuenta
  ) s
 WHERE d.TOTD_CUENTA IS NULL
    OR d.TOTD_DEBE_LOC <> s.debe_loc OR d.TOTD_HABER_LOC <> s.haber_loc
    OR d.TOTD_DEBE_ORI <> s.debe_ori OR d.TOTD_HABER_ORI <> s.haber_ori
    OR d.TOTD_DEBE_CON <> s.debe_con OR d.TOTD_HABER_CON <> s.haber_con;
IF @msg_tot IS NOT NULL
    RAISERROR(@msg_tot, 16, 1);
"""


# ============================================================
# ALTA (spec 4.2 a 4.6): un solo lote
# ============================================================

def sql_alta(ctx, datos):
    """Devuelve el lote SQL completo del alta: una sola transaccion con la
    division, el proveedor, la guarda de duplicados, la numeracion, el
    comprobante, la cuenta corriente, el vencimiento, los asientos, los totales
    mantenidos y la verificacion de totales antes del COMMIT."""
    parametros = parametros_cxp(ctx)
    d = validar_alta(ctx, datos)
    verificar_iva(d)
    renglones = renglones_con_residual(d)
    lineas = lineas_asiento(d, parametros, renglones)

    partes = ['SET NOCOUNT ON;', 'SET XACT_ABORT ON;', 'BEGIN TRANSACTION;', 'BEGIN TRY;']
    partes.append(verificar_division(d['division']))
    partes.append(_guarda_proveedor(d['proveedor']))
    partes.append(sql_duplicado(ctx, d))
    partes.append(_numeracion(ctx, d))
    partes.append(_insertar_cdpr(d))
    partes.append(_insertar_ctep(d))
    partes.append(_insertar_rccp(d))
    partes.append(_insertar_vctp(d))
    partes.append(_insertar_casi(d, parametros))
    partes.append(_insertar_rasi(d, lineas))
    partes.append(_insertar_aasi(d, lineas))
    partes.append(_insertar_rasp(d))
    partes.append(_insertar_ictp(d))
    partes.append(_insertar_nctp(d))
    partes.append(_claves_totales_alta(d, parametros, lineas))
    partes.append(_totales_alta(d, parametros, lineas))
    partes.append(verificacion_totales(d['division'], '@claves_m', '@claves_d'))
    partes.append('COMMIT TRANSACTION;')
    partes.append('SELECT @ctacte AS ctacte, @nro_cdpr AS nro_comprobante, '
                  '@nro_asi AS nro_asiento, ' + lit(d['tipo_comp']) + ' AS tipo;')
    partes.append(_cierre_try_catch())
    return '\n'.join(partes)


# ============================================================
# BAJA (spec 4.7): diagnostico previo, dos caminos, un solo lote
# ============================================================

# Barrido COMPLETO de las FKs medidas del circuito (130_esquema_circuito_cxp.md):
# todo lo que referencia CPAG_CDPR, CPAG_CTEP o CPAG_VCTP y NO es parte del ciclo
# que la baja borra (RCCP, RASP, ICTP, VCTP, NCTP). Si alguna tabla tiene filas,
# la baja NO es limpia: se devuelve la lista y no se toca nada.
BLOQUEOS_BAJA = (
    ('ACFI_BUCA', 'BUCA_DIVISION_CDPR = {division} AND BUCA_TIPO_CDPR = {tipo} AND BUCA_NUMERO_CDPR = {numero}',
     'BUCA_NUMERO_CDPR', 'una factura de compra (ACFI_BUCA)'),
    ('ACFI_CMNA', 'CMNA_DIVISION_CDPR = {division} AND CMNA_TIPO_CDPR = {tipo} AND CMNA_NUMERO_CDPR = {numero}',
     'CMNA_NUMERO_CDPR', 'una factura de compra (ACFI_CMNA)'),
    ('COMP_ANTC', 'ANTC_DIVISION_CDPR = {division} AND ANTC_TIPO_CDPR = {tipo} AND ANTC_NUMERO_CDPR = {numero}',
     'ANTC_NUMERO_CDPR', 'un anticipo de compra (COMP_ANTC)'),
    ('COMP_CVCP', 'CVCP_DIVISION_CDPR = {division} AND CVCP_TIPO_CDPR = {tipo} AND CVCP_NUMERO_CDPR = {numero}',
     'CVCP_NUMERO_CDPR', 'un comprobante de compra con stock (COMP_CVCP)'),
    ('COMP_MCRF', 'MCRF_DIVISION_CDPR = {division} AND MCRF_TIPO_CDPR = {tipo} AND MCRF_NUMERO_CDPR = {numero}',
     'MCRF_MOVSTO_MOST', 'un movimiento de stock del comprobante de compra (COMP_MCRF)'),
    ('CPAG_CPMP', 'CPMP_DIVISION_CDPR = {division} AND CPMP_TIPO_CDPR = {tipo} AND CPMP_NUMERO_CDPR = {numero}',
     'CPMP_NUMERO_CDPR', 'un pago de comprobante (CPAG_CPMP)'),
    ('IMAC_OPCP', 'OPCP_DIVISION = {division} AND OPCP_TIPO = {tipo} AND OPCP_NUMERO = {numero}',
     'OPCP_NUMERO', 'una orden de pago (IMAC_OPCP)'),
    ('PROD_CVPP', 'CVPP_DIVISION_CDPR = {division} AND CVPP_TIPO_CDPR = {tipo} AND CVPP_NUMERO_CDPR = {numero}',
     'CVPP_NUMERO_CDPR', 'un comprobante de produccion (PROD_CVPP)'),
    ('ACER_LIQC', 'LIQC_CTACTE_CTEP = {ctacte}', 'LIQC_CTACTE_CTEP', 'una liquidacion (ACER_LIQC)'),
    ('COMP_AANC', 'AANC_CTACTE_CPBTE_COMPRAS = {ctacte} OR AANC_CTACTE_ANTICIPO = {ctacte}',
     'AANC_CTACTE_CPBTE_COMPRAS', 'un anticipo (COMP_AANC)'),
    ('CPAG_AUPC', 'AUPC_CTACTE_CTEP = {ctacte}', 'AUPC_CTACTE_CTEP', 'una autorizacion de pago (CPAG_AUPC)'),
    ('CPAG_CPII', 'CPII_CTACTE_CTEP = {ctacte}', 'CPII_CTACTE_CTEP', 'un comprobante interno (CPAG_CPII)'),
    ('CPAG_RCTP', 'RCTP_CTACTE_CTEP = {ctacte}', 'RCTP_CTACTE_CTEP', 'una retencion (CPAG_RCTP)'),
    ('CPAG_ROPP', 'ROPP_CTACTE_CTEP = {ctacte}', 'ROPP_NUMERO_OPPR', 'una orden de pago (CPAG_ROPP)'),
    ('CPAG_AOPP', 'AOPP_CTACTE_CTEP = {ctacte}', 'AOPP_NUMERO_OPPR', 'una aplicacion de pago (CPAG_AOPP)'),
    ('REGA_DRGA', 'DRGA_CTACTE_CTEP = {ctacte}', 'DRGA_CTACTE_CTEP', 'un registro de retencion (REGA_DRGA)'),
    ('CPAG_CCPV', 'CCPV_CTACTE_CTEP = {ctacte}', 'CCPV_CTACTE_CTEP', 'un comprobante de pago (CPAG_CCPV)'),
    ('CPAG_CCSP', 'CCSP_CTACTE_VCTP = {ctacte}', 'CCSP_CTACTE_VCTP', 'un comprobante de pago (CPAG_CCSP)'),
    ('CPAG_DCCP', 'DCCP_CTACTE_VCTP = {ctacte}', 'DCCP_CTACTE_VCTP', 'un detalle de pago (CPAG_DCCP)'),
)

# Tablas del ciclo que la baja SI borra, en orden de dependencias. `CPAG_RCCP`
# va PRIMERO: es el que referencia a `CPAG_CTEP` (FK CTEP_R02) y hoy se borraba
# ultimo (por eso la baja de la app moria con un 500 opaco). `CPAG_NCTP` entra
# aca a proposito: la app MISMA inserta los datos del proveedor eventual sobre la
# cuenta corriente del comprobante (NCTP_CTACTE_CTEP = @ctacte), asi que
# tratarla como bloqueo haria imposible borrar una factura de proveedor eventual.
CICLO_BAJA = (
    ('CPAG_RCCP', 'RCCP_DIVISION_CDPR = {division} AND RCCP_TIPO_CDPR = {tipo} AND RCCP_NUMERO_CDPR = @nro_interno', True),
    ('CPAG_RASP', 'RASP_DIVISION = {division} AND RASP_CTACTE_CTEP = @ctacte', True),
    ('CPAG_ICTP', 'ICTP_CTACTE_CTEP = @ctacte', False),
    ('CPAG_VCTP', 'VCTP_CTACTE_CTEP = @ctacte', False),
    ('CPAG_NCTP', 'NCTP_CTACTE_CTEP = @ctacte', False),
)


def validar_baja(ctx, datos):
    """Valida la forma de la baja: numero interno obligatorio (si no, es un
    cliente viejo: fail-closed), tipo de comprobante habilitado y motivo
    obligatorio."""
    parametros_cxp(ctx)
    if not isinstance(datos, dict):
        raise ErrorValidacion(PREFIJO_VAL + 'CLIENTE_VIEJO', MENSAJE_CLIENTE_VIEJO)
    division = validar_entero(ctx.division, 'division', positivo=True)
    tipo_comp = validar_codigo(datos.get('tipo_comp', 'FCP'), 'tipo_comp', PATRON_TIPO, default='FCP')
    # Misma regla que el alta (y mismo mensaje): este circuito solo escribe los
    # tipos que carga la aplicacion (TIPOS_ALTA). Con cualquier PATRON_TIPO
    # aceptado, una baja con tipo_comp='FMR' armaba el lote y podia borrar un
    # comprobante del ERP desde aca (fail-open, contra el CXP_VAL_TIPO del alta).
    if tipo_comp not in TIPOS_ALTA:
        raise ErrorValidacion(
            PREFIJO_VAL + 'TIPO',
            "El tipo de comprobante '" + tipo_comp + "' no lo carga la aplicacion: "
            "solo se aceptan " + ' y '.join(TIPOS_ALTA) + ".")
    try:
        nro_interno = int(str(datos.get('nro_interno')).strip())
    except (TypeError, ValueError):
        raise ErrorValidacion(PREFIJO_VAL + 'CLIENTE_VIEJO', MENSAJE_CLIENTE_VIEJO)
    if nro_interno <= 0:
        raise ErrorValidacion(PREFIJO_VAL + 'CLIENTE_VIEJO', MENSAJE_CLIENTE_VIEJO)
    # CDPR_NUMERO_CDPR es decimal(10,0): sin la cota, un numero de 11 digitos
    # reventaba en el DECLARE del lote con un error de conversion (500 opaco, sin
    # `codigo` para el cliente).
    if nro_interno > 9999999999:
        raise ErrorValidacion(PREFIJO_VAL + 'ENTERO',
                              "El numero interno del comprobante (" + str(nro_interno) +
                              ") admite hasta 10 digitos (decimal(10,0)).")
    motivo = str(datos.get('motivo') or '').strip()
    if not motivo:
        raise ErrorValidacion(PREFIJO_VAL + 'MOTIVO', MENSAJE_MOTIVO)
    return {'division': division, 'tipo_comp': tipo_comp,
            'nro_interno': nro_interno, 'motivo': motivo[:200]}


def _ubicar_comprobante(d):
    """Cuenta corriente y asiento del comprobante identificado por su numero
    INTERNO (nunca por el Nro. DTE del PDF)."""
    return f"""
DECLARE @ctacte INT, @asiento INT, @nro_interno DECIMAL(10,0) = {d['nro_interno']};
SELECT @ctacte = r.RCCP_CTACTE_CTEP
  FROM CPAG_RCCP r
 WHERE r.RCCP_DIVISION_CDPR = {d['division']} AND r.RCCP_TIPO_CDPR = {lit(d['tipo_comp'])}
   AND r.RCCP_NUMERO_CDPR = @nro_interno;
IF NOT EXISTS (SELECT 1 FROM CPAG_CDPR
                WHERE CDPR_DIVISION_CDPR = {d['division']} AND CDPR_TIPO_CDPR = {lit(d['tipo_comp'])}
                  AND CDPR_NUMERO_CDPR = @nro_interno)
    RAISERROR('{PREFIJO_INT}MOV_NO_EXISTE|El comprobante {d["tipo_comp"]} {d["nro_interno"]} de la division {d["division"]} no existe (o ya se borro).', 16, 1);
IF @ctacte IS NULL
    RAISERROR('{PREFIJO_INT}MOV_NO_EXISTE|El comprobante {d["tipo_comp"]} {d["nro_interno"]} no tiene cuenta corriente asociada (CPAG_RCCP): no se puede eliminar desde aca.', 16, 1);
-- Medido el 18/09/2026 (_investigacion_gt/134_aasi_y_cardinalidades.py): 0
-- comprobantes con mas de una fila en CPAG_RCCP y 0 con mas de una cuenta
-- corriente (32.005 comprobantes en GT, 49.868 en RD; maximo 1 fila y 1 cuenta).
-- El SELECT de arriba no falla con varias filas: se queda con una cualquiera, y
-- con dos cuentas corrientes distintas borraria la que no es.
IF (SELECT COUNT(*) FROM CPAG_RCCP
     WHERE RCCP_DIVISION_CDPR = {d['division']} AND RCCP_TIPO_CDPR = {lit(d['tipo_comp'])}
       AND RCCP_NUMERO_CDPR = @nro_interno) > 1
    RAISERROR('{PREFIJO_INT}BAJA_BLOQUEADA|El comprobante {d["tipo_comp"]} {d["nro_interno"]} tiene mas de una cuenta corriente en CPAG_RCCP (un comprobante, una cuenta corriente): la transaccion se revierte sin borrar nada.', 16, 1);
-- Medido el 18/09/2026: CPAG_RASP tiene UNA fila por cuenta corriente en GT
-- (48.828) y RD (69.282), con maximo 1 fila y 1 asiento por cuenta y 0 filas sin
-- su asiento en SIST_CASI (_investigacion_gt/133_rasp_unicidad.py). El chequeo es
-- la red para que un cambio del ERP no deje un asiento huerfano: el borrado de
-- CPAG_RASP va por cuenta corriente, asi que dos asientos distintos dejarian uno
-- de ellos sin revertir sus totales y sin verificar.
IF NOT EXISTS (SELECT 1 FROM CPAG_RASP
                WHERE RASP_DIVISION = {d['division']} AND RASP_CTACTE_CTEP = @ctacte)
    RAISERROR('{PREFIJO_INT}BAJA_BLOQUEADA|El comprobante {d["tipo_comp"]} {d["nro_interno"]} no tiene asiento en CPAG_RASP (una cuenta corriente, un solo asiento): la transaccion se revierte sin borrar nada.', 16, 1);
IF EXISTS (SELECT 1 FROM CPAG_RASP
            WHERE RASP_DIVISION = {d['division']} AND RASP_CTACTE_CTEP = @ctacte
            GROUP BY RASP_CTACTE_CTEP
           HAVING COUNT(DISTINCT RASP_ASIENTO) > 1)
    RAISERROR('{PREFIJO_INT}BAJA_BLOQUEADA|El comprobante {d["tipo_comp"]} {d["nro_interno"]} tiene mas de un asiento distinto en CPAG_RASP (una cuenta corriente, un solo asiento): la transaccion se revierte sin borrar nada.', 16, 1);
-- La direccion inversa: medido el 18/09/2026, 0 asientos compartidos por dos
-- cuentas corrientes en GT y RD. Si pasara, la reversion de CONT_TOTM/CONT_TOTD
-- (que va por cuenta y mes, no por comprobante) restaria importes ajenos.
IF EXISTS (SELECT 1 FROM CPAG_RASP
            WHERE RASP_DIVISION = {d['division']}
            GROUP BY RASP_DIVISION, RASP_ASIENTO
           HAVING COUNT(DISTINCT RASP_CTACTE_CTEP) > 1)
    RAISERROR('{PREFIJO_INT}BAJA_BLOQUEADA|El comprobante {d["tipo_comp"]} {d["nro_interno"]} comparte el asiento con otra cuenta corriente en CPAG_RASP (un asiento, una cuenta corriente): la transaccion se revierte sin borrar nada.', 16, 1);
SELECT @asiento = RASP_ASIENTO FROM CPAG_RASP
 WHERE RASP_DIVISION = {d['division']} AND RASP_CTACTE_CTEP = @ctacte;
"""


def _capturar_asiento(d):
    """Copia las lineas del asiento a dos variables de tabla ANTES de borrar
    nada: con eso se revierten los totales exactamente por lo que se borro.

    La captura va con `INNER JOIN SIST_CASI`: si un renglon del asiento quedara
    afuera (un `SIST_RASI` sin su `SIST_CASI`), `_revertir_totales` compararia
    CONT_* contra los propios renglones capturados y pasaria verde, dejando el
    importe de ese renglon en `CONT_TOTM`/`CONT_TOTD`: un subconteo SILENCIOSO,
    no un fail-closed (el ledger lo tenia anotado al reves). Por eso despues de
    capturar se compara cuantas filas entraron al JOIN contra las que tiene el
    asiento en `SIST_RASI` y se aborta con `CXP_INT_TOTALES` si no coinciden: la
    transaccion se revierte sin haber tocado los totales del mayor."""
    return f"""
DECLARE @rev_m TABLE (cuenta VARCHAR(15), anio INT, mes INT,
    debe_loc DECIMAL(14,2), haber_loc DECIMAL(14,2), debe_ori DECIMAL(14,2),
    haber_ori DECIMAL(14,2), debe_con DECIMAL(14,2), haber_con DECIMAL(14,2));
DECLARE @rev_d TABLE (cuenta VARCHAR(15), subdiario VARCHAR(3), fecha DATE,
    debe_loc DECIMAL(14,2), haber_loc DECIMAL(14,2), debe_ori DECIMAL(14,2),
    haber_ori DECIMAL(14,2), debe_con DECIMAL(14,2), haber_con DECIMAL(14,2));
IF @asiento IS NOT NULL
BEGIN
    DECLARE @filas_rasi INT, @filas_join INT;
    SELECT @filas_rasi = COUNT(*) FROM SIST_RASI
     WHERE RASI_DIVISION = {d['division']} AND RASI_ASIENTO = @asiento;
    INSERT INTO @rev_m (cuenta, anio, mes, debe_loc, haber_loc, debe_ori, haber_ori, debe_con, haber_con)
    SELECT r.RASI_CUENTA, YEAR(c.CASI_FECHA), MONTH(c.CASI_FECHA),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_LOC ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_LOC ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_ORI ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_ORI ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_CON ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_CON ELSE 0 END), 0)
      FROM SIST_RASI r
      JOIN SIST_CASI c ON c.CASI_DIVISION = r.RASI_DIVISION AND c.CASI_ASIENTO = r.RASI_ASIENTO
     WHERE r.RASI_DIVISION = {d['division']} AND r.RASI_ASIENTO = @asiento
     GROUP BY r.RASI_CUENTA, YEAR(c.CASI_FECHA), MONTH(c.CASI_FECHA);
    -- Filas que el JOIN capturo de verdad (los COUNT crudos, sin agrupar): si un
    -- renglon se quedo afuera, la suma no llega a @filas_rasi y se aborta.
    SELECT @filas_join = ISNULL(SUM(filas), 0) FROM (
        SELECT COUNT(*) AS filas
          FROM SIST_RASI r
          JOIN SIST_CASI c ON c.CASI_DIVISION = r.RASI_DIVISION AND c.CASI_ASIENTO = r.RASI_ASIENTO
         WHERE r.RASI_DIVISION = {d['division']} AND r.RASI_ASIENTO = @asiento
         GROUP BY r.RASI_CUENTA, YEAR(c.CASI_FECHA), MONTH(c.CASI_FECHA)
    ) t;
    IF @filas_join <> @filas_rasi
    BEGIN
        -- T-SQL NO acepta concatenacion en el PRIMER argumento de RAISERROR
        -- (solo un literal, una variable o una cadena con parametros %s/%d): el
        -- mensaje se arma en una variable, como `@msg_tot` y `@msg_bloqueo`. Con
        -- la concatenacion inline este lote no parseaba (error 102, `Incorrect
        -- syntax near '+'`) y la baja moria SIEMPRE, con el alta ya escrita.
        DECLARE @msg_totales VARCHAR(400);
        SET @msg_totales = '{PREFIJO_INT}TOTALES|Faltan renglones del asiento del comprobante ' + CAST({d['nro_interno']} AS VARCHAR(20))
             + ' al capturarlos para revertir los totales: se capturaron ' + CAST(@filas_join AS VARCHAR(10))
             + ' de ' + CAST(@filas_rasi AS VARCHAR(10)) + '. La transaccion se revierte sin borrar nada.';
        RAISERROR(@msg_totales, 16, 1);
    END
    INSERT INTO @rev_d (cuenta, subdiario, fecha, debe_loc, haber_loc, debe_ori, haber_ori, debe_con, haber_con)
    SELECT r.RASI_CUENTA, c.CASI_SUBDIARIO, CONVERT(date, c.CASI_FECHA),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_LOC ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_LOC ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_ORI ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_ORI ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'D' THEN r.RASI_IMP_CON ELSE 0 END), 0),
           ISNULL(SUM(CASE WHEN r.RASI_SIGNO = 'H' THEN r.RASI_IMP_CON ELSE 0 END), 0)
      FROM SIST_RASI r
      JOIN SIST_CASI c ON c.CASI_DIVISION = r.RASI_DIVISION AND c.CASI_ASIENTO = r.RASI_ASIENTO
     WHERE r.RASI_DIVISION = {d['division']} AND r.RASI_ASIENTO = @asiento
     GROUP BY r.RASI_CUENTA, c.CASI_SUBDIARIO, CONVERT(date, c.CASI_FECHA);
END
"""


def _bloqueos_baja(d):
    """Diagnostico previo: cuenta que tiene el comprobante en cada tabla del
    circuito que NO forma parte del ciclo. Si hay algo, arma la lista
    (`|bloqueo=tabla;filas=n;primer_id=x`) y levanta CXP_INT_BAJA_BLOQUEADA
    ANTES de cualquier DELETE.

    El mensaje lleva ademas CUANTAS de las tablas dieron > 0: la lista se corta
    a los 1300 caracteres (y RAISERROR no pasa de ~2047 bytes), asi que el
    contador es lo que le dice al operador si lo que ve esta completo."""
    valores = {'division': d['division'], 'tipo': lit(d['tipo_comp']),
               'numero': d['nro_interno'], 'ctacte': '@ctacte'}
    total = len(BLOQUEOS_BAJA)
    partes = ["DECLARE @bloqueos VARCHAR(1500) = '';", "DECLARE @detalle VARCHAR(600) = '';",
              "DECLARE @nbloq INT = 0;"]
    for indice, (tabla, condicion, columna_id, etiqueta) in enumerate(BLOQUEOS_BAJA):
        partes.append(f"""
DECLARE @nb_{indice} INT, @ib_{indice} VARCHAR(20);
SELECT @nb_{indice} = COUNT(*), @ib_{indice} = CAST(MIN({columna_id}) AS VARCHAR(20))
  FROM {tabla} WHERE {condicion.format(**valores)};
IF @nb_{indice} > 0
BEGIN
    SET @nbloq = @nbloq + 1;
    IF LEN(@bloqueos) < 1300
        SET @bloqueos = @bloqueos + '|bloqueo={tabla};filas=' + CAST(@nb_{indice} AS VARCHAR(20))
                      + ';primer_id=' + ISNULL(@ib_{indice}, 'NULL');
    SET @detalle = @detalle + CASE WHEN @detalle = '' THEN '' ELSE ', ' END + {lit(etiqueta)}
                 + ' (' + CAST(@nb_{indice} AS VARCHAR(20)) + ')';
END
""")
    partes.append(f"""
IF @bloqueos <> ''
BEGIN
    DECLARE @msg_bloqueo VARCHAR(2047);
    SET @msg_bloqueo = '{PREFIJO_INT}BAJA_BLOQUEADA|' + SUBSTRING(@bloqueos, 2, 1200)
                     + '|Bloquean ' + CAST(@nbloq AS VARCHAR(20)) + ' de {total} tablas del circuito.'
                     + ' El comprobante {d["tipo_comp"]} ' + CAST(@nro_interno AS VARCHAR(20))
                     + ' de la division {d["division"]} no se puede eliminar: lo referencia '
                     + @detalle + '. No se borro nada.';
    RAISERROR(@msg_bloqueo, 16, 1);
END
""")
    return '\n'.join(partes)


def _borrar_ciclo(d):
    """Borra el ciclo en ORDEN DE DEPENDENCIAS (CICLO_BAJA), despues los
    asientos (AASI -> RASI -> CASI) y por ultimo la cuenta corriente y el
    comprobante. Cada DELETE deja su @@ROWCOUNT en una variable."""
    partes = ["DECLARE @f_rccp INT = 0, @f_rasp INT = 0, @f_ictp INT = 0, @f_vctp INT = 0, "
              "@f_nctp INT = 0, @f_aasi INT = 0, @f_rasi INT = 0, @f_casi INT = 0, "
              "@f_ctep INT = 0, @f_cdpr INT = 0;"]
    for tabla, condicion, obligatoria in CICLO_BAJA:
        variable = '@f_' + tabla.split('_')[1].lower()
        partes.append(f"""
DELETE FROM {tabla} WHERE {condicion.format(division=d['division'], tipo=lit(d['tipo_comp']))};
SET {variable} = @@ROWCOUNT;""")
        if obligatoria:
            partes.append(f"""
IF {variable} = 0
    RAISERROR('{PREFIJO_INT}BAJA_BLOQUEADA|El comprobante {d["tipo_comp"]} {d["nro_interno"]} no tenia filas en {tabla}: la transaccion se revierte sin borrar nada.', 16, 1);""")
    partes.append(f"""
IF @asiento IS NOT NULL
BEGIN
    DELETE FROM SIST_AASI WHERE AASI_DIVISION = {d['division']} AND AASI_ASIENTO = @asiento;
    SET @f_aasi = @@ROWCOUNT;
    DELETE FROM SIST_RASI WHERE RASI_DIVISION = {d['division']} AND RASI_ASIENTO = @asiento;
    SET @f_rasi = @@ROWCOUNT;
    IF @f_rasi = 0
        RAISERROR('{PREFIJO_INT}BAJA_BLOQUEADA|El comprobante {d["tipo_comp"]} {d["nro_interno"]} tenia asiento pero sin renglones (SIST_RASI): la transaccion se revierte sin borrar nada.', 16, 1);
    DELETE FROM SIST_CASI WHERE CASI_DIVISION = {d['division']} AND CASI_ASIENTO = @asiento;
    SET @f_casi = @@ROWCOUNT;
END
DELETE FROM CPAG_CTEP WHERE CTEP_DIVISION = {d['division']} AND CTEP_CTACTE_CTEP = @ctacte;
SET @f_ctep = @@ROWCOUNT;
IF @f_ctep = 0
    RAISERROR('{PREFIJO_INT}BAJA_BLOQUEADA|No se pudo borrar la cuenta corriente del comprobante (CPAG_CTEP): la transaccion se revierte sin borrar nada.', 16, 1);
DELETE FROM CPAG_CDPR WHERE CDPR_DIVISION_CDPR = {d['division']} AND CDPR_TIPO_CDPR = {lit(d['tipo_comp'])} AND CDPR_NUMERO_CDPR = @nro_interno;
SET @f_cdpr = @@ROWCOUNT;
IF @f_cdpr = 0
    RAISERROR('{PREFIJO_INT}BAJA_BLOQUEADA|No se pudo borrar el comprobante (CPAG_CDPR): la transaccion se revierte sin borrar nada.', 16, 1);""")
    return '\n'.join(partes)


def _revertir_totales(d):
    """Revierte CONT_TOTM y CONT_TOTD exactamente por lo que tenia el asiento
    borrado (las lineas se capturaron en @rev_m / @rev_d). Si falta la fila de
    totales de alguna cuenta, aborta: no se puede revertir a ciegas."""
    return f"""
IF (SELECT COUNT(*) FROM @rev_m) > 0
BEGIN
    IF (SELECT COUNT(*) FROM @rev_m) <> (
        SELECT COUNT(*) FROM @rev_m v
        JOIN CONT_TOTM m ON m.TOTM_DIVISION = {d['division']} AND m.TOTM_CUENTA = v.cuenta
                        AND m.TOTM_ANO = v.anio AND m.TOTM_MES = v.mes)
        RAISERROR('{PREFIJO_INT}TOTALES|Falta la fila de CONT_TOTM de alguna cuenta del asiento del comprobante {d["nro_interno"]}.', 16, 1);
    UPDATE m
       SET m.TOTM_DEBE_LOC = m.TOTM_DEBE_LOC - v.debe_loc,
           m.TOTM_HABER_LOC = m.TOTM_HABER_LOC - v.haber_loc,
           m.TOTM_DEBE_ORI = m.TOTM_DEBE_ORI - v.debe_ori,
           m.TOTM_HABER_ORI = m.TOTM_HABER_ORI - v.haber_ori,
           m.TOTM_DEBE_CON = m.TOTM_DEBE_CON - v.debe_con,
           m.TOTM_HABER_CON = m.TOTM_HABER_CON - v.haber_con
      FROM CONT_TOTM m WITH (UPDLOCK, HOLDLOCK)
      JOIN @rev_m v ON v.cuenta = m.TOTM_CUENTA AND v.anio = m.TOTM_ANO AND v.mes = m.TOTM_MES
     WHERE m.TOTM_DIVISION = {d['division']};
END
IF (SELECT COUNT(*) FROM @rev_d) > 0
BEGIN
    IF (SELECT COUNT(*) FROM @rev_d) <> (
        SELECT COUNT(*) FROM @rev_d v
        JOIN CONT_TOTD t ON t.TOTD_DIVISION = {d['division']} AND t.TOTD_CUENTA = v.cuenta
                        AND t.TOTD_SUBDIARIO = v.subdiario AND t.TOTD_FECHA = v.fecha)
        RAISERROR('{PREFIJO_INT}TOTALES|Falta la fila de CONT_TOTD de alguna cuenta del asiento del comprobante {d["nro_interno"]}.', 16, 1);
    UPDATE t
       SET t.TOTD_DEBE_LOC = t.TOTD_DEBE_LOC - v.debe_loc,
           t.TOTD_HABER_LOC = t.TOTD_HABER_LOC - v.haber_loc,
           t.TOTD_DEBE_ORI = t.TOTD_DEBE_ORI - v.debe_ori,
           t.TOTD_HABER_ORI = t.TOTD_HABER_ORI - v.haber_ori,
           t.TOTD_DEBE_CON = t.TOTD_DEBE_CON - v.debe_con,
           t.TOTD_HABER_CON = t.TOTD_HABER_CON - v.haber_con
      FROM CONT_TOTD t WITH (UPDLOCK, HOLDLOCK)
      JOIN @rev_d v ON v.cuenta = t.TOTD_CUENTA AND v.subdiario = t.TOTD_SUBDIARIO
                   AND v.fecha = t.TOTD_FECHA
     WHERE t.TOTD_DIVISION = {d['division']};
END
"""


def _verificacion_restos(d):
    """Antes del COMMIT: 0 filas en cada tabla del circuito para ESE
    comprobante. Si quedo algo, se revierte todo (CXP_INT_BAJA_BLOQUEADA)."""
    comprobaciones = (
        ('CPAG_RCCP', 'RCCP_DIVISION_CDPR = {division} AND RCCP_TIPO_CDPR = {tipo} AND RCCP_NUMERO_CDPR = @nro_interno'),
        # Las dos vias: por numero interno y por cuenta corriente. El DELETE de
        # CPAG_RCCP va por numero, pero un RCCP que apunte a la misma cuenta con
        # otro numero tambien tiene que quedar en 0.
        ('CPAG_RCCP', 'RCCP_CTACTE_CTEP = @ctacte'),
        ('CPAG_CDPR', 'CDPR_DIVISION_CDPR = {division} AND CDPR_TIPO_CDPR = {tipo} AND CDPR_NUMERO_CDPR = @nro_interno'),
        ('CPAG_CTEP', 'CTEP_CTACTE_CTEP = @ctacte'),
        ('CPAG_RASP', 'RASP_CTACTE_CTEP = @ctacte'),
        ('CPAG_VCTP', 'VCTP_CTACTE_CTEP = @ctacte'),
        ('CPAG_ICTP', 'ICTP_CTACTE_CTEP = @ctacte'),
        ('CPAG_NCTP', 'NCTP_CTACTE_CTEP = @ctacte'),
        ('SIST_CASI', 'CASI_DIVISION = {division} AND CASI_ASIENTO = @asiento'),
        ('SIST_RASI', 'RASI_DIVISION = {division} AND RASI_ASIENTO = @asiento'),
        ('SIST_AASI', 'AASI_DIVISION = {division} AND AASI_ASIENTO = @asiento'),
    )
    valores = {'division': d['division'], 'tipo': lit(d['tipo_comp'])}
    partes = []
    for tabla, condicion in comprobaciones:
        partes.append(f"""
IF EXISTS (SELECT 1 FROM {tabla} WHERE {condicion.format(**valores)})
    RAISERROR('{PREFIJO_INT}BAJA_BLOQUEADA|Quedaron filas en {tabla} del comprobante {d["tipo_comp"]} {d["nro_interno"]}: se revierte la transaccion y no se borra nada.', 16, 1);""")
    return '\n'.join(partes)


def _resultado_baja():
    return """
SELECT @ctacte AS ctacte_eliminado, @asiento AS asiento_eliminado,
       @f_rccp AS filas_rccp, @f_rasp AS filas_rasp, @f_ictp AS filas_ictp,
       @f_vctp AS filas_vctp, @f_nctp AS filas_nctp, @f_aasi AS filas_aasi,
       @f_rasi AS filas_rasi, @f_casi AS filas_casi, @f_ctep AS filas_ctep,
       @f_cdpr AS filas_cdpr, 'ELIMINACION COMPLETA' AS resultado;
"""


def sql_baja(ctx, datos):
    """Devuelve el lote SQL completo de la baja: la division, el diagnostico
    previo dentro de la transaccion, dos caminos (limpia -> borra el ciclo
    completo; bloqueada -> RAISERROR con la lista y sin tocar una sola fila),
    reversion de totales y verificacion de 0 restos antes del COMMIT."""
    parametros_cxp(ctx)
    d = validar_baja(ctx, datos)
    partes = ['SET NOCOUNT ON;', 'SET XACT_ABORT ON;', 'BEGIN TRANSACTION;', 'BEGIN TRY;']
    partes.append(verificar_division(d['division']))
    partes.append(_ubicar_comprobante(d))
    partes.append(_capturar_asiento(d))
    partes.append(_bloqueos_baja(d))
    partes.append(_borrar_ciclo(d))
    partes.append(_revertir_totales(d))
    partes.append(verificacion_totales(d['division'], '@rev_m', '@rev_d'))
    partes.append(_verificacion_restos(d))
    partes.append('COMMIT TRANSACTION;')
    partes.append(_resultado_baja())
    partes.append(_cierre_try_catch())
    return '\n'.join(partes)


# ============================================================
# ERRORES DE LA BASE -> CODIGO + MENSAJE
# ============================================================

# Tablas del circuito que pueden aparecer en un 547 (FK inesperada) al borrar.
MENSAJES_FK_CXP = {
    'ACFI_BUCA': 'una factura de compra (ACFI_BUCA)',
    'ACFI_CMNA': 'una factura de compra (ACFI_CMNA)',
    'COMP_ANTC': 'un anticipo de compra (COMP_ANTC)',
    'COMP_CVCP': 'un comprobante de compra con stock (COMP_CVCP)',
    'COMP_MCRF': 'un movimiento de stock del comprobante de compra (COMP_MCRF)',
    'COMP_AANC': 'un anticipo (COMP_AANC)',
    'CPAG_CPMP': 'un pago de comprobante (CPAG_CPMP)',
    'CPAG_AUPC': 'una autorizacion de pago (CPAG_AUPC)',
    'CPAG_CPII': 'un comprobante interno (CPAG_CPII)',
    'CPAG_NCTP': 'las notas del proveedor eventual (CPAG_NCTP)',
    'CPAG_RCTP': 'una retencion (CPAG_RCTP)',
    'CPAG_ROPP': 'una orden de pago (CPAG_ROPP)',
    'CPAG_AOPP': 'una aplicacion de pago (CPAG_AOPP)',
    'CPAG_CCPV': 'un comprobante de pago (CPAG_CCPV)',
    'CPAG_CCSP': 'un comprobante de pago (CPAG_CCSP)',
    'CPAG_DCCP': 'un detalle de pago (CPAG_DCCP)',
    'IMAC_OPCP': 'una orden de pago (IMAC_OPCP)',
    'PROD_CVPP': 'un comprobante de produccion (PROD_CVPP)',
    'ACER_LIQC': 'una liquidacion (ACER_LIQC)',
    'REGA_DRGA': 'un registro de retencion (REGA_DRGA)',
}


def _parse_bloqueo(segmento):
    """'bloqueo=CPAG_AOPP;filas=3;primer_id=1001' -> dict (o None)."""
    if not segmento.startswith('bloqueo='):
        return None
    campos = {}
    for parte in segmento.split(';'):
        clave, _, valor = parte.partition('=')
        campos[clave.strip()] = valor.strip()
    # (Corregido el 18/09/2026: el brief y el plan leian `campos['tabla']`, pero
    # la clave del segmento que arma `_bloqueos_baja` es `bloqueo=` —asi lo dice
    # este docstring y asi lo espera el contrato de la spec §4.13, que pide
    # `bloqueos: [{tabla, filas, primer_id}]` en el 409—. Con `tabla` la lista
    # salia SIEMPRE vacia: el 409 quedaba sin `bloqueos`.)
    tabla = campos.get('bloqueo')
    if not tabla:
        return None

    def entero(valor):
        try:
            return int(valor)
        except (TypeError, ValueError):
            return None

    return {'tabla': tabla, 'filas': entero(campos.get('filas')),
            'primer_id': entero(campos.get('primer_id'))}


def mensaje_de_error_cxp(texto):
    """(codigo, mensaje, datos) de un error de la base.

    Los lotes marcan sus errores de negocio con `RAISERROR('CXP_...|mensaje')`;
    la baja ademas adjunta la lista de bloqueos en segmentos
    `bloqueo=tabla;filas=n;primer_id=x`. Un 547 (FK) se traduce a `CXP_INT_FK`
    con el circuito que referencia el comprobante. Cualquier otro error de la
    base NO expone su texto: sale un codigo generico."""
    texto = str(texto or '')
    inicio = texto.find('CXP_')
    if inicio >= 0:
        resto = texto[inicio:]
        cabecera, _, cola = resto.partition('|')
        codigo = cabecera.strip().split()[0].split('.')[0] if cabecera.strip() else 'CXP_INT'
        segmentos = [segmento.strip() for segmento in cola.split('|')] if cola else []
        bloqueos = [bloqueo for bloqueo in (_parse_bloqueo(s) for s in segmentos) if bloqueo]
        mensaje = ''
        for segmento in reversed(segmentos):
            if segmento and not segmento.startswith('bloqueo='):
                mensaje = segmento
                break
        datos = {'bloqueos': bloqueos} if bloqueos else {}
        return codigo, mensaje or codigo, datos
    if 'REFERENCE' in texto.upper():
        for tabla, descripcion in MENSAJES_FK_CXP.items():
            if tabla in texto:
                return ('CXP_INT_FK',
                        'No se puede eliminar: el comprobante esta referenciado por ' + descripcion + '.',
                        {})
        return ('CXP_INT_FK',
                'No se puede eliminar: el comprobante esta referenciado por otro circuito del ERP.', {})
    return 'CXP_INT', 'No se pudo completar la operacion de CxP.', {}


# ============================================================
# /api/validar_integridad (spec 4.12): SOLO LECTURA, acotado a la division
# ============================================================

# Contrato exacto que ya lee el frontend (`frontend/modules/cxp/eliminar.js`).
CLAVES_INTEGRIDAD = ('facturas_sin_rccp', 'rasp_sin_casi', 'casi_sin_rasi',
                     'asientos_sin_comentario', 'notas_debito_sin_rccp',
                     'estado_general', 'total_problemas')

# Las CUATRO cuentas que son un defecto ESTRUCTURAL del circuito (y por lo tanto
# las que suman `total_problemas` y deciden `estado_general`).
# `asientos_sin_comentario` queda afuera: medido el 18/09/2026 en GT, division 7
# (`_investigacion_gt/136_integridad_falsos_positivos.py`), da 6.953 (5.867
# acotado al subdiario de CxP 'CPA') y es como esta cargada la base; si sumara, la
# pantalla arrancaria con 7.107 "problemas" que no lo son. Se sigue DEVOLVIENDO
# (la pantalla lista las cinco cuentas), solo no suma.
CLAVES_ESTRUCTURALES = ('facturas_sin_rccp', 'rasp_sin_casi', 'casi_sin_rasi',
                        'notas_debito_sin_rccp')

# Tipos de comprobante de NOTA DE DEBITO, MEDIDOS en GT (24 tipos en total; los
# de credito/ajuste son A+, A-, CCC y CCE).
TIPOS_NOTA_DEBITO = ('D+', 'D-', 'DCP', 'DCC')


def sql_integridad(division):
    """Consulta de solo lectura con las cinco cuentas de problemas, acotada a la
    division pedida. `estado_general` y `total_problemas` los calcula el endpoint
    a partir de las CUATRO cuentas estructurales (ver `CLAVES_ESTRUCTURALES`).

    `facturas_sin_rccp` y `notas_debito_sin_rccp` cuentan solo comprobantes
    VIGENTES (`CDPR_FECHA_BAJA IS NULL`). Medido en GT, division 7
    (`_investigacion_gt/136_integridad_falsos_positivos.py`): `facturas_sin_rccp`
    da 149 sin el filtro y 37 con el, y `notas_debito_sin_rccp` 5 y 0. Los que
    quedan afuera son comprobantes que el ERP creo legitimamente sin cuenta
    corriente: contarlos hacia que la pantalla naciera gritando problemas que no
    lo son.

    `asientos_sin_comentario` NO se filtra y NO suma al total: medido el
    18/09/2026 en esa misma division da 6.953 (5.867 aun acotado al subdiario de
    CxP, 'CPA') y es COMO ESTA CARGADA LA BASE, no un defecto del circuito. Se
    sigue devolviendo porque la pantalla lista las cinco cuentas.

    `notas_debito_sin_rccp` cuenta los comprobantes de la division cuyo
    `CDPR_TIPO_CDPR` es un tipo de NOTA DE DEBITO y cuya cuenta corriente no
    tiene su fila de `CPAG_RCCP`. Los tipos son los MEDIDOS en GT (24 tipos de
    comprobante): notas de debito `D+`, `D-`, `DCP`, `DCC`; notas de credito o
    ajuste `A+`, `A-`, `CCC`, `CCE`. La etiqueta de la pantalla ("Notas de debito
    sin RCCP") se mantiene.

    `division` tiene que venir YA validada como entero (y no negativa) por el
    llamador: la funcion es publica y el valor se interpola en el SQL, igual que
    en `verificar_division`. Hoy el unico llamador es `/api/validar_integridad`,
    que la pasa por `_validar_entero_cxp(..., obligatoria=True)`.

    NO se usa `CPAG_NCTP` para esta clave: esa tabla son los DATOS DEL PROVEEDOR
    EVENTUAL (nombre, domicilio, CUIT, condicion IVA) que la app misma inserta
    sobre la cuenta corriente del comprobante, no notas. Contarla ahi daria un
    numero que no significa lo que dice la etiqueta. (El contrato de la spec 4.12
    son SIETE claves exactas, asi que tampoco se agrega un campo extra con ese
    conteo.)"""
    tipos = ', '.join(lit(tipo) for tipo in TIPOS_NOTA_DEBITO)
    return f"""
-- 136_integridad_falsos_positivos.py (medicion del 18/09/2026 en GT, division 7):
-- facturas_sin_rccp 149 -> 37 y notas_debito_sin_rccp 5 -> 0 al exigir
-- CDPR_FECHA_BAJA IS NULL; asientos_sin_comentario 6.953 (no es un defecto).
SELECT
  (SELECT COUNT(*) FROM CPAG_CDPR c
    WHERE c.CDPR_DIVISION_CDPR = {division}
      AND c.CDPR_FECHA_BAJA IS NULL
      AND NOT EXISTS (SELECT 1 FROM CPAG_RCCP r
                       WHERE r.RCCP_DIVISION_CDPR = c.CDPR_DIVISION_CDPR
                         AND r.RCCP_TIPO_CDPR = c.CDPR_TIPO_CDPR
                         AND r.RCCP_NUMERO_CDPR = c.CDPR_NUMERO_CDPR)) AS facturas_sin_rccp,
  (SELECT COUNT(*) FROM CPAG_RASP p
    WHERE p.RASP_DIVISION = {division}
      AND NOT EXISTS (SELECT 1 FROM SIST_CASI c
                       WHERE c.CASI_DIVISION = p.RASP_DIVISION
                         AND c.CASI_ASIENTO = p.RASP_ASIENTO)) AS rasp_sin_casi,
  (SELECT COUNT(*) FROM SIST_CASI c
    WHERE c.CASI_DIVISION = {division}
      AND NOT EXISTS (SELECT 1 FROM SIST_RASI r
                       WHERE r.RASI_DIVISION = c.CASI_DIVISION
                         AND r.RASI_ASIENTO = c.CASI_ASIENTO)) AS casi_sin_rasi,
  (SELECT COUNT(*) FROM SIST_CASI c
    WHERE c.CASI_DIVISION = {division}
      AND (c.CASI_COMENTARIO IS NULL
           OR LTRIM(RTRIM(c.CASI_COMENTARIO)) = '')) AS asientos_sin_comentario,
  (SELECT COUNT(*) FROM CPAG_CDPR c
    WHERE c.CDPR_DIVISION_CDPR = {division}
      AND c.CDPR_FECHA_BAJA IS NULL
      AND c.CDPR_TIPO_CDPR IN ({tipos})
      AND NOT EXISTS (SELECT 1 FROM CPAG_RCCP r
                       WHERE r.RCCP_DIVISION_CDPR = c.CDPR_DIVISION_CDPR
                         AND r.RCCP_TIPO_CDPR = c.CDPR_TIPO_CDPR
                         AND r.RCCP_NUMERO_CDPR = c.CDPR_NUMERO_CDPR)) AS notas_debito_sin_rccp;
"""
