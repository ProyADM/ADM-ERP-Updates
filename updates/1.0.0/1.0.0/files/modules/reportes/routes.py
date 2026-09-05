# modules/reportes/routes.py
# ============================================================
# RUTAS DE REPORTES - SIDESYS ERP
# ============================================================
# Ahora solo delegan la lógica a los servicios.
# ============================================================

from flask import Blueprint, jsonify, request, session
import logging
import pandas as pd  # <--- AGREGAR
from datetime import datetime  # <--- AGREGAR
from .services import contratos_service, pendiente_cobro_service, consolidado_pais_service, consolidado_total_service, ventas_manuales_service

reportes_bp = Blueprint('reportes', __name__)
logger = logging.getLogger(__name__)

# ============================================================
# REPORTE: CONTRATOS PENDIENTE DE FACTURAR
# ============================================================

@reportes_bp.route('/reportes/contratos', methods=['POST'])
def get_reporte_contratos():
    data = request.get_json() or {}
    resultado = contratos_service.obtener_reporte_contratos(
        anio=data.get('anio'),
        mes=data.get('mes'),
        base_override=data.get('base'),
        sociedad_override=data.get('sociedad')
    )
    return jsonify(resultado)

# ============================================================
# REPORTE: AÑOS DISPONIBLES (para contratos)
# ============================================================

@reportes_bp.route('/reportes/anos', methods=['GET'])
def get_anos_disponibles():
    # Esta función se mantiene igual, pero podemos moverla a utils si queremos
    # Por ahora la dejamos aquí porque es simple.
    try:
        from .services.utils import get_db_connection, get_db_connection_base
        base_param = request.args.get('base')
        sociedad_param = request.args.get('sociedad')
        if base_param:
            conn, division = get_db_connection_base(base_param, sociedad_param)
        else:
            conn, division = get_db_connection()
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT YEAR(COFF_FECHA_EST_FC) AS ANIO
            FROM dbo.ACCT_COFF
            WHERE COFF_FECHA_EST_FC IS NOT NULL
              AND YEAR(COFF_FECHA_EST_FC) >= 2020
            ORDER BY ANIO DESC
        """)
        anos = [row[0] for row in cursor.fetchall()]
        conn.close()
        if not anos:
            from datetime import datetime
            ano_actual = datetime.now().year
            anos = [ano_actual, ano_actual - 1, ano_actual - 2, ano_actual - 3, ano_actual - 4]
        return jsonify({'success': True, 'anos': anos})
    except Exception as e:
        logger.error(f"Error en get_anos_disponibles: {e}")
        return jsonify({'success': False, 'error': str(e), 'anos': []}), 500

# ============================================================
# REPORTE: PENDIENTE DE COBRO
# ============================================================

@reportes_bp.route('/reportes/pendiente_cobro', methods=['GET'])
def get_pendiente_cobro():
    base_override = request.args.get('base')
    sociedad_override = request.args.get('sociedad')
    resultado = pendiente_cobro_service.obtener_pendiente_cobro(base_override, sociedad_override)
    return jsonify(resultado)

# ============================================================
# REPORTE: CONSOLIDADO VENTAS POR PAÍS (sin manuales)
# ============================================================

@reportes_bp.route('/reportes/consolidado_ventas_pais', methods=['GET'])
def get_consolidado_ventas_pais():
    anio = request.args.get('anio')
    if anio and anio.isdigit():
        anio = int(anio)
    else:
        from datetime import datetime
        anio = datetime.now().year

    base_override = request.args.get('base')
    sociedad_override = request.args.get('sociedad')
    resultado = consolidado_pais_service.obtener_consolidado_pais(anio, base_override, sociedad_override)
    return jsonify(resultado)

# ============================================================
# REPORTE: CONSOLIDADO VENTAS GLOBAL (con manuales y cotización)
# ============================================================

@reportes_bp.route('/reportes/consolidado_ventas_global', methods=['GET'])
def get_consolidado_ventas_global():
    anio = request.args.get('anio')
    if anio and anio.isdigit():
        anio = int(anio)
    else:
        from datetime import datetime
        anio = datetime.now().year

    base_override = request.args.get('base')
    sociedad_override = request.args.get('sociedad')
    resultado = consolidado_total_service.obtener_consolidado_total(anio, base_override, sociedad_override)
    return jsonify(resultado)

# ============================================================
# REPORTE: AÑOS DISPONIBLES PARA VENTAS (para el selector del consolidado)
# ============================================================

@reportes_bp.route('/reportes/anos_ventas', methods=['GET'])
def get_anos_ventas():
    try:
        from .services.utils import get_db_connection, get_db_connection_base
        base_override = request.args.get('base')
        sociedad_override = request.args.get('sociedad')
        
        if base_override:
            conn, division = get_db_connection_base(base_override, sociedad_override)
        else:
            conn, division = get_db_connection()
        
        query = """
        SELECT DISTINCT YEAR(AASI_FECHA_REF) AS ANIO
        FROM SIST_AASI
        WHERE AASI_DIVISION = ?
          AND AASI_FECHA_REF IS NOT NULL
        ORDER BY ANIO DESC
        """
        df = pd.read_sql(query, conn, params=[division])
        conn.close()
        anos_bd = df['ANIO'].tolist() if not df.empty else []
        ano_actual = datetime.now().year
        anos_futuros = [ano_actual + 1, ano_actual, ano_actual - 1]
        todos_anos = list(set(anos_bd + anos_futuros))
        todos_anos.sort(reverse=True)
        anos_filtrados = [a for a in todos_anos if a >= 2025]
        if not anos_filtrados:
            anos_filtrados = [2027, 2026, 2025]
        anio_default = 2026
        return jsonify({'success': True, 'anos': anos_filtrados, 'anio_default': anio_default})
    except Exception as e:
        logger.error(f"Error en get_anos_ventas: {e}")
        return jsonify({'success': False, 'error': str(e), 'anos': [2027, 2026, 2025], 'anio_default': 2026}), 500

# ============================================================
# VENTAS MANUALES - CRUD
# ============================================================

@reportes_bp.route('/reportes/ventas_manuales', methods=['GET'])
def get_ventas_manuales():
    base = request.args.get('base')
    anio = request.args.get('anio')
    mes = request.args.get('mes')
    ventas = ventas_manuales_service.listar_ventas_manuales(base, anio, mes)
    # Convertir fechas y decimales a tipos serializables
    for v in ventas:
        if v.get('fecha_registro'):
            v['fecha_registro'] = v['fecha_registro'].isoformat() if hasattr(v['fecha_registro'], 'isoformat') else str(v['fecha_registro'])
        if v.get('fecha_creacion'):
            v['fecha_creacion'] = v['fecha_creacion'].isoformat() if hasattr(v['fecha_creacion'], 'isoformat') else str(v['fecha_creacion'])
        if v.get('importe_usd'):
            v['importe_usd'] = float(v['importe_usd'])
        if v.get('importe_ps'):
            v['importe_ps'] = float(v['importe_ps'])
    return jsonify({'success': True, 'data': ventas})

@reportes_bp.route('/reportes/ventas_manuales', methods=['POST'])
def crear_venta_manual():
    try:
        if session.get('rol') not in ['superadmin', 'admin']:
            return jsonify({'success': False, 'error': 'No tienes permiso'}), 403
        
        data = request.get_json()
        required = ['base', 'anio', 'mes', 'pais', 'fecha_registro']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'Falta campo: {field}'}), 400
        
        importe_usd = data.get('importe_usd', 0)
        importe_ps = data.get('importe_ps', 0)
        if (importe_usd is None or importe_usd <= 0) and (importe_ps is None or importe_ps <= 0):
            return jsonify({'success': False, 'error': 'Debe ingresar al menos un importe (USD o PS)'}), 400
        
        resultado = ventas_manuales_service.crear_venta_manual(
            base=data['base'],
            sociedad=data.get('sociedad'),
            anio=int(data['anio']),
            mes=int(data['mes']),
            pais=data['pais'],
            importe_usd=importe_usd,
            importe_ps=importe_ps,
            fecha_registro=data['fecha_registro'],
            comentario=data.get('comentario', ''),
            usuario=session.get('username', 'anonimo'),
            centro_costo=data.get('centro_costo')
        )
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Error creando venta manual: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@reportes_bp.route('/reportes/ventas_manuales/<int:venta_id>', methods=['DELETE'])
def eliminar_venta_manual(venta_id):
    if session.get('rol') not in ['superadmin', 'admin']:
        return jsonify({'success': False, 'error': 'No tienes permiso'}), 403
    resultado = ventas_manuales_service.eliminar_venta_manual(venta_id)
    return jsonify(resultado)

@reportes_bp.route('/reportes/ventas_manuales/importar', methods=['POST'])
def importar_ventas_manuales():
    try:
        if session.get('rol') not in ['superadmin', 'admin']:
            return jsonify({'success': False, 'error': 'No tienes permiso'}), 403
        
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'error': 'No se envió archivo'}), 400
        
        archivo = request.files['archivo']
        if archivo.filename == '':
            return jsonify({'success': False, 'error': 'Nombre vacío'}), 400

        # Leer archivo con pandas
        try:
            if archivo.filename.endswith('.csv'):
                df = pd.read_csv(archivo, encoding='utf-8-sig')
            else:
                df = pd.read_excel(archivo)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error al leer el archivo: {str(e)}'}), 400

        resultado = ventas_manuales_service.importar_ventas_manuales(df, usuario=session.get('username', 'anonimo'))
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Error importando ventas manuales: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500