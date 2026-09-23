# modules/reportes/services/ventas_manuales_base.py
# ============================================================
# VENTAS MANUALES: QUÉ BASE — DECISIÓN PURA (23/09/2026)
# ============================================================
# Este módulo es **stdlib puro**: no importa NADA de la app (ni `config`, ni
# `pyodbc`, ni `pandas`) ni siquiera dentro de las funciones. Todo lo que la
# decisión necesita entra por PARÁMETRO. Por eso se testea por ruta
# (`tests/test_ventas_manuales_base.py` + `tests/cargar_servicio.py`) y por eso
# se puede correr desde un cwd sin `.env.local` sin que el proceso muera.
#
# (Antes este módulo hacía `from config import BASES_DISPONIBLES` dentro de un
# `try/except Exception`: `config.py` termina en `sys.exit(1)` cuando falta el
# entorno, y `SystemExit` NO es `Exception`, así que el "módulo puro" mataba el
# proceso. Ahora el catálogo lo pasa el llamador; ver `catalogo` abajo.)
#
# POR QUÉ EXISTE
# --------------
# La tabla `VENTAS_MANUALES` es única para todos los países y todas las PCs. El
# 17/09/2026 se arregló que todas las operaciones ignoraran la base activa, pero
# la base canónica se resolvía como
#   `VENTAS_MANUALES_BASE` (env) -> `BASE_DEFAULT` de la instalación -> primera
#   base permitida.
# `BASE_DEFAULT` sale del `.env.local` de CADA PC (`config.BASE_DEFAULT`), así que
# una máquina con otro default escribía en OTRA tabla y sus ventas dejaban de
# verse desde el resto: el bug original, en silencio y con un warning en el log.
#
# Ahora la canónica es una CONSTANTE DE ESTE CÓDIGO (igual en todas las
# instalaciones, sin tocar ningún `.env.local`) y el usuario decidió qué pasa
# cuando su usuario no la alcanza:
#   · ESCRIBIR sin permiso -> ERROR con mensaje claro (nunca una venta en una
#     tabla que los demás no ven);
#   · LEER sin permiso -> sigue funcionando contra la base anterior, con AVISO.
#
# El override por variable de entorno queda como cambio de despliegue explícito
# (mover la canónica de servidor): `.env.ejemplo` lo documenta.

import logging

logger = logging.getLogger(__name__)

# ============================================================
# LA BASE CANÓNICA
# ============================================================
# Una sola tabla `VENTAS_MANUALES` para TODAS las PCs: si cada instalación
# eligiera su base por `.env.local`, dos PCs podrían escribir en dos tablas
# distintas y cada una vería sólo la mitad de las ventas (es el bug que este
# cambio cierra). Por eso la canónica vive acá, en el código, y no en el entorno:
# es la misma en todas las instalaciones por construcción, no por coincidencia.
# Para moverla hay que tocar este archivo y publicar: es a propósito.
BASE_CANONICA_VENTAS_MANUALES = 'plataforma_rd'

# Texto aprobado por el usuario (23/09/2026). Es lo que ve el operador cuando
# intenta guardar sin acceso a la canónica: dice QUÉ pasa, CUÁL es la base y QUÉ
# tiene que hacer, porque este error va directo a la pantalla.
MENSAJE_SIN_PERMISO = (
    'No se puede guardar la venta manual: tu usuario no tiene acceso a la base '
    'donde viven las ventas manuales (plataforma_rd). Pedile al administrador '
    'que te habilite esa base; si se guardara en otra, los demás usuarios no la '
    'verían.'
)


def _conocida(catalogo, base):
    """True si `base` tiene valor y es una base del catálogo.

    `catalogo is None` = NO verificar (modo relajado, ver `resolver`).
    """
    if catalogo is None:
        return bool(base)
    return bool(base) and base in catalogo


def _aviso_lectura(canonica, base, permitidas):
    """Aviso de que la LECTURA sigue contra otra base que la canónica.

    El llamador lo emite SÓLO cuando `base != canonica` (ver `resolver`): si la
    lectura termina en la canónica —porque el `BASE_DEFAULT` de la PC es la
    canónica— no hay nada que avisar, y avisar sería mentir ("no es la tabla
    compartida" cuando sí lo es).
    """
    return (
        'Ventas manuales: este usuario no alcanza la base canónica (%s) para '
        'escribir; la LECTURA sigue contra %s, que NO es la tabla compartida, así '
        'que puede faltar data. Bases permitidas: %s'
        % (canonica, base,
           'todas' if permitidas is None else (', '.join(permitidas) or 'ninguna')))


def resolver(permitidas, base_default, override=None, escritura=False, catalogo=None):
    """Decide la base de `VENTAS_MANUALES` y devuelve `(base, error, aviso)`.

    Entradas (las junta el llamador, `utils.base_ventas_manuales`):

    - `permitidas`: bases que el usuario de la sesión puede usar, o `None` si son
      TODAS (sin sesión, tarea de fondo, superadmin o `'*'`). Lista vacía = ninguna.
    - `base_default`: el `BASE_DEFAULT` de ESTA instalación (sale del `.env.local`
      de la PC). Puede venir vacío o fuera del catálogo: no se asume nada.
    - `override`: `VENTAS_MANUALES_BASE` (variable de entorno), o `None`.
    - `escritura`: `True` para crear/borrar/importar/asegurar tabla, `False` para leer.
    - `catalogo`: el catálogo de bases de la instalación (`config.BASES_DISPONIBLES`,
      un dict/iterable de nombres) o `None` = **no verificar** (modo relajado: los
      nombres se aceptan tal cual). Este módulo NO lo importa: lo pasa el llamador.
      `None` no es lo mismo que `{}`: un catálogo **vacío** no conoce ninguna base.

    Orden de decisión (el del brief aprobado, en ese orden):

    1. `override` si viene y es conocido -> `(override, None, None)`.
    2. la CANÓNICA si el usuario la alcanza (`permitidas is None` = todas) y la
       canónica existe en el catálogo -> `(canonica, None, None)`.
    3. ESCRIBIR sin permiso (o canónica fuera del catálogo)
       -> `(None, MENSAJE_SIN_PERMISO, None)`: la escritura NO cae a otra base.
    4. LEER sin permiso -> `(base_default, None, aviso)` si el default es conocido;
       si no, la primera permitida conocida; si no hay ninguna, `(base_default,
       None, aviso)` igual: el error real lo da la conexión, que es donde
       corresponde.

    Sobre `base`: sólo es `None` cuando hay que fallar (caso 3) **o cuando el
    `base_default` de la lectura viene vacío/`None` y no hay ninguna permitida
    conocida** (caso 4, última línea: devuelve ese valor tal cual, sin `error`).
    Ese caso no se da en producción —`config.BASE_DEFAULT` siempre es una base
    válida— pero el contrato escrito es éste: "si no hay `error`, se intenta
    conectar con lo que devuelva `base`".
    """
    canonica = BASE_CANONICA_VENTAS_MANUALES
    canonica_conocida = _conocida(catalogo, canonica)
    alcanza_canonica = permitidas is None or canonica in permitidas

    # 1. Override explícito: gana sobre todo, pero sólo si es una base conocida.
    override = (override or '').strip()
    if override:
        if _conocida(catalogo, override):
            return override, None, None
        # Un override fuera del catálogo se IGNORA (una variable mal escrita no
        # puede romper la carga) pero se grita en el log: alguien quiso mover la
        # canónica y no lo logró.
        logger.warning(
            'VENTAS_MANUALES_BASE="%s" no está en el catálogo de bases; se '
            'ignora y se sigue el orden normal' % override)

    # 2. La canónica: la misma en todas las instalaciones, sin depender de la base
    #    activa, del país ni del `.env.local` de la PC.
    if canonica_conocida and alcanza_canonica:
        return canonica, None, None

    # 3. Escribir sin alcanzar la canónica: se falla, con mensaje claro. Devolver
    #    otra base acá es exactamente el bug que este cambio cierra.
    if escritura:
        return None, MENSAJE_SIN_PERMISO, None

    # 4. Leer: se sigue como antes (red de seguridad) y se avisa.
    if _conocida(catalogo, base_default):
        return base_default, None, _aviso_si_no_es_canonica(canonica, base_default,
                                                            permitidas)
    for base in (permitidas or []):
        if base and base != canonica and _conocida(catalogo, base):
            return base, None, _aviso_lectura(canonica, base, permitidas)
    logger.error('Ventas manuales: no hay ninguna base utilizable para leer; '
                 'se usa %r' % (base_default,))
    return base_default, None, _aviso_si_no_es_canonica(canonica, base_default,
                                                        permitidas)


def _aviso_si_no_es_canonica(canonica, base, permitidas):
    """El aviso de lectura SÓLO si se lee de una base distinta de la canónica.

    Si la lectura termina en la canónica (el `BASE_DEFAULT` de la PC puede serla),
    no hay nada que avisar: el aviso diría que se lee de una base que NO es la
    tabla compartida cuando sí lo es.
    """
    if base == canonica:
        return None
    return _aviso_lectura(canonica, base, permitidas)
