# modules/stock/idempotencia.py
# ============================================================
# Almacen local de claves de idempotencia. Modulo PURO (solo stdlib): no
# importa Flask, config ni database, para poder testearlo sin app ni base.
#
# El frontend manda una clave por envio (header X-Idempotencia). Si la misma
# clave vuelve, el endpoint devuelve el resultado guardado en vez de escribir
# de nuevo: un doble clic o un reintento no duplica stock.
#
# Estructura del archivo:
#   {clave: {'fecha': ISO, 'resultado': {...}, 'huella': hash o None}}
# La `huella` es el hash del cuerpo del request: si la misma clave vuelve con
# OTRO cuerpo no es un reintento, es un error del cliente (409).
#
# Ademas de la clave del envio, los lotes usan una clave POR FILA
# (`clave_de_fila`: 'clave:n'). Cada fila es un read-modify-write del JSON: para
# un archivo de Excel grande eso son N escrituras del archivo completo (el
# volumen tipico son decenas de claves por dia, no miles).
# ============================================================

import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

HORAS_VIDA_DEFAULT = 24
CLAVE_MAX = 120
PATRON_CLAVE = re.compile(r'^[A-Za-z0-9_-]{1,' + str(CLAVE_MAX) + r'}$')

# Cuanto se guarda el candado de una clave que ya nadie usa (la clave en si vive
# HORAS_VIDA_DEFAULT; el candado se puede soltar antes).
VIDA_CANDADO_SEG = 3600

# Ruta por defecto: <app>/data/idempotencia_stock.json (este archivo vive en
# <app>/modules/stock/idempotencia.py).
RUTA_DEFAULT = Path(__file__).resolve().parents[2] / 'data' / 'idempotencia_stock.json'

# El read-modify-write del archivo se serializa: el volumen es de pocas
# decenas de claves por dia y perder una clave significa repetir el envio.
_CANDADO = threading.RLock()

# Candados POR CLAVE, del modulo y no de la instancia: cada request crea su
# propio AlmacenIdempotencia, asi que un candado por instancia no excluiria
# nada. La clave interna incluye la ruta del almacen (dos almacenes distintos no
# se pisan). `_CANDADOS_USO` guarda la ultima vez que se pidio cada candado para
# poder limpiar los viejos: los dos diccionarios se tocan SIEMPRE bajo _CANDADO.
_CANDADOS = {}
_CANDADOS_USO = {}


def huella_de_payload(payload):
    """Hash estable del cuerpo de un request (misma clave + mismo cuerpo =
    mismo envio). Se normaliza el orden de las claves y se serializa con
    default=str: un payload que JSON no conoce da huella distinta, pero nunca
    levanta (una excepcion aca romperia el endpoint)."""
    try:
        normalizado = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                 ensure_ascii=False, default=str)
    except Exception:
        return None
    return hashlib.sha256(normalizado.encode('utf-8')).hexdigest()


def clave_de_fila(clave, numero):
    """Clave de idempotencia de UNA fila de un lote: la clave del envio con el
    numero de fila. El cliente manda una sola clave por POST; el backend necesita
    una por fila para que un reintento no vuelva a aplicar las ya commiteadas.

    El ':' no es un caracter valido de header: estas claves son internas y nunca
    pasan por `clave_valida`."""
    return str(clave) + ':' + str(numero)


def clave_valida(clave):
    """La clave no puede estar vacia, tiene que tener hasta CLAVE_MAX
    caracteres y solo letras, numeros, '-' y '_' (viaja en un header)."""
    return isinstance(clave, str) and bool(PATRON_CLAVE.match(clave))


class AlmacenIdempotencia:
    """JSON en disco con vencimiento. `ruta_json=None` usa la ruta de la app."""

    def __init__(self, ruta_json=None, horas_vida=HORAS_VIDA_DEFAULT):
        self.ruta = Path(ruta_json) if ruta_json else RUTA_DEFAULT
        self.horas_vida = float(horas_vida)

    # -- API --------------------------------------------------------------

    @contextmanager
    def candado(self, clave):
        """Candado POR CLAVE: serializa el ciclo completo del endpoint (buscar +
        ejecutar + guardar). Sin esto la idempotencia era check-then-act: dos POST
        simultaneos con la misma clave (doble clic) pasaban los dos por `buscar`
        antes de que ninguno guardara y creaban DOS movimientos.

        Sin clave no hay nada que serializar (el `with` sigue funcionando).
        """
        if not clave:
            yield
            return
        interna = (str(self.ruta), str(clave))
        with _CANDADO:
            self._limpiar_candados()
            candado = _CANDADOS.get(interna)
            if candado is None:
                candado = _CANDADOS[interna] = threading.Lock()
            _CANDADOS_USO[interna] = time.monotonic()
        with candado:
            yield

    def veredicto(self, clave, huella=None):
        """Que hay que hacer con esta clave, en UNA sola consulta:
        - None: no hay nada guardado (hay que ejecutar y guardar);
        - ('previa', resultado): ya se proceso con la MISMA huella;
        - ('conflicto', None): la clave ya se uso con OTRA huella (409).
        """
        entrada = self.buscar_entrada(clave)
        if entrada is None:
            return None
        previa = entrada.get('huella')
        # Sin huella previa (formato anterior, o guardado sin huella) no se puede
        # comparar: se trata como reintento, que es el lado seguro.
        if previa is not None and huella is not None and previa != huella:
            return ('conflicto', None)
        return ('previa', entrada.get('resultado'))

    def buscar_entrada(self, clave):
        """La entrada completa ({'resultado', 'huella'}) o None si no esta o
        esta vencida."""
        with _CANDADO:
            datos = self._leer()
        entrada = datos.get(str(clave))
        if not isinstance(entrada, dict):
            return None
        fecha = self._fecha(entrada.get('fecha'))
        if fecha is None or self._vencida(fecha):
            return None
        return {'resultado': entrada.get('resultado'), 'huella': entrada.get('huella')}

    def buscar(self, clave):
        """Devuelve el resultado guardado o None si no esta o esta vencido."""
        entrada = self.buscar_entrada(clave)
        return None if entrada is None else entrada.get('resultado')

    def guardar(self, clave, resultado, huella=None):
        """Guarda (o reemplaza) el resultado de una clave. Devuelve True si pudo
        escribir. NUNCA levanta: el movimiento de stock ya esta commiteado cuando
        se llama y un 500 haria que el usuario reintente y lo duplique (los tipos
        que JSON no conoce, como Decimal o date, se guardan como texto). Cualquier
        falla del disco o de los datos se loguea y se devuelve False."""
        try:
            with _CANDADO:
                datos = self._limpiar(self._leer())
                datos[str(clave)] = {'fecha': datetime.now().isoformat(),
                                     'resultado': resultado,
                                     'huella': huella}
                return self._escribir(datos)
        except Exception as e:
            logger.error(f"No se pudo guardar la clave de idempotencia {clave}: {e}")
            return False

    def limpiar_vencidas(self):
        """Borra las entradas vencidas. Devuelve cuantas saco."""
        with _CANDADO:
            datos = self._leer()
            limpio = self._limpiar(datos)
            eliminadas = len(datos) - len(limpio)
            if eliminadas and not self._escribir(limpio):
                return 0
            return eliminadas

    # -- Internos ---------------------------------------------------------

    def _limpiar_candados(self):
        """Saca los candados que ya nadie usa (se llama con _CANDADO tomado).
        Nunca saca uno tomado, y el que se acaba de pedir tiene el uso al dia:
        un hilo que ya obtuvo la referencia siempre lo refresco antes."""
        ahora = time.monotonic()
        viejos = [interna for interna, candado in _CANDADOS.items()
                  if not candado.locked()
                  and ahora - _CANDADOS_USO.get(interna, ahora) > VIDA_CANDADO_SEG]
        for interna in viejos:
            _CANDADOS.pop(interna, None)
            _CANDADOS_USO.pop(interna, None)

    def _vencida(self, fecha):
        """Una fecha que no se puede restar (p.ej. aware, si algo se colo) se
        trata como vencida: este metodo no puede levantar."""
        try:
            return datetime.now() - fecha >= timedelta(hours=self.horas_vida)
        except TypeError:
            return True

    @staticmethod
    def _fecha(valor):
        """Una entrada con fecha ilegible se trata como vencida. Una fecha con
        offset se normaliza a hora local sin offset: `datetime.now()` es naive y
        restarle una aware levantaba TypeError (rompia buscar y guardar)."""
        if isinstance(valor, datetime):
            fecha = valor
        else:
            try:
                fecha = datetime.fromisoformat(str(valor))
            except (TypeError, ValueError):
                return None
        if not isinstance(fecha, datetime):
            return None
        if fecha.tzinfo is not None:
            fecha = fecha.astimezone().replace(tzinfo=None)
        return fecha

    def _limpiar(self, datos):
        return {clave: entrada for clave, entrada in datos.items()
                if isinstance(entrada, dict)
                and self._fecha(entrada.get('fecha')) is not None
                and not self._vencida(self._fecha(entrada.get('fecha')))}

    def _leer(self):
        """Archivo inexistente, ilegible o corrupto: se trata como vacio."""
        try:
            with open(self.ruta, 'r', encoding='utf-8') as archivo:
                datos = json.load(archivo)
        except (OSError, ValueError):
            return {}
        return datos if isinstance(datos, dict) else {}

    def _escribir(self, datos):
        """Escritura atomica (temporal + replace) para que una lectura
        concurrente nunca vea un JSON a medio escribir."""
        temporal = None
        try:
            os.makedirs(self.ruta.parent, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=str(self.ruta.parent),
                                             prefix=self.ruta.name + '.', suffix='.tmp',
                                             delete=False) as archivo:
                temporal = archivo.name
                json.dump(datos, archivo, ensure_ascii=False, default=str)
            os.replace(temporal, self.ruta)
            return True
        except Exception:
            if temporal:
                try:
                    os.remove(temporal)
                except OSError:
                    pass
            return False
