# modules/stock/servicio_movimientos.py
# ============================================================
# Capa unica de escritura de stock. Modulo PURO (solo stdlib): no importa
# Flask, config ni database, para poder testearlo sin app ni base.
# Todo el SQL de una operacion va en UN lote con XACT_ABORT + transaccion,
# guardas con RAISERROR('STK_...|mensaje') y verificacion de filas afectadas.
# ============================================================

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

PREFIJO_VAL = 'STK_VAL_'
PREFIJO_INT = 'STK_INT_'

# Tope de magnitud de una cantidad: por encima de esto no tiene sentido en el
# ERP y ademas el quantize de 4 decimales desbordaria la precision del contexto.
CANTIDAD_MAXIMA = Decimal('1000000000000')

# Longitudes maximas de los textos que llegan del request, medidas contra la
# base: STOC_PART.PART_PARTIDA_EMP es varchar(20) y STOC_MOST.MOST_DESCRIPCION
# es nvarchar(MAX).
PARTIDA_NOMBRE_MAX = 20
COMENTARIO_MAX = 1000


class ErrorValidacion(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


class Contexto:
    """Contexto de base ya resuelto por la capa que llama."""

    __slots__ = ('division', 'sucursal_imp', 'sucursal_emp', 'base', 'usuario')

    def __init__(self, division, sucursal_imp, sucursal_emp, base, usuario=''):
        self.division = int(division)
        self.sucursal_imp = int(sucursal_imp)
        self.sucursal_emp = int(sucursal_emp)
        self.base = str(base or '')
        self.usuario = str(usuario or '')


def lit(valor):
    """Misma semantica que modules/shared/database.py:_sql_literal (no se
    importa de ahi porque ese modulo arrastra Flask)."""
    if valor is None:
        return 'NULL'
    if isinstance(valor, bool):
        return '1' if valor else '0'
    if isinstance(valor, (int, Decimal)):
        return str(valor)
    if isinstance(valor, float):
        return repr(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def validar_cantidad(valor, campo='cantidad'):
    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        raise ErrorValidacion(PREFIJO_VAL + 'CANTIDAD',
                              "El campo '" + campo + "' no es un numero valido.")
    if not numero.is_finite():
        raise ErrorValidacion(PREFIJO_VAL + 'CANTIDAD',
                              "El campo '" + campo + "' no es un numero valido.")
    if numero <= 0:
        raise ErrorValidacion(PREFIJO_VAL + 'CANTIDAD',
                              "El campo '" + campo + "' tiene que ser mayor que cero.")
    if -numero.as_tuple().exponent > 4:
        raise ErrorValidacion(PREFIJO_VAL + 'CANTIDAD',
                              "El campo '" + campo + "' admite hasta 4 decimales.")
    if numero > CANTIDAD_MAXIMA:
        raise ErrorValidacion(PREFIJO_VAL + 'CANTIDAD',
                              "El campo '" + campo + "' es demasiado grande.")
    try:
        return numero.quantize(Decimal('0.0001'))
    except InvalidOperation:
        raise ErrorValidacion(PREFIJO_VAL + 'CANTIDAD',
                              "El campo '" + campo + "' no es un numero valido.")


def validar_entero(valor, campo):
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErrorValidacion(PREFIJO_VAL + 'ENTERO',
                              "El campo '" + campo + "' tiene que ser un numero entero.")


def validar_signo(valor):
    signo = str(valor or '').strip().upper()
    if signo not in ('E', 'S'):
        raise ErrorValidacion(PREFIJO_VAL + 'SIGNO',
                              "El signo tiene que ser 'E' (entrada) o 'S' (salida).")
    return signo


def validar_fecha(valor):
    """None o vacio -> None (el SQL usa la fecha de hoy). Si viene, tiene que
    ser una fecha ISO (AAAA-MM-DD)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor).strip())
    except (TypeError, ValueError):
        raise ErrorValidacion(PREFIJO_VAL + 'FECHA',
                              "La fecha tiene que venir en formato ISO (AAAA-MM-DD).")


def validar_texto(valor, campo, maximo=None):
    """None o vacio -> ''. Un valor que no sea texto es un error (no se
    convierten numeros ni objetos a texto por accidente)."""
    if valor is None:
        return ''
    if not isinstance(valor, str):
        raise ErrorValidacion(PREFIJO_VAL + 'TEXTO',
                              "El campo '" + campo + "' tiene que ser texto.")
    texto = valor.strip()
    if maximo is not None and len(texto) > maximo:
        raise ErrorValidacion(PREFIJO_VAL + 'TEXTO',
                              "El campo '" + campo + "' admite hasta " + str(maximo) + " caracteres.")
    return texto


def validar_partida_opcional(valor):
    """None o vacio -> None (el movimiento no lleva partida). Un id de partida
    tiene que ser un entero mayor que cero: el 0 no es 'sin partida', es un id
    invalido y no se ignora en silencio."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    partida = validar_entero(valor, 'partida')
    if partida <= 0:
        raise ErrorValidacion(PREFIJO_VAL + 'PARTIDA',
                              "El id de partida tiene que ser mayor que cero.")
    return partida


def guardas_articulo_deposito(articulo, deposito):
    return f"""
IF NOT EXISTS (SELECT 1 FROM STOC_ARTS WHERE ARTS_ARTICULO = {articulo} AND ARTS_FECHA_BAJA IS NULL)
    RAISERROR('{PREFIJO_VAL}ARTICULO|El articulo {articulo} no existe o esta dado de baja.', 16, 1);
IF ISNULL((SELECT ARTS_UNIMED_STOCK FROM STOC_ARTS WHERE ARTS_ARTICULO = {articulo}), '') <> 'UN'
    RAISERROR('{PREFIJO_VAL}UNIDAD|El articulo {articulo} no tiene unidad de stock UN: este circuito no lo soporta.', 16, 1);
IF NOT EXISTS (SELECT 1 FROM STOC_DPOS WHERE DPOS_DEPOSITO = {deposito} AND DPOS_UTILIZABLE = 1)
    RAISERROR('{PREFIJO_VAL}DEPOSITO|El deposito {deposito} no existe o no es utilizable.', 16, 1);
"""


def verificacion_agregado(articulo=None, deposito=None, desde=None):
    """La invariante del agregado, en UN solo lugar. Tres formas:
    - `verificacion_agregado(111, 2)`: el par literal.
    - `verificacion_agregado('@art', '@dep')`: el par en variables SQL.
    - `verificacion_agregado(desde='@pares p')`: todos los pares del origen, que
      tiene que exponer las columnas `art` y `dep` (lo usa la anulacion, que no
      conoce los pares hasta ejecutar el lote).
    """
    if desde:
        art, dep = 'p.art', 'p.dep'
        encabezado = f"SELECT 1 FROM {desde}\n    JOIN STOC_STDP s ON s.STDP_ARTICULO = {art} AND s.STDP_DEPOSITO = {dep}"
        etiqueta = 'El agregado de stock'
    else:
        art, dep = articulo, deposito
        encabezado = f"SELECT 1 FROM STOC_STDP s\n    WHERE s.STDP_ARTICULO = {art} AND s.STDP_DEPOSITO = {dep}"
        etiqueta = f"El agregado de stock del articulo {articulo} en el deposito {deposito}"
    condicion = 'WHERE '
    return f"""
IF EXISTS (
    {encabezado}
      AND ABS(s.STDP_STOCK_ACT - (
            SELECT ISNULL(SUM(CASE WHEN m.MOSD_SIGNO = 'E' THEN m.MOSD_CANT_UNISTO
                                   ELSE -m.MOSD_CANT_UNISTO END), 0)
            FROM STOC_MOSD m
            {condicion}m.MOSD_ARTICULO = {art} AND m.MOSD_DEPOSITO = {dep})) > 0.00005)
    RAISERROR('{PREFIJO_INT}STDP_DESVIO|{etiqueta} no quedo igual a la suma de sus movimientos.', 16, 1);
"""


# ============================================================
# DIAGNOSTICO DE ERRORES DE LA BASE
# ============================================================

# Las FK del ERP que pueden impedir borrar un movimiento (o su comprobante): se
# busca el nombre del circuito en el texto del error 547 para poder decirle al
# usuario donde se anula de verdad.
MENSAJES_FK = {
    'MCRF': 'un comprobante de compra (FMR): anulalo desde Cuentas a Pagar',
    'OCCE': 'una orden de compra',
    'NPCU': 'una nota de pedido/venta',
    'MORF': 'una venta (remito/factura)',
    'HRDR': 'una devolucion de distribucion',
    'PRDR': 'una orden de produccion (entrega de producto terminado)',
    'SRCE': 'un movimiento de produccion',
    'OFCE': 'una orden de fabricacion',
    'OFSP': 'una orden de fabricacion',
    'MTCP': 'una orden de produccion',
    'MTMC': 'una orden de produccion',
    'RFAD': 'una factura de venta',
    'RSPA': 'una salida por venta',
    'CPRC': 'un comprobante contable',
    'RENA': 'un movimiento de importacion',
    'RAMS': 'un ajuste de stock del ERP',
    # FK de las tablas del propio comprobante de stock: si aparece alguna, el
    # movimiento todavia esta referenciado por otro renglon del mismo libro.
    'MOST_R01': 'otro renglon del mismo comprobante de stock',
    'MOST_R04': 'otro renglon del mismo comprobante de stock',
    'MOST_R05': 'otro renglon del mismo comprobante de stock',
    'MSTE_R01': 'la otra pata de la transferencia',
    'MSTS_R01': 'el detalle de la transferencia',
    'TRES_R01': 'el detalle de la transferencia de entrada',
    'TRSS_R01': 'el detalle de la transferencia de salida',
}


def mensaje_de_error_sql(texto):
    """Traduce el error de la base a (codigo, mensaje). Los RAISERROR propios
    viajan como 'STK_...|mensaje'; los 547 (FK) se traducen a un mensaje que
    dice que circuito del ERP referencia el movimiento."""
    texto = str(texto or '')
    encontrado = re.search(r'STK_[A-Z0-9_]+', texto)
    if encontrado:
        codigo = encontrado.group(0)
        mensaje = texto.split('|', 1)[1].strip() if '|' in texto else ''
        return codigo, mensaje or codigo
    # 'REFERENCE' aparece tanto en el mensaje en ingles ("REFERENCE
    # constraint") como en el espanol ("restriccion REFERENCE").
    if 'REFERENCE' in texto.upper():
        for clave, descripcion in MENSAJES_FK.items():
            if clave in texto:
                return 'STK_INT_FK', ('No se puede anular: el movimiento esta referenciado por '
                                      + descripcion + '.')
        return 'STK_INT_FK', 'No se puede anular: el movimiento esta referenciado por otro circuito del ERP.'
    return 'STK_INT', 'No se pudo completar la operacion de stock.'


# ============================================================
# AJUSTE INDIVIDUAL (+ / -)
# ============================================================

def _numero_comprobante(ctx, tipo_com, sufijo=''):
    """Un lote puede necesitar dos comprobantes (transferencia: TRS y TRE):
    `sufijo` da nombres de variable distintos para no repetir el DECLARE."""
    var = '@num' + sufijo
    return f"""
DECLARE {var} DECIMAL(18,0);
UPDATE STOC_NUST WITH (UPDLOCK, ROWLOCK)
   SET NUST_ULT_NUMERO = NUST_ULT_NUMERO + 1, NUST_FECHA_ULT_COM = GETDATE()
 WHERE NUST_DIVISION = {ctx.division} AND NUST_SUCURSAL_IMP = {ctx.sucursal_imp}
   AND NUST_TIPO_COM = '{tipo_com}';
IF @@ROWCOUNT = 0
    RAISERROR('{PREFIJO_VAL}NUMERADOR|Falta el numerador {tipo_com} para la division {ctx.division} / sucursal {ctx.sucursal_imp} en esta base.', 16, 1);
SELECT {var} = NUST_ULT_NUMERO FROM STOC_NUST
 WHERE NUST_DIVISION = {ctx.division} AND NUST_SUCURSAL_IMP = {ctx.sucursal_imp}
   AND NUST_TIPO_COM = '{tipo_com}';
"""


def _id_movimiento(sufijo=''):
    """Idem que `_numero_comprobante`: la transferencia consume dos ids de
    movimiento en el mismo lote."""
    var = '@mov' + sufijo
    return f"""
DECLARE {var} INT;
UPDATE SIST_NUSI WITH (UPDLOCK, ROWLOCK)
   SET NUSI_ULTIMO_NUMERO = NUSI_ULTIMO_NUMERO + 1, NUSI_ULT_ACTUALIZACION_FYH = GETDATE()
 WHERE NUSI_NUMERADOR_ID = 5;
IF @@ROWCOUNT = 0
    RAISERROR('{PREFIJO_VAL}NUMERADOR_MOV|Falta el numerador de movimientos de stock (SIST_NUSI id 5).', 16, 1);
SELECT {var} = NUSI_ULTIMO_NUMERO FROM SIST_NUSI WHERE NUSI_NUMERADOR_ID = 5;
"""


def _numero_partida(var):
    """Numero de una partida NUEVA: sale del numerador del ERP (`SIST_NUSI` id
    6), no de `MAX(PART_PARTIDA)+1`.

    El ERP numera las partidas con ese numerador y lo trata como "ultimo usado"
    (`docs/INCIDENTE_PARTIDAS_AR_2026-09-21.md` §1 y §3: la base AR tiene el
    contador 1 atras, `plataforma_ur` 3 adelante y las otras 9 con
    `NUSI_ULTIMO_NUMERO = MAX(PART_PARTIDA)` exacto, medido en solo lectura con
    `_investigacion_gt/166_*` y `169_*`). Numerar con `MAX+1` es una SEGUNDA
    fuente sobre la misma clave primaria (`PART_PK1` = `PART_PARTIDA` sola,
    medido en `166_*` §2) y es el 2627 `PART_RK1` del incidente (§4).

    El numero que se escribe es `max(contador, MAX(PART_PARTIDA real)) + 1` y el
    contador QUEDA en ese valor: si el contador venia atras (base AR del
    incidente: contador 1486, MAX 1487, §1/§3) la primera alta de Stock lo
    vuelve a sincronizar en vez de repetir un numero ya usado.

    Si no existe la fila del numerador 6 el lote se corta ahi (fail-closed, igual
    que `_id_movimiento` con el id 5): NO hay vuelta atras a `MAX+1`, que es
    justamente la doble fuente que se esta sacando.

    Mismo mecanismo de exclusion que `_id_movimiento`: el `UPDLOCK` sobre la fila
    del numerador serializa a los que compiten por el numero (el ERP tambien
    actualiza esa fila). `var` ya viene declarada por el llamador: un `DECLARE`
    repetido en el mismo lote lo romperia.
    """
    return f"""
UPDATE SIST_NUSI WITH (UPDLOCK, ROWLOCK)
   SET NUSI_ULTIMO_NUMERO = (SELECT CASE WHEN NUSI_ULTIMO_NUMERO > ISNULL(MAX(PART_PARTIDA), 0)
                                         THEN NUSI_ULTIMO_NUMERO
                                         ELSE ISNULL(MAX(PART_PARTIDA), 0) END
                               FROM STOC_PART) + 1,
       NUSI_ULT_ACTUALIZACION_FYH = GETDATE()
 WHERE NUSI_NUMERADOR_ID = 6;
IF @@ROWCOUNT = 0
    RAISERROR('{PREFIJO_VAL}NUMERADOR_PARTIDA|Falta el numerador de partidas (SIST_NUSI id 6) en esta base.', 16, 1);
SELECT {var} = NUSI_ULTIMO_NUMERO FROM SIST_NUSI WHERE NUSI_NUMERADOR_ID = 6;
"""


def _fecha_sql(fecha):
    return "CAST(GETDATE() AS DATE)" if not fecha else f"CONVERT(date, {lit(fecha)}, 23)"


def _guarda_partida_obligatoria(articulo):
    """Si el articulo usa partidas, una salida SIN partida no puede pasar:
    descontaria el agregado sin tocar el stock por partida."""
    return f"""
IF ISNULL((SELECT ARTS_CON_PARTIDAS FROM STOC_ARTS WHERE ARTS_ARTICULO = {articulo}), 0) = 1
    RAISERROR('{PREFIJO_VAL}PARTIDA_OBLIGATORIA|El articulo {articulo} usa partidas: hay que indicar de que partida sale.', 16, 1);
"""


def _guarda_partida_no_aplica(articulo):
    """Al reves: un articulo que NO usa partidas no puede llevar partida ni
    nombre de partida (se escribian STOC_PART/STOC_SDPP/STOC_MOSP de mas)."""
    return f"""
IF ISNULL((SELECT ARTS_CON_PARTIDAS FROM STOC_ARTS WHERE ARTS_ARTICULO = {articulo}), 0) = 0
    RAISERROR('{PREFIJO_VAL}PARTIDA_NO_APLICA|El articulo {articulo} no usa partidas: no corresponde indicar una partida.', 16, 1);
"""


def _agregado_articulo(articulo, deposito, cantidad, operador, verificar=True):
    """`verificar=False` lo usa el ajuste en lote: la invariante compara el
    agregado contra la suma de TODOS los MOSD del par, asi que en un lote se
    corre una sola vez por par, despues de escribir todas las filas."""
    verificacion = verificacion_agregado(articulo, deposito) if verificar else ''
    if operador == '+':
        return f"""
IF EXISTS (SELECT 1 FROM STOC_STDP WHERE STDP_ARTICULO = {articulo} AND STDP_DEPOSITO = {deposito})
BEGIN
    UPDATE STOC_STDP SET STDP_STOCK_ACT = STDP_STOCK_ACT + {cantidad}
     WHERE STDP_ARTICULO = {articulo} AND STDP_DEPOSITO = {deposito};
    IF @@ROWCOUNT = 0
        RAISERROR('{PREFIJO_INT}STDP_SIN_FILA|No se pudo actualizar el agregado de stock del articulo {articulo} en el deposito {deposito}.', 16, 1);
END
ELSE
    INSERT INTO STOC_STDP (STDP_DEPOSITO, STDP_ARTICULO, STDP_STOCK_ACT, STDP_STEGR_PED,
        STDP_STEGR_FAB, STDP_STING_COM, STDP_STING_FAB, STDP_STRES_PED)
    VALUES ({deposito}, {articulo}, {cantidad}, 0, 0, 0, 0, 0);
""" + verificacion
    # La guarda del stock negativo va DENTRO del UPDATE: la condicion y la
    # escritura son atomicas, asi dos salidas concurrentes no pueden pasar las
    # dos. El error despues de @@ROWCOUNT = 0 distingue "no hay stock" de
    # "no existe la fila del agregado".
    return f"""
UPDATE STOC_STDP SET STDP_STOCK_ACT = STDP_STOCK_ACT - {cantidad}
 WHERE STDP_ARTICULO = {articulo} AND STDP_DEPOSITO = {deposito}
   AND ( ISNULL((SELECT ARTS_CONTROL_STOCK FROM STOC_ARTS WHERE ARTS_ARTICULO = {articulo}), 0) = 0
         OR ISNULL((SELECT DPOS_CTRL_STOCKNEG FROM STOC_DPOS WHERE DPOS_DEPOSITO = {deposito}), 0) <> 1
         OR STDP_STOCK_ACT - {cantidad} >= 0 );
IF @@ROWCOUNT = 0
BEGIN
    IF EXISTS (SELECT 1 FROM STOC_STDP WHERE STDP_ARTICULO = {articulo} AND STDP_DEPOSITO = {deposito})
        RAISERROR('{PREFIJO_VAL}STOCK|No hay stock suficiente del articulo {articulo} en el deposito {deposito} (el articulo controla stock y el deposito no admite negativo).', 16, 1);
    ELSE
        RAISERROR('{PREFIJO_INT}STDP_SIN_FILA|No existe el agregado de stock del articulo {articulo} en el deposito {deposito}: no se descuenta un movimiento sin respaldo.', 16, 1);
END
""" + verificacion


def _movimiento_partidas(signo, articulo, deposito, cantidad, partida, partida_nombre, renglon=None):
    """`renglon` es el numero de renglon del MOSD (y el de la variable de
    partida) cuando varias filas van en el mismo lote: dos `DECLARE @part` en
    un mismo batch romperian el lote entero."""
    var_partida = '@part' if renglon is None else '@part' + str(renglon)
    renglon_sql = 1 if renglon is None else renglon
    if signo == 'E':
        # Entrada: si el articulo usa partidas (lo dice el ERP en
        # ARTS_CON_PARTIDAS) SIEMPRE se crea o se reutiliza la partida y se
        # escribe STOC_SDPP + STOC_MOSP. Con nombre se busca por
        # PART_PARTIDA_EMP (y se rechaza la partida viva); sin nombre se crea
        # una nueva, igual que hacia routes.py. El numero de la partida nueva lo
        # da el numerador del ERP (`_numero_partida`), no `MAX(PART_PARTIDA)+1`.
        if partida_nombre:
            busca = f"""
    SELECT {var_partida} = PART_PARTIDA FROM STOC_PART WITH (UPDLOCK, HOLDLOCK)
     WHERE PART_ARTICULO = {articulo} AND PART_PARTIDA_EMP = {lit(partida_nombre)};
    IF {var_partida} IS NOT NULL
       AND EXISTS (SELECT 1 FROM STOC_SDPP
                   WHERE SDPP_PARTIDA = {var_partida} AND SDPP_ARTICULO = {articulo} AND SDPP_STOCK_ACT <> 0)
        RAISERROR('{PREFIJO_VAL}PARTIDA_VIVA|La partida indicada ya existe para este articulo y tiene stock: no se puede volver a ingresar.', 16, 1);
"""
            nombre_emp = lit(partida_nombre)
        else:
            busca = ''
            nombre_emp = 'CAST(' + var_partida + ' AS VARCHAR)'
        return f"""
IF ISNULL((SELECT ARTS_CON_PARTIDAS FROM STOC_ARTS WHERE ARTS_ARTICULO = {articulo}), 0) = 1
BEGIN
    DECLARE {var_partida} INT;
{busca}    IF {var_partida} IS NULL
    BEGIN{_numero_partida(var_partida)}        INSERT INTO STOC_PART (PART_PARTIDA, PART_PARTIDA_EMP, PART_ARTICULO, PART_FECHA_ALTA,
            PART_CANT_INI, PART_COSTO_GES_1, PART_COSTO_GES_2, PART_COSTO_GES_3, PART_COSTO_GES_4)
        VALUES ({var_partida}, {nombre_emp}, {articulo}, CAST(GETDATE() AS DATE), {cantidad}, 0, 0, 0, 0);
    END
    IF EXISTS (SELECT 1 FROM STOC_SDPP WHERE SDPP_DEPOSITO = {deposito} AND SDPP_PARTIDA = {var_partida} AND SDPP_ARTICULO = {articulo})
    BEGIN
        UPDATE STOC_SDPP SET SDPP_STOCK_ACT = SDPP_STOCK_ACT + {cantidad}
         WHERE SDPP_DEPOSITO = {deposito} AND SDPP_PARTIDA = {var_partida} AND SDPP_ARTICULO = {articulo};
        IF @@ROWCOUNT = 0
            RAISERROR('{PREFIJO_INT}SDPP_SIN_FILA|No se pudo actualizar el stock de la partida indicada.', 16, 1);
    END
    ELSE
        INSERT INTO STOC_SDPP (SDPP_DEPOSITO, SDPP_PARTIDA, SDPP_ARTICULO, SDPP_STOCK_ACT, SDPP_STRES_PED)
        VALUES ({deposito}, {var_partida}, {articulo}, {cantidad}, 0);
    INSERT INTO STOC_MOSP (MOSP_MOVSTO_MOST, MOSP_RENGLON_MOSD, MOSP_PARTIDA, MOSP_CANT_ING, MOSP_CANT_UNISTO, MOSP_FACTOR_UMS)
    VALUES (@mov, {renglon_sql}, {var_partida}, {cantidad}, {cantidad}, 1);
{_verificacion_partida(articulo, deposito, var_partida, 'la partida indicada')}END
"""
    if signo == 'S' and partida:
        # Mismo patron atomico que la transferencia: la guarda va dentro del
        # UPDATE y @@ROWCOUNT = 0 distingue "no hay stock de la partida"
        # (STK_VAL_PARTIDA_STOCK) de "no existe la fila" (STK_INT_SDPP_SIN_FILA).
        return _sdpp_salida(articulo, deposito, cantidad, partida,
                            PREFIJO_VAL + 'PARTIDA_STOCK',
                            'La partida ' + str(partida) + ' no tiene stock suficiente (' + str(cantidad) + ' pedido).') + f"""
INSERT INTO STOC_MOSP (MOSP_MOVSTO_MOST, MOSP_RENGLON_MOSD, MOSP_PARTIDA, MOSP_CANT_ING, MOSP_CANT_UNISTO, MOSP_FACTOR_UMS)
VALUES (@mov, {renglon_sql}, {partida}, {cantidad}, {cantidad}, 1);
"""
    return ''


def _verificacion_partida(articulo=None, deposito=None, referencia=None, etiqueta=None, desde=None):
    """`referencia` es la expresion SQL de la partida (un id literal o una
    variable, p. ej. @part). Compara STOC_SDPP contra STOC_MOSP.

    Con `desde` (p. ej. 'STOC_SDPP p JOIN @partidas x ON x.part = p.SDPP_PARTIDA')
    la comparacion se hace para cada fila del origen, usando las columnas
    `p.SDPP_ARTICULO`, `p.SDPP_DEPOSITO` y `p.SDPP_PARTIDA`: lo usa la anulacion,
    que no conoce las partidas hasta ejecutar el lote."""
    if desde:
        art, dep, part = 'p.SDPP_ARTICULO', 'p.SDPP_DEPOSITO', 'p.SDPP_PARTIDA'
        encabezado = f"SELECT 1 FROM {desde}"
        etiqueta = etiqueta or 'la partida'
    else:
        if not referencia:
            return ''
        art, dep, part = articulo, deposito, referencia
        encabezado = f"SELECT 1 FROM STOC_SDPP p\n    WHERE p.SDPP_ARTICULO = {articulo} AND p.SDPP_DEPOSITO = {deposito} AND p.SDPP_PARTIDA = {referencia}"
        etiqueta = etiqueta or ('la partida ' + str(referencia))
    return f"""
IF EXISTS (
    {encabezado}
      AND ABS(p.SDPP_STOCK_ACT - (
            SELECT ISNULL(SUM(CASE WHEN m.MOSD_SIGNO = 'E' THEN mp.MOSP_CANT_UNISTO ELSE -mp.MOSP_CANT_UNISTO END), 0)
            FROM STOC_MOSP mp JOIN STOC_MOSD m
              ON m.MOSD_MOVSTO_MOST = mp.MOSP_MOVSTO_MOST AND m.MOSD_RENGLON_MOSD = mp.MOSP_RENGLON_MOSD
            WHERE mp.MOSP_PARTIDA = {part} AND m.MOSD_ARTICULO = {art} AND m.MOSD_DEPOSITO = {dep})) > 0.00005)
    RAISERROR('{PREFIJO_INT}SDPP_DESVIO|El stock de {etiqueta} no quedo igual a la suma de sus movimientos.', 16, 1);
"""


def _comprobante_msva(ctx, tipo_com, fecha):
    return f"""
INSERT INTO STOC_MSVA (MSVA_DIVISION_MSVA, MSVA_SUCURSAL_MSVA, MSVA_TIPO_MSVA,
    MSVA_NUMERO_MSVA, MSVA_ORIGEN, MSVA_INDICADOR_DEP, MSVA_FECHA_EMI, MSVA_PESO_EMBALADO,
    MSVA_CANT_BULTOS, MSVA_TIENE_COSTOES, MSVA_REQ_FCANTICIP, MSVA_TIENE_REG_PPP,
    MSVA_INF_TABASTO, MSVA_INGRESO_ART_TC, MSVA_PESO_EMB_CAL, MSVA_VOLUMEN_EMB_CAL, MSVA_VOLUMEN_EMB_AJ)
VALUES ({ctx.division}, {ctx.sucursal_imp}, '{tipo_com}', @num, 1, 1, {fecha}, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0);
INSERT INTO STOC_MSMV (MSMV_MOVSTO_MOST, MSMV_DIVISION_MSVA, MSMV_SUCURSAL_MSVA, MSMV_TIPO_MSVA, MSMV_NUMERO_MSVA)
VALUES (@mov, {ctx.division}, {ctx.sucursal_imp}, '{tipo_com}', @num);
"""


def sql_ajuste(ctx, datos):
    signo = validar_signo(datos.get('signo'))
    articulo = validar_entero(datos.get('articulo'), 'articulo')
    deposito = validar_entero(datos.get('deposito'), 'deposito')
    cantidad = validar_cantidad(datos.get('cantidad'))
    # El id de partida se interpola en el SQL: se valida antes, como cualquier
    # otro valor que va al lote (restriccion global del plan).
    partida = validar_partida_opcional(datos.get('partida'))
    # En una entrada la partida se crea (o se reutiliza por nombre): el id de
    # una partida existente no tiene sentido y se rechaza en vez de ignorarlo.
    if signo == 'E' and partida is not None:
        raise ErrorValidacion(PREFIJO_VAL + 'PARTIDA_EN_ENTRADA',
                              "En una entrada hay que indicar el nombre de la partida, no su id.")
    partida_nombre = validar_texto(datos.get('partida_nombre'), 'partida_nombre', PARTIDA_NOMBRE_MAX)
    comentario = validar_texto(datos.get('comentario'), 'comentario', COMENTARIO_MAX) or None
    fecha = _fecha_sql(validar_fecha(datos.get('fecha')))
    tipo_com = 'AJ+' if signo == 'E' else 'AJ-'
    signo_sql = 'E' if signo == 'E' else 'S'
    operador = '+' if signo == 'E' else '-'
    # En la entrada las partidas las decide el tipo de articulo del ERP.
    if signo == 'E':
        crea_partidas = f"ISNULL((SELECT ARTS_CON_PARTIDAS FROM STOC_ARTS WHERE ARTS_ARTICULO = {articulo}), 0)"
    else:
        crea_partidas = '0'

    partes = ['SET NOCOUNT ON;', 'SET XACT_ABORT ON;', 'BEGIN TRANSACTION;', 'BEGIN TRY;']
    partes.append(_numero_comprobante(ctx, tipo_com))
    partes.append(_id_movimiento())
    partes.append(guardas_articulo_deposito(articulo, deposito))
    if partida or partida_nombre:
        partes.append(_guarda_partida_no_aplica(articulo))
    if signo == 'S' and not partida:
        partes.append(_guarda_partida_obligatoria(articulo))

    partes.append(f"""
INSERT INTO STOC_MOST (MOST_MOVSTO_MOST, MOST_ORIGEN, MOST_SUBORIGEN_VAR, MOST_FECHA_EMI,
    MOST_DIVISION, MOST_SUCURSAL_IMP, MOST_SUCURSAL_EMP, MOST_SUJETO, MOST_SUJETO_GLOBAL,
    MOST_TIENE_ASIENTO, MOST_DESCRIPCION)
VALUES (@mov, 1, 1, {fecha}, {ctx.division}, {ctx.sucursal_imp}, {ctx.sucursal_emp}, 0, 0, 0, {lit(comentario)});
""")

    partes.append(f"""
INSERT INTO STOC_MOSD (MOSD_MOVSTO_MOST, MOSD_RENGLON_MOSD, MOSD_ORIGEN, MOSD_SUBORIGEN_VAR,
    MOSD_DEPOSITO, MOSD_ARTICULO, MOSD_SIGNO, MOSD_MOD_STOCK, MOSD_CANT_ING, MOSD_UNIMED,
    MOSD_CANT_UNISTO, MOSD_FACTOR_UMS, MOSD_TIENE_PEDIDOS, MOSD_CREA_PARTIDAS, MOSD_TIENE_OC,
    MOSD_TIENE_REG_PPP, MOSD_TIENE_PPP_PAR)
VALUES (@mov, 1, 1, 1, {deposito}, {articulo}, '{signo_sql}', 1, {cantidad}, 'UN', {cantidad}, 1,
    0, {crea_partidas}, 0, 0, 0);
""")
    partes.append(_movimiento_partidas(signo, articulo, deposito, cantidad, partida, partida_nombre))
    partes.append(_agregado_articulo(articulo, deposito, cantidad, operador))
    if signo == 'S':
        partes.append(_verificacion_partida(articulo, deposito, partida))
    partes.append(_comprobante_msva(ctx, tipo_com, fecha))
    partes.append('COMMIT TRANSACTION;')
    partes.append('SELECT @mov AS movimiento, @num AS numero;')
    partes.append("""
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
""")
    return '\n'.join(partes)


# ============================================================
# AJUSTE EN LOTE (un comprobante, un renglon por fila)
# ============================================================

def sql_ajuste_lote(ctx, signo, filas):
    signo = validar_signo(signo)
    if not isinstance(filas, (list, tuple)) or len(filas) == 0:
        raise ErrorValidacion(PREFIJO_VAL + 'FILAS',
                              "El ajuste en lote necesita al menos una fila.")
    normalizadas = []
    partidas_vistas = {}
    for indice, fila in enumerate(filas, start=1):
        if not isinstance(fila, dict):
            raise ErrorValidacion(PREFIJO_VAL + 'FILA',
                                  "La fila " + str(indice) + " del lote no es un objeto valido.")
        articulo = validar_entero(fila.get('articulo'), 'articulo')
        deposito = validar_entero(fila.get('deposito'), 'deposito')
        cantidad = validar_cantidad(fila.get('cantidad'))
        partida = validar_partida_opcional(fila.get('partida'))
        # Las entradas del lote crean la partida (lo decide ARTS_CON_PARTIDAS
        # en SQL): un id de partida no tiene sentido y no se ignora en
        # silencio.
        if signo == 'E' and partida is not None:
            raise ErrorValidacion(PREFIJO_VAL + 'PARTIDA_EN_ENTRADA',
                                  "En un ajuste en lote las entradas crean la partida: no se indica su id.")
        # La misma fila de STOC_SDPP dos veces en el lote se pisaba a si misma
        # (la segunda fila recalculaba el stock desde el estado previo:
        # routes.py:543-551): se rechaza antes de armar el SQL.
        if partida is not None:
            clave = (articulo, deposito, partida)
            if clave in partidas_vistas:
                raise ErrorValidacion(PREFIJO_VAL + 'PARTIDA_REPETIDA',
                                      "La partida " + str(partida) + " aparece dos veces en el lote para el mismo articulo y deposito.")
            partidas_vistas[clave] = indice
        normalizadas.append({'renglon': indice, 'articulo': articulo, 'deposito': deposito,
                             'cantidad': cantidad, 'partida': partida})

    tipo_com = 'AJ+' if signo == 'E' else 'AJ-'
    signo_sql = 'E' if signo == 'E' else 'S'
    operador = '+' if signo == 'E' else '-'
    fecha = _fecha_sql(None)

    partes = ['SET NOCOUNT ON;', 'SET XACT_ABORT ON;', 'BEGIN TRANSACTION;', 'BEGIN TRY;']
    partes.append(_numero_comprobante(ctx, tipo_com))
    partes.append(_id_movimiento())
    # Guardas de articulo/deposito: una vez por par distinto, antes de
    # escribir nada.
    pares = []
    for fila in normalizadas:
        par = (fila['articulo'], fila['deposito'])
        if par not in pares:
            pares.append(par)
    for articulo, deposito in pares:
        partes.append(guardas_articulo_deposito(articulo, deposito))
    # Guardas de partida: la entrada crea o reutiliza la partida (lo decide
    # ARTS_CON_PARTIDAS); la salida la exige si el articulo usa partidas y la
    # rechaza si no las usa.
    if signo == 'S':
        vistas_guarda = []
        for fila in normalizadas:
            marca = (fila['articulo'], fila['partida'] is not None)
            if marca in vistas_guarda:
                continue
            vistas_guarda.append(marca)
            if fila['partida'] is not None:
                partes.append(_guarda_partida_no_aplica(fila['articulo']))
            else:
                partes.append(_guarda_partida_obligatoria(fila['articulo']))

    partes.append(f"""
INSERT INTO STOC_MOST (MOST_MOVSTO_MOST, MOST_ORIGEN, MOST_SUBORIGEN_VAR, MOST_FECHA_EMI,
    MOST_DIVISION, MOST_SUCURSAL_IMP, MOST_SUCURSAL_EMP, MOST_SUJETO, MOST_SUJETO_GLOBAL,
    MOST_TIENE_ASIENTO)
VALUES (@mov, 1, 1, {fecha}, {ctx.division}, {ctx.sucursal_imp}, {ctx.sucursal_emp}, 0, 0, 0);
""")
    for fila in normalizadas:
        if signo == 'E':
            crea_partidas = ("ISNULL((SELECT ARTS_CON_PARTIDAS FROM STOC_ARTS "
                             "WHERE ARTS_ARTICULO = " + str(fila['articulo']) + "), 0)")
        else:
            crea_partidas = '0'
        partes.append(f"""
INSERT INTO STOC_MOSD (MOSD_MOVSTO_MOST, MOSD_RENGLON_MOSD, MOSD_ORIGEN, MOSD_SUBORIGEN_VAR,
    MOSD_DEPOSITO, MOSD_ARTICULO, MOSD_SIGNO, MOSD_MOD_STOCK, MOSD_CANT_ING, MOSD_UNIMED,
    MOSD_CANT_UNISTO, MOSD_FACTOR_UMS, MOSD_TIENE_PEDIDOS, MOSD_CREA_PARTIDAS, MOSD_TIENE_OC,
    MOSD_TIENE_REG_PPP, MOSD_TIENE_PPP_PAR)
VALUES (@mov, {fila['renglon']}, 1, 1, {fila['deposito']}, {fila['articulo']}, '{signo_sql}', 1, {fila['cantidad']}, 'UN', {fila['cantidad']}, 1,
    0, {crea_partidas}, 0, 0, 0);
""")
        if signo == 'E':
            partes.append(_movimiento_partidas('E', fila['articulo'], fila['deposito'],
                                               fila['cantidad'], None, '', renglon=fila['renglon']))
        elif fila['partida'] is not None:
            partes.append(_movimiento_partidas('S', fila['articulo'], fila['deposito'],
                                               fila['cantidad'], fila['partida'], '',
                                               renglon=fila['renglon']))
    # Agregados: la invariante del par se verifica UNA sola vez, al final,
    # porque compara el agregado contra la suma de TODOS los MOSD del par
    # (incluidas las filas que todavia no se habian escrito).
    for fila in normalizadas:
        partes.append(_agregado_articulo(fila['articulo'], fila['deposito'], fila['cantidad'],
                                         operador, verificar=False))
    for articulo, deposito in pares:
        partes.append(verificacion_agregado(articulo, deposito))
    if signo == 'S':
        verificadas = []
        for fila in normalizadas:
            clave = (fila['articulo'], fila['deposito'], fila['partida'])
            if fila['partida'] is None or clave in verificadas:
                continue
            verificadas.append(clave)
            partes.append(_verificacion_partida(fila['articulo'], fila['deposito'], fila['partida']))
    partes.append(_comprobante_msva(ctx, tipo_com, fecha))
    partes.append('COMMIT TRANSACTION;')
    partes.append('SELECT @mov AS movimiento, @num AS numero;')
    partes.append("""
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
""")
    return '\n'.join(partes)


# ============================================================
# TRANSFERENCIA (dos movimientos, comprobantes TRS y TRE)
# ============================================================

def _sdpp_salida(articulo, deposito, cantidad, partida, codigo_falta=None, mensaje_falta=None):
    """Baja del stock de una partida. La guarda va DENTRO del UPDATE (la lectura
    y la escritura son atomicas) y @@ROWCOUNT = 0 distingue "no existe la fila"
    (STK_INT_SDPP_SIN_FILA) de "no hay stock" (el codigo lo decide el llamador:
    STK_VAL_STOCK en la transferencia, STK_VAL_PARTIDA_STOCK en el ajuste).

    El negativo no se decide con politica propia: valen las mismas dos banderas
    del ERP que en el agregado (ARTS_CONTROL_STOCK del articulo y
    DPOS_CTRL_STOCKNEG del deposito)."""
    codigo_falta = codigo_falta or (PREFIJO_VAL + 'STOCK')
    mensaje_falta = mensaje_falta or ('La partida ' + str(partida) + ' no tiene stock suficiente en el deposito '
                                      + str(deposito) + ' (se pidio ' + str(cantidad) + ').')
    return f"""
UPDATE STOC_SDPP SET SDPP_STOCK_ACT = SDPP_STOCK_ACT - {cantidad}
 WHERE SDPP_ARTICULO = {articulo} AND SDPP_DEPOSITO = {deposito} AND SDPP_PARTIDA = {partida}
   AND ( ISNULL((SELECT ARTS_CONTROL_STOCK FROM STOC_ARTS WHERE ARTS_ARTICULO = {articulo}), 0) = 0
         OR ISNULL((SELECT DPOS_CTRL_STOCKNEG FROM STOC_DPOS WHERE DPOS_DEPOSITO = {deposito}), 0) <> 1
         OR SDPP_STOCK_ACT - {cantidad} >= 0 );
IF @@ROWCOUNT = 0
BEGIN
    IF EXISTS (SELECT 1 FROM STOC_SDPP WHERE SDPP_ARTICULO = {articulo} AND SDPP_DEPOSITO = {deposito} AND SDPP_PARTIDA = {partida})
        RAISERROR('{codigo_falta}|{mensaje_falta}', 16, 1);
    ELSE
        RAISERROR('{PREFIJO_INT}SDPP_SIN_FILA|La partida {partida} no tiene stock en el deposito {deposito} para el articulo {articulo}.', 16, 1);
END
"""


def _sdpp_entrada(articulo, deposito, cantidad, partida, movimiento, renglon=1):
    """Alta del stock de una partida en el deposito destino (incremental) mas
    el renglon de STOC_MOSP del movimiento de entrada."""
    return f"""
IF EXISTS (SELECT 1 FROM STOC_SDPP WHERE SDPP_ARTICULO = {articulo} AND SDPP_DEPOSITO = {deposito} AND SDPP_PARTIDA = {partida})
BEGIN
    UPDATE STOC_SDPP SET SDPP_STOCK_ACT = SDPP_STOCK_ACT + {cantidad}
     WHERE SDPP_ARTICULO = {articulo} AND SDPP_DEPOSITO = {deposito} AND SDPP_PARTIDA = {partida};
    IF @@ROWCOUNT = 0
        RAISERROR('{PREFIJO_INT}SDPP_SIN_FILA|No se pudo actualizar el stock de la partida en el deposito destino.', 16, 1);
END
ELSE
    INSERT INTO STOC_SDPP (SDPP_DEPOSITO, SDPP_PARTIDA, SDPP_ARTICULO, SDPP_STOCK_ACT, SDPP_STRES_PED)
    VALUES ({deposito}, {partida}, {articulo}, {cantidad}, 0);
INSERT INTO STOC_MOSP (MOSP_MOVSTO_MOST, MOSP_RENGLON_MOSD, MOSP_PARTIDA, MOSP_CANT_ING, MOSP_CANT_UNISTO, MOSP_FACTOR_UMS)
VALUES ({movimiento}, {renglon}, {partida}, {cantidad}, {cantidad}, 1);
"""


def sql_transferencia(ctx, datos):
    articulo = validar_entero(datos.get('articulo'), 'articulo')
    dep_origen = validar_entero(datos.get('deposito_origen'), 'deposito_origen')
    dep_destino = validar_entero(datos.get('deposito_destino'), 'deposito_destino')
    if dep_origen == dep_destino:
        raise ErrorValidacion(PREFIJO_VAL + 'DEPOSITOS_IGUALES',
                              "El deposito de origen y el de destino no pueden ser el mismo.")
    cantidad = validar_cantidad(datos.get('cantidad'))
    partida = validar_partida_opcional(datos.get('partida'))
    comentario = validar_texto(datos.get('comentario'), 'comentario', COMENTARIO_MAX) or None
    fecha = _fecha_sql(validar_fecha(datos.get('fecha')))

    partes = ['SET NOCOUNT ON;', 'SET XACT_ABORT ON;', 'BEGIN TRANSACTION;', 'BEGIN TRY;']
    partes.append(_numero_comprobante(ctx, 'TRS', 'TRS'))
    partes.append(_numero_comprobante(ctx, 'TRE', 'TRE'))
    partes.append(_id_movimiento('S'))
    partes.append(_id_movimiento('E'))
    partes.append(guardas_articulo_deposito(articulo, dep_origen))
    partes.append(guardas_articulo_deposito(articulo, dep_destino))
    # La partida la exige o la rechaza el tipo de articulo del ERP: el servicio
    # es puro y no puede consultar ARTS_CON_PARTIDAS en Python.
    if partida is not None:
        partes.append(_guarda_partida_no_aplica(articulo))
    else:
        partes.append(_guarda_partida_obligatoria(articulo))

    partes.append(f"""
INSERT INTO STOC_MOST (MOST_MOVSTO_MOST, MOST_ORIGEN, MOST_SUBORIGEN_VAR, MOST_FECHA_EMI,
    MOST_DIVISION, MOST_SUCURSAL_IMP, MOST_SUCURSAL_EMP, MOST_SUJETO, MOST_SUJETO_GLOBAL,
    MOST_TIENE_ASIENTO, MOST_DESCRIPCION)
VALUES (@movS, 2, 0, {fecha}, {ctx.division}, {ctx.sucursal_imp}, {ctx.sucursal_emp}, 0, 0, 0, {lit(comentario)});
INSERT INTO STOC_MOSD (MOSD_MOVSTO_MOST, MOSD_RENGLON_MOSD, MOSD_ORIGEN, MOSD_SUBORIGEN_VAR,
    MOSD_DEPOSITO, MOSD_ARTICULO, MOSD_SIGNO, MOSD_MOD_STOCK, MOSD_CANT_ING, MOSD_UNIMED,
    MOSD_CANT_UNISTO, MOSD_FACTOR_UMS, MOSD_TIENE_PEDIDOS, MOSD_CREA_PARTIDAS, MOSD_TIENE_OC,
    MOSD_TIENE_REG_PPP, MOSD_TIENE_PPP_PAR)
VALUES (@movS, 1, 2, 0, {dep_origen}, {articulo}, 'S', 1, {cantidad}, 'UN', {cantidad}, 1, 0, 0, 0, 0, 0);
INSERT INTO STOC_MOST (MOST_MOVSTO_MOST, MOST_ORIGEN, MOST_SUBORIGEN_VAR, MOST_FECHA_EMI,
    MOST_DIVISION, MOST_SUCURSAL_IMP, MOST_SUCURSAL_EMP, MOST_SUJETO, MOST_SUJETO_GLOBAL,
    MOST_TIENE_ASIENTO, MOST_DESCRIPCION)
VALUES (@movE, 3, 0, {fecha}, {ctx.division}, {ctx.sucursal_imp}, {ctx.sucursal_emp}, 0, 0, 0, {lit(comentario)});
INSERT INTO STOC_MOSD (MOSD_MOVSTO_MOST, MOSD_RENGLON_MOSD, MOSD_ORIGEN, MOSD_SUBORIGEN_VAR,
    MOSD_DEPOSITO, MOSD_ARTICULO, MOSD_SIGNO, MOSD_MOD_STOCK, MOSD_CANT_ING, MOSD_UNIMED,
    MOSD_CANT_UNISTO, MOSD_FACTOR_UMS, MOSD_TIENE_PEDIDOS, MOSD_CREA_PARTIDAS, MOSD_TIENE_OC,
    MOSD_TIENE_REG_PPP, MOSD_TIENE_PPP_PAR)
VALUES (@movE, 1, 3, 0, {dep_destino}, {articulo}, 'E', 1, {cantidad}, 'UN', {cantidad}, 1, 0, 0, 0, 0, 0);
""")
    partes.append(f"""
INSERT INTO STOC_TRSS (TRSS_DIVISION_TRSS, TRSS_SUCURSAL_TRSS, TRSS_TIPO_TRSS, TRSS_NUMERO_TRSS,
    TRSS_FECHA_EMI, TRSS_DEPOSITO, TRSS_INF_TABASTO, TRSS_ES_TRANSITO, TRSS_TIPO_TRANSITO, TRSS_ES_DEVOL_PEDIDO)
VALUES ({ctx.division}, {ctx.sucursal_imp}, 'TRS', @numTRS, {fecha}, {dep_origen}, 0, 0, 1, 0);
INSERT INTO STOC_TRES (TRES_DIVISION_TRES, TRES_SUCURSAL_TRES, TRES_TIPO_TRES, TRES_NUMERO_TRES,
    TRES_FECHA_EMI, TRES_DEPOSITO, TRES_DIVISION_TRSS, TRES_SUCURSAL_TRSS, TRES_TIPO_TRSS, TRES_NUMERO_TRSS,
    TRES_PESO_EMBALADO, TRES_CANT_BULTOS, TRES_ES_TRANSITO, TRES_TIPO_TRANSITO, TRES_INGRESO_ART_TC,
    TRES_PESO_EMB_CAL, TRES_VOLUMEN_EMB_CAL, TRES_VOLUMEN_EMB_AJ)
VALUES ({ctx.division}, {ctx.sucursal_imp}, 'TRE', @numTRE, {fecha}, {dep_destino}, {ctx.division}, {ctx.sucursal_imp},
    'TRS', @numTRS, 0, 0, 0, 1, 0, 0, 0, 0);
INSERT INTO STOC_MSTS (MSTS_MOVSTO_MOST, MSTS_DIVISION_TRSS, MSTS_SUCURSAL_TRSS, MSTS_TIPO_TRSS, MSTS_NUMERO_TRSS)
VALUES (@movS, {ctx.division}, {ctx.sucursal_imp}, 'TRS', @numTRS);
INSERT INTO STOC_MSTE (MSTE_MOVSTO_MOST, MSTE_DIVISION_TRES, MSTE_SUCURSAL_TRES, MSTE_TIPO_TRES,
    MSTE_NUMERO_TRES, MSTE_MOVSTO_MSTS)
VALUES (@movE, {ctx.division}, {ctx.sucursal_imp}, 'TRE', @numTRE, @movS);
""")
    if partida is not None:
        partes.append(_sdpp_salida(articulo, dep_origen, cantidad, partida))
        partes.append(f"""
INSERT INTO STOC_MOSP (MOSP_MOVSTO_MOST, MOSP_RENGLON_MOSD, MOSP_PARTIDA, MOSP_CANT_ING, MOSP_CANT_UNISTO, MOSP_FACTOR_UMS)
VALUES (@movS, 1, {partida}, {cantidad}, {cantidad}, 1);
""")
        partes.append(_sdpp_entrada(articulo, dep_destino, cantidad, partida, '@movE'))
        partes.append(_verificacion_partida(articulo, dep_origen, partida))
        partes.append(_verificacion_partida(articulo, dep_destino, partida))
    partes.append(_agregado_articulo(articulo, dep_origen, cantidad, '-'))
    partes.append(_agregado_articulo(articulo, dep_destino, cantidad, '+'))
    partes.append('COMMIT TRANSACTION;')
    partes.append('SELECT @movS AS movimiento_salida, @movE AS movimiento_entrada, '
                  '@numTRS AS numero_transferencia, @numTRS AS numero;')
    partes.append("""
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
""")
    return '\n'.join(partes)


# ============================================================
# ANULACION DE UN MOVIMIENTO
# ============================================================


# ============================================================
# ANULACION DE MOVIMIENTOS
# ============================================================

def _anulacion_libros():
    """Libros del comprobante de stock (MSVA/MSMV, y MSTS/MSTE + TRES/TRSS si es
    una transferencia) SOLO para los movimientos que quedan sin renglones
    (@borrables), en el orden que exigen las FK:
    MSTE -> MSTS -> MSMV -> MSVA -> TRES/TRSS -> MOSS."""
    return f"""
-- 1. MSTE (entrada de una transferencia)
DECLARE @tres TABLE (div INT, suc INT, tipo VARCHAR(10), num DECIMAL(18,0), PRIMARY KEY (div, suc, tipo, num));
INSERT INTO @tres (div, suc, tipo, num)
SELECT DISTINCT e.MSTE_DIVISION_TRES, e.MSTE_SUCURSAL_TRES, e.MSTE_TIPO_TRES, e.MSTE_NUMERO_TRES
  FROM STOC_MSTE e JOIN @borrables b ON b.mov = e.MSTE_MOVSTO_MOST;
IF EXISTS (SELECT 1 FROM @tres)
BEGIN
    DELETE e FROM STOC_MSTE e JOIN @borrables b ON b.mov = e.MSTE_MOVSTO_MOST;
    IF @@ROWCOUNT = 0
        RAISERROR('{PREFIJO_INT}MSTE|No se pudo borrar el detalle de la transferencia de entrada.', 16, 1);
END
-- 2. MSTS (salida de una transferencia; MSTE la referencia, por eso va despues)
DECLARE @trss TABLE (div INT, suc INT, tipo VARCHAR(10), num DECIMAL(18,0), PRIMARY KEY (div, suc, tipo, num));
INSERT INTO @trss (div, suc, tipo, num)
SELECT DISTINCT s.MSTS_DIVISION_TRSS, s.MSTS_SUCURSAL_TRSS, s.MSTS_TIPO_TRSS, s.MSTS_NUMERO_TRSS
  FROM STOC_MSTS s JOIN @borrables b ON b.mov = s.MSTS_MOVSTO_MOST;
IF EXISTS (SELECT 1 FROM @trss)
BEGIN
    DELETE s FROM STOC_MSTS s JOIN @borrables b ON b.mov = s.MSTS_MOVSTO_MOST;
    IF @@ROWCOUNT = 0
        RAISERROR('{PREFIJO_INT}MSTS|No se pudo borrar el detalle de la transferencia de salida.', 16, 1);
END
-- 3. MSMV (comprobante de stock del movimiento)
DECLARE @msva TABLE (div INT, suc INT, tipo VARCHAR(10), num DECIMAL(18,0), PRIMARY KEY (div, suc, tipo, num));
INSERT INTO @msva (div, suc, tipo, num)
SELECT DISTINCT v.MSMV_DIVISION_MSVA, v.MSMV_SUCURSAL_MSVA, v.MSMV_TIPO_MSVA, v.MSMV_NUMERO_MSVA
  FROM STOC_MSMV v JOIN @borrables b ON b.mov = v.MSMV_MOVSTO_MOST;
IF EXISTS (SELECT 1 FROM @msva)
BEGIN
    DELETE v FROM STOC_MSMV v JOIN @borrables b ON b.mov = v.MSMV_MOVSTO_MOST;
    IF @@ROWCOUNT = 0
        RAISERROR('{PREFIJO_INT}MSMV|No se pudo borrar el movimiento del comprobante de stock.', 16, 1);
END
-- 4. MSVA (solo si ya no queda ningun MSMV de ese comprobante)
DELETE a FROM STOC_MSVA a JOIN @msva k
   ON a.MSVA_DIVISION_MSVA = k.div AND a.MSVA_SUCURSAL_MSVA = k.suc
  AND a.MSVA_TIPO_MSVA = k.tipo AND a.MSVA_NUMERO_MSVA = k.num
 WHERE NOT EXISTS (SELECT 1 FROM STOC_MSMV v
                   WHERE v.MSMV_DIVISION_MSVA = k.div AND v.MSMV_SUCURSAL_MSVA = k.suc
                     AND v.MSMV_TIPO_MSVA = k.tipo AND v.MSMV_NUMERO_MSVA = k.num);
-- 5. TRES / TRSS (transferencia, solo si ya no queda ningun MSTE/MSTS de ese comprobante)
DELETE r FROM STOC_TRES r JOIN @tres k
   ON r.TRES_DIVISION_TRES = k.div AND r.TRES_SUCURSAL_TRES = k.suc
  AND r.TRES_TIPO_TRES = k.tipo AND r.TRES_NUMERO_TRES = k.num
 WHERE NOT EXISTS (SELECT 1 FROM STOC_MSTE e
                   WHERE e.MSTE_DIVISION_TRES = k.div AND e.MSTE_SUCURSAL_TRES = k.suc
                     AND e.MSTE_TIPO_TRES = k.tipo AND e.MSTE_NUMERO_TRES = k.num);
DELETE s FROM STOC_TRSS s JOIN @trss k
   ON s.TRSS_DIVISION_TRSS = k.div AND s.TRSS_SUCURSAL_TRSS = k.suc
  AND s.TRSS_TIPO_TRSS = k.tipo AND s.TRSS_NUMERO_TRSS = k.num
 WHERE NOT EXISTS (SELECT 1 FROM STOC_MSTS s2
                   WHERE s2.MSTS_DIVISION_TRSS = k.div AND s2.MSTS_SUCURSAL_TRSS = k.suc
                     AND s2.MSTS_TIPO_TRSS = k.tipo AND s2.MSTS_NUMERO_TRSS = k.num);
-- 6. MOSS (si existiera para ese movimiento)
IF EXISTS (SELECT 1 FROM STOC_MOSS x JOIN @borrables b ON b.mov = x.MOSS_MOVSTO_MOST)
BEGIN
    DELETE x FROM STOC_MOSS x JOIN @borrables b ON b.mov = x.MOSS_MOVSTO_MOST;
    IF @@ROWCOUNT = 0
        RAISERROR('{PREFIJO_INT}MOSS|No se pudo borrar el movimiento del libro de stock.', 16, 1);
END
"""


def sql_anulacion(ctx, movimiento, renglon=None, motivo=''):
    """Anula un renglon, o el comprobante completo si no viene `renglon`.

    Diagnostico previo (no toca nada si no es hoja): el renglon existe, no viene
    de un comprobante de compra (FMR), ningun renglon tiene mas de una partida y
    la partida no fue consumida por OTRA salida (de cualquier fecha). Si el
    movimiento es una transferencia se anula el par completo: nunca queda media
    transferencia (por eso un renglon explicito de una transferencia se rechaza).

    El SELECT final devuelve UNA FILA POR RENGLON ANULADO (movimiento, renglon,
    articulo, deposito, signo, cantidad, partida y los valores PREVIOS de
    STDP_STOCK_ACT y SDPP_STOCK_ACT) mas el motivo: es lo que el endpoint guarda
    en la auditoria para poder reconstruir lo anulado."""
    mov = validar_entero(movimiento, 'movimiento')
    por_renglon = renglon not in (None, '')
    ren = validar_entero(renglon, 'renglon') if por_renglon else None
    motivo = validar_texto(motivo, 'motivo', COMENTARIO_MAX)
    if por_renglon:
        chequeo_existencia = f"SELECT 1 FROM STOC_MOSD WHERE MOSD_MOVSTO_MOST = {mov} AND MOSD_RENGLON_MOSD = {ren}"
        carga_renglones = f"INSERT INTO @a (mov, ren) VALUES ({mov}, {ren});"
        texto_movimiento = f"El movimiento {mov} renglon {ren} no existe."
        # Una transferencia se anula entera (las dos patas y sus libros): pedir
        # un renglon explicito de una pata dejaria la otra a medias.
        guarda_renglon_transferencia = f"""
IF EXISTS (SELECT 1 FROM STOC_MSTS WHERE MSTS_MOVSTO_MOST = {mov})
   OR EXISTS (SELECT 1 FROM STOC_MSTE WHERE MSTE_MOVSTO_MOST = {mov})
   OR EXISTS (SELECT 1 FROM STOC_MOST WHERE MOST_MOVSTO_MOST = {mov} AND MOST_ORIGEN IN (2, 3))
    RAISERROR('{PREFIJO_VAL}ANULAR_TRANSFERENCIA|Para anular una transferencia, anula el comprobante completo (sin indicar renglon).', 16, 1);
"""
    else:
        chequeo_existencia = f"SELECT 1 FROM STOC_MOSD WHERE MOSD_MOVSTO_MOST = {mov}"
        carga_renglones = (f"INSERT INTO @a (mov, ren)\n"
                           f"SELECT MOSD_MOVSTO_MOST, MOSD_RENGLON_MOSD FROM STOC_MOSD WHERE MOSD_MOVSTO_MOST = {mov};")
        texto_movimiento = f"El movimiento {mov} no tiene renglones."
        guarda_renglon_transferencia = ''
    return f"""
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;
BEGIN TRY;
IF NOT EXISTS ({chequeo_existencia})
    RAISERROR('{PREFIJO_VAL}MOV_NO_EXISTE|{texto_movimiento}', 16, 1);
-- Renglones a anular: el pedido, o todos los del comprobante.
DECLARE @a TABLE (mov INT NOT NULL, ren INT NOT NULL, PRIMARY KEY (mov, ren));
{carga_renglones}{guarda_renglon_transferencia}-- Una transferencia se anula completa (las dos patas).
DECLARE @movPar INT = NULL;
IF EXISTS (SELECT 1 FROM STOC_MSTS WHERE MSTS_MOVSTO_MOST = {mov})
   OR EXISTS (SELECT 1 FROM STOC_MSTE WHERE MSTE_MOVSTO_MOST = {mov})
   OR EXISTS (SELECT 1 FROM STOC_MOST WHERE MOST_MOVSTO_MOST = {mov} AND MOST_ORIGEN IN (2, 3))
BEGIN
    -- si {mov} es la salida, la entrada es la que la referencia
    SELECT @movPar = MSTE_MOVSTO_MOST FROM STOC_MSTE WHERE MSTE_MOVSTO_MSTS = {mov};
    -- si {mov} es la entrada, la salida es la referenciada
    IF @movPar IS NULL
        SELECT @movPar = MSTE_MOVSTO_MSTS FROM STOC_MSTE WHERE MSTE_MOVSTO_MOST = {mov};
END
IF @movPar IS NOT NULL
BEGIN
    INSERT INTO @a (mov, ren)
    SELECT m.MOSD_MOVSTO_MOST, m.MOSD_RENGLON_MOSD FROM STOC_MOSD m
     WHERE m.MOSD_MOVSTO_MOST = @movPar
       AND NOT EXISTS (SELECT 1 FROM @a a WHERE a.mov = m.MOSD_MOVSTO_MOST AND a.ren = m.MOSD_RENGLON_MOSD);
    IF NOT EXISTS (SELECT 1 FROM @a a WHERE a.mov = @movPar)
        RAISERROR('{PREFIJO_VAL}MOV_NO_EXISTE|La otra pata de la transferencia (movimiento %d) no tiene renglones.', 16, 1, @movPar);
END
IF NOT EXISTS (SELECT 1 FROM @a)
    RAISERROR('{PREFIJO_VAL}MOV_NO_EXISTE|{texto_movimiento}', 16, 1);
DECLARE @movs TABLE (mov INT NOT NULL PRIMARY KEY);
INSERT INTO @movs (mov) SELECT DISTINCT mov FROM @a;
DECLARE @pares TABLE (art INT NOT NULL, dep INT NOT NULL, PRIMARY KEY (art, dep));
INSERT INTO @pares (art, dep)
SELECT DISTINCT m.MOSD_ARTICULO, m.MOSD_DEPOSITO FROM STOC_MOSD m
 JOIN @a a ON a.mov = m.MOSD_MOVSTO_MOST AND a.ren = m.MOSD_RENGLON_MOSD;
DECLARE @partidas TABLE (part INT NOT NULL PRIMARY KEY);
INSERT INTO @partidas (part)
SELECT DISTINCT p.MOSP_PARTIDA FROM STOC_MOSP p
 JOIN @a a ON a.mov = p.MOSP_MOVSTO_MOST AND a.ren = p.MOSP_RENGLON_MOSD;

-- ==== Diagnostico previo: si algo no es hoja, no se toca nada ====
IF EXISTS (SELECT 1 FROM COMP_MCRF c JOIN @a a ON a.mov = c.MCRF_MOVSTO_MOST AND a.ren = c.MCRF_RENGLON_MOSD)
    RAISERROR('{PREFIJO_VAL}MOV_FMR|El movimiento viene de un comprobante de compra (FMR): anulalo desde Cuentas a Pagar.', 16, 1);
-- Un renglon con dos partidas distintas no se revierte a medias: se rechaza.
IF EXISTS (
    SELECT 1 FROM STOC_MOSP p JOIN @a a ON a.mov = p.MOSP_MOVSTO_MOST AND a.ren = p.MOSP_RENGLON_MOSD
     GROUP BY p.MOSP_MOVSTO_MOST, p.MOSP_RENGLON_MOSD HAVING COUNT(DISTINCT p.MOSP_PARTIDA) > 1)
    RAISERROR('{PREFIJO_VAL}ANULAR_MULTIPARTIDA|El movimiento tiene mas de una partida en el mismo renglon: no se puede anular por este circuito.', 16, 1);
-- Consumida: bloquea si OTRA salida de esa partida ya saco stock, de CUALQUIER
-- fecha (MOST_FECHA_EMI es date y "posterior" es indecidible: antes una salida
-- del mismo dia no bloqueaba la anulacion de la entrada). Se excluyen los
-- movimientos que se estan anulando (los de @a).
IF EXISTS (
    SELECT 1 FROM STOC_MOSP p
    JOIN @a a ON a.mov = p.MOSP_MOVSTO_MOST AND a.ren = p.MOSP_RENGLON_MOSD
    JOIN STOC_MOSP p2 ON p2.MOSP_PARTIDA = p.MOSP_PARTIDA
    JOIN STOC_MOSD m2 ON m2.MOSD_MOVSTO_MOST = p2.MOSP_MOVSTO_MOST
                     AND m2.MOSD_RENGLON_MOSD = p2.MOSP_RENGLON_MOSD
                     AND m2.MOSD_SIGNO = 'S'
    WHERE NOT EXISTS (SELECT 1 FROM @a x WHERE x.mov = m2.MOSD_MOVSTO_MOST))
    RAISERROR('{PREFIJO_VAL}CONSUMIDO|La partida de este movimiento ya fue usada por otra salida: no se puede anular.', 16, 1);

-- ==== Libros del comprobante: solo si queda sin renglones ====
DECLARE @borrables TABLE (mov INT NOT NULL PRIMARY KEY);
INSERT INTO @borrables (mov)
SELECT v.mov FROM @movs v
 WHERE NOT EXISTS (SELECT 1 FROM STOC_MOSD m
                   WHERE m.MOSD_MOVSTO_MOST = v.mov
                     AND NOT EXISTS (SELECT 1 FROM @a a WHERE a.mov = m.MOSD_MOVSTO_MOST AND a.ren = m.MOSD_RENGLON_MOSD));
{_anulacion_libros()}
-- ==== Reversion por renglon (incremental, con las banderas del ERP) ====
DECLARE @movA INT, @renA INT, @cant DECIMAL(18,4), @delta DECIMAL(18,4), @signo VARCHAR(1),
        @art INT, @dep INT, @part INT, @stdp_previo DECIMAL(18,4), @sdpp_previo DECIMAL(18,4);
-- Datos de cada renglon anulado, con los valores PREVIOS de stock: es lo que
-- devuelve el SELECT final para la auditoria (reconstruir lo anulado).
DECLARE @filas_anuladas TABLE (mov INT NOT NULL, ren INT NOT NULL, art INT NOT NULL,
        dep INT NOT NULL, signo VARCHAR(1) NOT NULL, cant DECIMAL(18,4) NOT NULL,
        part INT NULL, stdp_previo DECIMAL(18,4) NULL, sdpp_previo DECIMAL(18,4) NULL,
        PRIMARY KEY (mov, ren));
WHILE EXISTS (SELECT 1 FROM @a)
BEGIN
    SELECT TOP 1 @movA = mov, @renA = ren FROM @a ORDER BY mov, ren;
    SELECT @cant = MOSD_CANT_UNISTO, @signo = MOSD_SIGNO, @art = MOSD_ARTICULO, @dep = MOSD_DEPOSITO
      FROM STOC_MOSD WHERE MOSD_MOVSTO_MOST = @movA AND MOSD_RENGLON_MOSD = @renA;
    SET @part = NULL;
    SELECT @part = MOSP_PARTIDA FROM STOC_MOSP WHERE MOSP_MOVSTO_MOST = @movA AND MOSP_RENGLON_MOSD = @renA;
    SET @delta = CASE @signo WHEN 'E' THEN -@cant ELSE @cant END;
    -- Valores PREVIOS, antes de tocar nada de este renglon.
    SET @stdp_previo = NULL;
    SET @sdpp_previo = NULL;
    SELECT @stdp_previo = STDP_STOCK_ACT FROM STOC_STDP
     WHERE STDP_ARTICULO = @art AND STDP_DEPOSITO = @dep;
    IF @part IS NOT NULL
        SELECT @sdpp_previo = SDPP_STOCK_ACT FROM STOC_SDPP
         WHERE SDPP_ARTICULO = @art AND SDPP_DEPOSITO = @dep AND SDPP_PARTIDA = @part;
    INSERT INTO @filas_anuladas (mov, ren, art, dep, signo, cant, part, stdp_previo, sdpp_previo)
    VALUES (@movA, @renA, @art, @dep, @signo, @cant, @part, @stdp_previo, @sdpp_previo);
    IF @part IS NOT NULL
    BEGIN
        DELETE FROM STOC_MOSP WHERE MOSP_MOVSTO_MOST = @movA AND MOSP_RENGLON_MOSD = @renA;
        IF @@ROWCOUNT = 0
            RAISERROR('{PREFIJO_INT}MOSP|No se pudo borrar el renglon de partida del movimiento %d.', 16, 1, @movA);
    END
    DELETE FROM STOC_MOSD WHERE MOSD_MOVSTO_MOST = @movA AND MOSD_RENGLON_MOSD = @renA;
    IF @@ROWCOUNT = 0
        RAISERROR('{PREFIJO_INT}MOSD|No se pudo borrar el movimiento %d renglon %d.', 16, 1, @movA, @renA);
    IF @part IS NOT NULL
    BEGIN
        -- Igual que el agregado: si la reversion fuera a dejar la partida en
        -- negativo y el articulo controla stock y el deposito no admite
        -- negativos, se aborta.
        UPDATE STOC_SDPP SET SDPP_STOCK_ACT = SDPP_STOCK_ACT + @delta
         WHERE SDPP_ARTICULO = @art AND SDPP_DEPOSITO = @dep AND SDPP_PARTIDA = @part
           AND ( @delta >= 0
                 OR ISNULL((SELECT ARTS_CONTROL_STOCK FROM STOC_ARTS WHERE ARTS_ARTICULO = @art), 0) = 0
                 OR ISNULL((SELECT DPOS_CTRL_STOCKNEG FROM STOC_DPOS WHERE DPOS_DEPOSITO = @dep), 0) <> 1
                 OR SDPP_STOCK_ACT + @delta >= 0 );
        IF @@ROWCOUNT = 0
        BEGIN
            IF EXISTS (SELECT 1 FROM STOC_SDPP WHERE SDPP_ARTICULO = @art AND SDPP_DEPOSITO = @dep AND SDPP_PARTIDA = @part)
                RAISERROR('{PREFIJO_VAL}STOCK|Anular dejaria el stock de la partida %d en negativo.', 16, 1, @part);
            ELSE
                RAISERROR('{PREFIJO_INT}SDPP_SIN_FILA|No existe el stock de la partida que hay que revertir.', 16, 1);
        END
        IF NOT EXISTS (SELECT 1 FROM STOC_SDPP WHERE SDPP_PARTIDA = @part)
           AND NOT EXISTS (SELECT 1 FROM STOC_MOSP WHERE MOSP_PARTIDA = @part)
            DELETE FROM STOC_PART WHERE PART_PARTIDA = @part;
    END
    UPDATE STOC_STDP SET STDP_STOCK_ACT = STDP_STOCK_ACT + @delta
     WHERE STDP_ARTICULO = @art AND STDP_DEPOSITO = @dep
       AND ( @delta >= 0
             OR ISNULL((SELECT ARTS_CONTROL_STOCK FROM STOC_ARTS WHERE ARTS_ARTICULO = @art), 0) = 0
             OR ISNULL((SELECT DPOS_CTRL_STOCKNEG FROM STOC_DPOS WHERE DPOS_DEPOSITO = @dep), 0) <> 1
             OR STDP_STOCK_ACT + @delta >= 0 );
    IF @@ROWCOUNT = 0
    BEGIN
        IF EXISTS (SELECT 1 FROM STOC_STDP WHERE STDP_ARTICULO = @art AND STDP_DEPOSITO = @dep)
            RAISERROR('{PREFIJO_VAL}STOCK|Anular dejaria el agregado del articulo %d en el deposito %d en negativo.', 16, 1, @art, @dep);
        ELSE
            RAISERROR('{PREFIJO_INT}STDP_SIN_FILA|No existe el agregado de stock del articulo %d en el deposito %d.', 16, 1, @art, @dep);
    END
    DELETE FROM @a WHERE mov = @movA AND ren = @renA;
END
-- ==== Comprobantes sin renglones ====
IF NOT EXISTS (SELECT 1 FROM STOC_MOSD WHERE MOSD_MOVSTO_MOST = {mov})
BEGIN
    DELETE FROM STOC_MOST WHERE MOST_MOVSTO_MOST = {mov};
    IF @@ROWCOUNT = 0
        RAISERROR('{PREFIJO_INT}MOST|No se pudo borrar el comprobante {mov}.', 16, 1);
END
IF @movPar IS NOT NULL AND NOT EXISTS (SELECT 1 FROM STOC_MOSD WHERE MOSD_MOVSTO_MOST = @movPar)
BEGIN
    DELETE FROM STOC_MOST WHERE MOST_MOVSTO_MOST = @movPar;
    IF @@ROWCOUNT = 0
        RAISERROR('{PREFIJO_INT}MOST|No se pudo borrar el comprobante de la otra pata de la transferencia.', 16, 1);
END
{verificacion_agregado(desde='@pares p')}{_verificacion_partida(desde='STOC_SDPP p JOIN @partidas x ON x.part = p.SDPP_PARTIDA')}COMMIT TRANSACTION;
-- Una fila por renglon anulado (los valores previos quedaron capturados antes
-- de revertir): el endpoint los guarda en la auditoria.
SELECT {mov} AS movimiento_anulado, {lit(motivo)} AS motivo,
       f.mov AS movimiento, f.ren AS renglon, f.art AS articulo, f.dep AS deposito,
       f.signo AS signo, f.cant AS cantidad, f.part AS partida,
       f.stdp_previo AS stock_previo_agregado, f.sdpp_previo AS stock_previo_partida
  FROM @filas_anuladas f
 ORDER BY f.mov, f.ren;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
"""
