# modules/cxp/routes.py
# ============================================================
# RUTAS CXP - SIDESYS ERP (CORREGIDO)
# ============================================================

from flask import Blueprint, request, jsonify, g, session
import base64
import gc
import tempfile
import os
import re
import io
import time
from modules.shared.database import run_sql, run_sql_db, _sql_literal
from modules.shared.utils import to_base64
from .parser import parse_fel_page, extraer_texto_pagina, ocr_image_bytes
from cuentas import NIT_CUENTA_FIJA
from modules.shared.decorators import requiere_permiso, requiere_superadmin
from modules.shared.permisos import PermisosSistema
from modules.shared.config_central import auditar
from modules.shared.idempotencia import (AlmacenIdempotencia, clave_valida,
                                         huella_de_payload)
# El servicio trae sus propios errores: se importan con alias porque este modulo
# ya define un `ErrorValidacion` local (el de las validaciones de entrada de los
# demas endpoints de CxP).
from .servicio_comprobantes import (Contexto, ErrorValidacion as ErrorValidacionCxP,
                                    ErrorServicio as ErrorServicioCxP,
                                    CLAVES_INTEGRIDAD, CLAVES_ESTRUCTURALES, PARAMETROS_CXP,
                                    MENSAJE_CLAVE_INVALIDA, MENSAJE_CLAVE_REUTILIZADA,
                                    MENSAJE_CLIENTE_VIEJO, MENSAJE_MOTIVO,
                                    mensaje_de_error_cxp, sql_alta, sql_baja, sql_integridad,
                                    validar_alta, validar_baja)
import pdfplumber
import openpyxl
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

cxp_bp = Blueprint('cxp', __name__, url_prefix='/api')

# ============================================================
# VALIDACION DE ENTRADA CXP (anti-inyeccion SQL)
# ============================================================

class ErrorValidacion(Exception):
    """Error controlado de validacion de entrada (se devuelve como HTTP 400)."""
    pass


# ============================================================
# LIMPIEZA DE TEMPORALES (no puede romper la respuesta)
# ============================================================

def limpiar_temporal(ruta, intentos=3):
    """Borra un temporal SIN poder romper la respuesta del endpoint.

    En Windows `os.unlink` falla con `[WinError 32]` mientras algun proceso tenga
    el archivo abierto, y `pdfplumber`/`pdfminer` NO sueltan el handle al cerrar
    el documento: hay que soltar la referencia al objeto para que se recolecte.
    Medido el 19/09/2026 con un PDF real de 12 paginas: con `page.extract_text()`
    (y sin OCR), `close()` no alcanzaba, `del pdf` + `gc.collect()` si.

    Por eso: `gc.collect()` (el llamador tiene que haber soltado su referencia),
    y si el borrado igual falla, se reintenta un par de veces con una recoleccion
    en el medio. Si aun asi falla, se loguea y se SIGUE: el temporal queda en
    `%TEMP%` (inocuo, lo limpia el sistema) y una carga que salio bien nunca se
    convierte en 500 por esto. Nada de `raise` aca.

    Devuelve True si el archivo quedo borrado (o ya no estaba)."""
    for intento in range(intentos):
        gc.collect()
        try:
            os.unlink(ruta)
            return True
        except FileNotFoundError:
            return True
        except OSError as e:
            if intento == intentos - 1:
                logger.warning(f"No se pudo borrar el temporal {ruta} (queda en %TEMP%): {e}")
                return False
            time.sleep(0.2)
    return False


def _validar_fecha_cxp(valor, campo, obligatoria=False):
    if valor in (None, ''):
        if obligatoria:
            raise ErrorValidacion("El campo '" + campo + "' es obligatorio (formato AAAA-MM-DD)")
        return None
    try:
        return date.fromisoformat(str(valor).strip()).isoformat()
    except (TypeError, ValueError):
        raise ErrorValidacion("El campo '" + campo + "' debe tener formato AAAA-MM-DD")


def _validar_entero_cxp(valor, campo, obligatoria=False):
    if valor in (None, ''):
        if obligatoria:
            raise ErrorValidacion("El campo '" + campo + "' es obligatorio")
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErrorValidacion("El campo '" + campo + "' debe ser un numero entero")


# ============================================================
# RUTAS CXP - PROVEEDORES Y CONDICIONES
# ============================================================

@cxp_bp.route('/proveedores')
@requiere_permiso(PermisosSistema.CXP_VER)
def proveedores():
    try:
        q = request.args.get("q", "").replace("'", "''")
        rows = run_sql(f"""
            SELECT TOP 50 PROV_PROVEEDOR as id, PROV_NOMBRE as nombre
            FROM CPAG_PROV
            WHERE PROV_FECHA_BAJA IS NULL
              AND (CAST(PROV_PROVEEDOR AS VARCHAR) LIKE '%{q}%' OR PROV_NOMBRE LIKE '%{q}%')
            ORDER BY PROV_NOMBRE
        """)
        return jsonify(rows)
    except Exception as e:
        logger.error(f"Error en /proveedores: {e}")
        return jsonify([])

@cxp_bp.route('/condiciones_pago')
@requiere_permiso(PermisosSistema.CXP_VER)
def condiciones_pago():
    try:
        rows = run_sql("""
            SELECT CPPR_COND_PAGO as id, CPPR_NOMBRE as nombre
            FROM CPAG_CPPR WHERE CPPR_UTILIZABLE=1 ORDER BY CPPR_NOMBRE
        """)
        return jsonify(rows)
    except Exception as e:
        logger.error(f"Error en /condiciones_pago: {e}")
        return jsonify([])

@cxp_bp.route('/cuentas')
@requiere_permiso(PermisosSistema.CXP_VER)
def get_cuentas():
    """Cuentas de gasto DE LA BASE ACTIVA (antes devolvia siempre la lista
    hardcodeada de Guatemala, cualquiera fuera la base).

    Si la base activa no esta habilitada (no tiene entrada en `PARAMETROS_CXP`,
    hoy solo `plataforma_gt`) esto devuelve **200 con `[]`**, y el selector queda
    vacio. Lo que el operador ve en una base no habilitada NO es el selector: es
    el cartel "Cargador de Facturas exclusivo para Guatemala", que pone
    `validarBaseCxP()` (`frontend/modules/cxp/ui.js`) leyendo `cxp_habilitado` de
    `/api/bases`, porque esconde el modulo entero.

    El fallback con la lista de Guatemala de `frontend/modules/cxp/render.js` NO
    cubre este caso: vive en el `catch` de la carga de `/api/cuentas`, o sea que
    se dispara con un error de red o un HTTP no-ok, no con un 200 vacio."""
    try:
        parametros = PARAMETROS_CXP.get(getattr(g, 'db_database', '')) or {}
        cuentas = parametros.get('cuentas_gasto') or {}
        return jsonify([
            {"codigo": codigo, "nombre": datos["nombre"], "cco": datos["cco"]}
            for codigo, datos in sorted(cuentas.items())
        ])
    except Exception as e:
        logger.error(f"Error en /cuentas: {e}")
        return jsonify([])

# ============================================================
# RUTA: VALIDACION DE INTEGRIDAD DEL CIRCUITO DE CXP (solo lectura)
# ============================================================

@cxp_bp.route('/validar_integridad')
@requiere_permiso(PermisosSistema.CXP_VER)
def validar_integridad():
    """Chequeo real del circuito de CxP (antes esta URL no existia y la pantalla
    mostraba un OK ficticio). Solo lectura y acotado a la division pedida."""
    try:
        division = _validar_entero_cxp(request.args.get("division", 7), "division", obligatoria=True)
    except ErrorValidacion as e:
        return jsonify({"error": str(e), "codigo": "CXP_VAL_ENTERO"}), 400
    try:
        filas = run_sql(sql_integridad(division)) or []
    except Exception as e:
        logger.error(f"Error en /validar_integridad: {e}")
        return jsonify({"error": "No se pudo validar la integridad del circuito de Cuentas a Pagar."}), 500
    # Spec §4.12: el OK no puede ser ficticio. Sin la fila de conteos (o sin las
    # cinco cuentas) NO se midio nada: eso es un error del servidor, no un
    # "todo bien" con total_problemas = 0.
    sin_medicion = "No se pudo verificar la integridad del circuito de Cuentas a Pagar."
    if not filas:
        logger.error("validar_integridad: la consulta no devolvio la fila de conteos")
        return jsonify({"error": sin_medicion}), 500
    fila = filas[0] or {}
    try:
        conteos = {clave: int(fila.get(clave)) for clave in CLAVES_INTEGRIDAD[:5]}
    except (TypeError, ValueError) as e:
        logger.error(f"validar_integridad: la fila de conteos no trae las cinco cuentas: {e}")
        return jsonify({"error": sin_medicion}), 500
    # `total_problemas` y `estado_general` salen de las CUATRO cuentas
    # ESTRUCTURALES (`CLAVES_ESTRUCTURALES`), no de las cinco: una nota de debito
    # sin RCCP cuenta dos veces (esta en `facturas_sin_rccp` y en
    # `notas_debito_sin_rccp`, que es un subconjunto suyo), asi que sigue siendo
    # una cota superior y no la cantidad de comprobantes distintos.
    # `asientos_sin_comentario` NO suma: medido el 18/09/2026 en GT, division 7
    # (`_investigacion_gt/136_integridad_falsos_positivos.py`), da 6.953 (5.867
    # acotado al subdiario de CxP) y es como esta cargada la base, no un defecto
    # del circuito; se sigue devolviendo porque la pantalla lista las cinco
    # cuentas. La spec §4.12 fija SIETE claves exactas, asi que no se agrega un
    # campo con el total sin repeticiones.
    total = sum(conteos[clave] for clave in CLAVES_ESTRUCTURALES)
    return jsonify({**conteos,
                    "estado_general": "OK" if total == 0 else "CON PROBLEMAS",
                    "total_problemas": total})

# ============================================================
# RUTA: CENTROS DE COSTO
# ============================================================

@cxp_bp.route('/centros_costo')
@requiere_permiso(PermisosSistema.CXP_VER)
def get_centros_costo():
    """Lista de centros de costo desde CONT_IMAE"""
    try:
        print("📊 Consultando CONT_IMAE para centros de costo...")
        rows = run_sql("""
            SELECT 
                IMAE_INSTANCIA as codigo,
                IMAE_DESCRIPCION1 as nombre,
                'S' as cco
            FROM CONT_IMAE
            WHERE IMAE_MAESTRO = 'CCO'
            AND IMAE_UTILIZABLE = 1
            ORDER BY IMAE_INSTANCIA
        """)
        
        print(f"✅ Centros de costo encontrados: {len(rows) if rows else 0}")
        
        if rows and len(rows) > 0:
            return jsonify(rows)
        else:
            return jsonify([])
            
    except Exception as e:
        logger.error(f"Error en /centros_costo: {e}")
        return jsonify([])

@cxp_bp.route('/cotizacion')
@requiere_permiso(PermisosSistema.CXP_VER)
def get_cotizacion():
    try:
        moneda = request.args.get('moneda', 'DL')
        fecha = _validar_fecha_cxp(request.args.get('fecha'), 'fecha') or date.today().isoformat()
        
        if moneda == 'PS':
            return jsonify({"cotizacion": 1.0})
        
        rows = run_sql(f"""
            SELECT TOP 1 COTI_COTIZACION as c 
            FROM SIST_COTI
            WHERE COTI_MONEDA1='DL' AND COTI_MONEDA2='PS' AND COTI_FECHA <= '{fecha}'
            ORDER BY COTI_FECHA DESC
        """)
        
        cotizacion = float(str(rows[0]['c']).replace(',', '.')) if rows and rows[0].get('c') else 7.61982
        return jsonify({"cotizacion": cotizacion})
    except ErrorValidacion as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error en /cotizacion: {e}")
        return jsonify({"cotizacion": 7.61982})

@cxp_bp.route('/parsear_pdf', methods=["POST"])
@requiere_permiso(PermisosSistema.CXP_IMPORTAR)
def parsear_pdf():
    try:
        data = request.json
        if not data:
            return jsonify({"ok": False, "error": "Datos requeridos"}), 400
            
        file_b64 = data.get("file_b64")
        if not file_b64:
            return jsonify({"ok": False, "error": "Archivo no proporcionado"}), 400
            
        file_type = data.get("file_type", "application/pdf")
        file_bytes = base64.b64decode(file_b64)
        facturas = []

        if file_type.startswith("image/"):
            text = ocr_image_bytes(file_bytes)
            if len(text.strip()) < 20:
                return jsonify({"ok": False, "error": "No se pudo extraer texto de la imagen."}), 400
            parsed = parse_fel_page(text)
            parsed['pagina'] = 1
            facturas.append(parsed)
        else:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
                with pdfplumber.open(tmp_path) as pdf:
                    nros_vistos = set()
                    for i, page in enumerate(pdf.pages):
                        text = extraer_texto_pagina(page)
                        if len(text.strip()) < 20:
                            try:
                                img = page.to_image(resolution=200).original
                                buf = io.BytesIO()
                                img.save(buf, format="PNG")
                                text = ocr_image_bytes(buf.getvalue())
                            except Exception as e:
                                logger.warning(f"Error en OCR de página {i+1}: {e}")
                                continue
                        if len(text.strip()) < 20:
                            continue
                        parsed = parse_fel_page(text)
                        nro = parsed.get('numero_dte', '')
                        if nro and nro in nros_vistos:
                            continue
                        if nro:
                            nros_vistos.add(nro)
                        if not parsed.get('total') and not parsed.get('nit_emisor') and not parsed.get('numero_dte'):
                            continue
                        parsed['pagina'] = i + 1
                        facturas.append(parsed)
            finally:
                # El handle de pdfminer no se suelta con `close()`: el documento
                # se cierra (y se suelta la referencia) ACA, antes de borrar el
                # temporal, y el helper reintenta con una recoleccion en el medio.
                # Nunca levanta: con el PDF real de 12 paginas, el `os.unlink`
                # fallaba con WinError 32 y convertia en 500 una carga que habia
                # salido bien. El `vars()` es por si `pdfplumber.open` fallo (el
                # nombre no existe todavia y un NameError taparia el error real).
                if 'pdf' in vars():
                    pdf.close()
                    pdf = None
                limpiar_temporal(tmp_path)

        if not facturas:
            return jsonify({"ok": False, "error": "No se detectaron facturas en el archivo."}), 400

        for f in facturas:
            try:
                nit = f.get('nit_emisor', '')
                f['es_eventual'] = False
                f['cuenta_fija'] = NIT_CUENTA_FIJA.get(nit, '')
                if nit:
                    nit_clean = re.sub(r"['\s]", '', nit).upper()
                    nit_sql = nit_clean.replace("'", "''")
                    rows = run_sql(f"""
                        SELECT TOP 1 PROV_PROVEEDOR as id, PROV_NOMBRE as nombre, PROV_CUENTA_PROVED as cuenta_prov
                        FROM CPAG_PROV
                        WHERE UPPER(REPLACE(REPLACE(PROV_CUIT,'-',''),' ','')) LIKE '%{nit_sql}%' AND PROV_FECHA_BAJA IS NULL
                    """)
                    if rows:
                        f['proveedor_id'] = rows[0]['id']
                        f['proveedor_nombre'] = rows[0]['nombre']
                        f['cuenta_prov'] = rows[0].get('cuenta_prov', '') or '210101001'
                    else:
                        f['proveedor_id'] = None
                        f['proveedor_nombre'] = None
                    nctp = run_sql(f"""
                        SELECT TOP 1 NCTP_NOMBRE as nombre, NCTP_DOMICILIO as domicilio, NCTP_LOCALIDAD as localidad
                        FROM CPAG_NCTP
                        WHERE UPPER(REPLACE(REPLACE(NCTP_CUIT,'-',''),' ','')) = '{nit_sql}'
                        ORDER BY NCTP_CTACTE_CTEP DESC
                    """)
                    if nctp:
                        f['eventual_nombre'] = nctp[0]['nombre']
                        f['eventual_localidad'] = nctp[0]['localidad']
                        f['eventual_conocido'] = True
                    else:
                        f['eventual_nombre'] = f.get('nombre_emisor', '')
                        f['eventual_localidad'] = 'GT'
                        f['eventual_conocido'] = False
            except Exception as e:
                logger.warning(f"Error procesando factura: {e}")

        return jsonify({"ok": True, "facturas": facturas})
    except Exception as e:
        logger.error(f"Error en /parsear_pdf: {e}")
        return jsonify({"ok": False, "error": f"Error al procesar PDF: {str(e)}"}), 500

# ============================================================
# CXP: SERVICIO, EJECUCION Y TRADUCCION DE ERRORES
# ============================================================

# Mensajes del endpoint (los del servicio viven en servicio_comprobantes.py).
MENSAJE_ALTA_SIN_CONFIRMAR = ("No se pudo confirmar el comprobante grabado: reintentá y, "
                              "si persiste, avisá a soporte.")
MENSAJE_BAJA_SIN_CONFIRMAR = ("No se pudo confirmar la baja del comprobante: verificá si sigue "
                              "existiendo y, si persiste, avisá a soporte.")
MENSAJE_ENTERO_INTERNO = "El campo 'nro_interno' tiene que ser un numero entero."


def _contexto_cxp(datos):
    """Base activa (`g.db_database`), division del comprobante y usuario de la
    sesion (para la auditoria)."""
    return Contexto(base=g.db_database,
                    division=(datos or {}).get('division', 7),
                    usuario=session.get('username', ''))


def _filas_de_lote(sql):
    """Ejecuta el lote del servicio y traduce el error de la base a
    ErrorServicioCxP. El 547 (FK) se le pide a run_sql solo por este camino
    (ver database._texto_de_error_propio): asi el texto crudo de la base no
    llega a ningun otro modulo."""
    try:
        return run_sql(sql, permitir_error_fk=True) or []
    except Exception as e:
        logger.error(f"Error de CxP en el lote: {e}")
        codigo, mensaje, datos_extra = mensaje_de_error_cxp(str(e))
        raise ErrorServicioCxP(codigo, mensaje, datos_extra)


def _entero(valor):
    """Los ids y los numeros de comprobante salen como DECIMAL: jsonify no los
    serializa y el contrato del camino feliz los quiere int."""
    return None if valor is None else int(valor)


def _datos_de_error(e):
    """Datos extra del error del servicio que van tambien a la auditoria: hoy es
    la lista de bloqueos de una baja rechazada (spec §4.13: el evento tiene que
    decir QUE bloqueo, no solo el codigo y el texto)."""
    datos = getattr(e, 'datos', None) or {}
    return {'bloqueos': datos['bloqueos']} if datos.get('bloqueos') else {}


def _es_conflicto(codigo):
    return str(codigo or '').startswith('CXP_INT_') or codigo == 'CXP_VAL_CLAVE_REUTILIZADA'


def _es_validacion(codigo):
    return str(codigo or '').startswith('CXP_VAL_')


def _error_cxp(e):
    """Respuesta de un error del servicio: {"ok": false, "error", "codigo"} y el
    HTTP que le corresponde (409 para los CXP_INT_* y la clave reutilizada,
    400 para los CXP_VAL_*, 500 si el codigo es inesperado)."""
    cuerpo = {"ok": False, "error": e.mensaje, "codigo": e.codigo}
    if e.datos:
        cuerpo.update(e.datos)
    if _es_conflicto(e.codigo):
        return jsonify(cuerpo), 409
    if _es_validacion(e.codigo):
        return jsonify(cuerpo), 400
    return jsonify(cuerpo), 500


def _error_entrada(e):
    """Respuesta de un ErrorValidacion del servicio (400 con codigo)."""
    return jsonify({"ok": False, "error": e.mensaje, "codigo": e.codigo}), 400


class _IdempotenciaDelEnvio:
    """Clave de idempotencia del envio (header `X-Idempotencia` o campo
    `clave_idempotencia` del cuerpo) y huella del cuerpo, sobre el MISMO almacen
    que usa Stock (`modules/shared/idempotencia.py`).

    Misma clave + mismo cuerpo -> se devuelve exactamente el resultado guardado y
    no se escribe nada; misma clave + otro cuerpo -> 409 (esa clave ya se uso
    para otro comprobante). El ciclo buscar + ejecutar + guardar va DENTRO del
    candado por clave: sin eso, un doble clic (dos POST simultaneos con la misma
    clave) crea dos comprobantes."""

    def __init__(self, data=None):
        self.clave = (request.headers.get('X-Idempotencia') or '').strip()
        if not self.clave and isinstance(data, dict):
            self.clave = str(data.get('clave_idempotencia') or '').strip()
        self.huella = huella_de_payload(data) if data is not None else None
        self.almacen = AlmacenIdempotencia()

    def clave_invalida(self):
        return bool(self.clave) and not clave_valida(self.clave)

    def candado(self):
        return self.almacen.candado(self.clave)

    def respuesta_previa(self):
        """(respuesta, estado) si hay que contestar sin ejecutar; None si no."""
        if not self.clave:
            return None
        if self.clave_invalida():
            # La spec no define un codigo propio para la clave mal formada: se
            # usa el de forma (CXP_VAL_CODIGO) con el texto de la idempotencia.
            return jsonify({"ok": False, "error": MENSAJE_CLAVE_INVALIDA,
                            "codigo": "CXP_VAL_CODIGO"}), 400
        estado, resultado = self.almacen.veredicto(self.clave, self.huella) or (None, None)
        if estado == 'previa':
            return jsonify(resultado), 200
        if estado == 'conflicto':
            return jsonify({"ok": False, "error": MENSAJE_CLAVE_REUTILIZADA,
                            "codigo": "CXP_VAL_CLAVE_REUTILIZADA"}), 409
        return None

    def guardar(self, resultado):
        """El comprobante ya esta commiteado: si la clave no se puede guardar se
        loguea y la respuesta sigue siendo exitosa (fallar aca haria que el
        usuario reintente y duplique el comprobante). Un alta que FALLO no llega
        nunca aca: la clave queda libre para el reintento del operador."""
        if not self.clave:
            return
        try:
            if not self.almacen.guardar(self.clave, resultado, self.huella):
                logger.error(f"No se pudo guardar la clave de idempotencia {self.clave}: "
                             "un reintento del mismo envio puede duplicar el comprobante.")
        except Exception as e:      # pragma: no cover - defensivo
            logger.error(f"Excepcion al guardar la clave de idempotencia {self.clave}: {e}")


def _hacer_alta(ctx, datos):
    """Un alta: un solo lote del servicio (transaccion + guardas + numeracion +
    totales verificados). La validacion de los datos vive en el servicio (por eso
    el `validar_alta` de aca: el tipo normalizado tiene que salir de ahi, no del
    cuerpo ni de un valor por defecto)."""
    normalizado = validar_alta(ctx, datos)
    filas = _filas_de_lote(sql_alta(ctx, datos))
    if not filas:
        # El lote del alta siempre devuelve su fila de confirmacion: sin fila no
        # se puede afirmar que el comprobante quedo grabado. Antes salia ok:true
        # con ctacte/nro_comprobante/nro_asiento en null (y esa respuesta se
        # guardaba como la respuesta idempotente del envio).
        logger.error("El lote del alta no devolvio la fila de confirmacion: "
                     "no se puede afirmar que el comprobante quedo grabado.")
        raise ErrorServicioCxP('CXP_INT', MENSAJE_ALTA_SIN_CONFIRMAR)
    fila = filas[0]
    return {"ok": True,
            "ctacte": _entero(fila.get("ctacte")),
            "nro_comprobante": _entero(fila.get("nro_comprobante")),
            "nro_asiento": _entero(fila.get("nro_asiento")),
            "tipo": normalizado['tipo_comp']}


@cxp_bp.route('/cargar_factura', methods=["POST"])
@requiere_permiso(PermisosSistema.CXP_CREAR)
def cargar_factura():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"ok": False, "error": "Datos requeridos"}), 400
    try:
        ctx = _contexto_cxp(datos)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "El campo 'division' tiene que ser un numero entero.",
                        "codigo": "CXP_VAL_ENTERO"}), 400
    envio = _IdempotenciaDelEnvio(datos)
    # El evento se arma ANTES de validar (un alta rechazada tambien tiene que
    # quedar auditada): el `tipo_comp` es el que mando el cuerpo; el normalizado
    # viaja en `resultado['tipo']` del evento 'aplicada'.
    evento = {'evento': 'cxp.alta', 'usuario': ctx.usuario, 'base': ctx.base,
              'division': ctx.division, 'tipo_comp': datos.get('tipo_comp'),
              'proveedor': datos.get('proveedor_id'),
              'ref_prov': datos.get('ref_prov'), 'fecha_comp': datos.get('fecha'),
              'importe': datos.get('imp_bruto'), 'iva': datos.get('imp_iva')}
    with envio.candado():
        previa = envio.respuesta_previa()
        if previa is not None:
            return previa
        try:
            auditar({**evento, 'estado': 'solicitada', 'fecha': datetime.now().isoformat()})
            resultado = _hacer_alta(ctx, datos)
        except ErrorServicioCxP as e:
            auditar({**evento, **_datos_de_error(e), 'estado': 'rechazada', 'codigo': e.codigo,
                     'error': e.mensaje, 'fecha': datetime.now().isoformat()})
            return _error_cxp(e)
        except ErrorValidacionCxP as e:
            auditar({**evento, 'estado': 'rechazada', 'codigo': e.codigo, 'error': e.mensaje,
                     'fecha': datetime.now().isoformat()})
            return _error_entrada(e)
        except Exception as e:
            logger.error(f"Error inesperado en /cargar_factura: {e}")
            auditar({**evento, 'estado': 'fallida', 'error': str(e),
                     'fecha': datetime.now().isoformat()})
            return jsonify({"ok": False, "error": f"Error al cargar factura: {str(e)}"}), 500
        auditar({**evento, 'estado': 'aplicada', 'resultado': resultado,
                 'fecha': datetime.now().isoformat()})
        envio.guardar(resultado)
    return jsonify(resultado)


def _filas_borradas(fila):
    """Filas borradas por tabla (para la auditoria y para el operador)."""
    return {'rccp': _entero(fila.get("filas_rccp")),
            'rasp': _entero(fila.get("filas_rasp")),
            'ictp': _entero(fila.get("filas_ictp")),
            'vctp': _entero(fila.get("filas_vctp")),
            'nctp': _entero(fila.get("filas_nctp")),
            'aasi': _entero(fila.get("filas_aasi")),
            'rasi': _entero(fila.get("filas_rasi")),
            'casi': _entero(fila.get("filas_casi")),
            'ctep': _entero(fila.get("filas_ctep")),
            'cdpr': _entero(fila.get("filas_cdpr"))}


def _nro_interno_de_baja(datos):
    """(nro_interno o None, True si vino pero no es un entero).

    AUSENTE (o vacio, o <= 0) es el JS viejo mandando el Nro. DTE del PDF:
    fail-closed, `CXP_VAL_CLIENTE_VIEJO`. PRESENTE pero ilegible (p.ej. 678.0) NO
    es un cliente viejo: es un cuerpo mal armado, y recargar la pantalla no lo
    arregla (el operador tiene que mandar el numero interno), asi que sale
    `CXP_VAL_ENTERO`.

    Asimetria inofensiva y a proposito (documentada): el SERVICIO (`validar_baja`)
    responde `CXP_VAL_CLIENTE_VIEJO` para ese mismo string ilegible, porque
    `int(str(...))` le falla y no distingue "ausente" de "ilegible". El endpoint
    intercepta ANTES con `CXP_VAL_ENTERO`, que es el codigo mas preciso; si el
    servicio se llamara directo (tests, otro cliente) el codigo seria el otro."""
    if 'nro_interno' not in datos or str(datos.get('nro_interno') or '').strip() == '':
        return None, False
    try:
        nro_interno = int(str(datos['nro_interno']).strip())
    except (TypeError, ValueError):
        return None, True
    if nro_interno <= 0:
        return None, False
    return nro_interno, False


def _datos_de_baja(datos, ctx):
    """(nro_interno valido o None, si vino mal formado, evento de auditoria). El
    numero interno es OBLIGATORIO: un cuerpo sin el es el JS viejo mandando el
    Nro. DTE del PDF."""
    nro_interno, mal_formado = _nro_interno_de_baja(datos)
    evento = {'evento': 'cxp.baja', 'usuario': ctx.usuario, 'base': ctx.base,
              'division': datos.get('division'), 'nro_interno': nro_interno,
              'tipo_comp': datos.get('tipo_comp'),
              'motivo': str(datos.get('motivo') or '').strip()}
    return nro_interno, mal_formado, evento


@cxp_bp.route('/eliminar_factura', methods=["POST"])
@requiere_permiso(PermisosSistema.CXP_ELIMINAR)
def eliminar_factura():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        datos = {}
    try:
        ctx = _contexto_cxp(datos)
    except (TypeError, ValueError):
        auditar({'evento': 'cxp.baja', 'usuario': '', 'base': getattr(g, 'db_database', ''),
                 'division': datos.get('division'), 'estado': 'rechazada',
                 'codigo': 'CXP_VAL_ENTERO', 'fecha': datetime.now().isoformat()})
        return jsonify({"ok": False, "error": "El campo 'division' tiene que ser un numero entero.",
                        "codigo": "CXP_VAL_ENTERO"}), 400
    nro_interno, mal_formado, evento = _datos_de_baja(datos, ctx)
    if nro_interno is None:
        codigo = 'CXP_VAL_ENTERO' if mal_formado else 'CXP_VAL_CLIENTE_VIEJO'
        error = MENSAJE_ENTERO_INTERNO if mal_formado else MENSAJE_CLIENTE_VIEJO
        auditar({**evento, 'estado': 'rechazada', 'codigo': codigo, 'error': error,
                 'numero_comp_recibido': datos.get('numero_comp'),
                 'fecha': datetime.now().isoformat()})
        return jsonify({"ok": False, "error": error, "codigo": codigo}), 400
    if not evento['motivo']:
        auditar({**evento, 'estado': 'rechazada', 'codigo': 'CXP_VAL_MOTIVO',
                 'error': MENSAJE_MOTIVO, 'fecha': datetime.now().isoformat()})
        return jsonify({"ok": False, "error": MENSAJE_MOTIVO,
                        "codigo": "CXP_VAL_MOTIVO"}), 400
    # La auditoria de la solicitud se escribe ANTES del borrado: el rastro existe
    # aunque la baja falle (misma regla que la anulacion de Stock).
    auditar({**evento, 'estado': 'solicitada', 'fecha': datetime.now().isoformat()})
    try:
        # El normalizado de `validar_baja` es el que arma el lote y el mensaje: el
        # texto no puede ecoar el cuerpo (con tipo_comp='fcp' el servicio borra el
        # FCP, asi que el operador tiene que leer FCP). `sql_baja` lo revalida.
        normalizado = validar_baja(ctx, datos)
        filas = _filas_de_lote(sql_baja(ctx, normalizado))
        if not filas or not filas[0].get('resultado'):
            # El lote de la baja siempre devuelve su fila de confirmacion (con el
            # `resultado` del borrado). Sin ella -o con una fila a medias- no se
            # puede afirmar que el comprobante se haya borrado: antes salia
            # ok:true con ctacte_eliminado/asiento_eliminado en null y un
            # `resultado` fabricado con un `or`.
            logger.error("El lote de la baja no devolvio la fila de confirmacion: "
                         "no se puede afirmar que el comprobante se haya borrado.")
            raise ErrorServicioCxP('CXP_INT', MENSAJE_BAJA_SIN_CONFIRMAR)
        fila = filas[0]
    except ErrorServicioCxP as e:
        auditar({**evento, **_datos_de_error(e), 'estado': 'rechazada', 'codigo': e.codigo,
                 'error': e.mensaje, 'fecha': datetime.now().isoformat()})
        return _error_cxp(e)
    except ErrorValidacionCxP as e:
        auditar({**evento, 'estado': 'rechazada', 'codigo': e.codigo, 'error': e.mensaje,
                 'fecha': datetime.now().isoformat()})
        return _error_entrada(e)
    except Exception as e:
        logger.error(f"Error inesperado en /eliminar_factura: {e}")
        auditar({**evento, 'estado': 'fallida', 'error': str(e),
                 'fecha': datetime.now().isoformat()})
        return jsonify({"ok": False, "error": f"Error al eliminar factura: {str(e)}"}), 500
    filas_borradas = _filas_borradas(fila)
    resultado = {"ok": True,
                 "mensaje": (f"Comprobante {normalizado['tipo_comp']} "
                             f"{normalizado['nro_interno']} eliminado correctamente"),
                 "ctacte_eliminado": _entero(fila.get("ctacte_eliminado")),
                 "asiento_eliminado": _entero(fila.get("asiento_eliminado")),
                 "resultado": fila.get("resultado"),
                 "filas_borradas": filas_borradas}
    auditar({**evento, 'estado': 'aplicada', 'resultado': resultado,
             'filas_borradas': filas_borradas, 'fecha': datetime.now().isoformat()})
    return jsonify(resultado)

# ============================================================
# RUTA: DEBUG PDF
# ============================================================

@cxp_bp.route('/debug_pdf', methods=["POST"])
@requiere_superadmin
def debug_pdf():
    try:
        data = request.json
        if not data or not data.get("file_b64"):
            return jsonify({"error": "Archivo no proporcionado"}), 400
            
        file_bytes = base64.b64decode(data["file_b64"])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        result = []
        try:
            with pdfplumber.open(tmp_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    result.append({"pagina": i+1, "texto": page.extract_text() or ""})
        finally:
            # Mismo caso que en /parsear_pdf: se cierra el documento, se suelta la
            # referencia y el borrado del temporal no puede romper la respuesta.
            # El `vars()` es por si `pdfplumber.open` fallo (el nombre no existe
            # todavia y un NameError taparia el error real).
            if 'pdf' in vars():
                pdf.close()
                pdf = None
            limpiar_temporal(tmp_path)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error en /debug_pdf: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# RUTA: FACTURA DE PRUEBA
# ============================================================

@cxp_bp.route('/factura_prueba', methods=["GET"])
@requiere_permiso(PermisosSistema.CXP_VER)
def factura_prueba():
    try:
        return jsonify({
            "ok": True,
            "facturas": [{
                "tipo": "FCP",
                "moneda": "PS",
                "total": 1000.00,
                "imp_bruto": 892.86,
                "imp_iva": 107.14,
                "tasa_iva": 12,
                "numero_dte": "999999",
                "fecha": date.today().isoformat(),
                "nit_emisor": "999999999",
                "nombre_emisor": "PROVEEDOR DE PRUEBA",
                "descripcion_auto": "Factura de prueba",
                "archivo": "factura_prueba.pdf"
            }]
        })
    except Exception as e:
        logger.error(f"Error en /factura_prueba: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500