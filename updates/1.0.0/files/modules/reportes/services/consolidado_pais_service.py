# modules/reportes/services/consolidado_pais_service.py
# ============================================================
# SERVICIO: CONSOLIDADO VENTAS POR PAÍS
# Ventas = líneas de las cuentas 410101/410102 (definición en ventas_cuentas.py):
# sin filtro de subdiario y excluyendo intercompany (tipo de cliente 5 O nombre
# SIDESYS), en lugar de "sólo subdiario VTA con líneas analíticas".
# Conversión a USD: MISMA regla que Ventas Globales (ventas_cuentas.a_usd).
# ============================================================

import pandas as pd
import logging
from .utils import get_db_connection, get_db_connection_base, limpiar_datos, obtener_cotizacion_por_mes
from .ventas_cuentas import (
    cuentas_sql,
    join_ventas,
    filtro_intercompany,
    param_intercompany,
    apply_cliente,
    apply_analitica,
    rango_fechas,
    a_usd,
)
from config import BASES_DISPONIBLES

logger = logging.getLogger(__name__)

# Nombre de país que se muestra en el informe, por base.
NOMBRE_PAIS = {
    'plataforma': 'Argentina',
    'plataforma_rd': 'República Dominicana',
    'plataforma_uy': 'Uruguay',
    'plataforma_ur': 'Uruguay',
    'plataforma_hn': 'Honduras',
    'plataforma_gt': 'Guatemala',
    'plataforma_co': 'Colombia',
    'plataforma_pe': 'Perú',
    'plataforma_py': 'Paraguay',
    'plataforma_ec': 'Ecuador',
    'plataforma_mx': 'México',
    'plataforma_cr': 'Costa Rica',
}


def _num(valor):
    """float seguro: None / NaN / basura -> 0.0"""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if numero != numero else numero  # NaN != NaN


def importe_dl_detalle(df, anio, db_name):
    """Convierte cada línea del detalle a USD con la MISMA regla que
    Ventas Globales (ventas_cuentas.a_usd).

    Se usa la cotización del mes de la línea; dividir línea por línea da el mismo
    total que dividir el acumulado del mes, así el detalle y el total del informe
    coinciden con Ventas Globales para el mismo país y año.
    """
    es_ecuador = db_name == 'plataforma_ec'
    if df.empty:
        return []

    meses = sorted({int(m) for m in df['MES'].dropna().unique()})
    cotizaciones = {}
    for mes in meses:
        cotizaciones[mes] = None if es_ecuador else obtener_cotizacion_por_mes(
            anio, mes, base_referencia=db_name)

    resultado = []
    for local, conversion, signo, mes in zip(df['IMPORTE_LOCAL'], df['IMPORTE_CONVERSION'],
                                             df['SIGNO'], df['MES']):
        factor = -1.0 if str(signo).strip().upper() == 'D' else 1.0
        local_firmado = _num(local) * factor
        conversion_firmada = _num(conversion) * factor
        cotizacion = cotizaciones.get(int(mes)) if pd.notna(mes) else None
        resultado.append(a_usd(local_firmado, conversion_firmada, cotizacion,
                               es_ecuador=es_ecuador))
    return resultado


def obtener_consolidado_pais(anio, base_override=None, sociedad_override=None):
    try:
        if base_override:
            bases_a_consultar = {base_override: BASES_DISPONIBLES.get(base_override, {})}
        else:
            bases_a_consultar = BASES_DISPONIBLES

        all_dfs = []

        for db_name, db_info in bases_a_consultar.items():
            try:
                # Argentina tiene las divisiones 1 y 2 en la misma base
                if db_name == 'plataforma':
                    conn, _ = get_db_connection_base('plataforma')
                    division_cond = "c.CASI_DIVISION IN (1, 2)"
                    params_division = []
                else:
                    conn, division = get_db_connection_base(db_name)
                    division_cond = "c.CASI_DIVISION = ?"
                    params_division = [division]

                nombre_pais = NOMBRE_PAIS.get(db_name) or db_info.get('label', db_name)
                desde, hasta = rango_fechas(anio)

                query = f"""
                SELECT
                    c.CASI_DIVISION AS DIVISION,
                    r.RASI_IMP_LOC AS IMPORTE_LOCAL,
                    r.RASI_IMP_CON AS IMPORTE_CONVERSION,
                    r.RASI_SIGNO AS SIGNO,
                    c.CASI_FECHA AS FECHA,
                    an.CC_CLIENTE AS CC_CLIENTE,
                    an.CENTRO_COSTO AS CENTRO_COSTO,
                    c.CASI_SUBDIARIO AS SUBDIARIO,
                    cli.CLIE_NOMBRE AS CLIE_NOMBRE,
                    YEAR(c.CASI_FECHA) AS AÑO,
                    MONTH(c.CASI_FECHA) AS MES
                {join_ventas()}
                {apply_cliente()}
                {apply_analitica()}
                WHERE {division_cond}
                  AND r.RASI_CUENTA IN ({cuentas_sql()})
                  AND c.CASI_FECHA >= ? AND c.CASI_FECHA < ?
                  {filtro_intercompany()}
                ORDER BY c.CASI_FECHA DESC
                """
                params = params_division + [desde, hasta] + param_intercompany()

                df = pd.read_sql(query, conn, params=params)
                conn.close()
                if not df.empty:
                    df['PAIS'] = nombre_pais
                    # IMPORTE_DL se calcula con la MISMA regla que Ventas Globales
                    df['IMPORTE_DL'] = importe_dl_detalle(df, anio, db_name)
                    all_dfs.append(df)
            except Exception as e:
                logger.warning(f"No se pudo consultar la base {db_name}: {e}")
                continue

        if not all_dfs:
            return {
                'success': True,
                'data': [],
                'resumen_cliente': [],
                'resumen_centro': [],
                'resumen_subdiario': [],
                'totales': {
                    'total_local': 0,
                    'total_usd': 0,
                    'total_dl': 0,
                    'total_registros': 0,
                    'anio': anio
                }
            }

        df_final = pd.concat(all_dfs, ignore_index=True)
        df_final = limpiar_datos(df_final)
        df_final['CC_CLIENTE'] = df_final['CC_CLIENTE'].fillna('SIN CLIENTE')
        df_final['CENTRO_COSTO'] = df_final['CENTRO_COSTO'].fillna('SIN CENTRO')
        df_final['CLIE_NOMBRE'] = df_final['CLIE_NOMBRE'].fillna('SIN NOMBRE')
        df_final['SUBDIARIO'] = df_final['SUBDIARIO'].fillna('SIN SUBDIARIO')

        resumen_cliente = df_final.groupby('CLIE_NOMBRE').agg({
            'IMPORTE_LOCAL': 'sum',
            'IMPORTE_CONVERSION': 'sum',
            'IMPORTE_DL': 'sum',
            'DIVISION': 'count'
        }).reset_index()
        resumen_cliente.columns = ['Cliente', 'Total_Local', 'Total_USD', 'Total_DL', 'Transacciones']
        resumen_cliente = resumen_cliente.sort_values('Total_DL', ascending=False)

        resumen_centro = df_final.groupby('CENTRO_COSTO').agg({
            'IMPORTE_LOCAL': 'sum',
            'IMPORTE_CONVERSION': 'sum',
            'IMPORTE_DL': 'sum',
            'DIVISION': 'count'
        }).reset_index()
        resumen_centro.columns = ['Centro_Costo', 'Total_Local', 'Total_USD', 'Total_DL', 'Transacciones']
        resumen_centro = resumen_centro.sort_values('Total_DL', ascending=False)

        resumen_subdiario = df_final.groupby('SUBDIARIO').agg({
            'IMPORTE_LOCAL': 'sum',
            'IMPORTE_CONVERSION': 'sum',
            'IMPORTE_DL': 'sum',
            'DIVISION': 'count'
        }).reset_index()
        resumen_subdiario.columns = ['Subdiario', 'Total_Local', 'Total_USD', 'Total_DL', 'Transacciones']
        resumen_subdiario = resumen_subdiario.sort_values('Total_DL', ascending=False)

        detalle = []
        for _, row in df_final.iterrows():
            fecha_val = row.get('FECHA')
            if pd.isna(fecha_val) or fecha_val is None:
                fecha_str = ''
            elif hasattr(fecha_val, 'strftime'):
                fecha_str = fecha_val.strftime('%Y-%m-%d')
            else:
                fecha_str = str(fecha_val)

            detalle.append({
                'Division': int(row.get('DIVISION', 0)) if pd.notna(row.get('DIVISION', 0)) else 0,
                'Pais': str(row.get('PAIS', 'República Dominicana')),
                'Cliente': str(row.get('CC_CLIENTE', 'SIN CLIENTE')),
                'NombreCliente': str(row.get('CLIE_NOMBRE', 'SIN NOMBRE')),
                'CentroCosto': str(row.get('CENTRO_COSTO', 'SIN CENTRO')),
                'Fecha': fecha_str,
                'Anio': int(row.get('AÑO', 0)) if pd.notna(row.get('AÑO', 0)) else 0,
                'Mes': int(row.get('MES', 0)) if pd.notna(row.get('MES', 0)) else 0,
                'Signo': str(row.get('SIGNO', '')),
                'Subdiario': str(row.get('SUBDIARIO', 'SIN SUBDIARIO')),
                'Importe_Local': float(row.get('IMPORTE_LOCAL', 0)) if pd.notna(row.get('IMPORTE_LOCAL', 0)) else 0,
                'Importe_Conversion': float(row.get('IMPORTE_CONVERSION', 0)) if pd.notna(row.get('IMPORTE_CONVERSION', 0)) else 0,
                'Importe_DL': float(row.get('IMPORTE_DL', 0)) if pd.notna(row.get('IMPORTE_DL', 0)) else 0
            })

        total_local = float(df_final['IMPORTE_LOCAL'].sum()) if not df_final.empty else 0
        total_usd = float(df_final['IMPORTE_CONVERSION'].sum()) if not df_final.empty else 0
        total_dl = float(df_final['IMPORTE_DL'].sum()) if not df_final.empty else 0

        return {
            'success': True,
            'data': detalle,
            'resumen_cliente': resumen_cliente.to_dict(orient='records'),
            'resumen_centro': resumen_centro.to_dict(orient='records'),
            'resumen_subdiario': resumen_subdiario.to_dict(orient='records'),
            'totales': {
                'total_local': total_local,
                'total_usd': total_usd,
                'total_dl': total_dl,
                'total_registros': len(df_final),
                'anio': anio
            }
        }

    except Exception as e:
        logger.error(f"Error en consolidado_pais_service: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'data': [],
            'resumen_cliente': [],
            'resumen_centro': [],
            'resumen_subdiario': [],
            'totales': {
                'total_local': 0,
                'total_usd': 0,
                'total_dl': 0,
                'total_registros': 0,
                'anio': anio
            }
        }
