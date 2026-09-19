# modules/shared/update_politica.py
# Decisiones del updater. Stdlib puro (solo `time`): no importa Flask, `config`
# ni `modules.shared`, asi se testea sin app y sin red. `app.py` orquesta.
"""Politica de actualizaciones: cuando aplicar sola, cuando reiniciar y que
estado dejar. Todo lo que se pueda decidir sin tocar el disco ni la red vive
aca, para poder testearlo (mismo criterio que los servicios de Stock y CxP)."""
import time

MAX_INTENTOS = 3
# Estados que el frontend interpreta como "actualizacion en curso".
ESTADOS_EN_CURSO = ('descargando', 'instalando', 'reiniciando')
# Estados de exito: son los unicos que escriben `aplicada_en`.
ESTADOS_EXITO = ('completado', 'aplicada_sin_reinicio')


def _rutas(archivos_descargados):
    """Normaliza la lista de `descargar_archivos_diferenciales` (dicts con
    'path' o strings) a rutas con barra normal."""
    salida = []
    for entrada in archivos_descargados or []:
        if isinstance(entrada, dict):
            ruta = entrada.get('path')
        else:
            ruta = entrada
        if ruta:
            salida.append(str(ruta).replace('\\', '/'))
    return salida


def requiere_reinicio_del_diff(rutas):
    """True si entre las rutas hay algun `.py`.

    Es la regla compartida: la usa el pipeline para escribir
    `requires_restart` y el cliente para decidir si relanza.

    Normaliza con `_rutas` (acepta dicts `{'path': ...}` y strings, y las dos
    barras): es la misma forma que devuelve `descargar_archivos_diferenciales`, y
    antes un dict se evaluaba por su `repr` (`"{'path': 'app.py'}"` no termina en
    `.py`) y respondia que NO habia que reiniciar. El pipeline ya normalizaba
    antes de llamar, asi que el error estaba latente del lado del cliente.
    """
    return any(r.endswith('.py') for r in _rutas(rutas))


def necesita_reinicio(requires_restart, archivos_descargados):
    """Si hay que relanzar la app para que el cambio tenga efecto.

    Manda lo que REALMENTE se bajo: un `.py` obliga aunque el canal declare
    `requires_restart: false` (fail-safe: reiniciar de mas es barato, ejecutar
    codigo nuevo a medias no). Si no hay `.py`, se respeta lo que declare el
    canal; y si no se bajo **nada** (el disco ya estaba al dia: solo cambio la
    version declarada), no hay nada que reiniciar.
    """
    rutas = _rutas(archivos_descargados)
    if not rutas:
        return False
    if requiere_reinicio_del_diff(rutas):
        return True
    return bool(requires_restart)


def decidir_aplicacion(version_remota, estado_previo, arranque_por_actualizacion,
                       max_intentos=MAX_INTENTOS):
    """(aplicar, motivo): si este arranque debe aplicar la actualizacion solo.

    Motivos: 'aplicar', 'sin_version', 'arranque_por_actualizacion',
    'intentos_agotados'.
    """
    if not version_remota:
        return False, 'sin_version'
    if arranque_por_actualizacion:
        return False, 'arranque_por_actualizacion'
    intentos = (estado_previo or {}).get('intentos') or {}
    if int(intentos.get(version_remota) or 0) >= max_intentos:
        return False, 'intentos_agotados'
    return True, 'aplicar'


def estado_a_guardar(estado_previo, resultado, version=None, mensaje='', error=None,
                     archivos=0, origen=None, cuando=None):
    """Forma completa de `update_status.json`, conservando lo que ya estaba.

    - `intentos` cuenta solo los fallos y solo de la version en curso: cuando
      aparece una version nueva el contador arranca de cero (si no, una version
      que falla en esta PC bloquearia para siempre a las siguientes).
    - `origen` conserva el anterior si no se pasa (asi el estado que escribe
      `resolver_resultado_relanzamiento` no pierde que fue automatica).
    - `aplicada_en` se escribe en los exitos y se conserva despues.
    """
    previo = dict(estado_previo or {})
    intentos = dict(previo.get('intentos') or {})
    if version and version not in intentos:
        intentos = {}
    if resultado == 'error' and version:
        intentos[version] = int(intentos.get(version) or 0) + 1

    datos = {
        'estado': resultado,
        'mensaje': mensaje,
        'version': version,
        'error': error,
        'archivos': archivos,
        'origen': origen or previo.get('origen') or 'manual',
        'intentos': intentos,
        'timestamp': time.time(),
    }
    if resultado in ESTADOS_EXITO:
        datos['aplicada_en'] = cuando or time.strftime('%Y-%m-%d %H:%M:%S')
    elif previo.get('aplicada_en'):
        datos['aplicada_en'] = previo['aplicada_en']
    return datos


def backups_a_borrar(nombres, maximo=5):
    """De una lista de backups, los que sobran (los mas viejos).

    El nombre es `YYYYmmdd_HHMMSS`, asi que el orden alfabetico es cronologico:
    no hace falta parsear fechas.
    """
    ordenados = sorted([n for n in (nombres or []) if n], reverse=True)
    return ordenados[maximo:]
