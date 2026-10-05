# modules/shared/update_politica.py
# Decisiones del updater. Stdlib puro (solo `os` y `time`): no importa Flask, `config`
# ni `modules.shared`, asi se testea sin app y sin red. `app.py` orquesta.
"""Politica de actualizaciones: cuando aplicar sola, cuando reiniciar y que
estado dejar. Todo lo que se pueda decidir sin tocar el disco ni la red vive
aca, para poder testearlo (mismo criterio que los servicios de Stock y CxP)."""
import os
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


def necesita_reinicio(requires_restart, archivos_descargados, archivos_eliminados=None):
    """Si hay que relanzar la app para que el cambio tenga efecto.

    Manda lo que REALMENTE se bajo: un `.py` obliga aunque el canal declare
    `requires_restart: false` (fail-safe: reiniciar de mas es barato, ejecutar
    codigo nuevo a medias no). Si no hay `.py`, se respeta lo que declare el
    canal; y si no se bajo **nada** (el disco ya estaba al dia: solo cambio la
    version declarada), no hay nada que reiniciar.

    Las BAJAS cuentan igual que las altas: si esta version borra un `.py`, el
    proceso que lo tiene cargado sigue con el viejo hasta que se reinicie (una
    actualizacion que SOLO borra no baja nada y antes no reiniciaba nunca).
    """
    rutas = _rutas(archivos_descargados)
    bajas = _rutas(archivos_eliminados)
    if not rutas and not bajas:
        return False
    if requiere_reinicio_del_diff(rutas + bajas):
        return True
    return bool(requires_restart)


def calcular_eliminados(manifest_nuevo, manifest_anterior):
    """Rutas del manifest ANTERIOR que ya no estan en el nuevo.

    Es la lista que el pipeline firma en `deleted.json` y que el cliente usa para
    borrar. PURO (solo diccionarios): se testea sin publicar nada. El manifiesto es
    un SNAPSHOT COMPLETO por version, asi que "no esta en el nuevo" significa
    exactamente "esta version lo borro".
    """
    anterior = manifest_anterior or {}
    nuevo = manifest_nuevo or {}
    return sorted(rel for rel in anterior if rel not in nuevo)


def rutas_a_borrar_seguras(candidatas, app_dir, en_el_manifest=None):
    """Subconjunto de `candidatas` que es SEGURO borrar dentro de `app_dir`.

    La lista viaja FIRMADA (Ed25519) y sale del manifest anterior, asi que por
    construccion son rutas publicables. Esto es defensa en profundidad, para que un
    error del publicador (o una firma comprometida) no borre algo fuera de la
    carpeta de la app ni un archivo que la version destino necesita:
      - se descartan rutas absolutas, con unidad (`C:`), con `..`, vacias o que no
        sean texto;
      - la ruta resuelta tiene que quedar DENTRO de `app_dir` (nunca `app_dir` solo);
      - con `en_el_manifest`, se descarta todo lo que la version destino publica
        (un archivo del manifest NUEVO no se borra nunca).

    Devuelve rutas relativas con barra normal, ordenadas y sin repetir. NO toca el
    disco: quien llama verifica que existan y las borra.
    """
    publicados = {str(k).replace('\\', '/') for k in (en_el_manifest or {})}
    base = os.path.normcase(os.path.abspath(app_dir))
    seguras = set()
    for candidata in candidatas or []:
        if not isinstance(candidata, str):
            continue
        rel = candidata.strip().replace('\\', '/')
        if not rel or rel.startswith('/') or ':' in rel:
            continue
        partes = [p for p in rel.split('/') if p not in ('', '.')]
        if not partes or any(p == '..' for p in partes):
            continue
        rel = '/'.join(partes)
        if rel in publicados:
            continue
        destino = os.path.normcase(os.path.abspath(os.path.join(app_dir, *partes)))
        if not destino.startswith(base + os.sep):
            continue
        seguras.add(rel)
    return sorted(seguras)


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
