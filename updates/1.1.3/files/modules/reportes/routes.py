# modules/reportes/routes.py
# ============================================================
# RUTAS DE REPORTES - SIDESYS ERP
# ============================================================
# Ahora solo delegan la lógica a los servicios.
# C4: cada endpoint exige permiso (reportes.ver/crear/eliminar/importar) y
# valida las bases pedidas (?base= / body / Excel) contra bases_permitidas.
# ============================================================

from flask import Blueprint, jsonify, request, session, send_file
import logging
import os
import re
import pandas as pd  # <--- AGREGAR
from datetime import datetime  # <--- AGREGAR
from .services import contratos_service, pendiente_cobro_service, consolidado_pais_service, consolidado_total_service, ventas_manuales_service
from modules.shared.decorators import (
    requiere_permiso,
    chequear_acceso_base,
    chequear_acceso_total_bases,
    chequear_acceso_alguna_base,
    bases_permitidas_actuales,
)
from modules.shared.permisos import PermisosSistema
from modules.shared import config_central
from modules.shared import correo_outlook

reportes_bp = Blueprint('reportes', __name__)
logger = logging.getLogger(__name__)

# ============================================================
# REPORTE: CONTRATOS PENDIENTE DE FACTURAR
# ============================================================

@reportes_bp.route('/reportes/contratos', methods=['POST'])
@requiere_permiso(PermisosSistema.REPORTES_VER)
def get_reporte_contratos():
    data = request.get_json() or {}
    base_override = data.get('base')
    if base_override:
        chk = chequear_acceso_base(base_override)
        if chk:
            return chk
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
@requiere_permiso(PermisosSistema.REPORTES_VER)
def get_anos_disponibles():
    # Esta función se mantiene igual, pero podemos moverla a utils si queremos
    # Por ahora la dejamos aquí porque es simple.
    try:
        from .services.utils import get_db_connection, get_db_connection_base
        base_param = request.args.get('base')
        sociedad_param = request.args.get('sociedad')
        if base_param:
            chk = chequear_acceso_base(base_param)
            if chk:
                return chk
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
@requiere_permiso(PermisosSistema.REPORTES_VER)
def get_pendiente_cobro():
    base_override = request.args.get('base')
    sociedad_override = request.args.get('sociedad')
    if base_override:
        chk = chequear_acceso_base(base_override)
        if chk:
            return chk
    resultado = pendiente_cobro_service.obtener_pendiente_cobro(base_override, sociedad_override)
    return jsonify(resultado)

# ============================================================
# REPORTE: CONSOLIDADO VENTAS POR PAÍS (sin manuales)
# ============================================================

@reportes_bp.route('/reportes/consolidado_ventas_pais', methods=['GET'])
@requiere_permiso(PermisosSistema.REPORTES_VER)
def get_consolidado_ventas_pais():
    anio = request.args.get('anio')
    if anio and anio.isdigit():
        anio = int(anio)
    else:
        from datetime import datetime
        anio = datetime.now().year

    base_override = request.args.get('base')
    sociedad_override = request.args.get('sociedad')
    if base_override:
        chk = chequear_acceso_base(base_override)
        if chk:
            return chk
    # Sin ?base= este reporte recorre varias bases: se le pasa la lista del
    # usuario para que consulte SOLO las autorizadas (fail-closed).
    resultado = consolidado_pais_service.obtener_consolidado_pais(
        anio, base_override, sociedad_override,
        bases_permitidas=bases_permitidas_actuales())
    return jsonify(resultado)

# ============================================================
# REPORTE: CONSOLIDADO VENTAS GLOBAL (con manuales y cotización)
# ============================================================

@reportes_bp.route('/reportes/consolidado_ventas_global', methods=['GET'])
@requiere_permiso(PermisosSistema.REPORTES_VER)
def get_consolidado_ventas_global():
    # C4 (revisado 14/09/2026): antes exigía superadmin o bases '*'. Ahora alcanza
    # con tener AL MENOS UNA base, porque el reporte ya respeta `bases_permitidas`
    # (sólo consulta las bases del usuario) y devuelve `bases_incluidas` para que
    # la UI rotule que es un consolidado parcial. Un gerente con 2 bases puede ver
    # el consolidado DE SUS BASES sin que el resto de los países se filtre.
    chk = chequear_acceso_alguna_base()
    if chk:
        return chk

    anio = request.args.get('anio')
    if anio and anio.isdigit():
        anio = int(anio)
    else:
        from datetime import datetime
        anio = datetime.now().year

    base_override = request.args.get('base')
    sociedad_override = request.args.get('sociedad')
    if base_override:
        chk = chequear_acceso_base(base_override)
        if chk:
            return chk
    resultado = consolidado_total_service.obtener_consolidado_total(
        anio, base_override, sociedad_override,
        bases_permitidas=bases_permitidas_actuales())
    return jsonify(resultado)

# ============================================================
# REPORTE: AÑOS DISPONIBLES PARA VENTAS (para el selector del consolidado)
# ============================================================

@reportes_bp.route('/reportes/anos_ventas', methods=['GET'])
@requiere_permiso(PermisosSistema.REPORTES_VER)
def get_anos_ventas():
    try:
        from .services.utils import get_db_connection, get_db_connection_base
        base_override = request.args.get('base')
        sociedad_override = request.args.get('sociedad')
        if base_override:
            chk = chequear_acceso_base(base_override)
            if chk:
                return chk
        
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
@requiere_permiso(PermisosSistema.REPORTES_VER)
def get_ventas_manuales():
    base = request.args.get('base')
    anio = request.args.get('anio')
    mes = request.args.get('mes')
    if base:
        chk = chequear_acceso_base(base)
        if chk:
            return chk
    ventas = ventas_manuales_service.listar_ventas_manuales(base, anio, mes)

    # Alcance por país (17/09/2026). Con la tabla canónica las ventas de TODOS los
    # países viven juntas, así que hay que acotar acá:
    #   · el que puede con todo (superadmin / rol administrador) las ve todas;
    #   · el resto, solo las de sus países habilitados (fail-closed).
    # Cada fila lleva `puede_borrar` porque la decisión de borrado se calcula en
    # el servidor: así el frontend no puede "abrir" un borrado que el backend
    # igual rechazaría.
    from modules.shared.usuarios import get_gestor_usuarios
    username = session.get('username')
    gestor = get_gestor_usuarios()
    alcance_total = False
    try:
        datos = gestor.datos_usuario_completo(username) or {}
        alcance_total = bool(datos.get('es_superadmin')) or ('administrador' in (datos.get('roles') or []))
    except Exception as e:
        logger.warning(f'No se pudo resolver el alcance de ventas manuales: {e}')
        alcance_total = False
    permitidos = None if alcance_total else gestor.paises_permitidos(username)
    if permitidos is not None:
        ventas = [v for v in ventas if (v.get('pais') or '') in permitidos]
    for v in ventas:
        v['puede_borrar'] = bool(alcance_total or gestor.puede_gestionar_ventas_de(username, v.get('pais')))

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
    return jsonify({'success': True, 'data': ventas, 'alcance_total': alcance_total})

@reportes_bp.route('/reportes/ventas_manuales', methods=['POST'])
@requiere_permiso(PermisosSistema.REPORTES_CREAR)
def crear_venta_manual():
    try:
        data = request.get_json()
        required = ['base', 'anio', 'mes', 'pais', 'fecha_registro']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'Falta campo: {field}'}), 400
        
        chk = chequear_acceso_base(data.get('base'))
        if chk:
            return chk

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
@requiere_permiso(PermisosSistema.REPORTES_ELIMINAR)
def eliminar_venta_manual(venta_id):
    """Borra una venta manual, validando el ALCANCE POR PAÍS.

    Regla (17/09/2026, pedido del usuario): el superadmin y el rol `administrador`
    pueden borrar las de cualquier país; el resto, solo las de sus países
    habilitados. Antes este endpoint borraba por id sin validar nada: alcanzaba
    con tener `reportes.eliminar` para borrar la venta de cualquier país — y con
    la tabla canónica eso quedaba más expuesto, porque las ventas de todos los
    países viven juntas.
    """
    from modules.shared.usuarios import get_gestor_usuarios

    # Para borrar, el chequeo previo se hace en modo ESCRITURA: si el usuario no
    # alcanza la base canónica, el error de permiso se propaga y se devuelve como
    # JSON legible en vez de convertirse en un 404 "La venta no existe" (que era
    # mentira: la venta existe, lo que falta es acceso).
    #
    # 200 + `success: false`, igual que los otros tres caminos del módulo (crear,
    # importar y el `jsonify(resultado)` del propio borrado): es un error de
    # NEGOCIO, y un 500 se lee como caída del servidor (dispara alertas y
    # monitoreo). (Ojo: el frontend del borrado hace `r.json()` sin mirar `r.ok`,
    # así que con 500 también vería el mensaje; el motivo es la consistencia.)
    try:
        venta = ventas_manuales_service.obtener_venta_manual(venta_id,
                                                            para_escritura=True)
    except Exception as e:
        logger.error(f'Error verificando la venta manual {venta_id} para borrar: {e}')
        return jsonify({'success': False, 'error': str(e)})

    if not venta:
        return jsonify({'success': False, 'error': 'La venta no existe'}), 404

    username = session.get('username')
    gestor = get_gestor_usuarios()
    if not gestor.puede_gestionar_ventas_de(username, venta.get('pais')):
        logger.warning(f'Borrado de venta manual denegado: {username} -> '
                       f'id={venta_id} pais={venta.get("pais")}')
        return jsonify({
            'success': False,
            'error': 'No podés borrar ventas de un país que no tenés habilitado.'
        }), 403

    resultado = ventas_manuales_service.eliminar_venta_manual(venta_id)
    if resultado.get('success'):
        logger.info(f'Venta manual {venta_id} eliminada por {username} '
                    f'(pais={venta.get("pais")})')
    return jsonify(resultado)

@reportes_bp.route('/reportes/ventas_manuales/importar', methods=['POST'])
@requiere_permiso(PermisosSistema.REPORTES_IMPORTAR)
def importar_ventas_manuales():
    try:
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

        # C4: validar que las bases indicadas en el Excel estén autorizadas.
        if 'base' in df.columns:
            bases_archivo = [str(b).strip() for b in df['base'].dropna().unique()]
            for b in bases_archivo:
                chk = chequear_acceso_base(b)
                if chk:
                    return chk

        resultado = ventas_manuales_service.importar_ventas_manuales(df, usuario=session.get('username', 'anonimo'))
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Error importando ventas manuales: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# EXPORTAR A .XLSX (reemplaza las descargas CSV del cliente)
# ============================================================
# Generico: el cliente envia {archivo, hoja, columnas, filas} y el servidor
# devuelve un .xlsx real (openpyxl). Toda exportacion de reportes pasa aca.
#
# Parametros OPCIONALES de presentacion (brief 23/09/2026, "Ventas Globales igual
# a la pantalla"). Si el cliente no los manda, NADA de esto se aplica y el
# archivo sale igual que antes:
#   formatos           lista alineada con `columnas`: numero de formato de Excel
#                      por columna ('' o null = celda como hoy).
#   anchos             lista de anchos de columna en caracteres; los indices con
#                      valor valido pisan el ancho automatico (el resto queda igual).
#   filas_negrita      indices 0-based de las filas de DATOS que van en negrita.
#   congelar_encabezado bool: true congela en la fila siguiente al encabezado,
#                      false lo suelta (si no viene, queda como hoy: congelado).
#   rellenos           lista de {'fila', 'columna', 'color'} (0-based, fila de
#                      datos y columna) con el color de fondo de esa celda.
#   sin_cuadricula     bool: true APAGA las lineas de cuadricula de la hoja
#                      (`ws.sheet_view.showGridLines = False`). Ausente (o
#                      cualquier otro valor) = como hoy, con cuadricula.
#   agrupaciones       lista de {'desde', 'hasta', 'colapsado'} con indices
#                      0-BASED de filas de DATOS (mismo criterio que
#                      `filas_negrita` y `rellenos`: la fila de encabezado es la
#                      1, asi que la fila de Excel es `indice + 2`). Aplica el
#                      agrupamiento NATIVO de Excel
#                      (`ws.row_dimensions.group(...)`, `outline_level=1`) y, si
#                      `colapsado` es verdadero, deja las filas OCULTAS. Ademas
#                      pone `ws.sheet_properties.outlinePr.summaryBelow = False`
#                      para que el `+/-` del grupo quede en la fila de ARRIBA (la
#                      del pais) y no abajo. Lo usa Ventas Globales para las
#                      filas de sociedad de Argentina (brief 24/09/2026). Un
#                      grupo invalido (`desde`/`hasta` no enteros, fuera de
#                      rango, `desde > hasta`) se IGNORA; ausente = como hoy, sin
#                      ningun grupo. Tope: 200 grupos por pedido.
#   agrupaciones_columnas
#                      lista de {'desde', 'hasta', 'colapsado'} con indices
#                      0-BASED de COLUMNAS de datos (mismo criterio que
#                      `rellenos`: la letra de Excel es `get_column_letter(indice
#                      + 1)`, o sea que el indice 0 es la columna A). Es el
#                      hermano de `agrupaciones` pero en las COLUMNAS: aplica
#                      `ws.column_dimensions.group(...)` con `outline_level=1` y,
#                      si `colapsado` es verdadero, deja las columnas OCULTAS.
#                      Ademas pone `ws.sheet_properties.outlinePr.summaryRight =
#                      False` (UNA sola vez, y solo si hay algun grupo valido)
#                      para que el `+/-` del grupo quede en la columna de la
#                      IZQUIERDA (el rotulo del anio). Lo usa Pendiente de
#                      Facturar para los meses de cada anio (brief 24/09/2026). Un
#                      grupo invalido (`desde`/`hasta` no enteros, fuera de
#                      rango, `desde > hasta`) se IGNORA; ausente = como hoy: sin
#                      ningun grupo y sin MODIFICAR `outlinePr` (este codigo no lo
#                      toca). OJO: openpyxl lo escribe SIEMPRE, con los defaults de
#                      Excel (`<outlinePr summaryBelow="1" summaryRight="1"/>`),
#                      que ya estaban antes de este cambio; por eso el XML del
#                      libro sale byte a byte igual al de antes (medido, ver
#                      `report.md`). Tope: 200 grupos.

def _exportar_lista_opcional(data, nombre):
    """Lista del body o [] si no vino / no es lista (valor invalido = ignorar)."""
    valor = data.get(nombre)
    if not isinstance(valor, list):
        return []
    return valor


def _exportar_entero(valor):
    """Int del valor o None si no es un entero valido (no revienta)."""
    try:
        if isinstance(valor, bool):
            return None
        return int(valor)
    except (TypeError, ValueError):
        return None


def _exportar_formato(valor, indice, total_columnas):
    """Formato de Excel de una columna, o None si no corresponde aplicarlo."""
    if indice >= total_columnas or indice >= len(valor):
        return None
    formato = valor[indice]
    if not isinstance(formato, str) or not formato.strip():
        return None
    return formato[:60]


def _exportar_ancho(valor):
    """Ancho de columna en caracteres, o None si el valor no sirve.

    None (el `null` del body) o un valor no numerico o fuera de rango NO pisan el
    ancho automatico: la celda/columna queda "como hoy".
    """
    try:
        ancho = float(valor)
    except (TypeError, ValueError):
        return None
    if ancho != ancho:  # NaN
        return None
    if ancho <= 0 or ancho > 100:
        return None
    return ancho


def _exportar_color(valor):
    """Color ARGB/RGB de un relleno, o None si no es un string usable."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    return valor.strip().lstrip('#')[:8].upper()


def _exportar_archivo_y_hoja(data):
    """Nombre del archivo y de la hoja saneados (lo comparten descarga y envio)."""
    import re as _re
    archivo = _re.sub(r'[\\/:*?"<>|]', '_', str(data.get('archivo') or 'exportacion.xlsx'))[:80]
    if not archivo.lower().endswith('.xlsx'):
        archivo += '.xlsx'
    hoja = _re.sub(r'[\[\]:*?/\\]', '', str(data.get('hoja') or 'Hoja1'))[:31] or 'Hoja1'
    return archivo, hoja


def construir_xlsx(data):
    """El .xlsx del pedido, como bytes. UNA SOLA funcion arma el libro.

    La usan la DESCARGA (`exportar_xlsx`) y el ENVIO por correo
    (`enviar_xlsx`): el adjunto del correo tiene que ser identico al archivo que
    el usuario baja (brief 23/09/2026). Si el armado se duplicara, los dos
    archivos se separarian con el primer cambio.

    Devuelve `(bytes_del_xlsx, archivo, hoja)` o `(None, mensaje_de_error, None)`
    si el payload no sirve.
    """
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    archivo, hoja = _exportar_archivo_y_hoja(data)

    columnas = data.get('columnas') or []
    if not isinstance(columnas, list):
        columnas = []
    columnas = [str(c)[:60] for c in columnas][:60]

    filas = data.get('filas') or []
    if not isinstance(filas, list) or len(filas) > 200000:
        return None, 'Filas invalidas o demasiadas', None

    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    if columnas:
        ws.append(columnas)
        for cell in ws[1]:
            cell.font = Font(bold=True)
    for fila in filas:
        if not isinstance(fila, (list, tuple)):
            continue
        limpia = []
        for valor in list(fila)[:60]:
            if valor is None or isinstance(valor, (int, float, bool, str)):
                limpia.append(valor)
            else:
                limpia.append(str(valor)[:1000])
        ws.append(limpia)

    # Ancho aproximado de columnas (primeras 200 filas)
    for i, col in enumerate(ws.columns, 1):
        maxlen = 8
        for cell in list(col)[:200]:
            v = cell.value
            if v is not None:
                maxlen = max(maxlen, min(len(str(v)), 60))
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = maxlen + 2

    # ---- Presentacion opcional (si no viene, todo queda como hoy) --------
    formatos = _exportar_lista_opcional(data, 'formatos')
    anchos = _exportar_lista_opcional(data, 'anchos')
    if formatos or anchos:
        for indice, fila in enumerate(filas):
            if not isinstance(fila, (list, tuple)):
                continue
            for columna in range(min(len(fila), len(columnas))):
                formato = _exportar_formato(formatos, columna, len(columnas))
                if formato:
                    letra = get_column_letter(columna + 1)
                    ws[f'{letra}{indice + 2}'].number_format = formato
    for indice, valor in enumerate(anchos):
        if indice >= len(columnas):
            continue
        ancho = _exportar_ancho(valor)
        if ancho is not None:
            letra = get_column_letter(indice + 1)
            ws.column_dimensions[letra].width = ancho

    for bruto in _exportar_lista_opcional(data, 'filas_negrita'):
        indice = _exportar_entero(bruto)
        if indice is None or indice < 0 or indice >= len(filas):
            continue
        for columna in range(1, len(columnas) + 1):
            ws.cell(row=indice + 2, column=columna).font = Font(bold=True)

    for relleno in _exportar_lista_opcional(data, 'rellenos'):
        if not isinstance(relleno, dict):
            continue
        indice = _exportar_entero(relleno.get('fila'))
        columna = _exportar_entero(relleno.get('columna'))
        color = _exportar_color(relleno.get('color'))
        if indice is None or columna is None or color is None:
            continue
        if indice < 0 or indice >= len(filas) or columna < 0 or columna >= len(columnas):
            continue
        ws.cell(row=indice + 2, column=columna + 1).fill = PatternFill(
            fill_type='solid', start_color=color, end_color=color)

    # `congelar_encabezado` AUSENTE -> como hoy (congelado en A2). Presente
    # en false -> el cliente pide explicitamente NO congelar.
    if data.get('congelar_encabezado') is False:
        ws.freeze_panes = None
    else:
        ws.freeze_panes = 'A2'

    # `sin_cuadricula` AUSENTE -> como hoy (la hoja mantiene la cuadricula: el
    # XML sale SIN el atributo, que es el default visible de Excel). Presente en
    # `true` -> `showGridLines="0"` (Ventas Globales). Cualquier otro valor se
    # ignora: el campo es opcional y los demas reportes no lo mandan.
    if data.get('sin_cuadricula') is True:
        ws.sheet_view.showGridLines = False

    # `agrupaciones` (brief 24/09/2026): agrupamiento NATIVO de Excel. Los indices
    # son 0-based de filas de DATOS -> fila de Excel = indice + 2. Ausente o
    # invalido = como hoy (sin ningun grupo): ningun otro informe cambia. OJO con
    # `outlinePr`: openpyxl lo escribe SIEMPRE, con los defaults de Excel
    # (`summaryBelow="1" summaryRight="1"`), asi que con el campo ausente el XML
    # del libro sale BYTE A BYTE igual al de antes del cambio, pero el bloque
    # esta (medido: auxiliar 322 de la entrega
    # `2026-09-24-pendiente-facturar-columnas-por-anio`; el comentario anterior
    # afirmaba "sin outlinePr" y era inexacto). `summaryBelow = False` solo se
    # escribe si hay algun grupo valido.
    for grupo in _exportar_lista_opcional(data, 'agrupaciones')[:200]:
        if not isinstance(grupo, dict):
            continue
        desde = _exportar_entero(grupo.get('desde'))
        hasta = _exportar_entero(grupo.get('hasta'))
        if desde is None or hasta is None:
            continue
        if desde < 0 or desde > hasta or hasta >= len(filas):
            continue
        # El `+/-` del grupo queda en la fila de ARRIBA (la del pais, que es el
        # padre), no abajo.
        ws.sheet_properties.outlinePr.summaryBelow = False
        ws.row_dimensions.group(desde + 2, hasta + 2, outline_level=1,
                                hidden=bool(grupo.get('colapsado')))

    # `agrupaciones_columnas` (brief 24/09/2026): el mismo agrupamiento NATIVO de
    # Excel pero en las COLUMNAS. Los indices son 0-based de COLUMNAS de datos
    # (mismo criterio que `rellenos`: la letra de Excel es `indice + 1`). Ausente
    # o invalido = como hoy: sin ningun grupo y sin MODIFICAR `outlinePr` (este
    # codigo no lo toca; openpyxl lo escribe SIEMPRE con los defaults de Excel,
    # `summaryBelow="1" summaryRight="1"`, tambien cuando el campo no viene, asi
    # que el XML sale byte a byte igual al de antes del cambio): ningun otro
    # informe cambia. `summaryRight = False` se escribe UNA sola vez y solo si hay
    # algun grupo valido: deja el `+/-` en la columna de la IZQUIERDA del grupo
    # (en Pendiente de Facturar, la del rotulo del anio).
    grupos_columnas = []
    for grupo in _exportar_lista_opcional(data, 'agrupaciones_columnas')[:200]:
        if not isinstance(grupo, dict):
            continue
        desde = _exportar_entero(grupo.get('desde'))
        hasta = _exportar_entero(grupo.get('hasta'))
        if desde is None or hasta is None:
            continue
        if desde < 0 or desde > hasta or hasta >= len(columnas):
            continue
        grupos_columnas.append((desde, hasta, bool(grupo.get('colapsado'))))
    if grupos_columnas:
        ws.sheet_properties.outlinePr.summaryRight = False
        for desde, hasta, colapsado in grupos_columnas:
            ws.column_dimensions.group(get_column_letter(desde + 1),
                                       get_column_letter(hasta + 1),
                                       outline_level=1, hidden=colapsado)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue(), archivo, hoja


@reportes_bp.route('/reportes/exportar_xlsx', methods=['POST'])
@requiere_permiso(PermisosSistema.REPORTES_VER)
def exportar_xlsx():
    try:
        from io import BytesIO

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'success': False, 'error': 'Cuerpo requerido'}), 400

        contenido, archivo, _hoja = construir_xlsx(data)
        if contenido is None:
            return jsonify({'success': False, 'error': archivo}), 400

        return send_file(
            BytesIO(contenido),
            as_attachment=True,
            download_name=archivo,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error exportando xlsx: {e}")
        return jsonify({'success': False, 'error': 'Error generando el archivo'}), 500


# ============================================================
# ENVIAR EL .XLSX POR CORREO (envio directo con el Outlook del usuario)
# ============================================================
# Brief 23/09/2026 ("Enviar el informe por correo desde Outlook") y brief
# 24/09/2026 ("Argentina por sociedad, nombre del archivo y envio directo"),
# que revierte la decision anterior: el correo ya NO queda como borrador abierto,
# se ENVIA (`Send()`, ver `modules/shared/correo_outlook.py`).
#
# El cuerpo es el MISMO de `exportar_xlsx` mas `para`/`asunto`/`cuerpo`: el
# adjunto sale de `construir_xlsx`, asi que es identico al de la descarga.

# Carpeta del adjunto: Outlook referencia el archivo por ruta mientras lo manda,
# asi que no se borra al terminar el request (se van conservando los ultimos N;
# ver `_podar_correos`).
CARPETA_CORREOS = os.path.join(os.environ.get('PROGRAMDATA', r'C:\ProgramData'),
                               'SidesysERP', 'correos')
MAX_CORREOS = 20

# Una direccion con forma valida: algo@algo.algo, sin espacios ni separadores.
PATRON_CORREO = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9]([A-Za-z0-9\-]*[A-Za-z0-9])?'
                           r'(\.[A-Za-z0-9]([A-Za-z0-9\-]*[A-Za-z0-9])?)+$')

# `config_central.auditar` es el mecanismo de auditoria del proyecto (una linea
# JSON en el almacen central, con respaldo en data/). Se deja en una constante
# para que las pruebas puedan doblarlo.
AUDITORIA = config_central.auditar

# La funcion que ENVIA el informe. Tambien en constante para poder doblarla:
# NINGUNA prueba abre Outlook ni manda un correo real.
ENVIAR_CORREO = correo_outlook.enviar_informe


def destinatarios_validos(para):
    """`(validos, invalidos)` del campo `para`.

    Separadores: `;` y `,` (los dos, como pide el brief). Una direccion sin
    forma valida se descarta y se informa: el endpoint responde 400 si no quedo
    NINGUNA valida.
    """
    validos = []
    invalidos = []
    texto = '' if para is None else str(para)
    for bruto in re.split(r'[;,]', texto):
        direccion = bruto.strip()
        if not direccion:
            continue
        if PATRON_CORREO.match(direccion):
            validos.append(direccion)
        else:
            invalidos.append(direccion)
    return validos, invalidos


def _podar_correos(carpeta, maximo=MAX_CORREOS):
    """Borra los adjuntos mas viejos de `carpeta`. Devuelve cuantos borro.

    Solo mira los `.xlsx` (los adjuntos que escribe este endpoint): un archivo
    ajeno en la carpeta no se toca. Nunca levanta por el disco: la retencion no
    puede tumbar el envio.
    """
    try:
        nombres = [n for n in os.listdir(carpeta) if n.lower().endswith('.xlsx')]
    except OSError:
        return 0
    rutas = []
    for nombre in nombres:
        completa = os.path.join(carpeta, nombre)
        try:
            rutas.append((os.path.getmtime(completa), completa))
        except OSError:
            continue
    borrados = 0
    for _fecha, completa in sorted(rutas, reverse=True)[maximo:]:
        try:
            os.remove(completa)
            borrados += 1
        except OSError as e:
            logger.warning(f"No se pudo borrar el adjunto viejo {completa}: {e}")
    return borrados


@reportes_bp.route('/reportes/enviar_xlsx', methods=['POST'])
@requiere_permiso(PermisosSistema.REPORTES_VER)
def enviar_xlsx():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'detalle': 'Cuerpo requerido'}), 400

    # 1) Destinatarios: se valida ANTES de armar el Excel (no se gasta trabajo en
    #    un pedido que no puede salir).
    validos, invalidos = destinatarios_validos(data.get('para'))
    if not validos:
        detalle = ('Indicá al menos un destinatario con dirección válida '
                   '(varios separados por ";" o ",").')
        if invalidos:
            detalle += ' No se reconocieron: ' + ', '.join(invalidos[:5])
        return jsonify({'success': False, 'detalle': detalle}), 400

    asunto = str(data.get('asunto') or '').replace('\r', ' ').replace('\n', ' ').strip()
    # Los saltos de linea se planan y el espacio sobrante se colapsa: el asunto
    # de un correo es de UNA linea (nunca un encabezado inyectado).
    asunto = ' '.join(asunto.split())
    if len(asunto) > 300:
        return jsonify({'success': False, 'detalle':
                        'El asunto es demasiado largo (máximo 300 caracteres).'}), 400
    cuerpo = str(data.get('cuerpo') or '')

    # 2) El adjunto: EXACTAMENTE el mismo armado que la descarga.
    try:
        contenido, archivo, _hoja = construir_xlsx(data)
    except Exception as e:
        logger.error(f"Error armando el xlsx para enviar: {e}")
        return jsonify({'success': False, 'detalle': 'Error generando el archivo'}), 500
    if contenido is None:
        return jsonify({'success': False, 'detalle': archivo}), 400

    # 3) El archivo en disco: el borrador de Outlook lo referencia por ruta.
    try:
        os.makedirs(CARPETA_CORREOS, exist_ok=True)
        nombre = f'{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}_{os.path.basename(archivo)}'
        ruta_adjunto = os.path.join(CARPETA_CORREOS, nombre)
        with open(ruta_adjunto, 'wb') as f:
            f.write(contenido)
    except Exception as e:
        logger.error(f"No se pudo guardar el adjunto del correo: {e}")
        return jsonify({'success': False, 'detalle':
                        'No se pudo guardar el archivo del informe para adjuntar.'}), 500
    _podar_correos(CARPETA_CORREOS)

    # 4) El envio por Outlook. `enviar_informe` no propaga excepciones.
    ok, detalle = ENVIAR_CORREO(ruta_adjunto, '; '.join(validos),
                                asunto or os.path.basename(archivo), cuerpo)

    # 5) Auditoria: quien, a quienes y que informe. `auditar` nunca lanza; el try
    #    es por si el mecanismo no estuviera disponible (nunca una excepcion
    #    despues de haber mandado el correo).
    try:
        AUDITORIA({'evento': 'reportes.enviar_xlsx',
                   'usuario': session.get('username') or 'desconocido',
                   'para': validos,
                   'informe': os.path.basename(archivo),
                   'asunto': asunto,
                   'filas': len(data.get('filas') or []),
                   'adjunto': ruta_adjunto,
                   'resultado': 'enviado' if ok else 'fallido',
                   'detalle': detalle})
    except Exception as e:
        logger.error(f"No se pudo auditar el envio del informe: {e}")

    return jsonify({'success': bool(ok), 'detalle': detalle})
