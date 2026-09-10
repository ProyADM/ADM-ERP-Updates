# modules/cotizaciones/routes.py
# ============================================================
# RUTAS DE COTIZACIONES - SIDESYS ERP (VERSIÓN MEJORADA)
# ============================================================

from datetime import date, datetime
import base64
import io
import os
import tempfile
import logging
import zipfile
from flask import Blueprint, jsonify, request, session
import openpyxl
import pyodbc
from config import (
    BASES_COTI,
    SQL_SERVER,
    SQL_USERNAME,
    SQL_PASSWORD,
    SQL_ENCRYPT_ACTIVO,
)
from modules.shared.decorators import requiere_permiso, chequear_acceso_total_bases
from modules.shared.permisos import PermisosSistema
from modules.shared.usuarios import get_gestor_usuarios

# Configurar logging
logger = logging.getLogger(__name__)

cotizaciones_bp = Blueprint("cotizaciones", __name__, url_prefix="/api/cotizaciones")

__all__ = ["cotizaciones_bp"]

# ============================================================
# PAÍSES PERMITIDOS (VALIDACIÓN)
# ============================================================

PAISES_PERMITIDOS = list(BASES_COTI.keys())

# Países prioritarios para obtener cotización (primero RD, luego el resto)
PAISES_PRIORITARIOS = ['RD'] + [p for p in PAISES_PERMITIDOS if p != 'RD']

# ============================================================
# C4 - ACCESO POR PAÍS (sigla → base de BASES_COTI)
# ============================================================

def _siglas_permitidas_usuario():
    """Siglas a las que accede el usuario actual (vacío si no tiene acceso).
    superadmin / bases_permitidas=['*'] → todas."""
    gestor = get_gestor_usuarios()
    username = session.get('username')
    if not username:
        return []
    usuario = gestor.usuarios.get(username)
    if not usuario:
        return []
    if usuario.es_superadmin or '*' in usuario.bases_permitidas:
        return list(PAISES_PERMITIDOS)
    return [
        sigla for sigla, base_code in BASES_COTI.items()
        if gestor.tiene_acceso_a_base(username, base_code)
    ]

def _chequear_siglas_acceso(siglas):
    """Valida (fail-closed) que TODAS las siglas pedidas estén autorizadas.
    Retorna None si OK o una respuesta Flask 401/403."""
    username = session.get('username')
    if not username:
        return jsonify({
            "error": "No autenticado",
            "code": "UNAUTHORIZED",
            "login_url": "/"
        }), 401
    gestor = get_gestor_usuarios()
    usuario = gestor.usuarios.get(username)
    if usuario and (usuario.es_superadmin or '*' in usuario.bases_permitidas):
        return None
    no_permitidas = [
        s for s in siglas
        if s in PAISES_PERMITIDOS and not gestor.tiene_acceso_a_base(username, BASES_COTI[s])
    ]
    if no_permitidas:
        return jsonify({
            "error": f"País(es) no autorizado(s) para este usuario: {', '.join(sorted(set(no_permitidas)))}",
            "code": "BASE_FORBIDDEN"
        }), 403
    return None

def validar_sigla(sigla: str) -> bool:
    """Valida que la sigla del país sea válida"""
    return sigla in PAISES_PERMITIDOS

def validar_fecha(fecha: str) -> bool:
    """Valida que la fecha tenga formato YYYY-MM-DD"""
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        return True
    except (ValueError, TypeError):
        return False

def validar_cotizacion(valor) -> bool:
    """Valida que la cotización sea un número positivo"""
    try:
        val = float(valor)
        return val > 0
    except (ValueError, TypeError):
        return False

def sanitizar_fecha(fecha: str) -> str:
    """Sanitiza una fecha para evitar inyección"""
    if not validar_fecha(fecha):
        raise ValueError(f"Fecha inválida: {fecha}")
    return fecha

# ============================================================
# CONEXIÓN DIRECTA POR PAÍS
# ============================================================

def obtener_conexion_pais(sigla):
    """Obtiene conexión a la base de datos de un país específico"""
    if not validar_sigla(sigla):
        raise ValueError(f"País no válido: {sigla}")
    
    db_name = BASES_COTI.get(sigla)
    if not db_name:
        raise ValueError(f"No existe base de datos para la sigla: {sigla}")
    
    try:
        from config import SQL_SERVER_PLATAFORMA
    except ImportError:
        SQL_SERVER_PLATAFORMA = SQL_SERVER

    server = SQL_SERVER_PLATAFORMA if sigla == "AR" else SQL_SERVER
    
    conn_str = (
        'DRIVER={SQL Server};'
        f'SERVER={server};'
        f'DATABASE={db_name};'
        f'UID={SQL_USERNAME};'
        f'PWD={SQL_PASSWORD};'
        'TrustServerCertificate=yes;'
        + ('Encrypt=yes;' if SQL_ENCRYPT_ACTIVO else '')
        + 'Timeout=10;'            # Timeout de conexión (segundos)
        + 'Connect Timeout=10;'    # Alternativa
    )
    return pyodbc.connect(conn_str)

def obtener_conexion_pais_segura(sigla):
    """Obtiene conexión con manejo de errores"""
    try:
        return obtener_conexion_pais(sigla)
    except pyodbc.Error as e:
        logger.error(f"Error de conexión a {sigla}: {e}")
        raise RuntimeError(f"No se pudo conectar a la base de datos de {sigla}")
    except Exception as e:
        logger.error(f"Error inesperado en {sigla}: {e}")
        raise

# ============================================================
# FUNCIÓN AUXILIAR PARA GUARDAR COTIZACIONES (EVITA DUPLICACIÓN)
# ============================================================

def _guardar_cotizaciones(items):
    """
    Guarda una lista de cotizaciones en las bases correspondientes.
    
    Args:
        items: Lista de diccionarios con keys: fecha, cotizacion, bases (lista de siglas)
    
    Returns:
        dict: {ok, insertados, errores, bases_con_error}
    """
    if not items:
        return {"ok": False, "insertados": 0, "errores": ["No hay items para guardar"], "bases_con_error": []}
    
    errores = []
    ok = 0
    bases_con_error = []
    
    for item in items:
        fecha = item["fecha"]
        cotizacion = item["cotizacion"]
        bases = item.get("bases", PAISES_PERMITIDOS)
        
        # Validar que las bases sean válidas
        bases_validas = [b for b in bases if b in PAISES_PERMITIDOS]
        if not bases_validas:
            errores.append(f"No hay bases válidas para la fecha {fecha}")
            continue
        
        for sigla in bases_validas:
            conn = None
            try:
                conn = obtener_conexion_pais_segura(sigla)
                cursor = conn.cursor()

                # Consulta UPSERT con parámetros
                query = """
                    IF EXISTS (SELECT 1 FROM SIST_COTI WHERE COTI_MONEDA1=? AND COTI_MONEDA2=? AND COTI_FECHA=?)
                        UPDATE SIST_COTI SET COTI_COTIZACION=?
                        WHERE COTI_MONEDA1=? AND COTI_MONEDA2=? AND COTI_FECHA=?
                    ELSE
                        INSERT INTO SIST_COTI (COTI_MONEDA1, COTI_MONEDA2, COTI_FECHA, COTI_COTIZACION)
                        VALUES (?, ?, ?, ?)
                """
                cursor.execute(query, (
                    'DL', 'PS', fecha,
                    cotizacion,
                    'DL', 'PS', fecha,
                    'DL', 'PS', fecha, cotizacion
                ))
                conn.commit()
                ok += 1
                logger.info(f"Cotización {cotizacion} guardada en {sigla} para fecha {fecha}")
                
            except pyodbc.Error as e:
                error_msg = f"{sigla} {fecha}: {str(e)}"
                errores.append(error_msg)
                bases_con_error.append(sigla)
                logger.error(f"Error SQL en {sigla}: {e}")
            except Exception as e:
                error_msg = f"{sigla} {fecha}: {str(e)}"
                errores.append(error_msg)
                bases_con_error.append(sigla)
                logger.error(f"Error inesperado en {sigla}: {e}")
            finally:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
    
    return {
        "ok": len(errores) == 0,
        "insertados": ok,
        "errores": errores,
        "bases_con_error": list(set(bases_con_error))
    }

# ============================================================
# RUTAS
# ============================================================

@cotizaciones_bp.route("/historico")
@requiere_permiso(PermisosSistema.COTIZACIONES_VER)
def historico():
    """Obtiene el historial de cotizaciones por país.
    C4: solo devuelve países a los que el usuario tiene acceso."""
    result = {}
    siglas = _siglas_permitidas_usuario()

    for sigla in siglas:
        conn = None
        try:
            conn = obtener_conexion_pais_segura(sigla)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    CONVERT(VARCHAR, COTI_FECHA, 23) as fecha,
                    COTI_MONEDA1 as moneda1,
                    COTI_MONEDA2 as moneda2,
                    COTI_COTIZACION as cotizacion
                FROM SIST_COTI
                WHERE COTI_MONEDA1 = ? AND COTI_MONEDA2 = ?
                ORDER BY COTI_FECHA DESC
            """, ('DL', 'PS'))
            
            columns = [column[0] for column in cursor.description]
            rows = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                if row_dict.get("cotizacion") is not None:
                    try:
                        row_dict["cotizacion"] = float(str(row_dict["cotizacion"]).replace(",", "."))
                    except (ValueError, TypeError):
                        row_dict["cotizacion"] = 0.0
                rows.append(row_dict)
                
            result[sigla] = rows
            
        except ValueError as e:
            logger.warning(f"País inválido: {sigla} - {e}")
            result[sigla] = {"error": f"País no válido: {sigla}"}
        except pyodbc.Error as e:
            logger.error(f"Error SQL en {sigla}: {e}")
            result[sigla] = {"error": f"Error de base de datos: {str(e)}"}
        except Exception as e:
            logger.error(f"Error inesperado en {sigla}: {e}")
            result[sigla] = {"error": f"Error inesperado: {str(e)}"}
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
                    
    return jsonify(result)


@cotizaciones_bp.route("/guardar", methods=["POST"])
@requiere_permiso(PermisosSistema.COTIZACIONES_CREAR)
def guardar():
    """Guarda una cotización en uno o varios países"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                "ok": False,
                "error": "No se recibieron datos"
            }), 400
        
        if not isinstance(data, list):
            return jsonify({
                "ok": False,
                "error": "Se esperaba una lista de cotizaciones"
            }), 400

        # C4: cada país destino debe estar autorizado para el usuario.
        siglas_pedidas = set()
        for item in data:
            if not isinstance(item, dict):
                return jsonify({"ok": False, "error": "Item inválido en la lista"}), 400
            siglas_pedidas.update(item.get("bases", PAISES_PERMITIDOS))
        chequeo = _chequear_siglas_acceso(list(siglas_pedidas))
        if chequeo:
            return chequeo
        
        items = []
        for item in data:
            # Validar campos
            if not item.get("fecha"):
                return jsonify({"ok": False, "error": "Fecha no proporcionada"}), 400
                
            if not validar_fecha(item["fecha"]):
                return jsonify({"ok": False, "error": f"Fecha inválida: {item['fecha']}"}), 400
                
            try:
                cotizacion = float(item["cotizacion"])
                if cotizacion <= 0:
                    return jsonify({"ok": False, "error": f"Cotización inválida (debe ser positiva): {cotizacion}"}), 400
            except (ValueError, TypeError):
                return jsonify({"ok": False, "error": f"Cotización inválida: {item.get('cotizacion')}"}), 400

            bases = item.get("bases", PAISES_PERMITIDOS)
            bases_validas = [b for b in bases if b in PAISES_PERMITIDOS]
            if not bases_validas:
                return jsonify({"ok": False, "error": f"No hay bases válidas para: {bases}"}), 400
            
            items.append({
                "fecha": item["fecha"],
                "cotizacion": cotizacion,
                "bases": bases_validas
            })
        
        resultado = _guardar_cotizaciones(items)
        
        if resultado["bases_con_error"]:
            return jsonify({
                "ok": resultado["ok"],
                "insertados": resultado["insertados"],
                "errores": resultado["errores"],
                "bases_con_error": resultado["bases_con_error"],
                "mensaje": f"⚠️ No se pudo guardar en: {', '.join(resultado['bases_con_error'])}."
            })
        
        return jsonify({
            "ok": resultado["ok"],
            "insertados": resultado["insertados"],
            "errores": resultado["errores"]
        })
        
    except Exception as e:
        logger.error(f"Error en guardar cotización: {e}")
        return jsonify({
            "ok": False,
            "error": f"Error inesperado: {str(e)}"
        }), 500


@cotizaciones_bp.route("/plantilla")
@requiere_permiso(PermisosSistema.COTIZACIONES_VER)
def plantilla():
    """Descarga plantilla Excel para cotizaciones (Fecha | Cotización | País opcional)"""
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cotizaciones"
        ws["A1"] = "Fecha"
        ws["B1"] = "Cotización DL"
        ws["C1"] = "País (opcional)"
        ws["A2"] = date.today().strftime("%d/%m/%Y")
        ws["B2"] = "7,61982"
        ws["C2"] = ""
        siglas = ", ".join(PAISES_PERMITIDOS)
        ws["A4"] = ("Dejá 'País' vacío para usar las bases seleccionadas en la pantalla. Siglas válidas: " + siglas)
        ws["A4"].font = openpyxl.styles.Font(italic=True, color="888888")
        for cell in ws["A"]:
            cell.number_format = "DD/MM/YYYY"
        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 16
        
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            wb.save(tmp.name)
            tmp_path = tmp.name
            
        from flask import send_file
        return send_file(tmp_path, as_attachment=True, download_name="plantilla_cotizaciones.xlsx")
        
    except Exception as e:
        logger.error(f"Error generando plantilla: {e}")
        return jsonify({"error": str(e)}), 500


@cotizaciones_bp.route("/importar_excel", methods=["POST"])
@requiere_permiso(PermisosSistema.COTIZACIONES_CREAR)
def importar_excel():
    """Importa cotizaciones desde un archivo Excel.

    Columnas: A=Fecha, B=Cotización, C=País (OPCIONAL).
    - Si la fila trae una sigla válida en C, esa cotización va SOLO a ese país.
    - Si C está vacía, se usa la/s base/s seleccionadas en la UI (payload 'bases').
    - Las filas con sigla desconocida/sin permiso NO se importan y se listan.
    - dry_run=true → solo previsualiza (no escribe nada) para el modal de confirmación.
    """
    try:
        data = request.json
        
        if not data or not data.get("file_b64"):
            return jsonify({
                "ok": False,
                "error": "No se recibió archivo"
            }), 400
            
        file_bytes = base64.b64decode(data["file_b64"])
        ui_bases = data.get("bases") or []
        dry_run = bool(data.get("dry_run"))

        try:
            # 🔴 FIX: leer desde memoria (BytesIO). Antes se escribía un archivo
            # temporal y openpyxl lo dejaba abierto → os.unlink() fallaba en
            # Windows con WinError 32 y toda importación daba 500.
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        except (openpyxl.utils.exceptions.InvalidFileException, zipfile.BadZipFile):
            return jsonify({
                "ok": False,
                "error": "El archivo no es un Excel válido"
            }), 400

        ws = wb.active
        ui_validas = [b for b in ui_bases if b in PAISES_PERMITIDOS]

        items = []
        errores_filas = []
        siglas_usadas = set(ui_validas)
        nro_fila = 1

        for row in ws.iter_rows(min_row=2, values_only=True):
            nro_fila += 1
            if not row or not row[0] or not row[1]:
                continue

            # Validar fecha
            fecha_val = row[0]
            if hasattr(fecha_val, "strftime"):
                fecha_str = fecha_val.strftime("%Y-%m-%d")
            else:
                parts = str(fecha_val).split("/")
                if len(parts) == 3:
                    try:
                        fecha_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                        if not validar_fecha(fecha_str):
                            continue
                    except:
                        continue
                else:
                    continue

            # Validar cotización
            try:
                coti_val = float(str(row[1]).replace(",", ".").replace(" ", ""))
                if coti_val <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            # Destino: columna C (País, opcional) por fila; si viene vacía → UI
            pais_raw = row[2] if len(row) > 2 else None
            if pais_raw is None or str(pais_raw).strip() == "":
                row_bases = ui_validas
                if not row_bases:
                    errores_filas.append(
                        f"Fila {nro_fila}: sin país destino (celda 'País' vacía y no hay países seleccionados)."
                    )
                    continue
            else:
                sigla = str(pais_raw).strip().upper()
                if sigla not in PAISES_PERMITIDOS:
                    errores_filas.append(f"Fila {nro_fila}: '{sigla}' no es una sigla válida.")
                    continue
                row_bases = [sigla]
                siglas_usadas.add(sigla)

            items.append({
                "fecha": fecha_str,
                "cotizacion": coti_val,
                "bases": row_bases
            })

        # C4: TODAS las siglas que se escribirían deben estar autorizadas.
        if siglas_usadas:
            chequeo = _chequear_siglas_acceso(sorted(siglas_usadas))
            if chequeo:
                return chequeo

        if not items:
            detalle = errores_filas[0] if errores_filas else "No se encontraron datos válidos en el Excel."
            return jsonify({
                "ok": False,
                "error": detalle,
                "errores": errores_filas
            }), 400

        # Resumen por país destino (equivalente a inserciones planeadas)
        por_pais = {}
        for it in items:
            for s in it["bases"]:
                por_pais[s] = por_pais.get(s, 0) + 1

        if dry_run:
            return jsonify({
                "ok": True,
                "preview": True,
                "filas_validas": len(items),
                "por_pais": por_pais,
                "errores": errores_filas
            })

        resultado = _guardar_cotizaciones(items)

        return jsonify({
            "ok": resultado["ok"] and not errores_filas,
            "insertados": resultado["insertados"],
            "errores": errores_filas + resultado["errores"],
            "bases_con_error": resultado["bases_con_error"],
            "por_pais": por_pais,
            "filas_validas": len(items)
        })
        
    except Exception as e:
        logger.error(f"Error importando Excel: {e}")
        return jsonify({
            "ok": False,
            "error": f"Error inesperado: {str(e)}"
        }), 500


@cotizaciones_bp.route("/cotizacion")
@requiere_permiso(PermisosSistema.COTIZACIONES_VER)
def cotizacion():
    """
    Obtiene la cotización para una fecha y moneda específica.
    Intenta obtenerla de países prioritarios (primero RD) antes de devolver 1.0.
    C4: solo consulta países a los que el usuario tiene acceso.
    """
    try:
        moneda = request.args.get("moneda", "DL")
        fecha = request.args.get("fecha", "")
        
        if moneda not in ['DL', 'PS']:
            return jsonify({
                "error": "Moneda inválida. Solo se permiten DL y PS",
                "code": "INVALID_CURRENCY"
            }), 400
        
        if moneda == "PS":
            return jsonify({"cotizacion": 1.0})
        
        if fecha and not validar_fecha(fecha):
            return jsonify({
                "error": "Fecha inválida. Formato esperado: YYYY-MM-DD",
                "code": "INVALID_DATE"
            }), 400

        # Intentar con países prioritarios (primero RD, luego el resto),
        # limitado a los países a los que el usuario tiene acceso (C4).
        permitidas = set(_siglas_permitidas_usuario())
        siglas_a_consultar = [s for s in PAISES_PRIORITARIOS if s in permitidas]
        for sigla in siglas_a_consultar:
            conn = None
            try:
                conn = obtener_conexion_pais_segura(sigla)
                cursor = conn.cursor()

                query = """
                    SELECT TOP 1 COTI_COTIZACION as coti
                    FROM SIST_COTI
                    WHERE COTI_MONEDA1 = ? AND COTI_MONEDA2 = ?
                """
                params = [moneda, 'PS']

                if fecha:
                    query += " AND COTI_FECHA <= ?"
                    params.append(fecha)

                query += " ORDER BY COTI_FECHA DESC"

                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row and row[0]:
                    try:
                        cotizacion = float(str(row[0]).replace(",", "."))
                        logger.info(f"Cotización obtenida de {sigla}: {cotizacion}")
                        return jsonify({"cotizacion": cotizacion})
                    except (ValueError, TypeError):
                        continue
                        
            except pyodbc.Error as e:
                logger.warning(f"Error al consultar cotización en {sigla}: {e}")
            except Exception as e:
                logger.warning(f"Error inesperado en {sigla}: {e}")
            finally:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
        
        # Si ningún país devolvió cotización, retornar 1.0
        logger.warning("No se encontró cotización en ningún país, usando 1.0")
        return jsonify({"cotizacion": 1.0})
        
    except Exception as e:
        logger.error(f"Error en cotización: {e}")
        return jsonify({"cotizacion": 1.0})