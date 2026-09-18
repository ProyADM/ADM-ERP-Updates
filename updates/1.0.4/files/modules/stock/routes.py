# modules/stock/routes.py
# ============================================================
# RUTAS STOCK - SIDESYS ERP (CORREGIDO - CONSULTAS PARAMETRIZADAS + SEGURIDAD)
# ============================================================

from flask import Blueprint, request, jsonify, g, session
from contextlib import ExitStack
import openpyxl
import threading
import json
import subprocess
import sys
import os
import io
import logging
import datetime
from decimal import Decimal, InvalidOperation
from modules.shared.database import run_sql, run_sql_db, _sql_literal, set_contexto_base
from config import BASES_DISPONIBLES, CATEGORIAS_ARTICULO, CUENTAS_POR_ORIGEN, _UY_COLS, _BASES_CONSOLIDADO, SQL_SERVER, SQL_USERNAME, SQL_PASSWORD
from modules.shared.decorators import requiere_permiso, chequear_acceso_base
from modules.shared.permisos import PermisosSistema
from modules.shared.config_central import auditar
# El servicio trae su propio ErrorValidacion (validacion de datos del
# movimiento): se importa con alias para no chocar con la de este modulo.
from .servicio_movimientos import (Contexto, ErrorValidacion as ErrorServicio, sql_ajuste,
                                   sql_ajuste_lote, sql_transferencia, sql_anulacion,
                                   mensaje_de_error_sql)
from .idempotencia import (AlmacenIdempotencia, clave_valida, clave_de_fila,
                           huella_de_payload)

logger = logging.getLogger(__name__)

stock_bp = Blueprint('stock', __name__, url_prefix='/api')

def _error_response(e, mensaje="Ocurrió un error en el servidor", codigo=500):
    """Devuelve un error genérico al cliente y loguea el detalle en el servidor.
    Nunca expone stack traces ni mensajes SQL/pyodbc al cliente."""
    import traceback
    logger.error(f"{mensaje}: {e}\n{traceback.format_exc()}")
    return jsonify({"error": mensaje}), codigo

# ============================================================
# VALIDACIÓN DE VARIABLES DE ENTORNO (NUEVO)
# ============================================================

def _get_sql_password():
    """Obtiene la contraseña SQL validando que exista"""
    password = os.environ.get('SQL_PASSWORD')
    if not password:
        raise ValueError("SQL_PASSWORD no definida en variables de entorno")
    return password

def _get_sql_username():
    """Obtiene el usuario SQL validando que exista"""
    username = os.environ.get('SQL_USERNAME')
    if not username:
        raise ValueError("SQL_USERNAME no definida en variables de entorno")
    return username

def _get_sql_server():
    """Obtiene el servidor SQL validando que exista"""
    server = os.environ.get('SQL_SERVER')
    if not server:
        raise ValueError("SQL_SERVER no definida en variables de entorno")
    return server

# ============================================================
# FUNCIÓN AUXILIAR PARA OBTENER PRÓXIMO ID DE MOVIMIENTO
# ============================================================
# sin uso tras el cableado al servicio (limpieza pendiente)
def _obtener_proximo_movimiento_id():
    """
    Obtiene el próximo ID de movimiento usando SIST_NUSI.
    Esto es coherente con el programa STO1000 y evita el error 2627.
    """
    sql = """
    BEGIN TRANSACTION;
    
    DECLARE @nuevo_id INT;
    
    UPDATE SIST_NUSI WITH (TABLOCKX) 
    SET NUSI_ULTIMO_NUMERO = NUSI_ULTIMO_NUMERO + 1,
        NUSI_ULT_ACTUALIZACION_FYH = GETDATE()
    WHERE NUSI_NUMERADOR_ID = 5;
    
    SELECT @nuevo_id = NUSI_ULTIMO_NUMERO 
    FROM SIST_NUSI 
    WHERE NUSI_NUMERADOR_ID = 5;
    
    COMMIT TRANSACTION;
    
    SELECT @nuevo_id AS NuevoID;
    """
    
    rows = run_sql(sql)
    if not rows:
        raise Exception("No se pudo obtener el próximo ID de movimiento")
    return rows[0]["NuevoID"]

# ============================================================
# RUTAS STOCK - ARTÍCULOS Y DEPÓSITOS
# ============================================================

@stock_bp.route('/articulos', methods=["GET"])
@requiere_permiso(PermisosSistema.STOCK_VER)
def listar_articulos():
    try:
        rows = run_sql("""
            SELECT ARTS_ARTICULO, ARTS_ARTICULO_EMP, ARTS_NOMBRE, ARTS_CON_PARTIDAS
            FROM STOC_ARTS 
            WHERE ARTS_FECHA_BAJA IS NULL
              AND ARTS_ARTICULO_EMP IS NOT NULL 
              AND LTRIM(RTRIM(ARTS_ARTICULO_EMP)) <> ''
              AND ARTS_ARTICULO_EMP NOT LIKE '%[^0-9.]%'
            ORDER BY ARTS_NOMBRE
        """)
        out = [{
            "id": r["ARTS_ARTICULO"],
            "codigo": r["ARTS_ARTICULO_EMP"],
            "nombre": r["ARTS_NOMBRE"],
            "con_partidas": bool(r["ARTS_CON_PARTIDAS"])
        } for r in rows]
        return jsonify(out)
    except Exception as e:
        return _error_response(e, "Error al listar artículos")

@stock_bp.route('/depositos', methods=["GET"])
@requiere_permiso(PermisosSistema.STOCK_VER)
def listar_depositos():
    try:
        rows = run_sql("SELECT DPOS_DEPOSITO, DPOS_NOMBRE FROM STOC_DPOS WHERE DPOS_UTILIZABLE = 1 ORDER BY DPOS_NOMBRE")
        out = [{"id": r["DPOS_DEPOSITO"], "nombre": r["DPOS_NOMBRE"]} for r in rows]
        return jsonify(out)
    except Exception as e:
        return _error_response(e, "Error al listar depósitos")

@stock_bp.route('/categorias', methods=["GET"])
@requiere_permiso(PermisosSistema.STOCK_VER)
def listar_categorias():
    try:
        from config import CATEGORIAS_ARTICULO
        out = [{"codigo": cod, "nombre": info["nombre"], "con_partidas_default": info["con_partidas_default"]} 
               for cod, info in CATEGORIAS_ARTICULO.items()]
        return jsonify(out)
    except Exception as e:
        return _error_response(e, "Error al listar categorías")

@stock_bp.route('/partidas', methods=["GET"])
@requiere_permiso(PermisosSistema.STOCK_VER)
def listar_partidas():
    articulo = request.args.get("articulo", type=int)
    deposito = request.args.get("deposito", type=int)
    # ✅ CORREGIDO: Consulta con parámetros
    rows = run_sql("""
        SELECT s.SDPP_PARTIDA, s.SDPP_STOCK_ACT, p.PART_PARTIDA_EMP
        FROM STOC_SDPP s 
        LEFT JOIN STOC_PART p ON p.PART_PARTIDA = s.SDPP_PARTIDA
        WHERE s.SDPP_ARTICULO = ? AND s.SDPP_DEPOSITO = ? AND s.SDPP_STOCK_ACT > 0
    """, params=[articulo, deposito])
    out = [{"partida": r["SDPP_PARTIDA"], "stock": float(r["SDPP_STOCK_ACT"]), "partida_emp": r["PART_PARTIDA_EMP"]} for r in rows]
    return jsonify(out)

@stock_bp.route('/stock', methods=["GET"])
@requiere_permiso(PermisosSistema.STOCK_VER)
def consultar_stock():
    try:
        where = [
            "s.STDP_STOCK_ACT <> 0",
            "a.ARTS_ARTICULO_EMP IS NOT NULL",
            "LTRIM(RTRIM(a.ARTS_ARTICULO_EMP)) <> ''",
            "a.ARTS_ARTICULO_EMP NOT LIKE '%[^0-9.]%'",
        ]
        articulo = request.args.get("articulo", type=int)
        deposito = request.args.get("deposito", type=int)
        q = request.args.get("q", "").strip().replace("'", "''")

        params = []
        if articulo:
            where.append("s.STDP_ARTICULO = ?")
            params.append(articulo)
        if deposito:
            where.append("s.STDP_DEPOSITO = ?")
            params.append(deposito)
        if q:
            where.append("a.ARTS_NOMBRE LIKE ?")
            params.append(f"%{q}%")

        where_sql = " AND ".join(where)
        
        # ✅ CORREGIDO: Consulta con parámetros
        query = f"""
            SELECT s.STDP_ARTICULO, a.ARTS_ARTICULO_EMP, a.ARTS_NOMBRE, a.ARTS_UNIMED_STOCK,
                s.STDP_DEPOSITO, d.DPOS_NOMBRE, s.STDP_STOCK_ACT
            FROM STOC_STDP s
            JOIN STOC_ARTS a ON a.ARTS_ARTICULO = s.STDP_ARTICULO
            JOIN STOC_DPOS d ON d.DPOS_DEPOSITO = s.STDP_DEPOSITO
            WHERE {where_sql}
            ORDER BY a.ARTS_NOMBRE, d.DPOS_NOMBRE
        """
        
        rows = run_sql(query, params=params)
        out = [{
            "articulo": r["STDP_ARTICULO"],
            "codigo": r["ARTS_ARTICULO_EMP"],
            "nombre": r["ARTS_NOMBRE"],
            "unidad": r["ARTS_UNIMED_STOCK"],
            "deposito": r["STDP_DEPOSITO"],
            "deposito_nombre": r["DPOS_NOMBRE"],
            "stock": float(r["STDP_STOCK_ACT"]),
        } for r in rows]
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# VALIDACION DE ENTRADA DE MOVIMIENTOS (anti-inyeccion SQL)
# ============================================================

class ErrorValidacion(Exception):
    """Error controlado de validacion de entrada (se devuelve como HTTP 400).

    Trae `codigo` para que la respuesta tenga la MISMA forma que las del
    servicio ({"error", "codigo"}): los endpoints mapean los dos
    ErrorValidacion (el de este modulo y el del servicio) igual."""

    codigo = 'STK_VAL_ENTRADA'

    def __init__(self, mensaje, codigo=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        if codigo:
            self.codigo = codigo


# sin uso tras el cableado al servicio (limpieza pendiente)
def _validar_entero(valor, campo):
    """Convierte un valor de entrada a int o lanza ErrorValidacion."""
    if valor is None or valor == '':
        raise ErrorValidacion("El campo '" + campo + "' es obligatorio")
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErrorValidacion("El campo '" + campo + "' debe ser un numero entero")


# sin uso tras el cableado al servicio (limpieza pendiente)
def _validar_decimal(valor, campo):
    """Convierte un valor de entrada a Decimal finito o lanza ErrorValidacion."""
    if valor is None or valor == '':
        raise ErrorValidacion("El campo '" + campo + "' es obligatorio")
    try:
        d = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ErrorValidacion("El campo '" + campo + "' debe ser un numero")
    if not d.is_finite():
        raise ErrorValidacion("El campo '" + campo + "' debe ser un numero finito")
    if abs(d) > Decimal('1e15'):
        raise ErrorValidacion("El campo '" + campo + "' excede el rango permitido")
    return d


# sin uso tras el cableado al servicio (limpieza pendiente)
def _validar_fecha(fecha, campo='fecha'):
    """Valida una fecha en formato AAAA-MM-DD (devuelve None si viene vacia)."""
    if fecha is None or str(fecha).strip() == '':
        return None
    try:
        return datetime.date.fromisoformat(str(fecha).strip()).isoformat()
    except (TypeError, ValueError):
        raise ErrorValidacion("El campo '" + campo + "' debe tener formato AAAA-MM-DD")


# sin uso tras el cableado al servicio (limpieza pendiente)
def _validar_signo(signo):
    """Valida el signo de un movimiento: 'E' (entrada) o 'S' (salida)."""
    s = str(signo or '').strip().upper()
    if s not in ('E', 'S'):
        raise ErrorValidacion("El campo 'signo' debe ser 'E' (entrada) o 'S' (salida)")
    return s


# ============================================================
# RUTAS STOCK - MOVIMIENTOS: SERVICIO, EJECUCION E IDEMPOTENCIA
# ============================================================

def _contexto_stock():
    """El usuario sale de la sesion, igual que en modules/shared/decorators.py:60."""
    return Contexto(division=g.division, sucursal_imp=g.sucursal,
                    sucursal_emp=getattr(g, 'sucursal_emp', g.sucursal),
                    base=g.db_database, usuario=session.get('username', ''))


def _filas_de_lote(sql):
    """Ejecuta el lote del servicio y traduce el error de la base a ErrorServicio.
    Devuelve TODAS las filas del SELECT final: la anulacion devuelve una por
    renglon anulado. El 547 (FK) se le pide a run_sql solo por este camino (ver
    database._texto_de_error_propio): asi el texto crudo de la base no llega a
    ningun otro modulo, y aca se traduce a un mensaje entendible."""
    try:
        return run_sql(sql, permitir_error_fk=True) or []
    except Exception as e:
        logger.error(f"Error de stock en el lote: {e}")
        codigo, mensaje = mensaje_de_error_sql(str(e))
        raise ErrorServicio(codigo, mensaje)


def _ejecutar_lote(sql):
    """La primera fila del lote (ajuste y transferencia devuelven una sola)."""
    return (_filas_de_lote(sql) or [{}])[0]


def _entero(valor):
    """Los ids y el numero de comprobante tienen que salir como int (el numero
    de comprobante llega como DECIMAL(18,0))."""
    return None if valor is None else int(valor)


def _numero(valor):
    """Los importes de stock llegan como Decimal y jsonify no los serializa."""
    return None if valor is None else float(valor)


# Mapa de errores del servicio: lo que no es anulable (o quedo referenciado por
# otro circuito) va con 409, la validacion de datos con 400 y el resto de las
# fallas internas del lote con 500.
CODIGOS_EN_CONFLICTO = ('STK_VAL_CONSUMIDO', 'STK_VAL_MOV_FMR', 'STK_VAL_ANULAR_MULTIPARTIDA',
                        'STK_VAL_ANULAR_TRANSFERENCIA', 'STK_INT_FK', 'STK_INT_STDP_SIN_FILA',
                        'STK_INT_SDPP_SIN_FILA', 'STK_INT_MOST')

# Mensajes de la idempotencia y de la anulacion (una sola fuente: los tests
# verifican el codigo, y el operador lee el texto).
MENSAJE_CLAVE_INVALIDA = "Clave de idempotencia invalida."
MENSAJE_CLAVE_REUTILIZADA = ("La clave de idempotencia ya fue usada con otro contenido: "
                             "reenviá la operación con una clave nueva.")
MENSAJE_MOTIVO = "El motivo es obligatorio para anular un movimiento."


def _estado_de_error(codigo):
    """HTTP que le corresponde al codigo del servicio."""
    if codigo in CODIGOS_EN_CONFLICTO:
        return 409
    if str(codigo or '').startswith('STK_VAL_'):
        return 400
    return 500


def _dict_error_servicio(e):
    """Cuerpo del error de un ErrorValidacion del servicio."""
    return {"error": e.mensaje, "codigo": e.codigo}


def _dict_error_entrada(e):
    """Cuerpo del error de un ErrorValidacion local (misma forma que el del
    servicio: {"error", "codigo"})."""
    return {"error": str(e), "codigo": getattr(e, 'codigo', 'STK_VAL_ENTRADA')}


def _error_stock(e):
    """Respuesta de un ErrorValidacion del servicio ({"error", "codigo"})."""
    return jsonify(_dict_error_servicio(e)), _estado_de_error(e.codigo)


def _error_entrada(e):
    """Respuesta de un ErrorValidacion local (400, {"error", "codigo"})."""
    return jsonify(_dict_error_entrada(e)), 400


class _IdempotenciaDelEnvio:
    """Clave de idempotencia del request (header X-Idempotencia) y huella del
    cuerpo. Si la misma clave vuelve con el MISMO cuerpo se devuelve EXACTAMENTE
    el resultado guardado y no se escribe nada (un doble clic o un reintento no
    duplican el movimiento); si vuelve con OTRO cuerpo es un error del cliente
    (409): esa clave ya se uso para otro movimiento.

    El ciclo buscar + ejecutar + guardar TIENE que ir dentro de `candado()`: sin
    la exclusion mutua, dos POST simultaneos con la misma clave pasaban los dos
    por la busqueda y creaban dos movimientos."""

    def __init__(self, data=None, clave=None):
        # Una clave pasada a mano es DERIVADA (clave de fila `clave:n`): no viene
        # del header, asi que no se le aplica el formato de `clave_valida`.
        self.derivada = clave is not None
        if clave is None:
            self.clave = (request.headers.get('X-Idempotencia') or '').strip()
        else:
            self.clave = str(clave).strip()
        # `data=None` = no se conoce el cuerpo (no se puede comparar la huella).
        self.huella = huella_de_payload(data) if data is not None else None
        self.almacen = AlmacenIdempotencia()

    def clave_invalida(self):
        """True si el header trae una clave que no cumple el formato."""
        if self.derivada:
            return False
        return bool(self.clave) and not clave_valida(self.clave)

    def candado(self):
        """Candado por clave (o un `with` sin efecto si el envio no lleva clave)."""
        return self.almacen.candado(self.clave)

    def verificar(self):
        """None si hay que ejecutar; ('previa', resultado) si ya se hizo con el
        mismo cuerpo; ('conflicto', None) si la clave se reuso con otro cuerpo;
        ('invalida', None) si la clave no tiene el formato permitido."""
        if not self.clave:
            return None
        if self.clave_invalida():
            return ('invalida', None)
        return self.almacen.veredicto(self.clave, self.huella)

    def respuesta_previa(self):
        """(respuesta, estado) si hay que contestar sin ejecutar; None si no."""
        estado, resultado = self.verificar() or (None, None)
        if estado == 'previa':
            return jsonify(resultado), 200
        if estado == 'conflicto':
            return jsonify({"error": MENSAJE_CLAVE_REUTILIZADA,
                            "codigo": "STK_VAL_CLAVE_REUTILIZADA"}), 409
        if estado == 'invalida':
            return jsonify({"error": MENSAJE_CLAVE_INVALIDA, "codigo": "STK_VAL_CLAVE"}), 400
        return None

    def guardar(self, resultado):
        """El movimiento ya esta commiteado: si la clave no se puede guardar se
        loguea y la respuesta sigue siendo exitosa (fallar aca haria que el
        usuario reintente y duplique el movimiento). El almacen ya no propaga
        excepciones; este try es la ultima red."""
        if not self.clave:
            return
        try:
            guardado = self.almacen.guardar(self.clave, resultado, self.huella)
        except Exception as e:      # pragma: no cover - defensivo
            logger.error(f"Excepcion al guardar la clave de idempotencia {self.clave}: {e}")
            return
        if not guardado:
            logger.error(f"No se pudo guardar la clave de idempotencia {self.clave}: "
                         "un reintento del mismo envio puede duplicar el movimiento.")


def _envio_de_fila(envio, numero, data):
    """Idempotencia de UNA fila de un lote: la clave del envio mas el numero de
    fila (`clave:n`). Sin clave no hay red y se devuelve None (comportamiento de
    siempre)."""
    if envio is None or not envio.clave:
        return None
    return _IdempotenciaDelEnvio(data=data, clave=clave_de_fila(envio.clave, numero))


def _hacer_ajuste(articulo, deposito, cantidad, signo, partida=None, fecha=None, partida_nombre=None, comentario=None):
    """Un ajuste individual: un solo lote del servicio (transaccion + guardas +
    verificaciones). La validacion de los datos vive en el servicio."""
    ctx = _contexto_stock()
    fila = _ejecutar_lote(sql_ajuste(ctx, {
        "articulo": articulo, "deposito": deposito, "cantidad": cantidad, "signo": signo,
        "partida": partida, "fecha": fecha, "partida_nombre": partida_nombre, "comentario": comentario,
    }))
    return {"ok": True, "movimiento": _entero(fila.get("movimiento")),
            "numero_comprobante": _entero(fila.get("numero")),
            "tipo": "AJ+" if str(signo or "").strip().upper() == "E" else "AJ-"}


@stock_bp.route('/ajuste', methods=["POST"])
@requiere_permiso(PermisosSistema.STOCK_AJUSTAR)
def ajuste():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON"}), 400
    envio = _IdempotenciaDelEnvio(data)
    # Buscar + ejecutar + guardar van DENTRO del candado de la clave: sin esa
    # exclusion mutua, un doble clic (dos POST en paralelo con la misma clave)
    # pasaba dos veces por la busqueda y creaba dos movimientos.
    with envio.candado():
        previa = envio.respuesta_previa()
        if previa is not None:
            return previa
        try:
            resultado = _hacer_ajuste(
                data.get("articulo"), data.get("deposito"), data.get("cantidad"), data.get("signo"),
                data.get("partida"), data.get("fecha"), data.get("partida_nombre"), data.get("comentario")
            )
        except ErrorServicio as e:
            return _error_stock(e)
        except ErrorValidacion as e:
            return _error_entrada(e)
        except Exception as e:
            logger.error(f"Error inesperado en /api/ajuste: {e}")
            return jsonify({"error": str(e)}), 500
        envio.guardar(resultado)
    return jsonify(resultado)


def _hacer_ajuste_lote(signo, filas):
    """Un comprobante con un renglon por fila, en un solo lote del servicio.
    La respuesta conserva las claves de siempre (incluido cantidad_renglones)."""
    ctx = _contexto_stock()
    fila = _ejecutar_lote(sql_ajuste_lote(ctx, signo, filas))
    return {"ok": True, "movimiento": _entero(fila.get("movimiento")),
            "numero_comprobante": _entero(fila.get("numero")),
            "tipo": "AJ+" if str(signo or "").strip().upper() == "E" else "AJ-",
            "cantidad_renglones": len(filas) if isinstance(filas, (list, tuple)) else 0}


@stock_bp.route('/ajuste/lote', methods=["POST"])
@requiere_permiso(PermisosSistema.STOCK_AJUSTAR)
def ajuste_lote():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON"}), 400
    envio = _IdempotenciaDelEnvio(data)
    with envio.candado():
        previa = envio.respuesta_previa()
        if previa is not None:
            return previa
        try:
            resultado = _hacer_ajuste_lote(data.get("signo"), data.get("filas", []))
        except ErrorServicio as e:
            return _error_stock(e)
        except ErrorValidacion as e:
            return _error_entrada(e)
        except Exception as e:
            logger.error(f"Error inesperado en /api/ajuste/lote: {e}")
            return jsonify({"error": str(e)}), 500
        envio.guardar(resultado)
    return jsonify(resultado)

# ============================================================
# RUTAS STOCK - TRANSFERENCIAS
# ============================================================

def _hacer_transferencia(articulo, dep_origen, dep_destino, cantidad, partida=None, fecha=None, comentario=None):
    """Una transferencia: los dos movimientos (salida y entrada) en un solo lote
    del servicio. La validacion de los datos vive en el servicio."""
    ctx = _contexto_stock()
    fila = _ejecutar_lote(sql_transferencia(ctx, {
        "articulo": articulo, "deposito_origen": dep_origen, "deposito_destino": dep_destino,
        "cantidad": cantidad, "partida": partida, "fecha": fecha, "comentario": comentario,
    }))
    return {"ok": True,
            "numero_transferencia": _entero(fila.get("numero_transferencia")),
            "movimiento_salida": _entero(fila.get("movimiento_salida")),
            "movimiento_entrada": _entero(fila.get("movimiento_entrada"))}


@stock_bp.route('/transferencia', methods=["POST"])
@requiere_permiso(PermisosSistema.STOCK_TRANSFERIR)
def transferencia():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON"}), 400
    envio = _IdempotenciaDelEnvio(data)
    with envio.candado():
        previa = envio.respuesta_previa()
        if previa is not None:
            return previa
        try:
            resultado = _hacer_transferencia(
                data.get("articulo"), data.get("deposito_origen"), data.get("deposito_destino"),
                data.get("cantidad"), data.get("partida"), data.get("fecha"), data.get("comentario")
            )
        except ErrorServicio as e:
            return _error_stock(e)
        except ErrorValidacion as e:
            return _error_entrada(e)
        except Exception as e:
            logger.error(f"Error inesperado en /api/transferencia: {e}")
            return jsonify({"error": str(e)}), 500
        envio.guardar(resultado)
    return jsonify(resultado)


def _transferir_fila(fila):
    """Una transferencia del lote, con el error de ESA fila: el lote sigue con
    las demas."""
    try:
        if not isinstance(fila, dict):
            raise ErrorValidacion("Cada fila debe ser un objeto")
        return _hacer_transferencia(
            fila.get("articulo"), fila.get("deposito_origen"), fila.get("deposito_destino"),
            fila.get("cantidad"), fila.get("partida")
        )
    except ErrorServicio as e:
        return _dict_error_servicio(e)
    except ErrorValidacion as e:
        return _dict_error_entrada(e)
    except Exception as e:
        return {"error": str(e)}


def _transferir_fila_cruda(fila):
    """Una fila ya normalizada del Excel: si el parseo de la fila fallo, ese
    error es el resultado de la fila (y no se llama al servicio)."""
    if "error" in fila:
        return {"error": fila["error"]}
    return _transferir_fila(fila)


def _todas_ok(resultados):
    """True si NINGUNA fila del lote devolvio error. El status HTTP sigue siendo
    200 (el detalle por fila es el contrato): esta bandera es la que le dice al
    cliente si puede cerrar la clave del envio o si tiene que conservarla para
    poder reintentar sin duplicar las filas que ya entraron."""
    return all(not r.get('error') for r in resultados)


def _transferir_filas(filas, numeros, envio, operacion=None):
    """Cada fila con su clave derivada (`clave:n`): un reintento del mismo lote
    no vuelve a aplicar las filas ya commiteadas. Sin clave no hay red y el
    comportamiento es el de siempre. `operacion` permite reusar esto desde el
    camino de Excel (que convierte los tipos de la fila antes de llamar)."""
    operacion = operacion or _transferir_fila
    resultados = []
    for fila, numero in zip(filas, numeros):
        envio_fila = _envio_de_fila(envio, numero, fila)
        if envio_fila is None:
            r = operacion(fila)
        else:
            with envio_fila.candado():
                estado, previo = envio_fila.verificar() or (None, None)
                if estado == 'previa':
                    r = dict(previo) if isinstance(previo, dict) else {"ok": True}
                elif estado == 'conflicto':
                    r = {"error": MENSAJE_CLAVE_REUTILIZADA, "codigo": "STK_VAL_CLAVE_REUTILIZADA"}
                else:
                    r = operacion(fila)
                    # Solo se guarda la fila que se aplico: una fila con error
                    # se puede reintentar con la misma clave.
                    if not r.get("error"):
                        envio_fila.guardar(r)
        r["fila"] = numero
        resultados.append(r)
    return resultados


@stock_bp.route('/transferencia/lote', methods=["POST"])
@requiere_permiso(PermisosSistema.STOCK_TRANSFERIR)
def transferencia_lote():
    data = request.get_json(silent=True)
    filas = data.get("filas", []) if isinstance(data, dict) else []
    envio = _IdempotenciaDelEnvio(data)
    if envio.clave_invalida():
        return jsonify({"error": MENSAJE_CLAVE_INVALIDA, "codigo": "STK_VAL_CLAVE"}), 400
    # El numero de fila es el del envio (1..N), igual que el "fila" de siempre.
    numeros = list(range(1, len(filas) + 1))
    resultados = _transferir_filas(filas, numeros, envio)
    return jsonify({"resultados": resultados, "todas_ok": _todas_ok(resultados)})

# ============================================================
# RUTAS STOCK - ANULACION DE MOVIMIENTOS (permiso stock.eliminar)
# ============================================================

def _fila_anulada(fila):
    """Datos de un renglon anulado, tal como los devuelve el SELECT final del
    lote (con los valores PREVIOS de stock)."""
    return {"movimiento": _entero(fila.get("movimiento")),
            "renglon": _entero(fila.get("renglon")),
            "articulo": _entero(fila.get("articulo")),
            "deposito": _entero(fila.get("deposito")),
            "signo": fila.get("signo"),
            "cantidad": _numero(fila.get("cantidad")),
            "partida": _entero(fila.get("partida")),
            "stock_previo_agregado": _numero(fila.get("stock_previo_agregado")),
            "stock_previo_partida": _numero(fila.get("stock_previo_partida"))}


@stock_bp.route('/stock/anular', methods=["POST"])
@requiere_permiso(PermisosSistema.STOCK_ELIMINAR)
def anular_movimiento_stock():
    """Anula un movimiento de stock. Sin `renglon` se anula el comprobante
    completo (es la unica forma de anular una transferencia). El `motivo` es
    OBLIGATORIO y la auditoria guarda, por renglon anulado, articulo, deposito,
    signo, cantidad, partida y los valores PREVIOS de stock: eso es lo que
    permite reconstruir lo anulado. No lleva clave de idempotencia: la anulacion
    ya es idempotente por si misma (el segundo intento da STK_VAL_MOV_NO_EXISTE).
    No hay pantalla de anulacion todavia: se usa por este endpoint."""
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON"}), 400
    ctx = _contexto_stock()
    motivo = datos.get("motivo")
    motivo = motivo.strip() if isinstance(motivo, str) else ''
    evento = {'evento': 'stock.anulacion', 'usuario': ctx.usuario, 'base': ctx.base,
              'movimiento': datos.get("movimiento"), 'renglon': datos.get("renglon"),
              'motivo': motivo}
    # La auditoria se escribe ANTES: el rastro existe aunque falle.
    if not motivo:
        auditar({**evento, 'estado': 'rechazada', 'codigo': 'STK_VAL_MOTIVO', 'error': MENSAJE_MOTIVO,
                 'fecha': datetime.datetime.now().isoformat()})
        return jsonify({"error": MENSAJE_MOTIVO, "codigo": "STK_VAL_MOTIVO"}), 400
    auditar({**evento, 'estado': 'solicitada', 'fecha': datetime.datetime.now().isoformat()})
    try:
        lote = sql_anulacion(ctx, datos.get("movimiento"), datos.get("renglon"), motivo)
        filas_sql = _filas_de_lote(lote)
    except ErrorServicio as e:
        auditar({**evento, 'estado': 'rechazada', 'codigo': e.codigo, 'error': e.mensaje,
                 'fecha': datetime.datetime.now().isoformat()})
        return _error_stock(e)
    except ErrorValidacion as e:
        return _error_entrada(e)
    except Exception as e:
        logger.error(f"Error inesperado en /api/stock/anular: {e}")
        auditar({**evento, 'estado': 'fallida', 'error': str(e),
                 'fecha': datetime.datetime.now().isoformat()})
        return jsonify({"error": str(e)}), 500
    primera = filas_sql[0] if filas_sql else {}
    filas = [_fila_anulada(fila) for fila in filas_sql]
    resultado = {"movimiento_anulado": _entero(primera.get("movimiento_anulado")),
                 "motivo": primera.get("motivo", motivo),
                 "filas": filas}
    auditar({**evento, 'estado': 'aplicada', 'resultado': resultado, 'filas': filas,
             'fecha': datetime.datetime.now().isoformat()})
    return jsonify({"ok": True, **resultado})

# ============================================================
# RUTAS STOCK - EXCEL
# ============================================================

@stock_bp.route('/excel/plantilla/<tipo>', methods=["GET"])
@requiere_permiso(PermisosSistema.STOCK_IMPORTAR)
def excel_plantilla(tipo):
    from flask import send_file
    import openpyxl
    import io
    wb = openpyxl.Workbook()
    ws = wb.active

    if tipo == "ajuste":
        ws.title = "Ajustes"
        ws.append(["articulo", "deposito", "cantidad", "partida"])
        ws.append([26, 2, 1, ""])
        ws.append(["# Todas las filas de este archivo generan UN SOLO comprobante (AJ+ o AJ-, elegido en la pantalla)", "", "", "# partida: solo si el artículo usa partidas y es salida"])
    elif tipo == "transferencia":
        ws.title = "Transferencias"
        ws.append(["articulo", "deposito_origen", "deposito_destino", "cantidad", "partida"])
        ws.append([26, 3, 2, 1, ""])
        ws.append(["# partida: solo si el artículo usa partidas (obligatoria en ese caso)", "", "", "", ""])
    elif tipo == "articulos":
        ws.title = "Articulos"
        ws.append(["nombre", "codigo", "categoria", "con_partidas", "se_compra", "se_vende", "origen"])
        ws.append(["Notebook Foodie 21.5", "10.8.9", "002", 1, 1, 1, "local"])
        ws.append(["# categoria: " + "/".join(CATEGORIAS_ARTICULO.keys()), "", "", "# con_partidas/se_compra/se_vende: 1 o 0", "", "", "# origen: local o exterior"])
    elif tipo == "articulos_modificar":
        ws.title = "ModificarArticulos"
        ws.append(["id", "nombre", "codigo", "categoria", "con_partidas", "se_compra", "se_vende", "origen"])
        ws.append([44, "Notebook Foodie 21.5", "10.8.9", "002", 1, 1, 1, "local"])
        ws.append(["# id: ID del artículo a modificar (ver en Consultar Stock)", "", "", "# categoria: " + "/".join(CATEGORIAS_ARTICULO.keys()), "# 1 o 0", "", "", "# local o exterior"])
    else:
        return jsonify({"error": "Tipo de plantilla inválido"}), 400

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"plantilla_{tipo}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@stock_bp.route('/excel/cargar/<tipo>', methods=["POST"])
@requiere_permiso(PermisosSistema.STOCK_IMPORTAR)
def excel_cargar(tipo):
    import openpyxl
    if "archivo" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400
    archivo = request.files["archivo"]

    try:
        wb = openpyxl.load_workbook(archivo, data_only=True)
        ws = wb.active
    except Exception as e:
        return jsonify({"error": f"No se pudo leer el Excel: {e}"}), 400

    rows = list(ws.iter_rows(min_row=2, values_only=True))
    resultados = []

    TIPOS_ARTICULOS = ("articulos", "articulos_modificar")
    if tipo in TIPOS_ARTICULOS:
        bases_solicitadas = request.form.getlist("bases")
        if not bases_solicitadas:
            resultados = _procesar_filas_articulos(tipo, rows)
            return jsonify({"resultados": resultados})

        base_original, server_original = g.db_database, g.db_server
        division_original, sucursal_original = g.division, g.sucursal
        resultados_por_base = {}
        try:
            for base in bases_solicitadas:
                if base not in BASES_DISPONIBLES:
                    resultados_por_base[base] = [{"error": f"Base desconocida: {base}", "fila": "-"}]
                    continue
                set_contexto_base(base)
                resultados_por_base[base] = _procesar_filas_articulos(tipo, rows)
        finally:
            g.db_database, g.db_server = base_original, server_original
            g.division, g.sucursal = division_original, sucursal_original

        return jsonify({"resultados_por_base": resultados_por_base})

    if tipo == "ajuste":
        signo = request.args.get("signo", "").strip().upper()
        if signo not in ("E", "S"):
            return jsonify({"error": "Falta indicar el signo (E o S) para la carga"}), 400

        filas = []
        numeros = []            # numero de fila del archivo (clave de idempotencia)
        for i, row in enumerate(rows):
            if not row or row[0] in (None, ""):
                continue
            try:
                articulo, deposito, cantidad = row[0], row[1], row[2]
                partida = row[3] if len(row) > 3 and row[3] not in (None, "") else None
                fila = {"articulo": int(articulo), "deposito": int(deposito), "cantidad": float(cantidad)}
                if partida is not None:
                    fila["partida"] = int(partida)
                filas.append(fila)
                numeros.append(i + 2)
            except Exception as e:
                # Mismo codigo que el servicio para una fila ilegible
                # (`STK_VAL_FILA`): el cliente recibe siempre {"error", "codigo"}.
                return jsonify({"error": f"Fila {i+2}: {e}", "codigo": "STK_VAL_FILA"}), 400

        if not filas:
            return jsonify({"error": "El archivo no tiene filas válidas"}), 400

        # Todo el archivo es UN comprobante: la clave del header se deriva por
        # fila del archivo (`clave:n`) para que un reintento del mismo archivo no
        # lo vuelva a escribir. Sin clave, comportamiento de siempre.
        envio = _IdempotenciaDelEnvio({'signo': signo, 'filas': filas})
        if envio.clave_invalida():
            return jsonify({"error": MENSAJE_CLAVE_INVALIDA, "codigo": "STK_VAL_CLAVE"}), 400
        envios = ([_envio_de_fila(envio, numero, fila) for fila, numero in zip(filas, numeros)]
                  if envio.clave else [])
        with ExitStack() as pila:
            for envio_fila in envios:
                pila.enter_context(envio_fila.candado())
            estados = [envio_fila.verificar() or (None, None) for envio_fila in envios]
            if any(estado == 'conflicto' for estado, _ in estados):
                return jsonify({"error": MENSAJE_CLAVE_REUTILIZADA,
                                "codigo": "STK_VAL_CLAVE_REUTILIZADA"}), 409
            previas = [resultado for estado, resultado in estados if estado == 'previa']
            if previas:
                # El comprobante ya se aplico con esta clave (o quedo guardado a
                # medias): se devuelve el resultado guardado sin reescribir.
                return jsonify(previas[0]), 200
            # El error tiene que salir como JSON, no como un 500 de Flask, y los
            # DOS ErrorValidacion (el del servicio y el de este modulo) van 400.
            try:
                resp = _hacer_ajuste_lote(signo, filas)
            except ErrorServicio as e:
                return _error_stock(e)
            except ErrorValidacion as e:
                return _error_entrada(e)
            except Exception as e:
                logger.error(f"Error inesperado en /excel/cargar/ajuste: {e}")
                return jsonify({"error": str(e)}), 500
            for envio_fila in envios:
                envio_fila.guardar(resp)
        return jsonify(resp)

    elif tipo == "transferencia":
        filas = []
        numeros = []            # numero de fila del archivo (clave de idempotencia)
        for i, row in enumerate(rows):
            if not row or row[0] in (None, ""):
                continue
            try:
                articulo, dep_origen, dep_destino, cantidad = row[0], row[1], row[2], row[3]
                partida = row[4] if len(row) > 4 and row[4] not in (None, "") else None
                filas.append({"articulo": int(articulo), "deposito_origen": int(dep_origen),
                              "deposito_destino": int(dep_destino), "cantidad": float(cantidad),
                              "partida": int(partida) if partida is not None else None})
            except Exception as e:
                filas.append({"error": f"Fila {i+2}: {e}"})
            numeros.append(i + 2)

        # Cada fila del archivo con su clave derivada (`clave:n`): un reintento
        # del mismo archivo no vuelve a aplicar las filas ya commiteadas.
        envio = _IdempotenciaDelEnvio({'tipo': 'transferencia', 'filas': filas})
        if envio.clave_invalida():
            return jsonify({"error": MENSAJE_CLAVE_INVALIDA, "codigo": "STK_VAL_CLAVE"}), 400
        resultados = _transferir_filas(filas, numeros, envio, operacion=_transferir_fila_cruda)
        # `todas_ok` es aditivo: el detalle por fila y el 200 no cambian.
        return jsonify({"resultados": resultados, "todas_ok": _todas_ok(resultados)})

    return jsonify({"error": "Tipo de carga no soportado"}), 400

def _procesar_filas_articulos(tipo, rows):
    resultados = []
    if tipo == "articulos":
        for i, row in enumerate(rows):
            if not row or row[0] in (None, ""):
                continue
            try:
                nombre, codigo, categoria = row[0], row[1], row[2]
                con_partidas = bool(row[3]) if len(row) > 3 and row[3] not in (None, "") else False
                se_compra = bool(row[4]) if len(row) > 4 and row[4] not in (None, "") else False
                se_vende = bool(row[5]) if len(row) > 5 and row[5] not in (None, "") else False
                origen = str(row[6]).strip().lower() if len(row) > 6 and row[6] not in (None, "") else None
                r = _crear_articulo(str(nombre), str(codigo), str(categoria), con_partidas, se_compra, se_vende, origen)
            except Exception as e:
                r = {"error": str(e)}
            r["fila"] = i + 2
            resultados.append(r)
    elif tipo == "articulos_modificar":
        for i, row in enumerate(rows):
            if not row or row[0] in (None, ""):
                continue
            try:
                articulo_id, nombre, codigo, categoria = row[0], row[1], row[2], row[3]
                con_partidas = bool(row[4]) if len(row) > 4 and row[4] not in (None, "") else False
                se_compra = bool(row[5]) if len(row) > 5 and row[5] not in (None, "") else False
                se_vende = bool(row[6]) if len(row) > 6 and row[6] not in (None, "") else False
                origen = str(row[7]).strip().lower() if len(row) > 7 and row[7] not in (None, "") else None
                r = _actualizar_articulo(int(articulo_id), str(nombre), str(codigo), str(categoria), con_partidas, se_compra, se_vende, origen)
            except Exception as e:
                r = {"error": str(e)}
            r["fila"] = i + 2
            resultados.append(r)
    return resultados

# ============================================================
# RUTAS STOCK - ARTÍCULOS CRUD
# ============================================================

def _crear_articulo(nombre, codigo, categoria, con_partidas, se_compra, se_vende, origen):
    if categoria not in CATEGORIAS_ARTICULO:
        return {"error": f"Categoría inválida: {categoria}"}
    if not se_compra and not se_vende:
        return {"error": "El artículo debe ser al menos 'se compra' o 'se vende'"}
    if origen not in CUENTAS_POR_ORIGEN:
        return {"error": "Falta indicar origen: local o exterior"}

    cuentas = CUENTAS_POR_ORIGEN[origen]
    existe = run_sql("SELECT 1 FROM STOC_ARTS WHERE ARTS_ARTICULO_EMP = ? AND ARTS_FECHA_BAJA IS NULL", params=[codigo])
    if existe:
        return {"error": f"Ya existe un artículo activo con código {codigo}"}

    sql_parts = ["BEGIN TRANSACTION;"]
    sql_parts.append("DECLARE @art INT = (SELECT ISNULL(MAX(ARTS_ARTICULO),0)+1 FROM STOC_ARTS WITH (UPDLOCK, TABLOCKX));")
    sql_parts.append(f"""
        INSERT INTO STOC_ARTS (
            ARTS_ARTICULO, ARTS_NOMBRE, ARTS_ARTICULO_EMP, ARTS_ARTICULO_IMP,
            ARTS_TIPO_ART, ARTS_UNIMED_STOCK, ARTS_CONTROL_STOCK, ARTS_CON_PARTIDAS,
            ARTS_NROS_SERIE, ARTS_CON_TALLES, ARTS_SE_VENDE, ARTS_SE_COMPRA,
            ARTS_FECHA_ALTA, ARTS_BLOQUEO_MOST, ARTS_PESO_EMB_UMS, ARTS_CANT_BULT_UMS,
            ARTS_FACTOR_HOMSTO, ARTS_CUENTA, ARTS_SE_PRODUCE, ARTS_CONSUMO_COM,
            ARTS_MODO_STOC_MIN, ARTS_STOCK_MINIMO, ARTS_GENERA_MOVSTK, ARTS_PORC_DMAXCAOF,
            ARTS_HABIL_PPP, ARTS_AJUS_CANT_UMS, ARTS_PORCMAX_AJUMS, ARTS_COSTEO_CIEMES,
            ARTS_FACTOR_UM_COT, ARTS_VOLUMEN_EMB_UMS, ARTS_DIAS_EXIS_ANTES_USO, ARTS_UMS_ES_UCMI,
            ARTS_FACTOR_UM_UCMI, ARTS_OPERA_CODBAR_PARTIDAS, ARTS_ASIGNA_AUTO_CODBAR_PARTIDAS,
            ARTS_APLICA_CTRL_CODBAR_PARTIDAS, ARTS_UTILIZA_CODIGO_BARRA,
            ARTS_REQ_ANAL_LAB_PARA_INGRESO, ARTS_REQ_IDENT_DEPOSITO_INGR_OTL,
            ARTS_EXIGE_VENCIM_PARTIDAS, ARTS_EXIGE_NUMERO_SERIE_PART
        ) VALUES (
            @art, {_sql_literal(nombre)}, {_sql_literal(codigo)}, '0',
            {_sql_literal(categoria)}, 'UN', 1, {1 if con_partidas else 0},
            0, 0, {1 if se_vende else 0}, {1 if se_compra else 0},
            CAST(GETDATE() AS DATE), 0, 0, 0,
            0, {_sql_literal(cuentas['arts'])}, 0, 1,
            1, 0, 1, 0,
            0, 0, 0, 0,
            0, 0, 0, 1,
            0, 0, 0,
            0, 1,
            0, 0,
            0, 0
        );
    """)

    if se_compra:
        sql_parts.append(f"""
            INSERT INTO STOC_ARCO (
                ARCO_ARTICULO, ARCO_RUBRO_COMPRA, ARCO_BLOQUEO_COMP, ARCO_CUENTA,
                ARCO_PESO_EMB_UMS, ARCO_CANT_BULT_UMS, ARCO_FACTOR_HOMCOM, ARCO_CANT_MIN_COMP,
                ARCO_CON_PREC_CERO, ARCO_UM_PRECIO_COM, ARCO_HAB_COMPRA_UM_DIF, ARCO_FACTOR_UM_DIF,
                ARCO_PORC_MAX_AJU_UM_DIF, ARCO_VOLUMEN_EMB_UMS, ARCO_ES_IMPORTADO
            ) VALUES (
                @art, '-', 0, {_sql_literal(cuentas['compra'])},
                0, 0, 0, 0,
                0, 0, 0, 0,
                0, 0, 0
            );
        """)

    if se_vende:
        sql_parts.append(f"""
            INSERT INTO STOC_ARVE (
                ARVE_ARTICULO, ARVE_RUBRO_VENTA, ARVE_BLOQUEO_VENTA, ARVE_CUENTA,
                ARVE_PESO_EMB_UMS, ARVE_CANT_BULT_UMS, ARVE_FACTOR_HOMVEN, ARVE_UM_PRECIO_VTA,
                ARVE_ES_BANDEJA, ARVE_ES_PALLET, ARVE_ES_CONJUNTO, ARVE_PRESTACION,
                ARVE_PERMITE_RES_DIF_PART, ARVE_VOLUMEN_EMB_UMS, ARVE_ADMIN_CORTES, ARVE_ES_SENIA
            ) VALUES (
                @art, '-', 0, {_sql_literal(cuentas['venta'])},
                0, 0, 0, 0,
                0, 0, 0, 0,
                0, 0, 0, 0
            );
        """)

    sql_parts.append("""
        UPDATE SIST_NUSI SET NUSI_ULTIMO_NUMERO = @art
        WHERE NUSI_NUMERADOR_ID = 4 AND NUSI_ULTIMO_NUMERO < @art;
    """)
    sql_parts.append("COMMIT TRANSACTION;")
    sql_parts.append("SELECT @art AS ArticuloId;")

    full_sql = " ".join(sql_parts)
    result_rows = run_sql(full_sql)
    r = result_rows[0] if result_rows else {}

    return {"ok": True, "articulo_id": r.get("ArticuloId")}

@stock_bp.route('/articulo', methods=["POST"])
@requiere_permiso(PermisosSistema.STOCK_CREAR)
def crear_articulo():
    data = request.get_json()
    try:
        resultado = _crear_articulo(
            data["nombre"], data["codigo"], data["categoria"], bool(data.get("con_partidas")),
            bool(data.get("se_compra")), bool(data.get("se_vende")), data.get("origen"),
        )
        if "error" in resultado:
            return jsonify(resultado), 400
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_bp.route('/articulo/<int:articulo_id>', methods=["GET"])
@requiere_permiso(PermisosSistema.STOCK_VER)
def detalle_articulo(articulo_id):
    rows = run_sql("""
        SELECT ARTS_ARTICULO, ARTS_NOMBRE, ARTS_ARTICULO_EMP, ARTS_TIPO_ART, ARTS_CON_PARTIDAS,
            ARTS_SE_COMPRA, ARTS_SE_VENDE, ARTS_CUENTA
        FROM STOC_ARTS WHERE ARTS_ARTICULO = ? AND ARTS_FECHA_BAJA IS NULL
    """, params=[articulo_id])
    if not rows:
        return jsonify({"error": "Artículo no encontrado"}), 404
    r = rows[0]
    cuenta = str(r["ARTS_CUENTA"]).strip()
    origen = "local" if cuenta == CUENTAS_POR_ORIGEN["local"]["arts"] else "exterior"

    return jsonify({
        "id": r["ARTS_ARTICULO"],
        "nombre": r["ARTS_NOMBRE"],
        "codigo": r["ARTS_ARTICULO_EMP"],
        "categoria": str(r["ARTS_TIPO_ART"]).strip(),
        "con_partidas": bool(r["ARTS_CON_PARTIDAS"]),
        "se_compra": bool(r["ARTS_SE_COMPRA"]),
        "se_vende": bool(r["ARTS_SE_VENDE"]),
        "origen": origen,
    })

def _actualizar_articulo(articulo_id, nombre, codigo, categoria, con_partidas, se_compra, se_vende, origen):
    if categoria not in CATEGORIAS_ARTICULO:
        return {"error": f"Categoría inválida: {categoria}"}
    if not se_compra and not se_vende:
        return {"error": "El artículo debe ser al menos 'se compra' o 'se vende'"}
    if origen not in CUENTAS_POR_ORIGEN:
        return {"error": "Falta indicar origen: local o exterior"}

    actual = run_sql("SELECT ARTS_SE_COMPRA, ARTS_SE_VENDE FROM STOC_ARTS WHERE ARTS_ARTICULO = ? AND ARTS_FECHA_BAJA IS NULL", params=[articulo_id])
    if not actual:
        return {"error": "Artículo no encontrado"}
    tenia_compra = bool(actual[0]["ARTS_SE_COMPRA"])
    tenia_venta = bool(actual[0]["ARTS_SE_VENDE"])

    duplicado = run_sql("""
        SELECT 1 FROM STOC_ARTS WHERE ARTS_ARTICULO_EMP = ? 
        AND ARTS_ARTICULO <> ? AND ARTS_FECHA_BAJA IS NULL
    """, params=[codigo, articulo_id])
    if duplicado:
        return {"error": f"Ya existe otro artículo activo con código {codigo}"}

    cuentas = CUENTAS_POR_ORIGEN[origen]

    sql_parts = ["BEGIN TRANSACTION;"]
    sql_parts.append(f"""
        UPDATE STOC_ARTS SET
            ARTS_NOMBRE = {_sql_literal(nombre)}, ARTS_ARTICULO_EMP = {_sql_literal(codigo)},
            ARTS_TIPO_ART = {_sql_literal(categoria)}, ARTS_CON_PARTIDAS = {1 if con_partidas else 0},
            ARTS_SE_COMPRA = {1 if se_compra else 0}, ARTS_SE_VENDE = {1 if se_vende else 0},
            ARTS_CUENTA = {_sql_literal(cuentas['arts'])}
        WHERE ARTS_ARTICULO = {articulo_id};
    """)

    if se_compra and not tenia_compra:
        sql_parts.append(f"""
            INSERT INTO STOC_ARCO (
                ARCO_ARTICULO, ARCO_RUBRO_COMPRA, ARCO_BLOQUEO_COMP, ARCO_CUENTA,
                ARCO_PESO_EMB_UMS, ARCO_CANT_BULT_UMS, ARCO_FACTOR_HOMCOM, ARCO_CANT_MIN_COMP,
                ARCO_CON_PREC_CERO, ARCO_UM_PRECIO_COM, ARCO_HAB_COMPRA_UM_DIF, ARCO_FACTOR_UM_DIF,
                ARCO_PORC_MAX_AJU_UM_DIF, ARCO_VOLUMEN_EMB_UMS, ARCO_ES_IMPORTADO
            ) VALUES (
                {articulo_id}, '-', 0, {_sql_literal(cuentas['compra'])},
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
            );
        """)
    elif se_compra and tenia_compra:
        sql_parts.append(f"""
            UPDATE STOC_ARCO SET ARCO_CUENTA = {_sql_literal(cuentas['compra'])}
            WHERE ARCO_ARTICULO = {articulo_id};
        """)
    elif not se_compra and tenia_compra:
        sql_parts.append(f"DELETE FROM STOC_ARCO WHERE ARCO_ARTICULO = {articulo_id};")

    if se_vende and not tenia_venta:
        sql_parts.append(f"""
            INSERT INTO STOC_ARVE (
                ARVE_ARTICULO, ARVE_RUBRO_VENTA, ARVE_BLOQUEO_VENTA, ARVE_CUENTA,
                ARVE_PESO_EMB_UMS, ARVE_CANT_BULT_UMS, ARVE_FACTOR_HOMVEN, ARVE_UM_PRECIO_VTA,
                ARVE_ES_BANDEJA, ARVE_ES_PALLET, ARVE_ES_CONJUNTO, ARVE_PRESTACION,
                ARVE_PERMITE_RES_DIF_PART, ARVE_VOLUMEN_EMB_UMS, ARVE_ADMIN_CORTES, ARVE_ES_SENIA
            ) VALUES (
                {articulo_id}, '-', 0, {_sql_literal(cuentas['venta'])},
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
            );
        """)
    elif se_vende and tenia_venta:
        sql_parts.append(f"""
            UPDATE STOC_ARVE SET ARVE_CUENTA = {_sql_literal(cuentas['venta'])}
            WHERE ARVE_ARTICULO = {articulo_id};
        """)
    elif not se_vende and tenia_venta:
        sql_parts.append(f"DELETE FROM STOC_ARVE WHERE ARVE_ARTICULO = {articulo_id};")

    sql_parts.append("COMMIT TRANSACTION;")
    full_sql = " ".join(sql_parts)
    run_sql(full_sql, fetch=False)

    return {"ok": True, "articulo_id": articulo_id}

@stock_bp.route('/articulo/<int:articulo_id>', methods=["PUT"])
@requiere_permiso(PermisosSistema.STOCK_EDITAR)
def actualizar_articulo(articulo_id):
    data = request.get_json()
    try:
        resultado = _actualizar_articulo(
            articulo_id, data["nombre"], data["codigo"], data["categoria"], bool(data.get("con_partidas")),
            bool(data.get("se_compra")), bool(data.get("se_vende")), data.get("origen"),
        )
        if "error" in resultado:
            return jsonify(resultado), 400
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_bp.route('/articulo/codigo/<codigo>/nombre', methods=["PUT"])
@requiere_permiso(PermisosSistema.STOCK_EDITAR)
def renombrar_articulo_por_codigo(codigo):
    data = request.get_json()
    nombre = data.get("nombre")
    bases = data.get("bases")
    # C4: validar acceso a cada base destino (fail-closed).
    _no_autorizadas = [
        b for b in (bases or [])
        if b in BASES_DISPONIBLES and chequear_acceso_base(b) is not None
    ]
    if _no_autorizadas:
        return jsonify({"error": f"Base(s) no autorizada(s): {', '.join(_no_autorizadas)}", "code": "BASE_FORBIDDEN"}), 403

    if not bases:
        try:
            rows = run_sql("SELECT ARTS_ARTICULO FROM STOC_ARTS WHERE ARTS_ARTICULO_EMP = ? AND ARTS_FECHA_BAJA IS NULL", params=[codigo])
            if not rows:
                return jsonify({"error": f"Artículo con código {codigo} no encontrado"}), 404
            articulo_id = rows[0]["ARTS_ARTICULO"]
            run_sql(f"UPDATE STOC_ARTS SET ARTS_NOMBRE = {_sql_literal(nombre)} WHERE ARTS_ARTICULO = {articulo_id};", fetch=False)
            return jsonify({"ok": True, "articulo_id": articulo_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    base_original, server_original = g.db_database, g.db_server
    division_original, sucursal_original = g.division, g.sucursal
    resultados_por_base = {}
    try:
        for base in bases:
            if base not in BASES_DISPONIBLES:
                resultados_por_base[base] = {"error": f"Base desconocida: {base}"}
                continue
            set_contexto_base(base)
            try:
                rows = run_sql("SELECT ARTS_ARTICULO FROM STOC_ARTS WHERE ARTS_ARTICULO_EMP = ? AND ARTS_FECHA_BAJA IS NULL", params=[codigo])
                if not rows:
                    resultados_por_base[base] = {"error": f"Artículo con código {codigo} no encontrado"}
                    continue
                articulo_id = rows[0]["ARTS_ARTICULO"]
                run_sql(f"UPDATE STOC_ARTS SET ARTS_NOMBRE = {_sql_literal(nombre)} WHERE ARTS_ARTICULO = {articulo_id};", fetch=False)
                resultados_por_base[base] = {"ok": True, "articulo_id": articulo_id}
            except Exception as e:
                resultados_por_base[base] = {"error": str(e)}
    finally:
        g.db_database, g.db_server = base_original, server_original
        g.division, g.sucursal = division_original, sucursal_original

    return jsonify({"resultados_por_base": resultados_por_base})

@stock_bp.route('/deposito/<int:deposito_id>/nombre', methods=["PUT"])
@requiere_permiso(PermisosSistema.STOCK_EDITAR)
def renombrar_deposito(deposito_id):
    data = request.get_json()
    nombre = data.get("nombre")
    if not nombre or not str(nombre).strip():
        return jsonify({"error": "El nombre no puede estar vacío"}), 400

    existe = run_sql("SELECT 1 FROM STOC_DPOS WHERE DPOS_DEPOSITO = ? AND DPOS_UTILIZABLE = 1", params=[deposito_id])
    if not existe:
        return jsonify({"error": "Depósito no encontrado"}), 404

    run_sql(f"UPDATE STOC_DPOS SET DPOS_NOMBRE = {_sql_literal(nombre)} WHERE DPOS_DEPOSITO = {deposito_id};", fetch=False)
    return jsonify({"ok": True, "deposito_id": deposito_id})

@stock_bp.route('/deposito/<int:deposito_id>/nombre/multibases', methods=["PUT"])
@requiere_permiso(PermisosSistema.STOCK_EDITAR)
def renombrar_deposito_multibases(deposito_id):
    data = request.get_json()
    nombre = data.get("nombre")
    bases = data.get("bases", [])
    # C4: validar acceso a cada base destino (fail-closed).
    _no_autorizadas = [
        b for b in (bases or [])
        if b in BASES_DISPONIBLES and chequear_acceso_base(b) is not None
    ]
    if _no_autorizadas:
        return jsonify({"error": f"Base(s) no autorizada(s): {', '.join(_no_autorizadas)}", "code": "BASE_FORBIDDEN"}), 403

    if not bases:
        return renombrar_deposito(deposito_id)

    base_original, server_original = g.db_database, g.db_server
    division_original, sucursal_original = g.division, g.sucursal
    resultados_por_base = {}
    try:
        for base in bases:
            if base not in BASES_DISPONIBLES:
                resultados_por_base[base] = {"error": f"Base desconocida: {base}"}
                continue
            set_contexto_base(base)
            try:
                existe = run_sql("SELECT 1 FROM STOC_DPOS WHERE DPOS_DEPOSITO = ? AND DPOS_UTILIZABLE = 1", params=[deposito_id])
                if not existe:
                    resultados_por_base[base] = {"error": "Depósito no encontrado"}
                    continue
                run_sql(f"UPDATE STOC_DPOS SET DPOS_NOMBRE = {_sql_literal(nombre)} WHERE DPOS_DEPOSITO = {deposito_id};", fetch=False)
                resultados_por_base[base] = {"ok": True}
            except Exception as e:
                resultados_por_base[base] = {"error": str(e)}
    finally:
        g.db_database, g.db_server = base_original, server_original
        g.division, g.sucursal = division_original, sucursal_original

    return jsonify({"resultados_por_base": resultados_por_base})

# ============================================================
# RUTAS STOCK - CONSOLIDADO (CORREGIDO - usa run_sql_db)
# ============================================================

def _stock_en_base(base, q):
    """
    Obtiene el stock de una base específica usando run_sql_db (conexión directa).
    Retorna (stock_dict, nombres_dict)
    """
    try:
        q_esc = q.replace("'", "''")
        where = (
            "a.ARTS_ARTICULO_EMP IS NOT NULL AND LTRIM(RTRIM(a.ARTS_ARTICULO_EMP)) <> '' "
            "AND a.ARTS_ARTICULO_EMP NOT LIKE '%[^0-9.]%' AND a.ARTS_FECHA_BAJA IS NULL"
        )
        if q_esc:
            where += f" AND (a.ARTS_NOMBRE LIKE '%{q_esc}%' OR a.ARTS_ARTICULO_EMP LIKE '%{q_esc}%')"

        query = f"""
            SELECT a.ARTS_ARTICULO_EMP AS codigo, a.ARTS_NOMBRE AS nombre,
                   s.STDP_DEPOSITO AS deposito, s.STDP_STOCK_ACT AS cantidad
            FROM STOC_STDP s
            JOIN STOC_ARTS a ON a.ARTS_ARTICULO = s.STDP_ARTICULO
            WHERE {where}
        """

        # Obtener credenciales de la base
        info = BASES_DISPONIBLES.get(base, {})
        server = info.get("server") or SQL_SERVER
        username = info.get("user") or SQL_USERNAME
        password = info.get("password") or SQL_PASSWORD

        # Usar run_sql_db para la conexión directa
        rows = run_sql_db(
            database=base,
            query=query,
            params=[],
            fetch=True,
            server=server,
            username=username,
            password=password,
            timeout=30
        )

        stock = {}
        nombres = {}
        for r in rows:
            cod = str(r.get("codigo", "")).strip()
            dep = int(r.get("deposito", 0))
            qty = float(r.get("cantidad", 0) or 0)
            nombre = str(r.get("nombre", "")).strip()
            if cod:
                stock[(cod, dep)] = qty
                if cod not in nombres:
                    nombres[cod] = nombre
        return stock, nombres

    except Exception as e:
        logger.error(f"Error en _stock_en_base para {base}: {e}")
        return {}, {}

@stock_bp.route('/stock/consolidado', methods=["GET"])
@requiere_permiso(PermisosSistema.STOCK_REPORTES)
def stock_consolidado():
    try:
        q = request.args.get("q", "").strip()

        resultados = {}
        lock = threading.Lock()
        errores = {}

        def consultar(base):
            try:
                s, n = _stock_en_base(base, q)
                with lock:
                    resultados[base] = (s, n)
            except Exception as e:
                with lock:
                    errores[base] = str(e)

        threads = []
        for base in list(BASES_DISPONIBLES.keys()):
            t = threading.Thread(target=consultar, args=(base,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=35)

        # Si todas las bases fallaron, devolver error
        if not resultados:
            return jsonify({"error": "No se pudo obtener stock de ninguna base", "detalles": errores}), 500

        nombres_por_base = {}
        uy_stock, uy_nombres = resultados.get("plataforma_ur", ({}, {}))

        for base, (stock, nombres) in resultados.items():
            sigla = BASES_DISPONIBLES[base]["sigla"]
            for cod, nombre in nombres.items():
                if nombre:
                    nombres_por_base.setdefault(cod, {})[base] = nombre

        for cod, nombre in uy_nombres.items():
            if nombre:
                nombres_por_base.setdefault(cod, {})["plataforma_ur"] = nombre

        todos_codigos = set(nombres_por_base.keys())
        if not todos_codigos:
            return jsonify([])

        DEPOSITO_SIGLA = {
            7: "HN",
            10: "HN",
            14: "RD",
            9: "CO",
            13: "PE",
            11: "PY",
            12: "EC",
        }
        DEPOSITO_NOMBRE = {
            7: "Honduras",
            10: "Honduras",
            14: "República Dominicana",
            9: "Colombia",
            13: "Perú",
            11: "Paraguay",
            12: "Ecuador",
        }

        def uy_col_detalle(col_name):
            deps = _UY_COLS[col_name]
            resultado = {}
            for cod in todos_codigos:
                detalle = {}
                for dep in deps:
                    cantidad = uy_stock.get((cod, dep), 0)
                    if cantidad > 0:
                        sigla = DEPOSITO_SIGLA.get(dep, f"DEP{dep}")
                        if sigla not in detalle:
                            detalle[sigla] = 0
                        detalle[sigla] += cantidad
                resultado[cod] = detalle
            return resultado

        uy_transito_detalle = uy_col_detalle("TRANSITO")
        
        def uy_col_total(col_name):
            deps = _UY_COLS[col_name]
            return {cod: sum(uy_stock.get((cod, d), 0) for d in deps) for cod in todos_codigos}

        uy_zf = uy_col_total("ZF")
        uy_fabrica = uy_col_total("FABRICA")
        uy_transito = uy_col_total("TRANSITO")

        def total_pais(base):
            stock, _ = resultados.get(base, ({}, {}))
            return {cod: sum(v for (c, d), v in stock.items() if c == cod) for cod in todos_codigos}

        paises_stock = {base: total_pais(base) for base in _BASES_CONSOLIDADO}

        filas = []

        def _sort_key(cod):
            try:
                return [int(x) for x in str(cod).split(".")]
            except Exception:
                return [0]

        for cod in sorted(todos_codigos, key=_sort_key):
            nombre_a_bases = {}
            for base, nombre in nombres_por_base.get(cod, {}).items():
                nombre_a_bases.setdefault(nombre, []).append(base)

            nombres_ordenados = sorted(nombre_a_bases.keys())
            inconsistente = len(nombres_ordenados) > 1
            total_global = (
                uy_zf.get(cod, 0) + uy_fabrica.get(cod, 0) + uy_transito.get(cod, 0)
                + sum(paises_stock[b].get(cod, 0) for b in _BASES_CONSOLIDADO)
            )
            if total_global == 0:
                continue

            for i, nombre in enumerate(nombres_ordenados):
                bases_de_este_nombre = nombre_a_bases[nombre]
                siglas_de_este_nombre = {BASES_DISPONIBLES[b]["sigla"] for b in bases_de_este_nombre}
                es_uy = "plataforma_ur" in bases_de_este_nombre

                siglas_ordenadas = sorted(
                    (["UY"] if es_uy else []) +
                    [BASES_DISPONIBLES[b]["sigla"] for b in bases_de_este_nombre if b != "plataforma_ur"]
                )
                
                transito_detalle = uy_transito_detalle.get(cod, {})
                transito_tooltip = ""
                if transito_detalle:
                    partes = [f"{pais}: {int(round(cant))}" for pais, cant in sorted(transito_detalle.items())]
                    transito_tooltip = " | ".join(partes)
                
                fila = {
                    "codigo": cod if i == 0 else "",
                    "nombre": nombre,
                    "inconsistente": inconsistente,
                    "primera_fila": i == 0,
                    "_siglas": siglas_ordenadas,
                    "ZF": uy_zf.get(cod, 0) if es_uy else 0,
                    "FABRICA": uy_fabrica.get(cod, 0) if es_uy else 0,
                    "TRANSITO": uy_transito.get(cod, 0) if es_uy else 0,
                    "_transito_tooltip": transito_tooltip,
                }
                for base in _BASES_CONSOLIDADO:
                    sigla = BASES_DISPONIBLES[base]["sigla"]
                    fila[sigla] = paises_stock[base].get(cod, 0) if sigla in siglas_de_este_nombre else 0

                fila["_total"] = (
                    fila["ZF"] + fila["FABRICA"] + fila["TRANSITO"]
                    + sum(fila[BASES_DISPONIBLES[b]["sigla"]] for b in _BASES_CONSOLIDADO)
                )
                filas.append(fila)

        return jsonify(filas)
    except Exception as e:
        logger.error(f"Error en stock_consolidado: {e}")
        return jsonify({"error": str(e)}), 500