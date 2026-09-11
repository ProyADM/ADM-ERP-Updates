# modules/reportes/services/consolidado_total_service.py
# ============================================================
# SERVICIO: CONSOLIDADO TOTAL DE VENTAS (GLOBAL)
# Ventas = líneas de las cuentas 410101/410102 (definición en ventas_cuentas.py)
# Importe_Local = RASI_IMP_LOC, Importe_Conversion = RASI_IMP_CON
# ============================================================

import pandas as pd
import logging
from .utils import get_db_connection, get_db_connection_base, limpiar_datos, obtener_cotizacion_por_mes, asegurar_tabla_ventas_manuales
from .ventas_cuentas import (
    cuentas_sql,
    join_ventas,
    filtro_intercompany,
    param_intercompany,
    importe_con_signo,
    rango_fechas,
    a_usd,
)
from config import BASES_DISPONIBLES

logger = logging.getLogger(__name__)

def obtener_ventas_manuales_global(anio):
    """Obtiene todas las ventas manuales de todas las bases, acumuladas por país"""
    try:
        asegurar_tabla_ventas_manuales()
        conn, _ = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT 
                pais,
                anio,
                mes,
                SUM(importe_usd) AS total_manual
            FROM VENTAS_MANUALES
            WHERE anio = ?
            GROUP BY pais, anio, mes
        """
        cursor.execute(query, [anio])
        rows = cursor.fetchall()
        conn.close()
        resultado = {}
        for row in rows:
            key = f"{row[0]}|{row[1]}|{row[2]}"
            resultado[key] = float(row[3]) if row[3] is not None else 0
        return resultado
    except Exception as e:
        logger.debug(f"Error obteniendo ventas manuales globales: {e}")
        return {}

def obtener_consolidado_total(anio, base_override=None, sociedad_override=None):
    try:
        asegurar_tabla_ventas_manuales()
        manuales_por_pais = obtener_ventas_manuales_global(anio)
        logger.info(f"📦 Ventas manuales globales para {anio}: {len(manuales_por_pais)} entradas")

        sigla_a_pais = {
            'AR': 'Argentina', 'UY': 'Uruguay', 'RD': 'República Dominicana',
            'HN': 'Honduras', 'GT': 'Guatemala', 'CO': 'Colombia',
            'PE': 'Perú', 'PY': 'Paraguay', 'EC': 'Ecuador',
            'MX': 'México', 'CR': 'Costa Rica'
        }
        pais_a_sigla = {v: k for k, v in sigla_a_pais.items()}

        data_global = []

        for db_name, db_info in BASES_DISPONIBLES.items():
            try:
                normalizar = {
                    'plataforma_rd': 'República Dominicana',
                    'plataforma_ar': 'Argentina',
                    'plataforma_mx': 'México',
                    'plataforma_gt': 'Guatemala',
                    'plataforma_hn': 'Honduras',
                    'plataforma_cr': 'Costa Rica',
                    'plataforma_pe': 'Perú',
                    'plataforma_py': 'Paraguay',
                    'plataforma_co': 'Colombia',
                    'plataforma_uy': 'Uruguay',
                    'plataforma_ec': 'Ecuador'
                }
                nombre_pais = normalizar.get(db_name, db_info.get('label', db_name))
                sigla = pais_a_sigla.get(nombre_pais, db_info.get('sigla', db_name))

                # Obtener conexión y división
                if db_name == 'plataforma':
                    conn, division = get_db_connection_base('plataforma')
                    # Argentina tiene divisiones 1 y 2
                    division_filter = "c.CASI_DIVISION IN (1, 2)"
                else:
                    conn, division = get_db_connection_base(db_name)
                    division_filter = "c.CASI_DIVISION = ?"

                # 🔴 DEFINICIÓN ÚNICA DE VENTAS (ver services/ventas_cuentas.py):
                # líneas de las cuentas 410101/410102, sin filtrar por subdiario,
                # excluyendo intercompany (tipo de cliente 5 O nombre SIDESYS).
                # Transacciones = cantidad de ASIENTOS (comprobantes), no de líneas.
                desde, hasta = rango_fechas(anio)
                query = f"""
                SELECT
                    YEAR(c.CASI_FECHA) AS Anio,
                    MONTH(c.CASI_FECHA) AS Mes,
                    COUNT(DISTINCT c.CASI_ASIENTO) AS Transacciones,
                    SUM({importe_con_signo('RASI_IMP_LOC')}) AS Importe_Local,
                    SUM({importe_con_signo('RASI_IMP_CON')}) AS Importe_Conversion
                {join_ventas()}
                WHERE {division_filter}
                  AND r.RASI_CUENTA IN ({cuentas_sql()})
                  AND c.CASI_FECHA >= ? AND c.CASI_FECHA < ?
                  {filtro_intercompany()}
                GROUP BY YEAR(c.CASI_FECHA), MONTH(c.CASI_FECHA)
                ORDER BY Anio, Mes
                """
                # Para Argentina no usamos ? en división porque ya está en el filtro
                if db_name == 'plataforma':
                    params = [desde, hasta] + param_intercompany()
                else:
                    params = [division, desde, hasta] + param_intercompany()

                df = pd.read_sql(query, conn, params=params)
                conn.close()

                real_meses = {}
                if not df.empty:
                    for _, row in df.iterrows():
                        mes = int(row['Mes'])
                        real_meses[mes] = {
                            'transacciones': int(row['Transacciones']),
                            'importe_local': float(row['Importe_Local']),
                            'importe_conversion': float(row['Importe_Conversion'])
                        }

                manual_meses = set()
                for key in manuales_por_pais.keys():
                    pais_key, anio_key, mes_key = key.split('|')
                    if pais_key == nombre_pais and int(anio_key) == anio:
                        manual_meses.add(int(mes_key))

                todos_meses = set(real_meses.keys()) | manual_meses
                if not todos_meses:
                    continue

                for mes in sorted(todos_meses):
                    real = real_meses.get(mes, {'transacciones': 0, 'importe_local': 0, 'importe_conversion': 0})
                    total_manual = manuales_por_pais.get(f'{nombre_pais}|{anio}|{mes}', 0)

                    # 🔴 CONVERSIÓN A USD — MISMA REGLA QUE VENTAS POR PAÍS
                    # (ventas_cuentas.a_usd): Ecuador ya es USD; con cotización
                    # del mes se divide el local; sin cotización se usa el
                    # importe de conversión del comprobante.
                    es_ecuador = db_name == 'plataforma_ec' or sigla == 'EC'
                    cotizacion = None
                    if not es_ecuador:
                        cotizacion = obtener_cotizacion_por_mes(anio, mes, base_referencia=db_name)
                        if cotizacion is not None and cotizacion > 0:
                            logger.info(f"📊 {nombre_pais} - {mes}/{anio} - Cotización: {cotizacion} - Local: {real['importe_local']} -> USD: {real['importe_local'] / cotizacion}")
                        else:
                            # Fallback: usar Importe_Conversion (USD del día) si no hay cotización
                            logger.warning(f"⚠️ Sin cotización para {nombre_pais} - {mes}/{anio}, usando Importe_Conversion: {real['importe_conversion']}")

                    importe_usd = a_usd(real['importe_local'], real['importe_conversion'],
                                        cotizacion, es_ecuador=es_ecuador)

                    importe_usd += total_manual

                    data_global.append({
                        'Sigla': sigla,
                        'Base': db_name,
                        'Anio': anio,
                        'Mes': mes,
                        'Transacciones': real['transacciones'],
                        'Importe_DL': importe_usd,
                        'Pais': nombre_pais
                    })

            except Exception as e:
                logger.warning(f"No se pudo consultar la base {db_name}: {e}")
                continue

        # Agregar países con solo manuales
        existentes = set()
        for item in data_global:
            existentes.add((item['Pais'], item['Anio'], item['Mes']))

        for key, importe in manuales_por_pais.items():
            if importe <= 0:
                continue
            pais_key, anio_str, mes_str = key.split('|')
            anio_int = int(anio_str)
            mes_int = int(mes_str)
            if (pais_key, anio_int, mes_int) not in existentes:
                sigla = pais_a_sigla.get(pais_key, 'XX')
                data_global.append({
                    'Sigla': sigla,
                    'Base': f'plataforma_{sigla.lower()}' if sigla != 'XX' else 'plataforma_xx',
                    'Anio': anio_int,
                    'Mes': mes_int,
                    'Transacciones': 0,
                    'Importe_DL': importe,
                    'Pais': pais_key
                })

        return {
            'success': True,
            'data': data_global,
            'total_registros': len(data_global),
            'ventas_manuales': manuales_por_pais
        }

    except Exception as e:
        logger.error(f"Error en consolidado_total_service: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'data': [],
            'total_registros': 0,
            'ventas_manuales': {}
        }