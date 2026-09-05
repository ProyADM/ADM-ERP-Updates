# modules/cxp/routes.py
# ============================================================
# RUTAS CXP - SIDESYS ERP (CORREGIDO)
# ============================================================

from flask import Blueprint, request, jsonify, g
import base64
import tempfile
import os
import re
import io
from modules.shared.database import run_sql, run_sql_db, _sql_literal
from modules.shared.utils import to_base64
from .parser import parse_fel_page, extraer_texto_pagina, ocr_image_bytes
from cuentas import CUENTAS, NIT_CUENTA_FIJA
import pdfplumber
import openpyxl
from datetime import date
import logging

logger = logging.getLogger(__name__)

cxp_bp = Blueprint('cxp', __name__, url_prefix='/api')

# ============================================================
# FUNCIÓN: ASEGURAR QUE LA DIVISIÓN EXISTE
# ============================================================

def asegurar_division(division):
    try:
        rows = run_sql(f"""
            SELECT COUNT(*) as existe 
            FROM SIST_DIVI 
            WHERE DIVI_DIVISION = {division}
        """)
        
        if rows and rows[0]['existe'] == 0:
            run_sql(f"""
                INSERT INTO SIST_DIVI (DIVI_DIVISION, DIVI_DESCRIPCION, DIVI_ABREVIATURA)
                VALUES ({division}, 'DIVISION {division} - CUENTAS A PAGAR', 'CXP{division}')
            """)
            print(f"✅ División {division} creada automáticamente")
            return True
        else:
            print(f"✅ División {division} ya existe")
            return True
    except Exception as e:
        logger.error(f"Error en asegurar_division: {e}")
        return False

# ============================================================
# RUTAS CXP - PROVEEDORES Y CONDICIONES
# ============================================================

@cxp_bp.route('/proveedores')
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
def get_cuentas():
    try:
        from cuentas import CUENTAS
        result = [
            {"codigo": k, "nombre": v["nombre"], "cco": v["cco"]}
            for k, v in sorted(CUENTAS.items())
        ]
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error en /cuentas: {e}")
        return jsonify([])

# ============================================================
# RUTA: CENTROS DE COSTO
# ============================================================

@cxp_bp.route('/centros_costo')
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
def get_cotizacion():
    try:
        moneda = request.args.get('moneda', 'DL')
        fecha = request.args.get('fecha', date.today().isoformat())
        
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
    except Exception as e:
        logger.error(f"Error en /cotizacion: {e}")
        return jsonify({"cotizacion": 7.61982})

@cxp_bp.route('/parsear_pdf', methods=["POST"])
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
                os.unlink(tmp_path)

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
# RUTA: CARGAR FACTURA
# ============================================================

@cxp_bp.route('/cargar_factura', methods=["POST"])
def cargar_factura():
    try:
        d = request.json
        if not d:
            return jsonify({"ok": False, "error": "Datos requeridos"}), 400
            
        division = int(d.get("division", 7))
        
        asegurar_division(division)
        
        proveedor = int(d["proveedor_id"])
        fecha = d["fecha"]
        ref_prov = str(d["ref_prov"])[:15]
        descripcion = d.get("descripcion", "").replace("'", "''")[:100]
        cond_pago = d.get("cond_pago", "00")
        moneda = d.get("moneda", "PS")
        tipo_comp = d.get("tipo_comp", "FCP")
        imp_bruto = float(d["imp_bruto"])
        imp_iva = float(d.get("imp_iva", 0))
        tasa_iva = float(d.get("tasa_iva", 12))
        imp_total = round(imp_bruto + imp_iva, 2)
        fecha_vto = d.get("fecha_vto", fecha)
        cotizacion = float(d.get("cotizacion", 1))
        renglones = d.get("renglones", [])
        eventual = d.get("eventual")
        
        if moneda == "PS":
            cotizacion = 1.0
            imp_bruto_loc = imp_bruto
            imp_iva_loc = imp_iva
            imp_total_loc = imp_total
            rows_coti = run_sql(f"""
                SELECT TOP 1 COTI_COTIZACION as c FROM SIST_COTI
                WHERE COTI_MONEDA1='DL' AND COTI_MONEDA2='PS' AND COTI_FECHA <= '{fecha}'
                ORDER BY COTI_FECHA DESC
            """)
            cotizacion_conv = float(str(rows_coti[0]['c']).replace(',', '.')) if rows_coti and rows_coti[0].get('c') else 1.0
        else:
            cotizacion_conv = cotizacion
            imp_total_loc = round(imp_total * cotizacion, 2)
            imp_bruto_loc = round(imp_bruto * cotizacion, 2)
            imp_iva_loc = round(imp_total_loc - imp_bruto_loc, 2)
        
        rows_ctacte = run_sql(f"""
            SELECT ISNULL(MAX(CTEP_CTACTE_CTEP), 0) + 1 as next_ctacte
            FROM CPAG_CTEP WITH (UPDLOCK, HOLDLOCK)
        """)
        
        if not rows_ctacte or rows_ctacte[0]['next_ctacte'] is None:
            return jsonify({"ok": False, "error": "No se pudo obtener número de CTACTE"}), 500
        
        ctacte = int(rows_ctacte[0]['next_ctacte'])
        
        rows_cdpr = run_sql(f"""
            SELECT ISNULL(MAX(CDPR_NUMERO_CDPR), 0) + 1 as next_cdpr
            FROM CPAG_CDPR WITH (UPDLOCK, HOLDLOCK)
            WHERE CDPR_TIPO_CDPR = '{tipo_comp}' AND CDPR_DIVISION_CDPR = {division}
        """)
        
        if not rows_cdpr or rows_cdpr[0]['next_cdpr'] is None or rows_cdpr[0]['next_cdpr'] == 0:
            nro_cdpr = 1
        else:
            nro_cdpr = int(rows_cdpr[0]['next_cdpr'])
        
        ictp_insert = ""
        if tipo_comp == 'FCP' and imp_iva > 0:
            ictp_insert = f"""
            INSERT INTO CPAG_ICTP (
                ICTP_CTACTE_CTEP, ICTP_IMPUESTO, ICTP_CATEGORIA_IMP,
                ICTP_IMP_GRA_ORI, ICTP_IMP_GRA_LOC,
                ICTP_IMPUESTO_ORI, ICTP_IMPUESTO_LOC,
                ICTP_FACTOR_IMP, ICTP_TASA, ICTP_ES_IVA,
                ICTP_PRORRATEA_IVA_CRFIS, ICTP_POR_COMP_IVA_CRFIS
            ) VALUES (
                {ctacte}, 'IVP', 'P12',
                {imp_bruto}, {imp_bruto_loc},
                {imp_iva}, {imp_iva_loc},
                1.0, {tasa_iva}, 1, 0, 100.0
            );"""
        
        nctp_insert = ""
        if eventual:
            nombre_ev = str(eventual.get("nombre", "")).replace("'", "''")[:90]
            nit_ev = str(eventual.get("nit", "")).replace("'", "''")[:15]
            dom_ev = str(eventual.get("domicilio", "")).replace("'", "''")[:60]
            loc_ev = str(eventual.get("localidad", "")).replace("'", "''")[:50]
            nctp_insert = f"""
            INSERT INTO CPAG_NCTP (
                NCTP_CTACTE_CTEP, NCTP_NOMBRE, NCTP_DOMICILIO,
                NCTP_LOCALIDAD, NCTP_CUIT, NCTP_CONDICION_IVA, NCTP_UTILIZABLE
            ) VALUES (
                {ctacte}, '{nombre_ev}', '{dom_ev}',
                '{loc_ev}', '{nit_ev}', 'RI', 1
            );"""
        
        cuenta_prov = d.get("cuenta_prov", "")
        if not cuenta_prov:
            if eventual:
                loc = str(eventual.get("localidad", "")).upper().strip()
                cuenta_prov = "210101002" if (moneda == "DL" and loc not in ("GT", "GUATEMALA", "")) else "210101001"
            else:
                cuenta_prov = "210101001"
        
        nombre_prov_esc = d.get("proveedor_nombre", "").replace("'", "''")[:60]
        
        if not renglones:
            cta = d.get("cuenta_gasto", "")
            cco = d.get("cco_codigo", "")
            if cta:
                renglones = [{"cuenta": cta, "importe": imp_bruto, "cco": cco}]
        
        rows_asi = run_sql(f"""
            SELECT ISNULL(MAX(CASI_ASIENTO), 0) + 1 as next_asi
            FROM SIST_CASI WITH (UPDLOCK, HOLDLOCK)
            WHERE CASI_DIVISION = {division}
        """)
        
        if not rows_asi:
            return jsonify({"ok": False, "error": "No se pudo obtener número de asiento"}), 500
        
        nro_asi = int(rows_asi[0]['next_asi'])
        
        renglon_iva = ""
        if imp_iva > 0:
            iva_con = round(imp_iva_loc / cotizacion_conv, 2) if cotizacion_conv else imp_iva_loc
            renglon_iva = f"""
            INSERT INTO SIST_RASI (
                RASI_DIVISION, RASI_ASIENTO, RASI_RENGLON,
                RASI_CUENTA, RASI_IMP_LOC, RASI_IMP_CON, RASI_IMP_ORI,
                RASI_SIGNO, RASI_CANTIDAD, RASI_DESCRIPCION, RASI_EDITABLE, RASI_FIJA
            ) VALUES (
                {division}, {nro_asi}, 1,
                '110401001', {imp_iva_loc}, {iva_con}, 0,
                'D', 0, 'IVA 12% GUATEMALA', 0, 1
            );"""
        
        renglones_sql = ""
        aasi_sql = ""
        renglones_validos = [(rg, idx) for idx, rg in enumerate(renglones) if str(rg.get("cuenta", "")).strip() and float(rg.get("importe", 0)) > 0]
        suma_rg_loc = 0.0
        
        for loop_idx, (rg, idx) in enumerate(renglones_validos):
            rg_cuenta = str(rg.get("cuenta", "")).replace("'", "")
            rg_imp = float(rg.get("importe", 0))
            rg_cco = str(rg.get("cco", "")).replace("'", "")
            rg_num = idx + 2
            rg_imp_loc = round(rg_imp * cotizacion, 2) if moneda != "PS" else rg_imp
            if loop_idx == len(renglones_validos) - 1:
                rg_imp_loc = round(imp_bruto_loc - suma_rg_loc, 2)
            suma_rg_loc += rg_imp_loc
            rg_imp_con = round(rg_imp_loc / cotizacion_conv, 2) if cotizacion_conv else rg_imp_loc
            
            renglones_sql += f"""
            INSERT INTO SIST_RASI (
                RASI_DIVISION, RASI_ASIENTO, RASI_RENGLON,
                RASI_CUENTA, RASI_IMP_LOC, RASI_IMP_CON, RASI_IMP_ORI,
                RASI_SIGNO, RASI_CANTIDAD, RASI_DESCRIPCION, RASI_EDITABLE, RASI_FIJA
            ) VALUES (
                {division}, {nro_asi}, {rg_num},
                '{rg_cuenta}', {rg_imp_loc}, {rg_imp_con}, 0,
                'D', 0, '', 1, 0
            );"""
            
            if rg_cco:
                aasi_sql += f"""
            DECLARE @nro_aasi_{idx} INT;
            SELECT @nro_aasi_{idx} = ISNULL(MAX(AASI_ASIENTO), 0) + 1
                FROM SIST_AASI WITH (UPDLOCK, HOLDLOCK)
                WHERE AASI_DIVISION = {division};
            INSERT INTO SIST_AASI (
                AASI_DIVISION, AASI_ASIENTO, AASI_RENGLON_ASI, AASI_RENGLON_APE,
                AASI_MAESTRO, AASI_INSTANCIA,
                AASI_IMP_LOC, AASI_IMP_CON, AASI_IMP_ORI,
                AASI_SIGNO, AASI_CANTIDAD
            ) VALUES (
                {division}, @nro_aasi_{idx}, {rg_num}, 1,
                'CCO', '{rg_cco}',
                {rg_imp_loc}, {rg_imp_con}, 0,
                'D', 0
            );"""
        
        rg_prov_num = len(renglones_validos) + 2
        prov_con = round(imp_total_loc / cotizacion_conv, 2) if cotizacion_conv else imp_total_loc
        
        query = f"""
        BEGIN TRANSACTION;
        BEGIN TRY
            
            INSERT INTO CPAG_CDPR (
                CDPR_DIVISION_CDPR, CDPR_TIPO_CDPR, CDPR_NUMERO_CDPR,
                CDPR_FECHA_EMI, CDPR_FECHA_PROV, CDPR_FECHA_REC,
                CDPR_PROVEEDOR, CDPR_REF_PROV,
                CDPR_ES_DIF_CAMBIO, CDPR_ES_PROVISION,
                CDPR_ORIGEN, CDPR_CLASIF_CVCO_1, CDPR_IMP_FISCAL, CDPR_CPBTE_FCE
            ) VALUES (
                {division}, '{tipo_comp}', {nro_cdpr},
                '{fecha}', '{fecha}', '{fecha}',
                {proveedor}, '{ref_prov}',
                0, 0, 1, '03', 0, 0
            );
            
            INSERT INTO CPAG_CTEP (
                CTEP_CTACTE_CTEP, CTEP_DIVISION, CTEP_ORIGEN,
                CTEP_PROVEEDOR, CTEP_FECHA_EMI,
                CTEP_COND_PAGO, CTEP_SIGNO, CTEP_DESCRIPCION,
                CTEP_MONEDA, CTEP_COTIZACION,
                CTEP_IMP_BRU_ORI, CTEP_IMP_BRU_LOC,
                CTEP_IMP_TOT_ORI, CTEP_IMP_TOT_LOC,
                CTEP_ES_DIF_CAMBIO
            ) VALUES (
                {ctacte}, {division}, 1,
                {proveedor}, '{fecha}',
                '{cond_pago}', 'H', '{descripcion}',
                '{moneda}', {cotizacion},
                {imp_bruto}, {imp_bruto_loc},
                {imp_total}, {imp_total_loc},
                0
            );
            
            INSERT INTO CPAG_RCCP (
                RCCP_CTACTE_CTEP, RCCP_DIVISION_CDPR, RCCP_TIPO_CDPR, RCCP_NUMERO_CDPR
            ) VALUES (
                {ctacte}, {division}, '{tipo_comp}', {nro_cdpr}
            );
            
            INSERT INTO CPAG_VCTP (
                VCTP_CTACTE_CTEP, VCTP_RENGLON_VCTP,
                VCTP_FECHA_VTO, VCTP_FECHA_VTO_FIN, VCTP_NUM_CUOTA,
                VCTP_IMP_ORI, VCTP_IMP_LOC, VCTP_SAL_ORI, VCTP_SAL_LOC
            ) VALUES (
                {ctacte}, 1,
                '{fecha_vto}', '{fecha_vto}', 1,
                {imp_total}, {imp_total_loc}, {imp_total}, {imp_total_loc}
            );
            
            INSERT INTO SIST_CASI (
                CASI_DIVISION, CASI_ASIENTO, CASI_ORIGEN,
                CASI_FECHA, CASI_SUBDIARIO, CASI_COTIZACION,
                CASI_COMENTARIO
            ) VALUES (
                {division}, {nro_asi}, 'CPCV',
                '{fecha}', 'CPA', {cotizacion},
                '{descripcion}'
            );
            
            {renglon_iva}
            {renglones_sql}
            
            INSERT INTO SIST_RASI (
                RASI_DIVISION, RASI_ASIENTO, RASI_RENGLON,
                RASI_CUENTA, RASI_IMP_LOC, RASI_IMP_CON, RASI_IMP_ORI,
                RASI_SIGNO, RASI_CANTIDAD, RASI_DESCRIPCION, RASI_EDITABLE, RASI_FIJA
            ) VALUES (
                {division}, {nro_asi}, {rg_prov_num},
                '{cuenta_prov}', {imp_total_loc}, {prov_con}, 0,
                'H', 0, '{nombre_prov_esc}', 0, 1
            );
            
            INSERT INTO CPAG_RASP (RASP_DIVISION, RASP_ASIENTO, RASP_CTACTE_CTEP)
            VALUES ({division}, {nro_asi}, {ctacte});
            
            {aasi_sql}
            {ictp_insert}
            {nctp_insert}
            
            SELECT {ctacte} as ctacte, {nro_cdpr} as nro_cdpr, {nro_asi} as nro_asi;
            
            COMMIT TRANSACTION;
            
        END TRY
        BEGIN CATCH
            ROLLBACK TRANSACTION;
            THROW;
        END CATCH;
        """
        
        rows = run_sql(query)
        ctacte_result = rows[0]["ctacte"] if rows else "?"
        nro_cdpr_result = rows[0]["nro_cdpr"] if rows else "?"
        nro_asi_result = rows[0]["nro_asi"] if rows else "?"
        return jsonify({
            "ok": True, 
            "ctacte": ctacte_result, 
            "nro_comprobante": nro_cdpr_result,
            "nro_asiento": nro_asi_result,
            "tipo": tipo_comp
        })
    except ValueError as e:
        logger.error(f"Error de valor en /cargar_factura: {e}")
        return jsonify({"ok": False, "error": f"Error de validación: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Error en /cargar_factura: {e}")
        return jsonify({"ok": False, "error": f"Error al cargar factura: {str(e)}"}), 500

# ============================================================
# RUTA: ELIMINAR FACTURA
# ============================================================

@cxp_bp.route('/eliminar_factura', methods=["POST"])
def eliminar_factura():
    try:
        d = request.json
        if not d:
            return jsonify({"ok": False, "error": "Datos requeridos"}), 400
            
        tipo_comp = d.get("tipo_comp", "FCP")
        numero_comp = int(d.get("numero_comp"))
        division = int(d.get("division", 7))
        
        rows_ctacte = run_sql(f"""
            SELECT RCCP_CTACTE_CTEP as ctacte
            FROM CPAG_RCCP
            WHERE RCCP_TIPO_CDPR = '{tipo_comp}'
            AND RCCP_NUMERO_CDPR = {numero_comp}
            AND RCCP_DIVISION_CDPR = {division}
        """)
        
        if not rows_ctacte:
            return jsonify({
                "ok": False, 
                "error": f"No se encontró el comprobante {tipo_comp} {numero_comp}"
            }), 404
        
        ctacte = rows_ctacte[0]['ctacte']
        
        rows_asiento = run_sql(f"""
            SELECT RASP_ASIENTO as asiento
            FROM CPAG_RASP
            WHERE RASP_DIVISION = {division}
            AND RASP_CTACTE_CTEP = {ctacte}
        """)
        
        asiento = rows_asiento[0]['asiento'] if rows_asiento else None
        
        query_parts = []
        
        if asiento:
            query_parts.append(f"""
            DELETE FROM SIST_AASI 
            WHERE AASI_DIVISION = {division} 
            AND AASI_ASIENTO = {asiento};
            """)
            query_parts.append(f"""
            DELETE FROM SIST_RASI 
            WHERE RASI_DIVISION = {division} 
            AND RASI_ASIENTO = {asiento};
            """)
            query_parts.append(f"""
            DELETE FROM SIST_CASI 
            WHERE CASI_DIVISION = {division} 
            AND CASI_ASIENTO = {asiento};
            """)
        
        query_parts.append(f"""
        DELETE FROM CPAG_RASP 
        WHERE RASP_DIVISION = {division} 
        AND RASP_CTACTE_CTEP = {ctacte};
        """)
        
        query_parts.append(f"""
        DELETE FROM CPAG_ICTP 
        WHERE ICTP_CTACTE_CTEP = {ctacte};
        """)
        
        query_parts.append(f"""
        DELETE FROM CPAG_VCTP 
        WHERE VCTP_CTACTE_CTEP = {ctacte};
        """)
        
        query_parts.append(f"""
        DELETE FROM CPAG_CTEP 
        WHERE CTEP_DIVISION = {division} 
        AND CTEP_CTACTE_CTEP = {ctacte};
        """)
        
        query_parts.append(f"""
        DELETE FROM CPAG_RCCP 
        WHERE RCCP_DIVISION_CDPR = {division} 
        AND RCCP_TIPO_CDPR = '{tipo_comp}' 
        AND RCCP_NUMERO_CDPR = {numero_comp};
        """)
        
        query_parts.append(f"""
        DELETE FROM CPAG_CDPR 
        WHERE CDPR_DIVISION_CDPR = {division} 
        AND CDPR_TIPO_CDPR = '{tipo_comp}' 
        AND CDPR_NUMERO_CDPR = {numero_comp};
        """)
        
        query = """
        BEGIN TRANSACTION;
        BEGIN TRY
        """ + "\n".join(query_parts) + """
            COMMIT TRANSACTION;
            
            SELECT 
                '✅ ELIMINACIÓN COMPLETA' as Resultado,
                """ + str(ctacte) + """ as ctacte_eliminado,
                """ + str(asiento if asiento else 'NULL') + """ as asiento_eliminado;
            
        END TRY
        BEGIN CATCH
            ROLLBACK TRANSACTION;
            THROW;
        END CATCH;
        """
        
        rows = run_sql(query)
        return jsonify({
            "ok": True,
            "mensaje": f"Comprobante {tipo_comp} {numero_comp} eliminado correctamente",
            "ctacte_eliminado": ctacte,
            "asiento_eliminado": asiento,
            "resultado": rows[0]['Resultado'] if rows else "OK"
        })
    except ValueError as e:
        return jsonify({"ok": False, "error": f"Error de validación: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Error en /eliminar_factura: {e}")
        return jsonify({"ok": False, "error": f"Error al eliminar factura: {str(e)}"}), 500

# ============================================================
# RUTA: DEBUG PDF
# ============================================================

@cxp_bp.route('/debug_pdf', methods=["POST"])
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
            os.unlink(tmp_path)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error en /debug_pdf: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# RUTA: FACTURA DE PRUEBA
# ============================================================

@cxp_bp.route('/factura_prueba', methods=["GET"])
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