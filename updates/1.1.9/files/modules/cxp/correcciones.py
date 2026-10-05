# modules/cxp/correcciones.py
# ============================================================
# CORRECCIONES DEL OPERADOR EN CxP: que se registra y como
# ============================================================
# El parser propone los campos de cada comprobante y el formulario se prellena con
# eso; el operador corrige lo que vino mal. Esa correccion es la mejor materia prima
# que hay para mejorar la lectura: dice en que campo se equivoco el parser y con que
# texto, sin IA, sin tokens y sin depender de nadie.
#
# Hasta el 03/10/2026 esa correccion se PERDIA: `/parsear_pdf` no audita nada y el
# alta guardaba solo los datos finales del formulario (`modules/cxp/routes.py`).
#
# POR QUE VIVE ACA Y NO EN routes.py:
#   - es stdlib puro (nada de Flask ni de base), asi que se testea sin app y sin SQL
#     (`tests/test_cxp_correcciones.py`), y routes.py ya tiene 767 lineas;
#   - viaja por el canal (`modules/` se publica) porque la app lo ejecuta.
#
# QUE SE REGISTRA: una linea de auditoria `cxp.correccion` por CADA CAMPO corregido,
# con el par (propuesto -> final), un recorte del texto alrededor del valor propuesto
# (para poder reproducir el error sin abrir el PDF) y el resultado del alta. Va por
# `auditar()` al mismo log que los altas, asi que se agrega entre todas las PC.

import re

# Campos que PROPONE el parser (`modules/cxp/campos.py`, `parsear`): son los unicos
# que pueden ser un error de lectura. Lo que decide el operador (centro de costo,
# cuenta contable, descripcion, condicion de pago) no entra: ensuciaria la senal.
CAMPOS_DEL_PARSER = ('tipo', 'moneda', 'total', 'imp_bruto', 'imp_iva',
                     'imp_especial', 'base_imponible', 'tasa_iva', 'fecha',
                     'numero_dte', 'nit_emisor', 'nombre_emisor',
                     'descripcion_auto')

# Topes defensivos: el cuerpo lo arma el navegador y no puede hacer crecer el log.
LARGO_VALOR = 120
LARGO_TEXTO = 4000
ANCHO_RECORTE = 200


def _texto(valor, largo=LARGO_VALOR):
    """Valor del parser o del formulario -> texto limpio y acotado.

    `None` es cadena vacia a proposito: "el parser no encontro el campo y el operador
    lo escribio" es una correccion (de las mas utiles), no un caso a descartar.
    """
    if valor is None:
        return ''
    return str(valor).strip()[:largo]


def validas(correcciones):
    """Solo lo que es una correccion de verdad: campo del parser y valor distinto.

    Estricto con la forma (un cliente raro no puede tumbar el alta) y con la
    igualdad: compara TEXTO, sin normalizar numeros. El frontend es el que sabe como
    se prelleno cada campo, asi que manda el par solo cuando de verdad cambio; esto
    es la guarda del servidor.
    """
    if not isinstance(correcciones, dict):
        return {}
    limpias = {}
    # `key=str`: las claves de un JSON siempre son texto, pero la funcion es publica
    # y con una clave de otro tipo `sorted` levantaria TypeError (y el alta se cae).
    for campo in sorted(correcciones, key=str):
        if campo not in CAMPOS_DEL_PARSER:
            continue
        par = correcciones[campo]
        if not isinstance(par, dict):
            continue
        propuesto = _texto(par.get('propuesto'))
        final = _texto(par.get('final'))
        if propuesto == final:
            continue
        limpias[campo] = {'propuesto': propuesto, 'final': final}
    return limpias


def recorte(texto, valor, ancho=ANCHO_RECORTE, etiquetas=()):
    """El tramo del texto alrededor de `valor` (o '' si no aparece).

    MEDIDO el 03/10/2026 en pantalla: buscar el valor LITERAL no alcanzaba. El parser
    guarda valores NORMALIZADOS (`2026-08-28`, `10500.00`) y el papel imprime otra
    forma (`28/08/2026`, `10,500.00`), asi que el recorte salia vacio justo en fecha y
    montos. Ahora se prueban variantes del mismo dato y, si ninguna aparece, se ubica
    la ETIQUETA del campo (`TOTAL`, `FECHA`, ...) y se devuelve la ventana desde ahi.

    Sigue siendo una APROXIMACION declarada: es la primera aparicion, asi que si el
    dato figura dos veces el recorte puede ser del lugar equivocado. Alcanza para
    reproducir el error; no lo afirma.
    """
    cuerpo = _texto(texto, LARGO_TEXTO)
    if not cuerpo:
        return ''
    for forma in _variantes(valor):
        recorte = _ventana(cuerpo, forma, ancho)
        if recorte:
            return recorte
    for etiqueta in etiquetas:
        recorte = _ventana(cuerpo, etiqueta, ancho)
        if recorte:
            return recorte
    return ''


# Etiquetas con las que el papel suele anunciar cada campo: ultimo recurso del
# recorte cuando el valor no aparece en ninguna de sus formas (ver `recorte`).
ETIQUETAS = {
    'total': ('TOTAL', 'Total a pagar', 'IMPORTE TOTAL'),
    'fecha': ('FECHA', 'Fecha de emision', 'FECHA DE EMISION'),
    'numero_dte': ('DTE', 'NUMERO', 'No.', 'SERIE'),
    'nit_emisor': ('NIT',),
    'nombre_emisor': ('NOMBRE', 'RAZON SOCIAL', 'NOMBRE COMERCIAL'),
    'imp_iva': ('IVA', 'IVA 12'),
    'imp_especial': ('IDP', 'TURISMO', 'IMPUESTO'),
    'moneda': ('MONEDA', 'QUETZALES', 'DOLARES'),
}


def _ventana(cuerpo, buscado, ancho):
    """El tramo de ±`ancho` alrededor de la primera aparicion (o '' si no esta)."""
    buscado = _texto(buscado)
    if not buscado:
        return ''
    pos = cuerpo.find(buscado)
    if pos < 0:
        return ''
    inicio = max(0, pos - ancho)
    fin = min(len(cuerpo), pos + len(buscado) + ancho)
    return cuerpo[inicio:fin].strip()


def _variantes(valor):
    """Las formas en que el MISMO dato puede estar impreso en el papel.

    El parser normaliza (`2026-08-28`, `10500.00`) y el comprobante imprime distinto:
    esta funcion genera las variantes razonables para poder ubicarlo en el texto.
    """
    original = _texto(valor)
    if not original:
        return []
    formas = [original]
    sin_miles = original.replace(',', '')
    if sin_miles != original:
        formas.append(sin_miles)
    if '.' in original:
        formas.append(original.replace('.', ','))
    if ',' in original and '.' not in original:
        formas.append(original.replace(',', '.'))
    # Los miles: el parser guarda `10500.00` y el papel imprime `10,500.00` (la forma
    # normal en Guatemala). Sin esta variante el monto impreso no se encontraba y el
    # recorte caia a la etiqueta aunque el dato estuviera a la vista. Solo para valores
    # CON decimales (los importes del formulario llevan `toFixed(2)`): un `numero_dte` de
    # 4 digitos no tiene que generar `1,000`, que haria que el recorte apunte a un monto
    # del papel en vez de a la etiqueta de su campo.
    miles = _con_miles(original) if '.' in original else ''
    if miles:
        formas.append(miles)
    partes = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', original)
    if partes:
        dia, mes, anio = partes.group(3), partes.group(2), partes.group(1)
        formas += [f'{dia}/{mes}/{anio}', f'{dia}-{mes}-{anio}']
    return [forma for forma in dict.fromkeys(formas) if forma]


def _con_miles(numero):
    """`10500.00` -> `10,500.00`; '' si la parte entera no es un numero o tiene <= 3 digitos.

    Solo se toca la PARTE ENTERA: los decimales no llevan separador de miles. El punto
    es el separador decimal del parser (el frontend manda `toFixed(2)`), asi que un
    valor con coma decimal no entra aca: de eso se ocupan las otras variantes.
    """
    entero, punto, decimales = numero.partition('.')
    if not entero.isdigit() or len(entero) <= 3:
        return ''
    grupos = []
    resto = entero
    while len(resto) > 3:
        grupos.insert(0, resto[-3:])
        resto = resto[:-3]
    grupos.insert(0, resto)
    return ','.join(grupos) + (punto + decimales if punto else '')


def _contexto(contexto):
    """Contexto del evento: quien, donde y de que comprobante salio la correccion."""
    contexto = contexto if isinstance(contexto, dict) else {}
    limpio = {}
    for clave in ('usuario', 'base', 'division', 'archivo', 'pagina', 'numero_dte'):
        valor = contexto.get(clave)
        limpio[clave] = '' if valor is None else valor
    limpio['archivo'] = _texto(limpio['archivo'])
    limpio['numero_dte'] = _texto(limpio['numero_dte'])
    return limpio


def eventos(correcciones, contexto, texto, estado, codigo=None):
    """Una linea `cxp.correccion` por campo corregido (lista, puede venir vacia).

    `estado` es el resultado del alta (`aplicada`/`rechazada`/`fallida`): un alta
    rechazada tambien dice algo y se puede filtrar al leer. `codigo` viaja cuando el
    rechazo trae uno (CXP_VAL_*).
    """
    salida = []
    for campo, par in validas(correcciones).items():
        evento = {'evento': 'cxp.correccion', **_contexto(contexto), 'campo': campo,
                  'propuesto': par['propuesto'], 'final': par['final'],
                  'recorte': recorte(texto, par['propuesto'],
                                     etiquetas=ETIQUETAS.get(campo, ())),
                  'estado': estado}
        if codigo:
            evento['codigo'] = codigo
        salida.append(evento)
    return salida
