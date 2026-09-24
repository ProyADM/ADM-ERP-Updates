# modules/cxp/campos.py
# ============================================================
# LECTURA DE CAMPOS DE UNA FACTURA FEL GUATEMALTECA, DESDE EL TEXTO
# ============================================================
# Solo stdlib: se puede testear con los textos reales de las rendiciones sin
# `config`, sin pdfplumber y sin tesseract (por eso vive aca y no en parser.py).
import re
from datetime import date

# ------------------------------------------------------------
# Importes
# ------------------------------------------------------------
# El corpus mezcla '150.00', '12,29', '4,86', '1,024.800' y '3,61'. Reglas:
#  · con los DOS separadores, el ULTIMO es el decimal ('1,024.800' = 1024,80);
#  · con UNO solo: 3 digitos detras = miles ('1,024' = 1024), el resto = decimal
#    ('12,29' = 12,29 y '3,61' = 3,61). Los importes de Q de estas facturas son
#    chicos, asi que una coma con dos decimales es decimal, nunca miles.
RX_IMPORTE = re.compile(r'\d[\d.,]*')


def importe(texto):
    """Importe en formato local -> float, o None si no hay numero."""
    t = re.sub(r'[^\d.,]', '', str(texto)).strip('.')
    if not t or not re.search(r'\d', t):
        return None
    if '.' in t and ',' in t:
        if t.rfind(',') > t.rfind('.'):
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
    elif ',' in t:
        entero, _, decimales = t.rpartition(',')
        t = (entero + decimales) if len(decimales) == 3 else (entero + '.' + decimales)
    try:
        return float(t)
    except ValueError:
        return None


# ------------------------------------------------------------
# Total
# ------------------------------------------------------------
# SOLO la misma linea (el grupo es `[^\n]*`, que no cruza el salto de linea y por
# eso no agarra el TOTAL del encabezado de la tabla con la cantidad de la linea
# siguiente), y se toma el ULTIMO importe de la linea: en las formas FEL la fila
# de totales trae varias columnas ('TOTALES: 0.00 0.00 200.00' -> 200.00). Cuando
# la fila trae letras despues de las columnas hay que cortar antes (ver `total()`).
# `TOTAL IMPUESTO` queda excluido a proposito: es la suma de impuestos, no el total.
#
# Dos trampas del OCR real, que obligan a NO usar `^` ni `\b`:
#  · la etiqueta viene pegada a la moneda y precedida de ruido en la misma linea
#    ('nn TOTALQ 200.00', pagina 10 de marzo), asi que `\b` la descartaria;
#  · pero sin `\b` entraria cualquier palabra que empiece con TOTAL. Por eso el
#    importe tiene que empezar a lo sumo 12 caracteres despues de la etiqueta.
# El 12 es el maximo seguro medido sobre el corpus, no un punto medio:
#  · el minimo real es 10 ('TOTAL A PAGAR: 50.00', 2026-05-1q-p03, el digito justo
#    en el 10) y 11 ('TOTAL FACTURA Q 1,393.00', fc-claro-p01: con 10 se pierde el
#    total real y `total()` devuelve None);
#  · el primer falso positivo entra a los 13 ('TOTALMENTE PAGADO 100.00') y hay
#    otro a los 14 ('Total de impuestos 109.800'), asi que subir la ventana a 13 o
#    mas rompe: 12 es el techo, no el piso.
# Con 12 quedan dentro las formas reales ('TOTALQ 200.00', 'Total Q 53.00',
# 'TOTALES: 0.00 0.00 200.00') y fuera las que no son total ('TOTALMENTE PAGADO',
# 'TOTAL EN LETRAS: ... CON 00/100', 'Total de impuestos 109.800',
# 'Total lineas 1,024.800' — este ultimo lo lee antes la via del importe en USD).
RX_TOTAL = re.compile(r'(?:SUB[^\S\n]*)?TOTAL(?:ES)?(?!\s*IMPUESTO)(?=[^\n]{0,12}\d)([^\n]*)', re.I)
RX_IMPORTE_TOTAL_USD = re.compile(r'Importe\s+total\s*\((?:USD|QTZ)\)\s*([\d.,]+)', re.I)

# El rotulo del total tambien llega DESTROZADO por el OCR. En 7 de las 57 paginas el
# papel imprime el total en una linea cuyo rotulo no es 'TOTAL' contiguo, asi que la
# via estricta no lo ve y `total()` devolvia None + aviso (0 en el payload: fail-closed,
# pero el operador tipeaba un importe que el papel muestra). Formas medidas:
#   'T O T A Leonnnncnuncnnonas! 46.00'   2026-03-1q-p13
#   'TOTA Liat 43.00'                     2026-07-03-almuerzo-mantenimiento-p01
#   '1 T 10) T A | 56.00'                 2026-07-2q-p06
#   'Fotal: Q 100'                        2026-07-07-bus-a-santa-lucia-p01
#   'T 16) T A 48.00'  /  'Tota 52.00'    2026-07-1q-p03 / 2026-07-1q-p07
#   'Total:' con 'Q 20.00' en la linea siguiente
#                                         2026-07-03-parqueo-mantenimiento-p01
# Las cuatro guardas y la ventana estan medidas con
# `_investigacion_gt/185_medir_rotulo_degradado.py` (paginas que cambian sobre las 57,
# barrido de la ventana 0..400 y pines sinteticos):
#  · `(?<!letra)`: no puede matchear ADENTRO de otra palabra (en SUBTOTAL la 'T' de
#    'TOTA' queda precedida por la 'B'). En el corpus su efecto es m=0: las 7 lineas con
#    SUB TOTAL de las 57 estan en paginas que ya tienen candidato estricto, asi que esta
#    via no corre ahi (se pinea con 'SUBTOTA Q 10.00' y 'COMPUTOTA Q 10.00': con la
#    guarda None, sin ella el subtotal entraria como total).
#  · `(?!TOTAL)`: el rotulo limpio (TOTAL/TOTALES, con o sin SUB) lo lee RX_TOTAL y no
#    se toca (R11/R15). En el corpus su efecto tambien es m=0: la unica pagina sin
#    candidato estricto con una linea de TOTAL contiguo es 2026-03-1q-p05, y ahi el
#    importe esta destrozado ('0.75.00' no es un importe), asi que no hay nada que leer.
#    Lo que la guarda protege es el CONTRATO: sin ella la ventana de 21 se le aplicaria
#    tambien al rotulo limpio y romperia el techo de 12 de R11/R15 (se pinea con
#    'TOTAL DE IMPUESTOS 109.800': con la guarda None, sin ella 109.80).
#  · `(?!letra)`: DEFENSIVA, m=0 en el corpus (lo unico que cambia es la etiqueta de
#    p13, de 'T O T A L' a 'T O T A', con el mismo 46.00). Evita que el rotulo degradado
#    matchee pegado a una palabra (se pinea con 'TOTAX 100.00': con la guarda None, sin
#    ella 100.00).
#  · la ventana de 21: es el MINIMO medido, no un punto medio. Las distancias reales de
#    las 7 lineas son 0, 1, 3, 4, 6 y 21 (p13: el rotulo 'T O T A' y el importe detras de
#    la palabra que el OCR destrozo, 'Leonnnncnuncnnonas!'); con 20 se pierde p13 (m=1) y
#    con 21 no falta ninguna. A diferencia de la ventana estricta (R15: primer falso
#    positivo a los 13), aca el corpus NO tiene ningun falso positivo en NINGUNA ventana:
#    el barrido 0..400 da los mismos candidatos y 0 falsos positivos, o sea que la ventana
#    la fija la necesidad real y no un techo de seguridad (lo que evita los falsos
#    positivos son las guardas del rotulo; la medicion se declara acotada AL CORPUS).
#
# FIX ROUND 1 (Important I1): las guardas tienen que tolerar EL MISMO ESPACIADO que
# tolera el rotulo, o el valor equivocado entra EN SILENCIO. Medido con el patron anterior
# al fix (`185_medir_rotulo_degradado.py`, seccion 7):
#   'SUB TOTA. Q. 16,07'                 -> 16.07 como TOTAL sin aviso (es un subtotal)
#   'SUB TOTA Q 10.00'                   -> 10.00 como TOTAL sin aviso
#   'SUB TOTAL:' + 'Q 16.07'             -> 16.07 como TOTAL sin aviso
#   'T O T A L DE IMPUESTOS 109.800'     -> 109.80 como TOTAL (es la suma de impuestos)
#   'T O T A L IMPUESTO Q 36.07'         -> 36.07 como TOTAL
#   'T O T A L M E N T E PAGADO 100.00'  -> 100.00 como TOTAL (palabra que empieza con TOTAL)
# Las seis son m=0 en las 57, pero el corpus escribe 'SUB TOTAL' con espacio en 6 de sus 7
# lineas de subtotal: la forma real, no la comoda (`SUBTOTA`). Ahora:
#  · el `SUB` se detecta en CODIGO antes del rotulo (`_es_subtotal`): el lookbehind de
#    Python es de ancho FIJO y el OCR mete cualquier cantidad de espacios ('SUB  TOTA'),
#    asi que `(?<!SUB )` no alcanza. El valor va por la via del SUB TOTAL, o sea CON aviso.
#  · la suma de impuestos y la palabra que empieza con TOTAL se rechazan con
#    `_rotulo_ajeno`, ANCLADO al inicio del match: un lookahead pegado al rotulo se esquiva
#    por backtracking (medido: 'T O T A L DE IMPUESTOS' entraba igual por la forma corta
#    'T O T A', porque el lookahead se evaluaba despues de 'T O T A').
#  · lo que SI es un total no se toca: 'TOTAL A PAGAR: 50.00' y 'T O T A L A PAGAR: 50.00'
#    siguen dando 50.00 (una guarda generica tipo `(?!\s*[A-Za-z])` se los comeria).
_ROTULO_TOTAL_DEGRADADO = (
    r'(?:[TF][^\S\n]*O[^\S\n]*T[^\S\n]*A[^\S\n]*L?'    # TOTAL/FOTAL/TOTA y el espaciado del OCR
    r'|T[^\S\n]+A)')                                   # 'T A' con la palabra del medio comida
RX_TOTAL_DEGRADADO = re.compile(
    r'(?<![A-Za-zÁÉÍÓÚáéíóúñÑ])'
    r'(?!(?:SUB[^\S\n]*)?TOTAL(?:ES)?)'
    + _ROTULO_TOTAL_DEGRADADO +
    r'(?![A-Za-zÁÉÍÓÚáéíóúñÑ])'
    r'(?=[^\n]{0,21}\d)([^\n]*)', re.I)
# El rotulo solo, ocupando la linea entera ('Total:' / 'TOTAL:'), con el importe (o los
# importes) en la/las lineas siguientes. El preprocesado (`limpiar_texto_superpuesto`)
# reconstruye algunos de estos casos, pero no el del parqueo: 'Q 20.00' no matchea su
# `^[Q\d\.,]+$` (tiene un espacio adentro) y ademas hay una linea vacia en el medio.
# El rotulo LIMPIO y el DEGRADADO se separan porque la prioridad entre las dos sub-reglas
# del renglon siguiente es una decision propia (fix round 1, M-b): primero el limpio.
RX_TOTAL_LIMPIO_SOLO = re.compile(
    r'^[^\S\n]*(?:SUB[^\S\n]*)?TOTAL(?:ES)?[^\S\n]*[:\-.,]*[^\S\n]*$', re.I)
RX_TOTAL_DEGRADADO_SOLO = re.compile(
    r'^[^\S\n]*(?:SUB[^\S\n]*)?' + _ROTULO_TOTAL_DEGRADADO
    + r'[^\S\n]*[:\-.,]*[^\S\n]*$', re.I)
# La linea del bloque tiene que ser SOLO el importe (con la moneda opcional): es lo que
# acota la regla del renglon siguiente (m=1 pagina en el corpus, el parqueo).
RX_IMPORTE_SOLO = re.compile(r'^[^\S\n]*(?:Q|GTQ|USD|\$)?[^\S\n]*\d[\d.,]*[^\S\n]*$', re.I)
# NORMALIZACION DEL ROTULO (fix round 2 de la Task 9). El fix round 1 toleraba el espaciado
# ENTRE las letras del rotulo, pero no el de ADENTRO de las palabras que lo siguen ni el 0
# por O; enumerar variantes dejaba agujeros de la misma clase (un total equivocado en
# silencio). En vez de enumerar, se normaliza el rotulo y se decide sobre la forma
# normalizada: sin espacios ni separadores ('.', '-', ':', '/', '_') y con 0->O y 1->I, que
# son los dos typos que el corpus ya muestra en otros rotulos ('10P' por 'IDP', 'erédito'
# por 'crédito'). Lo que cambia es SOLO como se decide si el rotulo es subtotal o ajeno: la
# via estricta, la tolerante, la ventana, la precedencia y el bloque del renglon siguiente
# quedan como estaban.
RX_SEPARADOR = re.compile(r'[\s.\-:/_]+')
RX_PLIEGUE = str.maketrans({'0': 'O', '1': 'I'})
# Las formas que NO son el total de la factura, sobre el rotulo NORMALIZADO: la suma de
# impuestos (con o sin 'DE') y una palabra que empieza con TOTAL (con o sin la E que el OCR
# mete de mas: 'T O T A L E M E N T E'). Los legitimos no caen aca (medido en 185, seccion 9:
# 'TOTALAPAGAR', 'TOTALFACTURA', 'TOTALES' y 'TOTAL' no matchean).
RX_AJENO = re.compile(r'^(?:TOTAL(?:DE)?IMPUESTOS?|TOTALE?MENTE)')


def _normalizar(trozo):
    """El rotulo sin espacios ni separadores, con 0->O y 1->I y en mayusculas."""
    return RX_SEPARADOR.sub('', trozo).upper().translate(RX_PLIEGUE)

# Los avisos de la via del total. `AVISO_SUBTOTAL` es el de siempre (R29) y ahora tambien
# lo usa la via degradada; `AVISO_RENGLON_SIGUIENTE` es del fix round 1 (M-a): el importe
# NO esta en la linea del rotulo, asi que el operador lo tiene que revisar. m=1 pagina en
# el corpus (el parqueo): el valor no cambia, si el aviso.
AVISO_SUBTOTAL = 'solo se encontro un SUB TOTAL: revisalo contra el papel'
AVISO_RENGLON_SIGUIENTE = ('el total se leyo en la linea siguiente del rotulo: '
                           'revisalo contra el papel')


def _importe_de_la_cola(cola):
    """El importe de la cola de una linea etiquetada, o None si no hay ninguno.

    Dos reglas, las dos medidas sobre el corpus (el porque esta en el comentario de
    RX_TOTAL, arriba):
     · en una fila de totales con columnas ('TOTALES: 0.00 225.00 IVA 24.107143') el
       total es el ULTIMO importe ANTES de que empiecen las letras, y el corte va
       DESPUES del primer numero para no romper 'TOTAL A PAGAR: 50.00' ni
       'TOTAL FACTURA Q 1,393.00';
     · el OCR mete un espacio dentro del numero ('TOTAL Q70. 00' = 70.00, pagina 12 de
       marzo): se pega antes de buscar importes, o el '00' se lee como un segundo
       importe y el ultimo valor de la fila pasa a ser 0.00.

    DEUDA CONOCIDA (M-c del fix round 2 de la Task 9, m=0 en el corpus, NO se arregla):
    con varios importes en la linea gana el ULTIMO ('Tota 46.00 12%' -> 12,00). Es la regla
    de R12 y es identica en la via estricta y en la tolerante, asi que cambiarla es otra
    tarea; queda declarada aca y en el reporte de la Task 9 (seccion 12).
    """
    primero = re.search(r'\d', cola)
    if primero:
        letras = re.search(r'[A-Za-zÁÉÍÓÚáéíóú]{2,}', cola[primero.start():])
        if letras:
            cola = cola[:primero.start() + letras.start()]
    cola = re.sub(r'(?<=[.,])\s+(?=\d)', '', cola)
    valores = [v for v in (importe(x) for x in RX_IMPORTE.findall(cola)) if v is not None]
    return valores[-1] if valores else None


def _rotulo_ajeno(texto, inicio):
    r"""True si el rotulo NORMALIZADO es una de las formas que no son el total.

     · la suma de impuestos ('T O T A L DE IMPUESTOS', 'T O T A L D E IMPUESTOS',
       'T O T A L IMPUEST0S'): la misma exclusion que el `(?!\s*IMPUESTO)` de RX_TOTAL,
       pero con el espaciado y los typos del OCR;
     · una palabra que empieza con TOTAL ('T O T A L M E N T E PAGADO',
       'T O T A L E M E N T E PAGADO').
    Se decide sobre la forma normalizada del texto que ARRANCA en el match: como lookahead
    del patron no sirve (el motor puede acortar el rotulo y esquivarlo: medido, 'T O T A L
    DE IMPUESTOS' entraba por la forma corta 'T O T A') y enumerar variantes dejo agujeros
    de la misma clase en el fix round 1 (el espaciado dentro de DE/MENTE, la O por 0).
    Medido con `_investigacion_gt/185_medir_rotulo_degradado.py`, secciones 7 y 9.
    """
    return bool(RX_AJENO.match(_normalizar(texto[inicio:inicio + 48])))


def _es_subtotal(texto, inicio):
    """True si el rotulo viene precedido por SUB, con el espaciado y los separadores del OCR.

    Se decide sobre el PREFIJO NORMALIZADO: 'SUB TOTA', 'SUB. TOTA', 'SUB- TOTA',
    'SUB: TOTA' y 'S U B TOTA' son el mismo subtotal (fix round 2; el fix round 1 exigia
    'SUB' exacto separado solo por espacios). El lookbehind de Python es de ancho FIJO, asi
    que el contexto se mira en codigo. Medido en `.../185`, secciones 7 y 9.
    """
    return _normalizar(texto[max(0, inicio - 10):inicio]).endswith('SUB')


def _linea_de_subtotal(linea):
    """True si la linea del rotulo, NORMALIZADA, empieza con SUBTOTA.

    Sólo se la llama con las lineas que ya matchearon RX_TOTAL_LIMPIO_SOLO o
    RX_TOTAL_DEGRADADO_SOLO, o sea: el rotulo (TOTAL/TOTALES o el degradado) SOLO en su linea,
    opcionalmente precedido por 'SUB' CONTIGUO. Consecuencia (declarada en el reporte de la
    Task 9, seccion 12): las formas con separadores o espacios DENTRO del 'SUB' de la linea
    ('SUB. TOTAL:', 'S U B TOTAL:') NO llegan hasta aca —los regexes de linea no las
    matchean— y quedan fail-closed (None + aviso, nunca como total). Dentro de lo que SI
    llega, la normalizacion distingue 'SUBTOTA' de 'SUBFOTAL' (m=0 en el corpus: el mutante
    que la apaga sobrevive y esta declarado, con efecto solo sobre el aviso).
    """
    return _normalizar(linea).startswith('SUBTOTA')


def _importes_del_renglon_siguiente(lineas, i):
    """Los importes de las lineas que siguen al rotulo solo, o [] si no hay ninguno.

    Se acumula el bloque de lineas que son SOLO un importe (las vacias del medio no lo
    cortan) y se devuelve el ULTIMO importe: es la misma regla que R12 aplica dentro de
    una linea ('TOTALES: 0.00 225.00' -> 225.00) y la que arregla el M-a del fix round 1
    ('TOTALES:' / '0.00' / '225.00' daba 0.00). El bloque se corta en la primera linea
    que no sea solo un importe y no se miran mas de 15 lineas.
    """
    valores = []
    j = i + 1
    while j < len(lineas) and j <= i + 15:
        if not lineas[j].strip():
            j += 1
            continue
        if not RX_IMPORTE_SOLO.match(lineas[j]):
            break
        valores.append(importe(lineas[j]))
        j += 1
    return [v for v in valores if v is not None]


def _total_de_rotulo_degradado(texto):
    """(valor, aviso) de la via del rotulo destrozado, o None si no hay nada que leer.

    Se consulta SOLO cuando la via estricta no encontro ni un total ni un SUB TOTAL
    (ver `total()`): por eso no puede cambiar el importe de una pagina que hoy devuelve
    uno. Medido con `_investigacion_gt/185_medir_rotulo_degradado.py`: sobre las 57
    cambian 7 paginas, las 7 con `None` (ninguna con candidato estricto).

    Prioridad (fix round 1, M-b: m=0 en el corpus, pineada con texto propio):
      1. el rotulo LIMPIO solo en su linea con el importe abajo: es la lectura mas fuerte
         de esta via (el rotulo es el mismo que busca la via estricta) y su bloque toma el
         ULTIMO importe (M-a);
      2. el rotulo DEGRADADO con el importe en la misma linea;
      3. el rotulo DEGRADADO solo con el importe abajo;
    y en las tres, un TOTAL/TOTALES gana sobre un SUB TOTAL (R29): el subtotal se devuelve
    CON `AVISO_SUBTOTAL`, nunca como total en silencio. Las dos sub-reglas del renglon
    siguiente llevan `AVISO_RENGLON_SIGUIENTE` porque el importe no esta en la linea del
    rotulo.
    """
    lineas = texto.split('\n')
    limpias, limpias_sub = [], []
    degradadas_solo, degradadas_solo_sub = [], []
    for i, linea in enumerate(lineas):
        if RX_TOTAL_LIMPIO_SOLO.match(linea):
            destino = limpias_sub if _linea_de_subtotal(linea) else limpias
            destino.extend(_importes_del_renglon_siguiente(lineas, i))
        elif RX_TOTAL_DEGRADADO_SOLO.match(linea):
            destino = degradadas_solo_sub if _linea_de_subtotal(linea) else degradadas_solo
            destino.extend(_importes_del_renglon_siguiente(lineas, i))
    if limpias:
        return limpias[-1], AVISO_RENGLON_SIGUIENTE
    inline, inline_sub = [], []
    for m in RX_TOTAL_DEGRADADO.finditer(texto):
        if _rotulo_ajeno(texto, m.start()):
            continue
        valor = _importe_de_la_cola(m.group(1))
        if valor is None:
            continue
        (inline_sub if _es_subtotal(texto, m.start()) else inline).append(valor)
    if inline:
        return inline[-1], ''
    if degradadas_solo:
        return degradadas_solo[-1], AVISO_RENGLON_SIGUIENTE
    if limpias_sub:
        return limpias_sub[-1], AVISO_SUBTOTAL
    if inline_sub:
        return inline_sub[-1], AVISO_SUBTOTAL
    if degradadas_solo_sub:
        return degradadas_solo_sub[-1], AVISO_SUBTOTAL
    return None


def total(texto):
    """(total, aviso). El aviso vacio significa 'se encontro en una linea
    etiquetada'; no garantiza que el papel diga ese numero.

    Entre dos LINEAS etiquetadas manda la precedencia del rotulo: se prefiere la ultima
    que diga TOTAL/TOTALES y no SUB TOTAL, porque un subtotal no es el total de la
    factura. Medido: 2026-03-1q-p04 imprime 'TOTAL Q. 18.00' (linea 31) y DESPUES
    'SUBTOTAL. Q. 16,07' (linea 34), y con la regla pelada del ultimo candidato el total
    salia 16.07 (el papel cierra con 18.00: 16,07 + 1,93 de IVA). Si el papel SOLO
    imprime un SUB TOTAL se devuelve ese valor, pero CON aviso, porque puede no ser el
    total; en el corpus no pasa en ninguna de las 57 paginas, asi que el aviso esta
    pinneado con texto propio. El SUB TOTAL con el importe en su linea tambien gana sobre
    la via del rotulo degradado: esa via esta para las paginas donde la via estricta no
    encontro NADA, y ninguna de las 7 paginas con un SUB TOTAL tiene ademas un rotulo
    degradado (m=0). Dentro de la via degradada la regla es la de
    `_total_de_rotulo_degradado`: un TOTAL gana sobre un SUB TOTAL, y el subtotal sale
    con aviso.
    """
    t = texto or ''
    m = RX_IMPORTE_TOTAL_USD.search(t)
    if m:
        valor = importe(m.group(1))
        if valor is not None:
            return valor, ''
    candidatos, subtotales = [], []
    for m in RX_TOTAL.finditer(t):
        valor = _importe_de_la_cola(m.group(1))
        if valor is not None:
            # El match arranca en el rotulo, asi que si empieza con SUB es un subtotal:
            # no hace falta tocar el patron (el grupo 1 sigue siendo la cola).
            if m.group(0)[:3].upper() == 'SUB':
                subtotales.append(valor)
            else:
                candidatos.append(valor)
    if candidatos:
        return candidatos[-1], ''
    if subtotales:
        return subtotales[-1], AVISO_SUBTOTAL
    leido = _total_de_rotulo_degradado(t)
    if leido is not None:
        return leido
    return None, 'no se encontro el total en una linea etiquetada'


# ------------------------------------------------------------
# Fecha
# ------------------------------------------------------------
# Se ancla en el rotulo de emision (que puede decir "FECHA DE EMISION",
# "Fecha y hora de emision" o "FECHA:"), admite los formatos reales del DTE
# (DD-MM-AAAA, DD/MM/AAAA, AAAA-MM-DD, DD-mes-AAAA y el año de dos digitos) y
# NUNCA inventa: si no encuentra nada devuelve vacio con aviso (antes ponia la
# fecha de hoy, y 14 de 57 facturas se cargaban en el mes equivocado).
#
# La primera alternativa del rotulo tiene que ir PRIMERO: 'FECHA DE EMISION:
# 14-07-2026' tambien matchea 'FECHA[^\S\n]*:' (el ':' esta 17 caracteres mas
# adelante), asi que si se invierte el orden la ventana de 80 se abre sobre
# ' de emision:' en vez de sobre la fecha.
#
# El ORDEN de las ramas es carga funcional, no estilo, y la rama DD-MM-AAAA tiene
# que ir ANTES que la de año de dos digitos: un año de cuatro digitos con '-'
# ('29-07-2099') tambien matchea 'DD-MM-AA' y el '+2000' de dos digitos solo se
# aplica si el año es < 100, pero si el año largo cae en la rama equivocada el
# resultado se sale del rango. Se recorren los candidatos de cada rama y se
# devuelve el primero VALIDO: una candidata imposible ('1501-22-00' del OCR) no
# puede tapar a la fecha buena que viene mas adelante en la misma pagina.
MESES = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
         'jul': 7, 'ago': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12}
RX_EMISION = re.compile(r'FECHA[^\S\n]*(?:DE[^\S\n]*)?(?:Y[^\S\n]*HORA[^\S\n]*DE[^\S\n]*)?'
                        r'(?:EMISI[OÓ]N|EMISION)|FECHA[^\S\n]*:', re.I)
# Las guardas `(?<!\d)` / `(?!\d)` impiden que una fecha se lea DENTRO de una cifra
# mas larga: sin ellas, '2026-02-31' tambien ofrece '26-02-31' (dia 26, mes 2, año
# 31 -> 2031, que existe) y un numero de DTE como '260714112026' ofrece '14-11-2026'.
# No son cosmeticas: son las que hacen que el filtro de `_candidatas` vea la fecha
# completa y la descarte, en vez de inventar una distinta a partir de sus digitos.
RX_ISO = re.compile(r'(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)')
RX_DDMM = re.compile(r'(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})(?!\d)')
RX_MES = re.compile(r'(\d{1,2})[-/.\s]*([A-Za-zÁÉÍÓÚáéíóú]{3,10})[-/.\s]*(\d{4})')


def _candidatas(trozo):
    """Fechas ISO del trozo, en orden de confianza y ya VALIDADAS.

    'Validada' es fuerte a proposito: dia y mes en rango **y** el dia existe en ese
    mes. Con solo dia<=31 y mes<=12, '2026-02-31' pasaba el filtro y despues
    reventaba en `date()` con ValueError: en la Task 7 eso aborta la pagina entera
    en vez de avisar. Una candidata que no es una fecha real no es una fecha, es
    ruido del OCR ('1501-22-00', '2026-02-31'), y descartarla deja que la busqueda
    siga con la fecha buena que viene mas adelante en la misma pagina.
    """
    for m in RX_ISO.finditer(trozo):
        anio, mes, dia = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if _existe(anio, mes, dia):
            yield anio, mes, dia
    for m in RX_MES.finditer(trozo):
        mes = MESES.get(m.group(2)[:3].lower())
        anio, dia = int(m.group(3)), int(m.group(1))
        if mes and _existe(anio, mes, dia):
            yield anio, mes, dia
    for m in RX_DDMM.finditer(trozo):
        anio = int(m.group(3))
        anio = anio + 2000 if anio < 100 else anio
        mes, dia = int(m.group(2)), int(m.group(1))
        if _existe(anio, mes, dia):
            yield anio, mes, dia


def _existe(anio, mes, dia):
    """True si es una fecha del calendario (no solo dia<=31 y mes<=12)."""
    try:
        date(anio, mes, dia)
        return True
    except ValueError:
        return False


def _fecha_en(trozo):
    for anio, mes, dia in _candidatas(trozo):
        return '%04d-%02d-%02d' % (anio, mes, dia)
    return ''


def _aviso_de_rango(valor):
    """Aviso si la fecha es imposible para una rendicion, o '' si entra en rango.

    NO se descarta la fecha por estar fuera de rango: el papel podria decir eso
    (una autorizacion, un vencimiento) y quien decide es el operador. Pero un año
    < 2000 o a mas de un año de hoy no puede pasar en silencio: en 2026-07-2q-p07
    el papel imprime '22-07-2028' y la factura se cargaba sin que nadie mirara.
    La cota es fija (365 dias) para que el umbral sea determinista.

    Recibe SIEMPRE una fecha ya validada por `_candidatas`, asi que `date()` no
    puede fallar aca: si se valida en este helper, el ValueError se dispara en el
    camino del aviso (donde ya no hay nada que hacer) en vez de en el filtro, donde
    la busqueda todavia puede seguir con la proxima candidata. Un año equivocado
    entre 2000 y 2025 NO se avisa a proposito: puede ser una factura vieja
    legitima, y esa plausibilidad relativa al periodo la mide el arnes (FECHA_FUERA).
    """
    anio, mes, dia = (int(p) for p in valor.split('-'))
    if anio < 2000 or (date(anio, mes, dia) - date.today()).days > 365:
        return 'la fecha parece fuera de rango: revisala contra el papel'
    return ''


def fecha(texto):
    """(fecha ISO, aviso). Nunca inventa: sin fecha legible devuelve ('', aviso)."""
    t = texto or ''
    m = RX_EMISION.search(t)
    encontrada = _fecha_en(t[m.end():m.end() + 80]) if m else ''
    if encontrada:
        return encontrada, _aviso_de_rango(encontrada)
    # No habia fecha junto al rotulo (o no habia rotulo): se usa la ultima red y se
    # avisa. Es la unica respuesta honesta: esa fecha puede ser de cualquier parte
    # de la pagina (una autorizacion, un vencimiento), no la de emision.
    encontrada = _fecha_en(t)
    if encontrada:
        return encontrada, '; '.join(
            x for x in ('la fecha no estaba junto al rotulo de emision',
                        _aviso_de_rango(encontrada)) if x)
    return '', 'no se encontro la fecha de emision'


# ------------------------------------------------------------
# Tipo de comprobante
# ------------------------------------------------------------
# El tipo decide si el IVA se separa (FCP, factura con IVA) o no (FCC, pequeño
# contribuyente), asi que no se adivina: cada valor sale de una leyenda que la
# factura misma imprime y, si no hay ninguna, se devuelve '' con aviso para que lo
# elija el operador. Antes la pantalla daba por hecho FCP y separaba un IVA que el
# papel podia no decir.
#
# Primero el FCC: su titulo ('Factura Pequeño Contribuyente') y la leyenda 'no genera
# derecho a credito fiscal'. De la leyenda alcanza con 'no genera derecho' porque el
# OCR real rompe justo la palabra que importa ('credito' -> 'eredito', como en
# 2026-07-1q-p10). Medido: exigir la leyenda completa ('no genera derecho a cr[eé]dito
# fiscal') tambien da 49/49 en este corpus, porque esa pagina imprime ademas el titulo
# legible del pequeño contribuyente; el patron suelto se queda porque lo pide el brief
# y porque no depende de que el titulo sobreviva al OCR.
#
# El FCP va despues y su señal robusta es TRIMESTRAL, no la leyenda entera: el OCR la
# destroza de todas las formas medidas en el corpus ('SUJETO A PAGO TRIMESTRAL',
# 'SUJETO A PAGD TRIMESTRAL', 'SLUETO A PAGOS TRIMESTRALES', 'Sujetos a pagos
# trimestrales', 'iSuieto a Pacos Trimestrales'). No sobrevive en TODAS: 2 de las 57
# paginas la escriben 'trinestralos' (2026-03-1q-p02) y 'teimastrales'
# (2026-07-07-bus-a-santa-lucia-p01), que `trimestra` no ve. Las dos fallan cerrado: la
# primera queda en '' con aviso y la elige el operador, y a la segunda la salva la
# señal de abajo. La clase final `[li1]` cubre que el OCR cierre la palabra con I o 1.
#
# 'agente de retencion' es la segunda señal del FCP (es la frase que el DTE imprime en
# las FCP). Ninguna de las 49 paginas verificadas la necesita -todas traen TRIMESTRAL y
# quitarla no cambia ninguna medicion-, pero tiene respaldo real en el corpus: en
# 2026-07-07-bus-a-santa-lucia-p01 el texto dice 'Sujeto a pagos teimastrales IS ik'
# (la r cambiada por i), asi que esta rama es la que deja esa factura en FCP en vez de
# pedirle el tipo al operador. No aparece en ninguna FCC.
RX_FCC = re.compile(r'peque[nñ]o\s+contribuyente|no\s+genera\s+derecho', re.I)
RX_FCP = re.compile(r'trimestra[li1]|agente\s+de\s+retenci[oó]n', re.I)


def tipo(texto):
    """(tipo, aviso). 'FCP', 'FCC' o '' + aviso para que la pantalla lo pida.

    El aviso vacio significa 'la leyenda estaba en el papel'; no garantiza que el
    OCR la haya leido en la pagina correcta. El orden FCC-antes-que-FCP es carga
    funcional: ninguna de las 57 paginas trae las dos frases, pero si alguna las
    trajera manda el FCC (declaracion legal sobre la clase del documento y lectura
    conservadora: no separa IVA); lo pinea test_con_las_dos_senales_gana_fcc.
    """
    t = texto or ''
    if RX_FCC.search(t):
        return 'FCC', ''
    if RX_FCP.search(t):
        return 'FCP', ''
    return '', 'sin leyenda de tipo: elegi FCP o FCC'


# ------------------------------------------------------------
# El IVA impreso
# ------------------------------------------------------------
# Es la señal del tipo cuando no hay leyenda (D4, ver `tipo_con_iva`) y el control con
# el que se recupera el impuesto especial. Tres decisiones y un orden, cada una con lo que
# la mide (la revision independiente corrio mutantes sobre estas guardas):
#  · El hueco entre el rotulo y el importe solo admite separadores y la moneda. Carga
#    funcional por los DOS lados: cruzarlo todo (el `[^\d\n]{0,8}` del brief no puede pasar
#    por encima de un digito) pierde el IVA de 2026-07-2q-p10, donde pdfplumber renderizo la
#    Q como 0 en TODA la pagina ('SUB TOTAL 0 230.09', 'Visa 0 230.00', 'IVA 0 23.87'), y
#    sin IVA esa pagina perdia tambien el impuesto especial del papel (7.14) y en silencio
#    (C1 de la revision); y admitir palabras deja entrar dos falsas lecturas medidas:
#    'Agente de Retencion del IVA FECHA: 09/03/2026' daba IVA 9.00 (el dia de la fecha) y
#    'Serie Administrativa: FEA105B' daba 105.00 (la 'iva' de adentro y el codigo de atras).
#    El hueco NO cruza el salto de linea (por eso no se usa `\s`, que si lo cruza): es la
#    misma disciplina de `total()` y `fecha()`, y evita que una etiqueta suelta tome el
#    importe de la linea siguiente. Medido: excluir el salto no cambia ninguna de las 57.
#    Y el hueco es PEREZOSO (`{0,8}?`), no codicioso: como admite el 0 y los separadores,
#    uno codicioso se come el arranque del importe ('IVA 0.000000' se leia '00' y un
#    'IVA 0.54' habria dado 54.00). Perezoso, el primer hueco que deja un importe valido
#    es el bueno: 'IVA 0.54' -> 0.54, 'IVA 0 23.87' -> 23.87 (el 0 suelto es la Q).
#  · El importe tiene 2+ digitos o un decimal. La rama del decimal es carga funcional
#    ('IVA 0.000000' de fc-almacenadora es 0.00, no None); la de 2+ digitos es defensiva
#    contra el '1' del codigo de la unidad gravable de FC Regus. Su alcance medido, con el
#    mutante 'sin la rama de 2+ digitos' (_investigacion_gt/165_probar_parsear.py): en el
#    TOTAL de la pagina no cambia nada (el ultimo match es 'Total de impuestos 109.800'),
#    pero en el CORPUS si cambia tres paginas — 2026-07-2q-p10, 2026-07-1q-p10 y
#    2026-07-2q-p13 pasan de None a 0.0 (el 'IVA 0 ...' de la moneda leida como cero, que
#    el hueco perezoso deja pasar hasta el '0') —, y la fila AISLADA
#    ('IVA 1 70.00 8.400') es la que la pinea como red: sin la rama daria IVA 1.00.
#  · Se toma el ULTIMO match, no el primero: carga funcional medida en las FEL, que
#    imprimen el IVA de cada renglon antes que el de la fila de totales ('IVA 18.750000' ...
#    'TOTALES: 0.00 225.00 IVA 24.107143'). Con el primero, la recuperacion del especial
#    inventaba 50.00 en una factura sin impuesto especial (2026-07-09-hotel-y-almuerzo-p01).
RX_IVA = re.compile(r'(?:T?IVA|Total\s+de\s+impuestos)[ \tQO0:,.()]{0,8}?'
                    r'(\d{2,}[\d.,]*|\d[.,]\d+)', re.I)
# La unica forma del corpus que imprime el IVA SIN rotulo: el ticket de parqueo de la
# app Rinde, 'detalles 4,86 GTQ 0.54 619 (12%)'. El importe del IVA es el ultimo con
# centavos de la linea (el '619' es un codigo entero del ticket). Es una sola pagina
# (2026-07-1q-p04) y sin esta via quedaria sin IVA impreso, con tasa_iva = 0 y un IVA a
# la vista, que es justo el caso que la D4 existe para evitar.
RX_IVA_TASA = re.compile(r'(\d[\d.,]*[.,]\d{1,2})(?=[^\n]*\([^\S\n]*12[^\S\n]*%[^\S\n]*\))')
RX_TOTAL_IMPUESTO = re.compile(r'TOTAL[^\S\n]*IMPUESTO[^\d\n]{0,8}(\d[\d.,]*)', re.I)


def iva_impreso(texto):
    """IVA que la factura imprime, o None si no imprime ninguno.

    El cero SI se devuelve: 'IVA 0.000000' es un dato del papel (el que decide que no
    es señal de tipo es `tipo_con_iva`, porque el cero no es "imprime un IVA").
    """
    t = texto or ''
    valores = [v for v in (importe(m.group(1)) for m in RX_IVA.finditer(t)) if v is not None]
    if valores:
        return valores[-1]
    marcas = [v for v in (importe(m.group(1)) for m in RX_IVA_TASA.finditer(t)) if v is not None]
    return marcas[-1] if marcas else None


def _total_impuestos(texto):
    """'TOTAL IMPUESTO' impreso (la suma de IVA + impuesto especial), o None."""
    m = RX_TOTAL_IMPUESTO.search(texto or '')
    return importe(m.group(1)) if m else None


# ------------------------------------------------------------
# Impuesto especial (IDP del combustible, turismo del hospedaje)
# ------------------------------------------------------------
# NO es IVA: vive dentro del bruto y la regla del negocio es
#     base = (total - especial) / 1.12      IVA = 12% de la base
#     bruto = base + especial               total = base + IVA + especial
# En el FCC (pequeño contribuyente) no se separa nada: total = bruto, IVA = 0 y
# especial = 0 por la regla del usuario. Esa regla es del negocio y la aplica quien
# compone el alta, no esta funcion (que no recibe el tipo): un FCC que igual imprima un
# rotulo legible devuelve el valor y el que arma el comprobante lo tiene que poner en 0.
# Medido: ninguna de las paginas FCC del corpus trae rotulo legible, asi que la funcion no
# devuelve valor en ninguna (en 2026-07-1q-p06 el 'TREO' que sigue a la descripcion es un
# codigo mas grande que el total: ahi solo sale el aviso de mencion, que la Task 7 tiene
# que apagar en el FCC junto con el valor).
#
# El valor se lee de su rotulo y, si el rotulo no sobrevivio al OCR, se RECUPERA
# invirtiendo la regla SOBRE EL TOTAL (nunca "a partir del IVA"): se buscan los importes
# del bloque de impuestos que sigue al total y se elige el que cierra la aritmetica con
# el IVA impreso (o con el TOTAL IMPUESTO) como control.
#
# La ventana entre el rotulo y el importe la acota la LINEA (`[^\d\n]` no cruza el salto
# de linea), asi que el importe es el PRIMER numero de la misma linea despues del
# rotulo. Medido: la propuesta del brief usaba una ventana de 12 caracteres y
# 'TURISMO HOSPEDAJE — 16.39' tiene 13 entre el rotulo y el importe (espacio,
# HOSPEDAJE, espacio, guion em, espacio), asi que la pagina del hotel caia en la
# recuperacion y daba 16.40 en vez del 16.39 que el papel imprime.
RX_ESPECIAL = (
    re.compile(r'TURISMO[^\d\n]*?(\d[\d.,]*)', re.I),
    re.compile(r'(?:IMPUESTO[^\S\n]*)?(?:IDP|1DP|10P|I0P|1OP)[^\d\n]*?(\d[\d.,]*)', re.I),
)
# Evidencia de que la factura SI trae el impuesto, para poder avisar cuando no se pudo
# leer ni recuperar. Cubre los rotulos que la clase de ESTE comentario (la de abajo,
# `RX_MENCION_ESPECIAL`) SI matchea; `RX_ESPECIAL`, la de arriba, es otra: matchea el
# literal `1OP` porque lo tiene listado. Medido con
# `_investigacion_gt/165_probar_parsear.py` seccion 4: IDP, 1DP, 10P, I0P y la D suelta
# de 'DP 010.75' dan True; `1OP` NO lo matchea `RX_MENCION_ESPECIAL` porque su clase es
# `[il1]?[d0]p` y la `O` no esta en `[d0]`, y en el corpus tiene 0 ocurrencias, asi que
# no se lista. Las dos formas que el OCR destruyo y que se
# quedan sin valor en el corpus: 'rp Q 7.14' (el IDP de 2026-07-2q-p10, que solo se
# recupera cuando hay IVA impreso: sin el, el aviso es la unica pista que le queda al
# operador) y 'TREO' (el turismo de 2026-07-1q-p06, donde el numero que le sigue,
# 15908080, es un codigo mas grande que el total, asi que no hay valor que leer). 'rp' es
# un token de dos letras y entra a proposito y con limites de palabra: en este corpus
# aparece UNA vez y justo en el lugar del IDP, pero es demasiado generico para leerle un
# importe; por eso NO esta en RX_ESPECIAL: el valor lo prueba la aritmetica, no la etiqueta.
RX_MENCION_ESPECIAL = re.compile(r'turismo|tursnmo|turism0|treo|\b[il1]?[d0]p\b|\brp\b', re.I)
# Control del cierre. La tolerancia es de 5 centavos y no de medio centavo: el papel
# redondea distinto (imprime 19.68 en 'TOTAL IMPUESTO' donde la regla da 19.67) y el
# cierre tiene que aceptar ese centavo.
TOLERANCIA_CIERRE = 0.05
AVISO_RECUPERADO_BLOQUE = ('el rotulo del impuesto especial no se leyo: '
                           'se recupero del bloque de impuestos')
AVISO_RECUPERADO_TOTAL = ('el rotulo del impuesto especial no se leyo: '
                          'se recupero del total (puede variar 1 centavo)')
AVISO_ESPECIAL_ILEGIBLE = ('la factura menciona un impuesto especial (IDP o turismo) '
                           'que no se pudo leer ni recuperar')


def cierra(total, especial, iva_impreso):
    """¿Cierra la regla del negocio con esos tres numeros?

    base = (total - especial)/1.12 e IVA = 12% de esa base. Sin total o sin IVA no hay
    nada que cerrar: devuelve False en vez de reventar con None (asi la llaman la
    recuperacion y la Task 7, que puede no tener uno de los dos).
    """
    if not total or iva_impreso is None:
        return False
    subtotal = round(total - (especial or 0), 2)
    base = round(subtotal / 1.12, 2)
    return abs(round(subtotal - base, 2) - iva_impreso) <= TOLERANCIA_CIERRE


def _bloque_de_impuestos(texto):
    """Importes de las lineas que siguen a la del TOTAL y antes de la leyenda o del
    certificador. En el combustible de julio: 5.26 (el IDP, sin rotulo legible) y 15.51
    (el IVA). Incluye el importe en letras ('MIL ... 80/100') y los codigos: por eso el
    que lo usa tiene que exigir que el cierre aritmetico se cumpla.
    """
    partes = []
    visto_total = False
    for linea in (texto or '').splitlines():
        if RX_TOTAL.search(linea):
            visto_total = True
            continue
        if not visto_total:
            continue
        if re.search(r'(?i)trimestra|agente\s+de\s+retenci|certificador|turno|sujeto', linea):
            break
        partes.extend(v for v in (importe(x) for x in RX_IMPORTE.findall(linea)) if v)
    return partes


def especial(texto, total, iva=None, total_impuestos=None):
    """(valor, origen, aviso) del impuesto especial.

    `origen` es 'rotulo' (el importe lo dice el papel), 'recuperado' (sale de invertir
    la regla sobre el total) o None (la factura no trae el impuesto o no se pudo
    determinar). El aviso explica la recuperacion, o avisa cuando el papel menciona el
    impuesto y no se pudo leer ni recuperar: nada se inventa, pero nada se calla
    tampoco. Sin total no se acepta el rotulo, porque la guarda `valor < total` es lo
    unico que impide que un codigo de la linea se lea como impuesto.

    `iva` y `total_impuestos` son el IVA y el TOTAL IMPUESTO ya leidos; si no se pasan,
    se extraen del texto (es el modo en que los usa la Task 7, que ya los necesita para
    su propia aritmetica y los puede reusar).

    OJO para quien compone el alta: en un FCC (pequeño contribuyente) el impuesto
    especial tiene que quedar en 0 aunque esta funcion devuelva un valor, porque ahi el
    total ES el bruto y no se separa nada.
    """
    t = texto or ''
    for rx in RX_ESPECIAL:
        for m in reversed(list(rx.finditer(t))):
            valor = importe(m.group(1))
            if valor and total and valor < total:
                return valor, 'rotulo', ''
    if not total:
        return None, None, _aviso_de_mencion(t)
    iva_imp = iva if iva is not None else iva_impreso(t)
    total_imp = total_impuestos if total_impuestos is not None else _total_impuestos(t)
    # La factura sin impuesto especial tiene que cerrar con especial 0: si ese cierre ya
    # se cumple, no hay nada que recuperar y la aritmetica no puede "cerrar" con
    # cualquier cosa. Es la guarda que encontro la medicion: en fc-regus-p01 el
    # '80/100' del importe en letras cerraba y daba 1015.47 (la verdad curada es 0.00).
    control_cero = iva_imp if iva_imp is not None else total_imp
    if control_cero is not None and cierra(total, 0.0, control_cero):
        return None, None, ''
    # (a) El bloque de impuestos: el importe que NO es el IVA ni el total y que cierra.
    for valor in _bloque_de_impuestos(t):
        if valor in (total, iva_imp) or valor >= total:
            continue
        control = iva_imp if iva_imp is not None else (total_imp - valor if total_imp else None)
        if control is not None and cierra(total, valor, control):
            return valor, 'recuperado', AVISO_RECUPERADO_BLOQUE
    # (b) Inversa de la regla con el IVA impreso (o con el TOTAL IMPUESTO). Se prueban
    # los centavos vecinos porque el redondeo al centavo deja dos valores validos: en el
    # combustible de julio la inversa directa da 5.24 donde el papel dice 5.26, y el
    # bloque de (a) es el que trae el 5.26 exacto.
    candidatos = []
    if iva_imp:
        candidatos.append(round(total - iva_imp - round(iva_imp / 0.12, 2), 2))
    if total_imp:
        candidatos.append(round((total_imp * (1 + 1 / 0.12) - total) / (1 / 0.12), 2))
    for candidato in candidatos:
        for delta in (0, -0.01, 0.01, -0.02, 0.02):
            valor = round(candidato + delta, 2)
            if 0 < valor < total:
                control = iva_imp if iva_imp is not None else (total_imp - valor)
                if cierra(total, valor, control):
                    return valor, 'recuperado', AVISO_RECUPERADO_TOTAL
    return None, None, _aviso_de_mencion(t)


def _aviso_de_mencion(texto):
    """Aviso si el papel menciona el impuesto especial y no se pudo determinar."""
    return AVISO_ESPECIAL_ILEGIBLE if RX_MENCION_ESPECIAL.search(texto or '') else ''


# ------------------------------------------------------------
# El tipo con la señal del IVA impreso (D4 de la spec)
# ------------------------------------------------------------
# `tipo()` lee SOLO leyendas y esta bien que lo haga (el instrumento lo mide 49/49).
# Pero la spec pide ademas que una factura que imprime un IVA sea FCP aunque no traiga
# ninguna leyenda: 2026-07-1q-p04 (el parqueo) imprime 0.54 y no tiene leyenda, y sin
# esta señal quedaria con tasa_iva = 0 y un IVA a la vista. El orden es carga funcional:
# la leyenda del papel manda (una FCC que imprime un IVA sigue siendo FCC, y el servicio
# la rechazaria si se cargara como FCP); el IVA solo decide cuando no hay leyenda.
# La Task 7 tiene que usar ESTA funcion al componer el tipo de `parsear()`.
def tipo_con_iva(texto):
    """(tipo, aviso). Leyendas primero; si no hay, el IVA impreso > 0 da FCP."""
    valor, aviso = tipo(texto)
    if valor:
        return valor, aviso
    iva = iva_impreso(texto)
    if iva and iva > 0:
        return 'FCP', ('sin leyenda de tipo: se tomo FCP porque la factura imprime IVA '
                       '(%s)' % ('%.2f' % iva))
    return '', aviso


# ------------------------------------------------------------
# Emisor: nombre, NIT y numero de DTE
# ------------------------------------------------------------
# Los tres rotulos se confunden entre si en el OCR real y equivocarlos obliga al operador
# a corregir la factura a mano: el nombre y el NIT son lo que ata la factura a un
# proveedor y el numero de DTE es el que identifica el documento. Medido sobre las 57
# paginas (probes _investigacion_gt/160_medir_emisor.py y 161_mutantes_emisor.py, contra
# las columnas que la tabla limpia dejo verificadas a mano): NIT 39/39, DTE 39/39 y nombre
# 15/15. La copia literal del brief de la Task 6 daba 34/39, 37/39 y 5/15, y la regla de
# 153_proponer_verdad.py 34/39, 37/39 y 5/15.
#
# Las reglas, cada una con lo que la mide (m = paginas del corpus que cambian al
# desactivar la regla, contadas con _investigacion_gt/164_auditar_emisor.py; lo que va sin
# m es defensivo y no afirma respaldo):
#  · TOPES (RX_CORTE, m=7 sobre el NIT). Lo que venga despues de los rotulos del comprador
#    ('DATOS DEL COMPRADOR', 'NIT Receptor', 'Nombre Cliente'), del certificador ('DATOS
#    DEL CERTIFICADOR', 'Certificador:', 'Superintendencia', 'INFILE', 'GUATEFACTURAS',
#    'AINNOVA') o de SIDESYS no es del emisor: sin el corte, 7 paginas devuelven un NIT
#    ajeno. Medido con 161_mutantes_emisor.py (bloque M2), el NIT del COMPRADOR
#    (97108065) en 2026-03-1q-p06 y el del MISMO comprador con el guion que mete el OCR
#    (9710806-5) en las cuatro fc-regus; el de DIGIFACT (7745482-) en 2026-03-1q-p09 y el
#    de la Superintendencia (16693949) en el desayuno del 8.
#    'DATOS DEL VENDEDOR'/'DEL EMISOR' NO cortan: en 2026-07-1q-p09 el nombre esta DESPUES
#    de ese rotulo y en 2026-03-1q-p08 esta ANTES, asi que la linea del rotulo se saltea
#    como cualquier otra etiqueta.
#  · El NIT del emisor es el primer NIT de la cabecera. El rotulo se reconoce corrompido
#    porque el OCR real imprime 'NLT.' (2026-03-1q-p02), 'NAT:' (2026-03-1q-p10) y 'NET'
#    (2026-03-1q-p12) en su lugar, y las FEL nuevas lo rotulan 'Nit Emisor:'. Medido
#    quitando cada forma: cada letra corrompida cambia 1 pagina y el grupo 'Emisor' cambia
#    10 (sin el, las diez devuelven el NIT vacio). El NIT del comprador NO necesita lista
#    propia: el tope lo deja afuera (medido: filtrar ademas 97108065 / 97104065 / 97108066
#    / 97108085 no cambia ninguna de las 57, y ese filtro se quito por eso).
#  · El numero de DTE sale del rotulo ('NUMERO DE DTE', 'NUMERO', el OCR 'Nusero'/'NUNERO',
#    'NUMERO FEL', 'Factura No') y se recorren los candidatos para descartar el que sea
#    igual al NIT (la bandera DTE_IGUAL_NIT del instrumento mide 4 paginas sobre el parser
#    actual; en `emisor()` esa guarda no cambia ninguna de las 57, asi que su pin es un
#    test con texto propio). El rotulo suelto 'No.'/'Ne.' (el OCR perdio el 'de DTE', m=2)
#    solo vale al PRINCIPIO de la linea: suelto agarra el 'NO.:' de 'TELEFONO TITULAR
#    NO.: 42182908' (fc-claro, un telefono) y el 'NO:' de adentro de 'TURNO: 354877'
#    (2026-07-2q-p01), los dos medidos.
#  · El nombre se elige entre las lineas de la cabecera que parecen un nombre, en este
#    orden:
#    (1) la primera con sufijo societario COMPLETO, m=10. 'SOCIEDAD ANONIMA' pelado no
#        cuenta, porque es la continuacion de la linea anterior. Es la regla que saca el
#        nombre del parqueo (2026-07-1q-p04: sin ella esa pagina cae en '+ REGIHEN', el
#        resto de 'REGIHEN FEL') y la que prefiere la razon social en 2026-03-1q-p02/05/06
#        y 2026-03-1q-p12.
#    (2) la fila del emisor de las FEL nuevas, la que lleva 'Serie ... Numero de DTE', m=12:
#        es el nombre del NEGOCIO y la persona va en la linea de arriba. El controlador fijo
#        que la verdad es el negocio (R31) porque el negocio es el proveedor.
#    (3) la primera y, dentro del grupo de variantes de la misma empresa (mismo primer
#        token), la lectura mas legible, m=1: 2026-07-1q-p08 elige 'GASOLINERA SANTA
#        ROSALIA' sobre 'GASOLINERA SANTA RGSALTA,'.
#    Ademas, una linea sin NINGUNA palabra de 4 letras no es un nombre (m=2: cae 'de ze, a'
#    de 2026-07-2q-p08 y '. 4 . e' de 2026-07-2q-p04, y 'e OTE. - A' de 2026-07-1q-p04 no
#    llega a ser candidata). El corte del rotulo del serie/numero dentro de RX_COLA (m=13
#    solo, m=20 toda la cola) es lo que impide que el nombre sea el rotulo del serie
#    ('SERTE :31819283' en 2026-07-1q-p08) y que las FEL se queden con la cola
#    'Serie: ...'; 'a) HOTEL DEL VALLE FACTURA' conserva el nombre. Lo
#    que no es un nombre (el encabezado del DTE, las direcciones, los codigos de
#    autorizacion, el medio de pago, el NIT) se descarta entero. La puntuacion del borde NO
#    se toca: el papel imprime 'COMBUSTIBLES ENERGETICOS DE GUATEMALA,' con su coma y
#    limpiarla seria inventar.
#  · AVISOS. Un nombre que igual se devuelve pero parece ruido del OCR deja
#    AVISO_NOMBRE_ILEGIBLE (m=2: 2026-03-1q-p11 y 2026-07-2q-p04, las dos sin `nombre`
#    verificado; cada una la enciende una señal distinta de `_nombre_dudoso`). Y la linea
#    de la persona sin sufijo societario deja AVISO_NOMBRE_PERSONA (m=0: defensivo, ninguna
#    de las 57 termina ahi y se pinea con texto propio; desactivando la regla (2) el aviso
#    se enciende en 8 paginas, que es para lo que esta).
RX_CORTE = re.compile(
    r'DATOS\s+DEL\s+(?:COMPRADOR|CERTIFICADOR|POS|RECEPTOR)|NIT\s*Receptor|NIT\s*Cliente|'
    r'Nombre\s+(?:Receptor|Cliente)|Superintendencia|SIDESYS|SIDESY|CERTIFICADOR|'
    r'Certificador\s*:|INFILE|GUATEFACTURAS|AINNOVA|AINNGVA|\bSAT\b', re.I)
RX_NIT = re.compile(r'\bN[.,]?[I1LlAE][.,]?T[.,]?(?:[^\S\n]*Emisor)?[^\S\n]*:?[^\S\n]*'
                    r'([\d][\d\-]{5,})', re.I)
RX_DTE = re.compile(
    r'(?:N[ÚU][SMN]ERO[^\S\n]*DE[^\S\n]*DTE|N[ÚU][SMN]ERO[^\S\n]*FEL|N[ÚU][SMN]ERO|'
    r'Factura[^\S\n]*No|^[^\w\n]*N[eo0][.,]?[^\S\n]*:)'
    r'(?:[^\S\n]*:){0,2}[^\S\n]*([\d][\d\-]{5,})', re.I | re.M)
# Ruido que el OCR pega a la MISMA linea del nombre: se CORTA la cola y la linea sigue
# siendo candidata. El corte en el rotulo del serie/numero es el arreglo del bug.
RX_COLA = (
    RX_CORTE,
    re.compile(r'N[ÚU][SMN]ERO[^\S\n]*DE[^\S\n]*AUTORIZACI', re.I),
    re.compile(r'N[ÚU][SMN]ERO', re.I),
    re.compile(r'(?:R[EÉ]GIMEN|REGI[MN]EN|REGIWEN)[^\S\n]*FEL', re.I),
    re.compile(r'\bSER[I1L]E\b|\bSERTE\b|\bSerie\b[^\S\n]*:', re.I),
    re.compile(r'\bN[.,]?[I1LlAE][.,]?T[.,]?\b', re.I),
    re.compile(r'\bFACTURA\b', re.I),
    re.compile(r'\bFEL\b', re.I),
    re.compile(r'[0-9A-F]{6,}(?:-[0-9A-F]+)+', re.I),
    re.compile(r'\bFECHA\b', re.I),
)
# Lineas que no son un nombre aunque queden limpias. OJO: 'electronico' NO se excluye
# ('RIO ELECTRONICO' de 2026-03-1q-p08 parece el nombre del proveedor) y 'ributari' va sin
# la T porque el OCR imprime 'DOCUMENTO ARIBUTARIO ELECTRONICO'.
RX_BASURA = re.compile(r'ributari|peque[nñ]o\s+contribuyente|^FEL$|comprobante|'
                       r'constancia\s+de|recibo\s+escalonado|^\W*datos\s+del|'
                       r'^(efectivo|contado|tarjeta|visa|mastercard|transferencia|cheque|'
                       r'dep[oó]sito|pago|otros?)$', re.I)
# El rotulo 'DATOS DEL EMISOR' destrozado por el OCR: '7 Dates del Enicors' (2026-07-2q-p12).
RX_ROTULO_ROTO = re.compile(r'\bd[ao]t[oe]s?\b\s+d[e3]l\b', re.I)
# Un correo o una URL no son el nombre del emisor. DEFENSIVA, no medida: mutarla (que no
# matchee nada) no cambia ninguna de las 57 paginas, y se queda porque un renglon con solo
# un correo es plausible en otra rendicion.
RX_CORREO = re.compile(r'@|https?:|www\.|\.com\b|\.gt\b|\.net\b', re.I)
# DEFENSIVA, no medida: mutarla (que no matchee nada) no cambia ninguna de las 57 paginas.
# Se queda porque una direccion que empiece con 'Avenida'/'Colonia' es plausible en otra
# rendicion y el filtro es barato.
RX_DIRECCION = re.compile(r'\b(calle|avenida|avda|colonia|zona|kil[oó]metro|km|carretera|aldea|'
                          r'boulevard|blvd|ruta|edificio|centro\s+comercial|plaza|diagonal|calzada|'
                          r'local|residencial|barrio|col\.)', re.I)
RX_SOLO_SIGNOS = re.compile(r'^[\d\s.,\-_/|:;*#+()\[\]{}=<>"\'`~^\\@$%&!?—–]+$')
# Codigo de autorizacion (un solo token con digitos y guiones, como
# 'ADODBAFO-1577-40F1-ADED-12E3544E71E3'): no es un nombre.
RX_CODIGO = re.compile(r'^\S*\d\S*-\S+$')
RX_PALABRA = re.compile(r'[^\W\d_]+')
RX_VOCAL = re.compile(r'[aeiouáéíóúü]', re.I)
# Sufijo societario: para que cuente tiene que haber un NOMBRE antes del sufijo, porque
# 'SOCIEDAD ANONIMA' pelado es la continuacion de la linea de arriba.
RX_SUFIJO = re.compile(r'\bS\.?\s?A\.?\b|\bSOCIEDAD\s+AN[OÓ]NIMA\b|\bLTDA\b|'
                       r'\bS\.\s?DE\s?R\.?\s?L', re.I)
# Fila del emisor de las FEL nuevas: la serie y el numero de DTE en la MISMA linea. Las
# dos partes son necesarias: 'SERIE' suelto tambien aparece en renglones que no son el
# nombre (2026-07-2q-p04 tiene '... BAJA VERAPAZ _ SERIE "y').
RX_FILA_EMISOR = re.compile(r'SER[I1L]E\b[^\n]{0,40}N[ÚU][SMN]ERO[^\S\n]*DE[^\S\n]*DTE|'
                            r'SERIE[^\S\n]*DE[^\S\n]*DOCUMENTO', re.I)
# Rotulo del nombre que el OCR deja pegado adelante: 'Nombre comercial: Regus ...'.
RX_ROTULO_NOMBRE = re.compile(r'^\W*(?:nombre\s+comercial|nombre|raz[oó]n\s+social|emisor)\W*:\s*',
                              re.I)
# Token que mezcla letras y digitos ('-ora3ip'): no es una palabra de un nombre.
RX_MEZCLA = re.compile(r'\b(?=[^\W_]*\d)(?=[^\W_]*[^\W\d_])[^\W_]{2,}\b')
# La linea de la persona en las FEL nuevas lleva el rotulo de la autorizacion.
RX_AUTORIZACION = re.compile(r'AUTORIZACI', re.I)

AVISO_SIN_NOMBRE = 'no se encontro el nombre del emisor'
AVISO_SIN_NIT = 'no se encontro el NIT del emisor'
AVISO_SIN_DTE = 'no se encontro el numero de DTE'
AVISO_DTE_IGUAL_NIT = 'el unico numero rotulado como DTE es el NIT del emisor: no se tomo'
AVISO_NOMBRE_ILEGIBLE = 'el nombre del emisor parece ilegible: revisalo contra el papel'
AVISO_NOMBRE_PERSONA = ('el nombre leido parece el de la persona y no el del negocio: '
                        'revisalo contra el papel')


def _digitos(valor):
    """Solo los digitos de un valor: '7027581-5' y '70275815' son el mismo NIT."""
    return ''.join(c for c in str(valor or '') if c.isdigit())


def _limpia_nombre(linea):
    """Linea sin la cola de rotulo que el OCR le pego, o vacia si era solo el rotulo.

    Solo se recorta el ESPACIO de los bordes: la puntuacion que el papel imprime se deja
    como esta (ver la nota de las reglas, arriba). El rotulo del nombre pegado ADELANTE
    ('Nombre comercial: Regus ...') si se saca, porque no es parte del nombre.
    """
    limpio = (linea or '').strip()
    for rx in RX_COLA:
        m = rx.search(limpio)
        if m:
            limpio = limpio[:m.start()]
    return RX_ROTULO_NOMBRE.sub('', limpio).strip()


def _palabras(nombre):
    """Palabras de solo letras del nombre (los digitos y simbolos no son palabras)."""
    return RX_PALABRA.findall(nombre or '')


def _es_nombre(limpio):
    """True si la linea limpia todavia parece el nombre de una empresa o persona.

    Se pide al menos UNA palabra de 4 letras: con menos, lo que queda es ruido del OCR
    ('e OTE. - A', 'de ze, a', '. 4 . e').
    """
    if len(limpio) < 4 or not [p for p in _palabras(limpio) if len(p) >= 4]:
        return False
    if RX_SOLO_SIGNOS.match(limpio) or RX_CODIGO.match(limpio):
        return False
    if RX_BASURA.search(limpio) or RX_ROTULO_ROTO.search(limpio):
        return False
    if RX_DIRECCION.search(limpio) or RX_CORREO.search(limpio):
        return False
    if RX_NIT.search(limpio):
        return False
    return True


def _sufijo_completo(limpio):
    """True si el nombre trae sufijo societario CON nombre antes.

    'CAPPU, SOCIEDAD ANONIMA' si; 'SOCIEDAD ANONIMA' pelado no, porque es la continuacion
    de la linea anterior (2026-03-1q-p01 y 2026-07-1q-p08 imprimen el nombre cortado).
    """
    m = RX_SUFIJO.search(limpio)
    return bool(m and _palabras(limpio[:m.start()]))


def _legibilidad(nombre):
    """Minima proporcion de vocales por palabra de 3+ letras (0.0 si no hay ninguna).

    El OCR come vocales en la palabra que destroza: 'RGSALTA' tiene 2 de 7 y 'ROSALIA' 4.
    """
    ratios = [len(RX_VOCAL.findall(p)) / float(len(p))
              for p in _palabras(nombre) if len(p) >= 3]
    return min(ratios) if ratios else 0.0


def _mejor_variante(candidatos):
    """El primer candidato, salvo que otra linea de la MISMA empresa se lea mejor.

    'Misma empresa' = mismo primer token. Es lo que elige 'GASOLINERA SANTA ROSALIA' sobre
    'GASOLINERA SANTA RGSALTA,' en 2026-07-1q-p08, sin tocar 2026-07-1q-p01 (donde la
    primera lectura, 'COMBUSTIBLES ENERGETICOS DE GUATEMALA,', ya es la buena).
    """
    clave = (_palabras(candidatos[0][1]) or [candidatos[0][1]])[0].lower()
    grupo = [c for c in candidatos if (_palabras(c[1]) or [c[1]])[0].lower() == clave]
    return max(grupo, key=lambda c: (_legibilidad(c[1]), -candidatos.index(c)))


def _nombre_dudoso(nombre):
    """True si el nombre parece ruido del OCR: se devuelve igual, pero CON aviso.

    DOS señales, cada una con la pagina que la enciende: un token que mezcla letras y
    digitos ('-ora3ip' de 2026-07-2q-p04) y mas de la mitad de las letras repartidas en
    palabras de 1 o 2 (': ae a ae Emisor Ac ae ae :' de 2026-03-1q-p11). Un umbral de
    "menos de N letras" se probo y NO se dejo: no cambiaba ninguna de las 57 y una empresa
    con nombre corto ('REGUS') no tiene por que quedar marcada.
    """
    if RX_MEZCLA.search(nombre):
        return True
    letras = sum(len(p) for p in _palabras(nombre))
    cortas = sum(len(p) for p in _palabras(nombre) if len(p) <= 2)
    return cortas * 2 > letras


def _nombre_persona(nombre, linea):
    """True si el nombre elegido es la linea de la PERSONA y no la del negocio.

    DEFENSIVO, no medido: ninguna de las 57 paginas termina eligiendo una linea asi (la
    preferencia por la fila del emisor la deja fuera), asi que se pinea con texto propio.
    La señal es la linea del rotulo de autorizacion SIN sufijo societario: el rotulo solo
    no alcanza, porque en fc-almacenadora / fc-consolidados / fc-vesco el nombre del
    NEGOCIO tambien viene en una linea con 'NUMERO DE AUTORIZACION'.
    """
    return bool(RX_AUTORIZACION.search(linea) and not _sufijo_completo(nombre))


def emisor(texto):
    """Nombre, NIT y numero de DTE del emisor, mas la lista de avisos.

    Devuelve {'nombre': str, 'nit': str, 'dte': str, 'avisos': [str, ...]}. Cada campo
    que no se puede determinar viene VACIO y deja su aviso: nunca se completa con un valor
    plausible (el mismo contrato de `total()` y `fecha()`, con la lista en vez del segundo
    elemento de la tupla porque aca son tres campos). La Task 7 tiene que mostrar los
    avisos al operador.

    El 'dte' nunca es igual al 'nit': si el unico numero rotulado como numero de documento
    es el NIT del emisor, no se devuelve y queda el aviso. Y un nombre que se devuelve pero
    parece ruido del OCR (o que es la linea de la persona y no la del negocio) tambien deja
    su aviso: un nombre mal leido no puede pasar en silencio.
    """
    t = texto or ''
    cabecera = []
    for linea in t.splitlines():
        if RX_CORTE.search(linea):
            break
        cabecera.append(linea)
    nit = ''
    for m in RX_NIT.finditer('\n'.join(cabecera)):
        nit = m.group(1).strip()
        break
    candidatos_dte = [m.group(1).strip() for m in RX_DTE.finditer(t)]
    dte = ''
    for candidato in candidatos_dte:
        if _digitos(candidato) and _digitos(candidato) != _digitos(nit):
            dte = candidato
            break
    candidatos = [(linea, _limpia_nombre(linea)) for linea in cabecera]
    candidatos = [(linea, limpio) for linea, limpio in candidatos if _es_nombre(limpio)]
    nombre, linea_nombre = '', ''
    if candidatos:
        elegido = next((c for c in candidatos if _sufijo_completo(c[1])), None)
        if elegido is None:
            elegido = next((c for c in candidatos if RX_FILA_EMISOR.search(c[0])), None)
        if elegido is None:
            elegido = _mejor_variante(candidatos)
        linea_nombre, nombre = elegido
    avisos = []
    if not nombre:
        avisos.append(AVISO_SIN_NOMBRE)
    elif _nombre_dudoso(nombre):
        avisos.append(AVISO_NOMBRE_ILEGIBLE)
    elif _nombre_persona(nombre, linea_nombre):
        avisos.append(AVISO_NOMBRE_PERSONA)
    if not nit:
        avisos.append(AVISO_SIN_NIT)
    if dte:
        pass
    elif any(_digitos(c) and _digitos(c) == _digitos(nit) for c in candidatos_dte):
        avisos.append(AVISO_DTE_IGUAL_NIT)
    else:
        avisos.append(AVISO_SIN_DTE)
    return {'nombre': nombre, 'nit': nit, 'dte': dte, 'avisos': avisos}


# ------------------------------------------------------------
# Preprocesado del texto superpuesto
# ------------------------------------------------------------
# La funcion vivia en `parser.py` (que no se puede importar sin `config` y sin OCR) y se
# muda aca porque `parsear()` tiene que aplicar EL MISMO preprocesado antes de leer: los
# patrones del modulo estan medidos sobre el texto ya limpio. `parser.py` la re-exporta
# para los consumidores que la importan de ahi (`modules/cxp/__init__.py`): ese re-export
# es un SUPERVIVIENTE DE MUTANTE POR DISENO (quitarlo no rompe ningun test, porque el
# unico consumidor es `modules/cxp/__init__.py`, que no se puede importar sin Flask), y
# se queda a proposito.
# Medido con _investigacion_gt/184_medir_dedup_nombres.py sobre las 57 (DOS magnitudes
# distintas, no mezclar):
#  · el EFECTO PROPIO de la regla entregada (colapsar corridas de 3+ letras): reescribe
#    16 lineas en 12 paginas de las fixtures, y sobre el corpus es INERTE: `parsear()`
#    devuelve lo mismo con el dedup 3+ que sin el (m=0 campos);
#  · la DIFERENCIA con la regla 2+ de la Task 7: 220 lineas en 54 paginas, que es lo que
#    la 2+ hacia DE MAS. Ese de mas se comia la doble letra legitima del nombre del
#    emisor: el payload cambia SOLO en `nombre`, en 13 paginas, y de los 15 nombres
#    verificados la 2+ leia 11 y la 3+ lee 15.
# Se aplica igual porque es parte del contrato de `parse_fel_page` y la pantalla recibe
# tambien texto de OCR, que no pasa por ahi. El canario del nombre es
# `test_la_doble_letra_del_nombre_sobrevive_a_la_limpieza`.
def limpiar_texto_superpuesto(text):
    """Limpia texto con capas superpuestas."""
    if not text:
        return ""

    def reconstruir_total(t):
        lines = t.split('\n')
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.search(r'TOTAL[:\s]*$', line.strip(), re.I):
                fragmentos = []
                j = i + 1
                while j < len(lines) and j < i + 15:
                    frag = lines[j].strip()
                    if re.match(r'^[Q\d\.,]+$', frag):
                        fragmentos.append(frag)
                        j += 1
                    else:
                        break
                if fragmentos:
                    joined = ''.join(fragmentos).replace('QQ', 'Q').replace('Q.Q.', 'Q.')
                    result.append(line.strip() + ' ' + joined)
                    i = j
                    continue
            result.append(line)
            i += 1
        return '\n'.join(result)

    text = reconstruir_total(text)
    lines = text.split('\n')
    dup_count = sum(1 for l in lines if re.search(r'(.)\1{1,}', l) and len(l) > 4)
    if dup_count < max(3, len(lines) * 0.15):
        return text
    cleaned_lines = []
    for line in lines:
        if re.search(r'(.)\1', line) and len(line) > 4:
            # El colapso es de corridas de TRES o mas letras repetidas, no de dos: con
            # `\1+` (Task 7) la limpieza se comia la doble letra legitima del nombre del
            # emisor. Medido con `_investigacion_gt/184_medir_dedup_nombres.py` sobre las
            # 57: esta regla reescribe 16 lineas en 12 paginas (y es inerte para `parsear()`
            # en el corpus); la 2+ cambiaba ademas otras 220 lineas en 54 paginas y dejaba
            # 4 de los 15 nombres verificados sin su nombre del papel ('a) HOTEL DEL VALE'
            # por VALLE, 'POLO CAMPERO' por POLLO, 'CAPU' por CAPPU y 'HOTEL SLEP-IN WVJ'
            # por SLEEP-INN). El canario es
            # `test_la_doble_letra_del_nombre_sobrevive_a_la_limpieza`.
            dedup = re.sub(r'([A-Za-záéíóúÁÉÍÓÚñÑ])\1{2,}', r'\1', line)
            cleaned_lines.append(dedup)
        else:
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


def _descripcion_auto(texto):
    """Descripcion del gasto para las cuentas automaticas (regla de la etapa 3).

    Se muda tal cual desde `parser.py`: la pantalla la usa para elegir la cuenta cuando el
    concepto no la fija (`render.js` -> `cuentaAutoDesdeDesc(f.descripcion_auto)`) y no
    tiene nada que ver con los campos del DTE.
    """
    try:
        if re.search(r'cargo[s]?\s+moratori|inter[eé]s?\s+por\s+cargo', texto, re.I):
            return 'Cargos moratorios e intereses por pago fuera de termino'
        if re.search(r'(?:^|\n)\s*(?:SERVICIO\s+)?Oficina\s*[-–]|alquiler\s+de\s+oficina', texto, re.I):
            m_per = re.search(r'[Oo]ficina[^\n]*\n\s*\((\d{2})/(\d{2})/(\d{4})\s*[-–]\s*\d{2}/(\d{2})/(\d{4})\)', texto)
            if m_per:
                return 'Alquiler oficina %s/%s' % (m_per.group(4), m_per.group(5))
            todos = re.findall(r'\d{2}/\d{2}/\d{4}\s*[-–]\s*\d{2}/(\d{2})/(\d{4})', texto)
            return 'Alquiler oficina %s/%s' % (todos[-1][0], todos[-1][1]) if todos \
                else 'Alquiler oficina'
        if re.search(r'subarrendamiento\s+bodega|cargo\s+admin.*bodega', texto, re.I):
            m_per = re.search(r'[Dd]e\s+\d{1,2}/(\d{2})/(\d{4})\s+a\s+\d{1,2}/\d{2}/\d{4}', texto)
            return 'Alquiler bodega %s/%s' % (m_per.group(1), m_per.group(2)) if m_per \
                else 'Alquiler bodega'
    except Exception:
        pass
    return ''


# ------------------------------------------------------------
# parsear(): el contrato de salida del modulo puro
# ------------------------------------------------------------
# Es lo que devolvia `parser.parse_fel_page` (todas sus claves) MAS `avisos` y
# `imp_especial_origen`; `parser.parse_fel_page` ahora delega aca. El `parsear(text or '')`
# del parser es un SUPERVIVIENTE DE MUTANTE EQUIVALENTE por diseno: `parsear(None)` y
# `parsear('')` devuelven el mismo primer return, asi que ningun test puede distinguirlos
# (lo midio la revision de la Task 7, mutante `S`).
#
# El bloque de impuestos es el de la ETAPA 3 (`modules/cxp/impuestos.calcular_impuestos`,
# la regla que aprobo el usuario), con sus cuatro caminos: `total <= 0` -> todo 0; FCC ->
# el total es el bruto y no se separa nada; tipo '' (sin leyenda y sin IVA impreso) -> no
# se calcula IVA y lo elige el operador; FCP -> base = (total - especial)/1,12 y, si hay
# IVA impreso > 0, el IVA impreso manda y la base se recalcula con el. La aritmetica queda
# DUPLICADA a proposito: `calcular_impuestos` saca el especial del detector viejo (sin la
# recuperacion de la Task 5) y no tiene parametro para inyectarlo, y este modulo es stdlib
# puro por diseno (spec 3.1): lo verifica `TestPureza.test_el_modulo_es_stdlib_puro`
# en `tests/test_cxp_campos.py`, con la lista blanca explicita de la stdlib, asi que no
# importa modulos de la app. La red contra la divergencia es el test de equivalencia
# sobre las 57 paginas.
#
# Dos diferencias deliberadas respecto de `calcular_impuestos`:
#  · el tipo sale de `tipo_con_iva()` (la leyenda del papel y, si NO hay leyenda, el IVA
#    impreso > 0 -> FCP: es la D4 de la spec), no de `detectar_tipo()`;
#  · el especial sale de `especial()` (rotulo + recuperacion desde el total) y su origen
#    viaja en `imp_especial_origen` para que la pantalla lo muestre.
RX_MONEDA_USD = re.compile(r'Moneda[:\s]+USD|USD\s*-\s*Dolar', re.I)
# El control de cierre: con el IVA impreso mandando sobre la base calculada (camino FCP),
# `base + IVA + especial = total` es la unica verificacion que queda. La tolerancia es la
# misma del modulo (`cierra`), que acepta el centavo que el papel redondea distinto: el
# caso testigo imprime 19.68 donde la regla da 19.67 y NO tiene que avisar (m=57: 57
# paginas medidas, 0 falsos avisos, con _investigacion_gt/165_probar_parsear.py).
AVISO_CIERRE = 'el IVA impreso no cierra con la base calculada: revisar la factura'


def parsear(texto):
    """Los campos de una factura FEL leidos del texto, mas la lista de avisos.

    Devuelve todas las claves de `parse_fel_page` (`tipo`, `aviso_tipo`, `total`, `fecha`,
    `nit_emisor`, `nombre_emisor`, `numero_dte`, `imp_especial`, `base_imponible`,
    `imp_bruto`, `imp_iva`, `tasa_iva`, `descripcion_auto`, `moneda`) mas:
      · `avisos`: los avisos de cada campo (`total`, `fecha`, `tipo`, `especial`, `emisor`)
        y el control de cierre cuando el IVA impreso no cierra con la base calculada;
      · `imp_especial_origen`: 'rotulo' | 'recuperado' | '' (de donde salio el especial).

    Los dos returns tempranos de `parse_fel_page` conservan su forma: texto vacio o de
    menos de 10 caracteres -> solo el error, el tipo sin definir y los ceros; texto sin
    lineas utiles -> el diccionario completo con los ceros y el placeholder del nombre
    (es una cadena de pantalla, no un dato leido: cambiarla es de la Task 8).
    """
    if not texto or len(texto.strip()) < 10:
        return {'error': 'No se pudo extraer texto', 'tipo': '',
                'aviso_tipo': 'sin leyenda de tipo: elegi FCP o FCC',
                'imp_especial': 0, 'base_imponible': 0,
                'avisos': ['no se pudo extraer texto de la pagina']}
    t = limpiar_texto_superpuesto(texto)
    if not [l for l in t.split('\n') if l.strip()]:
        return {'tipo': '', 'aviso_tipo': 'sin leyenda de tipo: elegi FCP o FCC',
                'moneda': 'PS', 'total': 0, 'imp_bruto': 0, 'imp_iva': 0,
                'imp_especial': 0, 'base_imponible': 0, 'tasa_iva': 12, 'fecha': '',
                'numero_dte': '', 'nit_emisor': '',
                'nombre_emisor': 'PROVEEDOR NO IDENTIFICADO', 'descripcion_auto': '',
                'imp_especial_origen': '',
                'avisos': ['la pagina no tiene lineas utiles: no se pudo leer ningun campo']}

    avisos = []
    valor_total, aviso = total(t)
    if aviso:
        avisos.append(aviso)
    valor_fecha, aviso = fecha(t)
    if aviso:
        avisos.append(aviso)
    valor_tipo, aviso_tipo = tipo_con_iva(t)
    if aviso_tipo:
        avisos.append(aviso_tipo)
    iva = iva_impreso(t)
    valor_especial, origen, aviso_especial = especial(t, valor_total, iva=iva)
    if aviso_especial:
        avisos.append(aviso_especial)
    emi = emisor(t)
    avisos.extend(emi['avisos'])

    # `total()` devuelve None cuando no encontro el total en una linea etiquetada (y 0.0
    # cuando el papel imprime cero): los dos se tratan igual recien aca, DESPUES de que
    # `especial()` vio el valor original (su guarda `valor < total` distingue None de 0, y
    # sin total no puede aceptar el rotulo: un codigo de la linea se leeria como impuesto).
    monto = float(valor_total or 0)
    imp_especial = float(valor_especial or 0)
    origen = origen or ''
    base = bruto = iva_calculado = 0.0
    tasa = 0
    if monto <= 0:
        # Sin datos no hay nada que calcular (y no se inventa).
        imp_especial, origen = 0, ''
    elif valor_tipo == 'FCC':
        # En FCC el total ES el bruto y no se separa nada, aunque `especial()` haya leido
        # el rotulo (`especial()` no recibe el tipo, asi que la Task 5 dejo anotado que el
        # 0 lo tiene que forzar quien compone el alta). El aviso del especial se apaga: no
        # hay nada que revisar en un impuesto que este regimen no separa.
        imp_especial, origen, base, bruto = 0, '', monto, monto
        if aviso_especial:
            avisos.remove(aviso_especial)
    else:
        if imp_especial >= monto:
            imp_especial, origen = 0, ''   # el dato no puede ser mayor que la factura
        subtotal = round(monto - imp_especial, 2)
        if not valor_tipo:
            # Sin leyenda y sin IVA impreso no se puede saber si es FCP o FCC (el tipo ''
            # NO es "sin argumento"): no se calcula IVA y lo elige el operador. Aca la tasa
            # queda en 0 y NO en 12: el tipo no esta definido, asi que la pantalla no puede
            # mostrar una tasa que nadie eligio (el payload viejo ponia 12 porque asumia
            # FCP; la D4 lo saco).
            base, bruto = subtotal, monto
        else:
            # FCP, con o sin IVA impreso: 12 es la tasa del regimen, y el IVA impreso (si
            # hay) solo decide su importe, no la tasa.
            tasa = 12
            base = round(subtotal / 1.12, 2)
            iva_calculado = round(subtotal - base, 2)
            if iva and iva > 0:
                # El IVA impreso manda: la base se recalcula con el para que la suma cierre.
                iva_calculado = round(float(iva), 2)
                base = round(subtotal - iva_calculado, 2)
            bruto = round(base + imp_especial, 2)
            if iva and iva > 0 and not cierra(monto, imp_especial, iva_calculado):
                avisos.append(AVISO_CIERRE)

    return {'tipo': valor_tipo, 'aviso_tipo': aviso_tipo,
            'moneda': 'DL' if RX_MONEDA_USD.search(t) else 'PS',
            'total': monto, 'imp_bruto': bruto, 'imp_iva': iva_calculado,
            'imp_especial': imp_especial, 'base_imponible': base, 'tasa_iva': tasa,
            'fecha': valor_fecha, 'numero_dte': emi['dte'], 'nit_emisor': emi['nit'],
            'nombre_emisor': emi['nombre'] or 'PROVEEDOR NO IDENTIFICADO',
            'descripcion_auto': _descripcion_auto(t),
            'avisos': avisos, 'imp_especial_origen': origen}
