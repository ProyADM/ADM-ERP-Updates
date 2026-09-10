# modules/shared/routes.py
# ============================================================
# RUTAS COMPARTIDAS - SIDESYS ERP
# ============================================================
# ✅ Este archivo ya está correcto (usa consultas parametrizadas)
# ============================================================

from flask import Blueprint, request, jsonify, current_app
from config import BASES_DISPONIBLES, BASE_DEFAULT, SOCIEDAD_DEFAULT
from .database import run_sql, run_sql_db
from .decorators import requiere_admin, chequear_acceso_total_bases
from .relanzar import lanzar_relanzador
import subprocess
import threading
import os
import sys
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

shared_bp = Blueprint('shared', __name__, url_prefix='/api')

# Bases a excluir de las notificaciones (si no funcionan)
BASES_EXCLUIDAS_NOTIFICACIONES = ['plataforma']  # Argentina no disponible

@shared_bp.route('/bases', methods=['GET'])
def listar_bases():
    out = []
    for cod, info in BASES_DISPONIBLES.items():
        item = {"codigo": cod, "label": info["label"], "sigla": info["sigla"]}
        if "sociedades" in info:
            item["sociedades"] = [{"codigo": s, "label": d["label"]} for s, d in info["sociedades"].items()]
        out.append(item)
    return jsonify({"bases": out, "default": BASE_DEFAULT, "sociedad_default": SOCIEDAD_DEFAULT})

@shared_bp.route('/centros_costo', methods=['GET'])
def centros_costo():
    cliente = request.args.get("cliente", "")
    concepto = request.args.get("concepto", "")
    
    query = """
        SELECT IMAE_INSTANCIA as codigo,
               IMAE_DESCRIPCION1 as nombre,
               IMAE_DESCRIPCION2 as cliente,
               IMAE_DESCRIPCION3 as concepto
        FROM CONT_IMAE
        WHERE IMAE_MAESTRO='CCO' AND IMAE_UTILIZABLE=1
    """
    params = []
    
    if cliente:
        query += " AND UPPER(IMAE_DESCRIPCION2) LIKE ?"
        params.append(f"%{cliente.upper()}%")
    if concepto:
        query += " AND UPPER(IMAE_DESCRIPCION3) LIKE ?"
        params.append(f"%{concepto.upper()}%")
        
    query += " ORDER BY IMAE_DESCRIPCION1"
    
    rows = run_sql(query, params=params)
    return jsonify(rows)

@shared_bp.route('/reiniciar', methods=['POST'])
@requiere_admin
def reiniciar():
    """Reinicia la app con un relanzador DESPRENDIDO.

    Antes esto hacia `subprocess.Popen([python] + sys.argv, cwd=modules/shared)`:
    el cwd era el del modulo (config.py no encontraba .env.local), el hijo
    quedaba atado al padre y el proceso nuevo moria al arrancar. Ahora se usa el
    mismo mecanismo que el auto-reinicio de actualizaciones.
    """
    def _restart():
        time.sleep(0.5)
        try:
            app_dir = current_app.config.get('APP_INSTALL_DIR') or os.getcwd()
            puerto = int(os.environ.get('APP_PORT', '5000'))
            ok, detalle = lanzar_relanzador(app_dir, puerto=puerto, motivo='api_reiniciar')
            if not ok:
                logger.error(f"No se pudo lanzar el relanzador: {detalle}")
        except Exception as e:
            logger.error(f"Error al reiniciar: {e}")
        finally:
            os._exit(0)

    threading.Thread(target=_restart, daemon=True).start()
    return jsonify({"ok": True, "mensaje": "Reiniciando la aplicación..."})

# ============================================================
# NUEVO: NOTIFICACIONES GLOBALES
# ============================================================

@shared_bp.route('/notificaciones/resumen', methods=['GET'])
def notificaciones_resumen():
    """
    Devuelve el número de cambios recientes (stock, ventas, contratos)
    en todas las bases desde un timestamp dado.

    C4: es una lectura multi-base sobre TODAS las bases → exige superadmin o
    bases_permitidas=['*'] (un usuario parcial no debe recibir totales globales
    parciales).
    """
    try:
        chequeo = chequear_acceso_total_bases()
        if chequeo:
            return chequeo

        desde_str = request.args.get('desde')
        if desde_str:
            try:
                desde = datetime.fromisoformat(desde_str)
            except ValueError:
                desde = datetime.now() - timedelta(days=1)
        else:
            desde = datetime.now() - timedelta(days=1)

        resultados = []
        total_global = 0
        bases_a_consultar = [b for b in BASES_DISPONIBLES if b not in BASES_EXCLUIDAS_NOTIFICACIONES]

        for nombre_base in bases_a_consultar:
            info = BASES_DISPONIBLES[nombre_base]
            sigla = info.get('sigla', nombre_base)
            try:
                # Obtener división de la base
                division = info.get('division', 5)
                if nombre_base == 'plataforma' and 'sociedades' in info:
                    primera_soc = list(info['sociedades'].keys())[0] if info['sociedades'] else 'sidesys'
                    division = info['sociedades'][primera_soc].get('division', 1)

                # Contar ventas nuevas (CCOB_CTEC)
                query_ventas = """
                    SELECT COUNT(*) AS total
                    FROM CCOB_CTEC c
                    INNER JOIN CCOB_CLIE cl ON c.CTEC_CLIENTE = cl.CLIE_CLIENTE
                    WHERE c.CTEC_DIVISION = ?
                      AND c.CTEC_FECHA_EMI > ?
                      AND cl.CLIE_TIPO_CLI != '5'
                      AND c.CTEC_IMP_TOT_ORI IS NOT NULL
                """
                ventas = run_sql_db(nombre_base, query_ventas, params=[division, desde], fetch=True)
                ventas = ventas[0]['total'] if ventas else 0

                # Contar contratos nuevos (ACCT_COCA sin factura)
                query_contratos = """
                    SELECT COUNT(*) AS total
                    FROM ACCT_COCA ca
                    LEFT JOIN ACCT_COFF cf ON ca.COCA_NUMINT_COCA = cf.COFF_NUMINT_COCA
                    WHERE ca.COCA_FECHA_ALTA > ?
                      AND cf.COFF_NUMINT_COCA IS NULL
                """
                contratos = run_sql_db(nombre_base, query_contratos, params=[desde], fetch=True)
                contratos = contratos[0]['total'] if contratos else 0

                # Contar movimientos de stock (STOC_MOST)
                query_stock = """
                    SELECT COUNT(*) AS total
                    FROM STOC_MOST
                    WHERE MOST_FECHA_EMI > ?
                """
                stock = run_sql_db(nombre_base, query_stock, params=[desde], fetch=True)
                stock = stock[0]['total'] if stock else 0

                total_base = ventas + contratos + stock
                total_global += total_base

                if total_base > 0:
                    resultados.append({
                        'base': nombre_base,
                        'sigla': sigla,
                        'stock': stock,
                        'ventas': ventas,
                        'contratos': contratos,
                        'total': total_base
                    })
            except Exception as e:
                # Si falla una base, la ignoramos silenciosamente (solo log en debug)
                if current_app.debug:
                    logger.warning(f"⚠️ Error al consultar base {nombre_base}: {e}")
                continue

        # Ordenar por total descendente
        resultados.sort(key=lambda x: x['total'], reverse=True)

        return jsonify({
            'success': True,
            'desde': desde.isoformat(),
            'total': total_global,
            'detalle': resultados
        })

    except Exception as e:
        logger.error(f"Error en notificaciones/resumen: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500