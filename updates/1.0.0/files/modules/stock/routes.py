# modules/stock/routes.py
# ============================================================
# RUTAS STOCK - SIDESYS ERP (CORREGIDO - CONSULTAS PARAMETRIZADAS + SEGURIDAD)
# ============================================================

from flask import Blueprint, request, jsonify, g
import openpyxl
import threading
import json
import subprocess
import sys
import os
import io
import logging
from modules.shared.database import run_sql, run_sql_db, _sql_literal, set_contexto_base
from config import BASES_DISPONIBLES, CATEGORIAS_ARTICULO, CUENTAS_POR_ORIGEN, _UY_COLS, _BASES_CONSOLIDADO, SQL_SERVER, SQL_USERNAME, SQL_PASSWORD

logger = logging.getLogger(__name__)

stock_bp = Blueprint('stock', __name__, url_prefix='/api')

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
        import traceback
        print(f"❌ Error en /api/articulos: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@stock_bp.route('/depositos', methods=["GET"])
def listar_depositos():
    try:
        rows = run_sql("SELECT DPOS_DEPOSITO, DPOS_NOMBRE FROM STOC_DPOS WHERE DPOS_UTILIZABLE = 1 ORDER BY DPOS_NOMBRE")
        out = [{"id": r["DPOS_DEPOSITO"], "nombre": r["DPOS_NOMBRE"]} for r in rows]
        return jsonify(out)
    except Exception as e:
        import traceback
        print(f"❌ Error en /api/depositos: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@stock_bp.route('/categorias', methods=["GET"])
def listar_categorias():
    try:
        from config import CATEGORIAS_ARTICULO
        out = [{"codigo": cod, "nombre": info["nombre"], "con_partidas_default": info["con_partidas_default"]} 
               for cod, info in CATEGORIAS_ARTICULO.items()]
        return jsonify(out)
    except Exception as e:
        import traceback
        print(f"❌ Error en /api/categorias: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@stock_bp.route('/partidas', methods=["GET"])
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
# RUTAS STOCK - AJUSTES
# ============================================================

def _hacer_ajuste(articulo, deposito, cantidad, signo, partida=None, fecha=None, partida_nombre=None, comentario=None):
    division, sucursal_imp, sucursal_emp = g.division, g.sucursal, g.sucursal
    tipo_com = "AJ+" if signo == "E" else "AJ-"
    fecha_sql = f"'{fecha}'" if fecha else "CAST(GETDATE() AS DATE)"

    # ✅ CORREGIDO: Consulta con parámetros
    rows = run_sql("SELECT ARTS_CON_PARTIDAS FROM STOC_ARTS WHERE ARTS_ARTICULO = ?", params=[articulo])
    if not rows:
        return {"error": "Artículo no encontrado"}
    con_partidas = bool(rows[0]["ARTS_CON_PARTIDAS"])

    if signo == "S" and con_partidas and not partida:
        return {"error": "Este artículo usa partidas: falta indicar cuál"}
    if signo == "S" and con_partidas:
        rows = run_sql("""
            SELECT SDPP_STOCK_ACT FROM STOC_SDPP
            WHERE SDPP_DEPOSITO = ? AND SDPP_PARTIDA = ? AND SDPP_ARTICULO = ?
        """, params=[deposito, partida, articulo])
        if not rows or float(rows[0]["SDPP_STOCK_ACT"]) < cantidad:
            return {"error": "Stock insuficiente en esa partida"}

    crea_partidas = 1 if (signo == "E" and con_partidas) else 0

    mov_id = _obtener_proximo_movimiento_id()
    
    sql_parts = ["BEGIN TRANSACTION;"]
    sql_parts.append(f"DECLARE @mov INT = {mov_id};")
    
    sql_parts.append(f"""
        DECLARE @num INT = (SELECT NUST_ULT_NUMERO+1 FROM STOC_NUST WITH (UPDLOCK, ROWLOCK)
        WHERE NUST_DIVISION={division} AND NUST_SUCURSAL_IMP={sucursal_imp} AND NUST_TIPO_COM='{tipo_com}');
    """)
    sql_parts.append(f"""
        UPDATE STOC_NUST SET NUST_ULT_NUMERO=@num, NUST_FECHA_ULT_COM=GETDATE()
        WHERE NUST_DIVISION={division} AND NUST_SUCURSAL_IMP={sucursal_imp} AND NUST_TIPO_COM='{tipo_com}';
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_MOST (MOST_MOVSTO_MOST, MOST_ORIGEN, MOST_SUBORIGEN_VAR, MOST_FECHA_EMI,
            MOST_DIVISION, MOST_SUCURSAL_IMP, MOST_SUCURSAL_EMP, MOST_SUJETO, MOST_SUJETO_GLOBAL, MOST_TIENE_ASIENTO, MOST_DESCRIPCION)
        VALUES (@mov, 1, 1, {fecha_sql}, {division}, {sucursal_imp}, {sucursal_emp}, 0, 0, 0, {_sql_literal(comentario)});
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_MOSD (MOSD_MOVSTO_MOST, MOSD_RENGLON_MOSD, MOSD_ORIGEN, MOSD_SUBORIGEN_VAR,
            MOSD_DEPOSITO, MOSD_ARTICULO, MOSD_SIGNO, MOSD_MOD_STOCK, MOSD_CANT_ING, MOSD_UNIMED,
            MOSD_CANT_UNISTO, MOSD_FACTOR_UMS, MOSD_TIENE_PEDIDOS, MOSD_CREA_PARTIDAS, MOSD_TIENE_OC,
            MOSD_TIENE_REG_PPP, MOSD_TIENE_PPP_PAR)
        VALUES (@mov, 1, 1, 1, {deposito}, {articulo}, '{signo}', 1, {cantidad}, 'UN', {cantidad}, 1,
            0, {crea_partidas}, 0, 0, 0);
    """)

    if signo == "E":
        if con_partidas:
            sql_parts.append("DECLARE @part INT = (SELECT ISNULL(MAX(PART_PARTIDA),0)+1 FROM STOC_PART WITH (UPDLOCK, TABLOCKX));")
            sql_parts.append(f"""
                INSERT INTO STOC_PART (PART_PARTIDA, PART_PARTIDA_EMP, PART_ARTICULO, PART_FECHA_ALTA,
                    PART_CANT_INI, PART_COSTO_GES_1, PART_COSTO_GES_2, PART_COSTO_GES_3, PART_COSTO_GES_4)
                VALUES (@part, {_sql_literal(partida_nombre) if partida_nombre else 'CAST(@part AS VARCHAR)'}, {articulo}, CAST(GETDATE() AS DATE), {cantidad}, 0, 0, 0, 0);
            """)
            sql_parts.append(f"""
                INSERT INTO STOC_SDPP (SDPP_DEPOSITO, SDPP_PARTIDA, SDPP_ARTICULO, SDPP_STOCK_ACT, SDPP_STRES_PED)
                VALUES ({deposito}, @part, {articulo}, {cantidad}, 0);
            """)
        sql_parts.append(f"""
            IF EXISTS (SELECT 1 FROM STOC_STDP WHERE STDP_DEPOSITO={deposito} AND STDP_ARTICULO={articulo})
                UPDATE STOC_STDP SET STDP_STOCK_ACT = STDP_STOCK_ACT + {cantidad}
                WHERE STDP_DEPOSITO={deposito} AND STDP_ARTICULO={articulo};
            ELSE
                INSERT INTO STOC_STDP (STDP_DEPOSITO, STDP_ARTICULO, STDP_STOCK_ACT, STDP_STEGR_PED,
                    STDP_STEGR_FAB, STDP_STING_COM, STDP_STING_FAB, STDP_STRES_PED)
                VALUES ({deposito}, {articulo}, {cantidad}, 0, 0, 0, 0, 0);
        """)
    else:
        if con_partidas:
            sql_parts.append(f"""
                DECLARE @restante DECIMAL(18,4) = (SELECT SDPP_STOCK_ACT FROM STOC_SDPP
                    WHERE SDPP_DEPOSITO={deposito} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={articulo}) - {cantidad};
            """)
            sql_parts.append(f"""
                IF @restante <= 0
                    DELETE FROM STOC_SDPP WHERE SDPP_DEPOSITO={deposito} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={articulo};
                ELSE
                    UPDATE STOC_SDPP SET SDPP_STOCK_ACT=@restante
                    WHERE SDPP_DEPOSITO={deposito} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={articulo};
            """)
        sql_parts.append(f"""
            UPDATE STOC_STDP SET STDP_STOCK_ACT = STDP_STOCK_ACT - {cantidad}
            WHERE STDP_DEPOSITO={deposito} AND STDP_ARTICULO={articulo};
        """)

    sql_parts.append(f"""
        INSERT INTO STOC_MSVA (MSVA_DIVISION_MSVA, MSVA_SUCURSAL_MSVA, MSVA_TIPO_MSVA,
            MSVA_NUMERO_MSVA, MSVA_ORIGEN, MSVA_INDICADOR_DEP, MSVA_FECHA_EMI, MSVA_PESO_EMBALADO,
            MSVA_CANT_BULTOS, MSVA_TIENE_COSTOES, MSVA_REQ_FCANTICIP, MSVA_TIENE_REG_PPP,
            MSVA_INF_TABASTO, MSVA_INGRESO_ART_TC, MSVA_PESO_EMB_CAL, MSVA_VOLUMEN_EMB_CAL, MSVA_VOLUMEN_EMB_AJ)
        VALUES ({division}, {sucursal_imp}, '{tipo_com}', @num, 1, 1, {fecha_sql}, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0);
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_MSMV (MSMV_MOVSTO_MOST, MSMV_DIVISION_MSVA, MSMV_SUCURSAL_MSVA,
            MSMV_TIPO_MSVA, MSMV_NUMERO_MSVA)
        VALUES (@mov, {division}, {sucursal_imp}, '{tipo_com}', @num);
    """)

    sql_parts.append("COMMIT TRANSACTION;")
    sql_parts.append("SELECT @mov AS Movimiento, @num AS Numero;")

    full_sql = " ".join(sql_parts)
    result_rows = run_sql(full_sql)
    movimiento = result_rows[0]["Movimiento"] if result_rows else None
    numero = result_rows[0]["Numero"] if result_rows else None

    return {"ok": True, "movimiento": movimiento, "numero_comprobante": numero, "tipo": tipo_com}

@stock_bp.route('/ajuste', methods=["POST"])
def ajuste():
    data = request.get_json()
    try:
        resultado = _hacer_ajuste(
            data["articulo"], data["deposito"], data["cantidad"], data["signo"],
            data.get("partida"), data.get("fecha"), data.get("partida_nombre"), data.get("comentario")
        )
        if "error" in resultado:
            return jsonify(resultado), 400
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _hacer_ajuste_lote(signo, filas):
    if not filas:
        return {"error": "No hay filas para cargar"}

    division, sucursal_imp, sucursal_emp = g.division, g.sucursal, g.sucursal
    tipo_com = "AJ+" if signo == "E" else "AJ-"

    info_articulos = {}
    for fila in filas:
        art = fila["articulo"]
        if art not in info_articulos:
            rows = run_sql("SELECT ARTS_CON_PARTIDAS FROM STOC_ARTS WHERE ARTS_ARTICULO = ?", params=[art])
            if not rows:
                return {"error": f"Artículo {art} no encontrado"}
            info_articulos[art] = bool(rows[0]["ARTS_CON_PARTIDAS"])

        con_partidas = info_articulos[art]
        if signo == "S" and con_partidas and not fila.get("partida"):
            return {"error": f"Artículo {art} usa partidas: falta indicar cuál (fila con depósito {fila['deposito']})"}
        if signo == "S" and con_partidas:
            rows = run_sql("""
                SELECT SDPP_STOCK_ACT FROM STOC_SDPP
                WHERE SDPP_DEPOSITO = ? AND SDPP_PARTIDA = ? AND SDPP_ARTICULO = ?
            """, params=[fila['deposito'], fila['partida'], art])
            if not rows or float(rows[0]["SDPP_STOCK_ACT"]) < fila["cantidad"]:
                return {"error": f"Stock insuficiente en partida {fila['partida']} del artículo {art}"}

    mov_id = _obtener_proximo_movimiento_id()
    
    sql_parts = ["BEGIN TRANSACTION;"]
    sql_parts.append(f"DECLARE @mov INT = {mov_id};")
    
    sql_parts.append(f"""
        DECLARE @num INT = (SELECT NUST_ULT_NUMERO+1 FROM STOC_NUST WITH (UPDLOCK, ROWLOCK)
        WHERE NUST_DIVISION={division} AND NUST_SUCURSAL_IMP={sucursal_imp} AND NUST_TIPO_COM='{tipo_com}');
    """)
    sql_parts.append(f"""
        UPDATE STOC_NUST SET NUST_ULT_NUMERO=@num, NUST_FECHA_ULT_COM=GETDATE()
        WHERE NUST_DIVISION={division} AND NUST_SUCURSAL_IMP={sucursal_imp} AND NUST_TIPO_COM='{tipo_com}';
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_MOST (MOST_MOVSTO_MOST, MOST_ORIGEN, MOST_SUBORIGEN_VAR, MOST_FECHA_EMI,
            MOST_DIVISION, MOST_SUCURSAL_IMP, MOST_SUCURSAL_EMP, MOST_SUJETO, MOST_SUJETO_GLOBAL, MOST_TIENE_ASIENTO)
        VALUES (@mov, 1, 1, CAST(GETDATE() AS DATE), {division}, {sucursal_imp}, {sucursal_emp}, 0, 0, 0);
    """)

    for idx, fila in enumerate(filas, start=1):
        art = fila["articulo"]
        deposito = fila["deposito"]
        cantidad = fila["cantidad"]
        partida = fila.get("partida")
        con_partidas = info_articulos[art]
        crea_partidas = 1 if (signo == "E" and con_partidas) else 0

        sql_parts.append(f"""
            INSERT INTO STOC_MOSD (MOSD_MOVSTO_MOST, MOSD_RENGLON_MOSD, MOSD_ORIGEN, MOSD_SUBORIGEN_VAR,
                MOSD_DEPOSITO, MOSD_ARTICULO, MOSD_SIGNO, MOSD_MOD_STOCK, MOSD_CANT_ING, MOSD_UNIMED,
                MOSD_CANT_UNISTO, MOSD_FACTOR_UMS, MOSD_TIENE_PEDIDOS, MOSD_CREA_PARTIDAS, MOSD_TIENE_OC,
                MOSD_TIENE_REG_PPP, MOSD_TIENE_PPP_PAR)
            VALUES (@mov, {idx}, 1, 1, {deposito}, {art}, '{signo}', 1, {cantidad}, 'UN', {cantidad}, 1,
                0, {crea_partidas}, 0, 0, 0);
        """)

        if signo == "E":
            if con_partidas:
                sql_parts.append(f"""
                    DECLARE @part{idx} INT = (SELECT ISNULL(MAX(PART_PARTIDA),0)+1 FROM STOC_PART WITH (UPDLOCK, TABLOCKX));
                """)
                sql_parts.append(f"""
                    INSERT INTO STOC_PART (PART_PARTIDA, PART_PARTIDA_EMP, PART_ARTICULO, PART_FECHA_ALTA,
                        PART_CANT_INI, PART_COSTO_GES_1, PART_COSTO_GES_2, PART_COSTO_GES_3, PART_COSTO_GES_4)
                    VALUES (@part{idx}, CAST(@part{idx} AS VARCHAR), {art}, CAST(GETDATE() AS DATE), {cantidad}, 0, 0, 0, 0);
                """)
                sql_parts.append(f"""
                    INSERT INTO STOC_SDPP (SDPP_DEPOSITO, SDPP_PARTIDA, SDPP_ARTICULO, SDPP_STOCK_ACT, SDPP_STRES_PED)
                    VALUES ({deposito}, @part{idx}, {art}, {cantidad}, 0);
                """)
            sql_parts.append(f"""
                IF EXISTS (SELECT 1 FROM STOC_STDP WHERE STDP_DEPOSITO={deposito} AND STDP_ARTICULO={art})
                    UPDATE STOC_STDP SET STDP_STOCK_ACT = STDP_STOCK_ACT + {cantidad}
                    WHERE STDP_DEPOSITO={deposito} AND STDP_ARTICULO={art};
                ELSE
                    INSERT INTO STOC_STDP (STDP_DEPOSITO, STDP_ARTICULO, STDP_STOCK_ACT, STDP_STEGR_PED,
                        STDP_STEGR_FAB, STDP_STING_COM, STDP_STING_FAB, STDP_STRES_PED)
                    VALUES ({deposito}, {art}, {cantidad}, 0, 0, 0, 0, 0);
            """)
        else:
            if con_partidas:
                sql_parts.append(f"""
                    DECLARE @restante{idx} DECIMAL(18,4) = (SELECT SDPP_STOCK_ACT FROM STOC_SDPP
                        WHERE SDPP_DEPOSITO={deposito} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={art}) - {cantidad};
                """)
                sql_parts.append(f"""
                    IF @restante{idx} <= 0
                        DELETE FROM STOC_SDPP WHERE SDPP_DEPOSITO={deposito} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={art};
                    ELSE
                        UPDATE STOC_SDPP SET SDPP_STOCK_ACT=@restante{idx}
                        WHERE SDPP_DEPOSITO={deposito} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={art};
                """)
            sql_parts.append(f"""
                UPDATE STOC_STDP SET STDP_STOCK_ACT = STDP_STOCK_ACT - {cantidad}
                WHERE STDP_DEPOSITO={deposito} AND STDP_ARTICULO={art};
            """)

    sql_parts.append(f"""
        INSERT INTO STOC_MSVA (MSVA_DIVISION_MSVA, MSVA_SUCURSAL_MSVA, MSVA_TIPO_MSVA,
            MSVA_NUMERO_MSVA, MSVA_ORIGEN, MSVA_INDICADOR_DEP, MSVA_FECHA_EMI, MSVA_PESO_EMBALADO,
            MSVA_CANT_BULTOS, MSVA_TIENE_COSTOES, MSVA_REQ_FCANTICIP, MSVA_TIENE_REG_PPP,
            MSVA_INF_TABASTO, MSVA_INGRESO_ART_TC, MSVA_PESO_EMB_CAL, MSVA_VOLUMEN_EMB_CAL, MSVA_VOLUMEN_EMB_AJ)
        VALUES ({division}, {sucursal_imp}, '{tipo_com}', @num, 1, 1, CAST(GETDATE() AS DATE), 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0);
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_MSMV (MSMV_MOVSTO_MOST, MSMV_DIVISION_MSVA, MSMV_SUCURSAL_MSVA,
            MSMV_TIPO_MSVA, MSMV_NUMERO_MSVA)
        VALUES (@mov, {division}, {sucursal_imp}, '{tipo_com}', @num);
    """)

    sql_parts.append("COMMIT TRANSACTION;")
    sql_parts.append("SELECT @mov AS Movimiento, @num AS Numero;")

    full_sql = " ".join(sql_parts)
    result_rows = run_sql(full_sql)
    movimiento = result_rows[0]["Movimiento"] if result_rows else None
    numero = result_rows[0]["Numero"] if result_rows else None

    return {"ok": True, "movimiento": movimiento, "numero_comprobante": numero, "tipo": tipo_com, "cantidad_renglones": len(filas)}

@stock_bp.route('/ajuste/lote', methods=["POST"])
def ajuste_lote():
    data = request.get_json()
    try:
        resultado = _hacer_ajuste_lote(data["signo"], data.get("filas", []))
        if "error" in resultado:
            return jsonify(resultado), 400
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# RUTAS STOCK - TRANSFERENCIAS
# ============================================================

def _hacer_transferencia(articulo, dep_origen, dep_destino, cantidad, partida=None, fecha=None, comentario=None):
    division, sucursal_imp, sucursal_emp = g.division, g.sucursal, g.sucursal
    fecha_sql = f"'{fecha}'" if fecha else "CAST(GETDATE() AS DATE)"
    if dep_origen == dep_destino:
        return {"error": "El depósito origen y destino no pueden ser el mismo"}

    rows = run_sql("SELECT ARTS_CON_PARTIDAS FROM STOC_ARTS WHERE ARTS_ARTICULO = ?", params=[articulo])
    if not rows:
        return {"error": "Artículo no encontrado"}
    con_partidas = bool(rows[0]["ARTS_CON_PARTIDAS"])

    if con_partidas and not partida:
        return {"error": "Este artículo usa partidas: falta indicar cuál"}
    if con_partidas:
        rows = run_sql("""
            SELECT SDPP_STOCK_ACT FROM STOC_SDPP
            WHERE SDPP_DEPOSITO = ? AND SDPP_PARTIDA = ? AND SDPP_ARTICULO = ?
        """, params=[dep_origen, partida, articulo])
        if not rows or float(rows[0]["SDPP_STOCK_ACT"]) < cantidad:
            return {"error": "Stock insuficiente en esa partida, en el depósito de origen"}
    else:
        rows = run_sql("""
            SELECT STDP_STOCK_ACT FROM STOC_STDP
            WHERE STDP_DEPOSITO = ? AND STDP_ARTICULO = ?
        """, params=[dep_origen, articulo])
        if not rows or float(rows[0]["STDP_STOCK_ACT"]) < cantidad:
            return {"error": "Stock insuficiente en depósito de origen"}

    mov_id_salida = _obtener_proximo_movimiento_id()
    mov_id_entrada = _obtener_proximo_movimiento_id()
    
    sql_parts = ["BEGIN TRANSACTION;"]
    sql_parts.append(f"DECLARE @movS INT = {mov_id_salida};")
    sql_parts.append(f"DECLARE @movE INT = {mov_id_entrada};")
    
    sql_parts.append(f"""
        INSERT INTO STOC_MOST (MOST_MOVSTO_MOST, MOST_ORIGEN, MOST_SUBORIGEN_VAR, MOST_FECHA_EMI,
            MOST_DIVISION, MOST_SUCURSAL_IMP, MOST_SUCURSAL_EMP, MOST_SUJETO, MOST_SUJETO_GLOBAL, MOST_TIENE_ASIENTO, MOST_DESCRIPCION)
        VALUES (@movS, 2, 0, {fecha_sql}, {division}, {sucursal_imp}, {sucursal_emp}, 0, 0, 0, {_sql_literal(comentario)});
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_MOSD (MOSD_MOVSTO_MOST, MOSD_RENGLON_MOSD, MOSD_ORIGEN, MOSD_SUBORIGEN_VAR,
            MOSD_DEPOSITO, MOSD_ARTICULO, MOSD_SIGNO, MOSD_MOD_STOCK, MOSD_CANT_ING, MOSD_UNIMED,
            MOSD_CANT_UNISTO, MOSD_FACTOR_UMS, MOSD_TIENE_PEDIDOS, MOSD_CREA_PARTIDAS, MOSD_TIENE_OC,
            MOSD_TIENE_REG_PPP, MOSD_TIENE_PPP_PAR)
        VALUES (@movS, 1, 2, 0, {dep_origen}, {articulo}, 'S', 1, {cantidad}, 'UN', {cantidad}, 1, 0, 0, 0, 0, 0);
    """)

    sql_parts.append(f"""
        INSERT INTO STOC_MOST (MOST_MOVSTO_MOST, MOST_ORIGEN, MOST_SUBORIGEN_VAR, MOST_FECHA_EMI,
            MOST_DIVISION, MOST_SUCURSAL_IMP, MOST_SUCURSAL_EMP, MOST_SUJETO, MOST_SUJETO_GLOBAL, MOST_TIENE_ASIENTO, MOST_DESCRIPCION)
        VALUES (@movE, 3, 0, {fecha_sql}, {division}, {sucursal_imp}, {sucursal_emp}, 0, 0, 0, {_sql_literal(comentario)});
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_MOSD (MOSD_MOVSTO_MOST, MOSD_RENGLON_MOSD, MOSD_ORIGEN, MOSD_SUBORIGEN_VAR,
            MOSD_DEPOSITO, MOSD_ARTICULO, MOSD_SIGNO, MOSD_MOD_STOCK, MOSD_CANT_ING, MOSD_UNIMED,
            MOSD_CANT_UNISTO, MOSD_FACTOR_UMS, MOSD_TIENE_PEDIDOS, MOSD_CREA_PARTIDAS, MOSD_TIENE_OC,
            MOSD_TIENE_REG_PPP, MOSD_TIENE_PPP_PAR)
        VALUES (@movE, 1, 3, 0, {dep_destino}, {articulo}, 'E', 1, {cantidad}, 'UN', {cantidad}, 1, 0, 0, 0, 0, 0);
    """)

    sql_parts.append(f"""
        DECLARE @numTRS INT = (SELECT NUST_ULT_NUMERO+1 FROM STOC_NUST WITH (UPDLOCK, ROWLOCK)
        WHERE NUST_DIVISION={division} AND NUST_SUCURSAL_IMP={sucursal_imp} AND NUST_TIPO_COM='TRS');
    """)
    sql_parts.append(f"""
        UPDATE STOC_NUST SET NUST_ULT_NUMERO=@numTRS, NUST_FECHA_ULT_COM=GETDATE()
        WHERE NUST_DIVISION={division} AND NUST_SUCURSAL_IMP={sucursal_imp} AND NUST_TIPO_COM='TRS';
    """)
    sql_parts.append(f"""
        DECLARE @numTRE INT = (SELECT NUST_ULT_NUMERO+1 FROM STOC_NUST WITH (UPDLOCK, ROWLOCK)
        WHERE NUST_DIVISION={division} AND NUST_SUCURSAL_IMP={sucursal_imp} AND NUST_TIPO_COM='TRE');
    """)
    sql_parts.append(f"""
        UPDATE STOC_NUST SET NUST_ULT_NUMERO=@numTRE, NUST_FECHA_ULT_COM=GETDATE()
        WHERE NUST_DIVISION={division} AND NUST_SUCURSAL_IMP={sucursal_imp} AND NUST_TIPO_COM='TRE';
    """)

    sql_parts.append(f"""
        INSERT INTO STOC_TRSS (TRSS_DIVISION_TRSS, TRSS_SUCURSAL_TRSS, TRSS_TIPO_TRSS, TRSS_NUMERO_TRSS,
            TRSS_FECHA_EMI, TRSS_DEPOSITO, TRSS_INF_TABASTO, TRSS_ES_TRANSITO, TRSS_TIPO_TRANSITO, TRSS_ES_DEVOL_PEDIDO)
        VALUES ({division}, {sucursal_imp}, 'TRS', @numTRS, {fecha_sql}, {dep_origen}, 0, 0, 1, 0);
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_TRES (TRES_DIVISION_TRES, TRES_SUCURSAL_TRES, TRES_TIPO_TRES, TRES_NUMERO_TRES,
            TRES_FECHA_EMI, TRES_DEPOSITO, TRES_DIVISION_TRSS, TRES_SUCURSAL_TRSS, TRES_TIPO_TRSS, TRES_NUMERO_TRSS,
            TRES_PESO_EMBALADO, TRES_CANT_BULTOS, TRES_ES_TRANSITO, TRES_TIPO_TRANSITO, TRES_INGRESO_ART_TC,
            TRES_PESO_EMB_CAL, TRES_VOLUMEN_EMB_CAL, TRES_VOLUMEN_EMB_AJ)
        VALUES ({division}, {sucursal_imp}, 'TRE', @numTRE, {fecha_sql}, {dep_destino}, {division}, {sucursal_imp},
            'TRS', @numTRS, 0, 0, 0, 1, 0, 0, 0, 0);
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_MSTS (MSTS_MOVSTO_MOST, MSTS_DIVISION_TRSS, MSTS_SUCURSAL_TRSS, MSTS_TIPO_TRSS, MSTS_NUMERO_TRSS)
        VALUES (@movS, {division}, {sucursal_imp}, 'TRS', @numTRS);
    """)
    sql_parts.append(f"""
        INSERT INTO STOC_MSTE (MSTE_MOVSTO_MOST, MSTE_DIVISION_TRES, MSTE_SUCURSAL_TRES, MSTE_TIPO_TRES,
            MSTE_NUMERO_TRES, MSTE_MOVSTO_MSTS)
        VALUES (@movE, {division}, {sucursal_imp}, 'TRE', @numTRE, @movS);
    """)

    sql_parts.append(f"""
        UPDATE STOC_STDP SET STDP_STOCK_ACT = STDP_STOCK_ACT - {cantidad}
        WHERE STDP_DEPOSITO={dep_origen} AND STDP_ARTICULO={articulo};
    """)
    sql_parts.append(f"""
        IF EXISTS (SELECT 1 FROM STOC_STDP WHERE STDP_DEPOSITO={dep_destino} AND STDP_ARTICULO={articulo})
            UPDATE STOC_STDP SET STDP_STOCK_ACT = STDP_STOCK_ACT + {cantidad}
            WHERE STDP_DEPOSITO={dep_destino} AND STDP_ARTICULO={articulo};
        ELSE
            INSERT INTO STOC_STDP (STDP_DEPOSITO, STDP_ARTICULO, STDP_STOCK_ACT, STDP_STEGR_PED,
                STDP_STEGR_FAB, STDP_STING_COM, STDP_STING_FAB, STDP_STRES_PED)
            VALUES ({dep_destino}, {articulo}, {cantidad}, 0, 0, 0, 0, 0);
    """)

    if con_partidas:
        sql_parts.append(f"""
            DECLARE @restanteP DECIMAL(18,4) = (SELECT SDPP_STOCK_ACT FROM STOC_SDPP
                WHERE SDPP_DEPOSITO={dep_origen} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={articulo}) - {cantidad};
        """)
        sql_parts.append(f"""
            IF @restanteP <= 0
                DELETE FROM STOC_SDPP WHERE SDPP_DEPOSITO={dep_origen} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={articulo};
            ELSE
                UPDATE STOC_SDPP SET SDPP_STOCK_ACT=@restanteP
                WHERE SDPP_DEPOSITO={dep_origen} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={articulo};
        """)
        sql_parts.append(f"""
            IF EXISTS (SELECT 1 FROM STOC_SDPP WHERE SDPP_DEPOSITO={dep_destino} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={articulo})
                UPDATE STOC_SDPP SET SDPP_STOCK_ACT = SDPP_STOCK_ACT + {cantidad}
                WHERE SDPP_DEPOSITO={dep_destino} AND SDPP_PARTIDA={partida} AND SDPP_ARTICULO={articulo};
            ELSE
                INSERT INTO STOC_SDPP (SDPP_DEPOSITO, SDPP_PARTIDA, SDPP_ARTICULO, SDPP_STOCK_ACT, SDPP_STRES_PED)
                VALUES ({dep_destino}, {partida}, {articulo}, {cantidad}, 0);
        """)

    sql_parts.append("COMMIT TRANSACTION;")
    sql_parts.append("SELECT @movS AS MovSalida, @movE AS MovEntrada, @numTRS AS NumeroTransferencia;")

    full_sql = " ".join(sql_parts)
    result_rows = run_sql(full_sql)
    r = result_rows[0] if result_rows else {}

    return {
        "ok": True,
        "numero_transferencia": r.get("NumeroTransferencia"),
        "movimiento_salida": r.get("MovSalida"),
        "movimiento_entrada": r.get("MovEntrada"),
    }

@stock_bp.route('/transferencia', methods=["POST"])
def transferencia():
    data = request.get_json()
    try:
        resultado = _hacer_transferencia(
            data["articulo"], data["deposito_origen"], data["deposito_destino"],
            data["cantidad"], data.get("partida"), data.get("fecha"), data.get("comentario")
        )
        if "error" in resultado:
            return jsonify(resultado), 400
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_bp.route('/transferencia/lote', methods=["POST"])
def transferencia_lote():
    data = request.get_json()
    filas = data.get("filas", [])
    resultados = []
    for i, fila in enumerate(filas):
        try:
            r = _hacer_transferencia(
                fila["articulo"], fila["deposito_origen"], fila["deposito_destino"],
                fila["cantidad"], fila.get("partida")
            )
        except Exception as e:
            r = {"error": str(e)}
        r["fila"] = i + 1
        resultados.append(r)
    return jsonify({"resultados": resultados})

# ============================================================
# RUTAS STOCK - EXCEL
# ============================================================

@stock_bp.route('/excel/plantilla/<tipo>', methods=["GET"])
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
            except Exception as e:
                return jsonify({"error": f"Fila {i+2}: {e}"}), 400

        if not filas:
            return jsonify({"error": "El archivo no tiene filas válidas"}), 400

        resp = _hacer_ajuste_lote(signo, filas)
        if "error" in resp:
            return jsonify(resp), 400
        return jsonify(resp)

    elif tipo == "transferencia":
        for i, row in enumerate(rows):
            if not row or row[0] in (None, ""):
                continue
            try:
                articulo, dep_origen, dep_destino, cantidad = row[0], row[1], row[2], row[3]
                partida = row[4] if len(row) > 4 and row[4] not in (None, "") else None
                r = _hacer_transferencia(
                    int(articulo), int(dep_origen), int(dep_destino), float(cantidad),
                    int(partida) if partida is not None else None,
                )
            except Exception as e:
                r = {"error": str(e)}
            r["fila"] = i + 2
            resultados.append(r)
        return jsonify({"resultados": resultados})

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
def renombrar_articulo_por_codigo(codigo):
    data = request.get_json()
    nombre = data.get("nombre")
    bases = data.get("bases")

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
def renombrar_deposito_multibases(deposito_id):
    data = request.get_json()
    nombre = data.get("nombre")
    bases = data.get("bases", [])

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