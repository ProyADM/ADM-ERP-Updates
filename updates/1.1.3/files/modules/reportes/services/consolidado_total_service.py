# modules/reportes/services/consolidado_total_service.py
# ============================================================
# SERVICIO: CONSOLIDADO TOTAL DE VENTAS (GLOBAL)
# Ventas = líneas de las cuentas 410101/410102 (definición en ventas_cuentas.py)
# Importe_Local = RASI_IMP_LOC, Importe_Conversion = RASI_IMP_CON
# ============================================================
# Brief 24/09/2026 ("Argentina por sociedad"): Argentina son DOS empresas
# (Sidesys, división 1, y Advansur, división 2), así que el consolidado ya no
# puede sumarlas en una sola consulta con `CASI_DIVISION IN (1, 2)`:
#   - se hace UNA consulta por sociedad del catálogo
#     (`config.BASES_DISPONIBLES['plataforma']['sociedades']`, la fuente única);
#   - cada fila mensual de Argentina sale con `Sociedad`/`SociedadLabel`/`Division`
#     y sigue con `Pais: 'Argentina'` (el frontend sigue agrupando por `Pais`);
#   - las ventas manuales se leen POR SOCIEDAD (clave `pais|sociedad|anio|mes`)
#     y se suman en la fila de SU sociedad.
# ============================================================

import pandas as pd
import logging
from .utils import (get_db_connection, get_db_connection_base, get_db_connection_ventas_manuales,
                    limpiar_datos, obtener_cotizacion_por_mes, asegurar_tabla_ventas_manuales)
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

# Clave de la sociedad de Argentina a la que se imputa una fila con `sociedad`
# vacía/NULL. DEFENSIVO (brief §3.1.3): el usuario dijo que esas filas NO existen.
# Si alguna vez aparecieran, sumarlas a Sidesys (división 1) es preferible a
# perderlas en silencio o a reventar el consolidado.
SOCIEDAD_DEFENSIVA_ARGENTINA = 'sidesys'


def _normalizar_sociedad(sociedad):
    """Clave con la que se agrupa/lee una sociedad: `str(x or '').strip().lower()`.

    `''` = fila sin sociedad (los países que no tienen desglose por sociedad).
    """
    return str(sociedad or '').strip().lower()


def obtener_ventas_manuales_global(anio):
    """Ventas manuales de todas las bases, POR PAÍS Y POR SOCIEDAD.

    Devuelve `{ 'pais|sociedad|anio|mes': importe }`; la sociedad va normalizada
    (`str(sociedad or '').strip().lower()`; `''` = sin sociedad). El único
    consumidor es `obtener_consolidado_total`, en este mismo archivo.
    """
    try:
        asegurar_tabla_ventas_manuales()
        # Base CANÓNICA (17/09/2026): las ventas manuales de todos los países se
        # leen de una sola tabla. Antes se leía la de la base ACTIVA, así que el
        # consolidado perdía las filas cargadas desde otra base (descuadre
        # silencioso: el total parecía válido).
        conn, _ = get_db_connection_ventas_manuales()
        cursor = conn.cursor()
        query = """
            SELECT 
                pais,
                sociedad,
                anio,
                mes,
                SUM(importe_usd) AS total_manual
            FROM VENTAS_MANUALES
            WHERE anio = ?
            GROUP BY pais, sociedad, anio, mes
        """
        cursor.execute(query, [anio])
        rows = cursor.fetchall()
        conn.close()
        resultado = {}
        for row in rows:
            key = f"{row[0]}|{_normalizar_sociedad(row[1])}|{row[2]}|{row[3]}"
            resultado[key] = float(row[4]) if row[4] is not None else 0
        return resultado
    except Exception as e:
        logger.debug(f"Error obteniendo ventas manuales globales: {e}")
        return {}

def obtener_consolidado_total(anio, base_override=None, sociedad_override=None,
                             bases_permitidas=None):
    bases_fallidas = []
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

        # Bases que este pedido puede tocar (fail-closed). Antes se iteraba
        # BASES_DISPONIBLES completo: un usuario con 2 bases recibía las 11.
        if bases_permitidas is None or '*' in bases_permitidas:
            bases_a_consultar = BASES_DISPONIBLES
        else:
            bases_a_consultar = {b: BASES_DISPONIBLES[b] for b in bases_permitidas
                                 if b in BASES_DISPONIBLES}
        # Países habilitados: sirve para no colar las ventas manuales de un país
        # que el usuario no tiene permitido (se leen todas juntas desde una base).
        siglas_permitidas = {db_info.get('sigla') for db_info in bases_a_consultar.values()}
        paises_permitidos = {sigla_a_pais[s] for s in siglas_permitidas if s in sigla_a_pais}

        data_global = []

        for db_name, db_info in bases_a_consultar.items():
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

                # ---- Qué divisiones se consultan para esta base -------------
                # Argentina: UNA consulta POR SOCIEDAD del catálogo de config
                # (nada de listas nuevas hardcodeadas). El resto de las bases:
                # una sola consulta con la división de la base, como hoy.
                if db_name == 'plataforma':
                    sociedades_consulta = list((db_info.get('sociedades') or {}).items())
                else:
                    sociedades_consulta = [(None, None)]

                # Cada elemento: (sociedad_clave, sociedad_info_o_None).
                filas_de_la_base = []
                # Si falla la consulta de UNA sociedad de Argentina, la base
                # entera queda fallida (ver el final de este bloque).
                fallo_alguna_sociedad = False

                for sociedad_clave, sociedad_info in sociedades_consulta:
                    if sociedad_clave is None:
                        conn, division = get_db_connection_base(db_name)
                        params_division = [division]
                    else:
                        conn, division = get_db_connection_base(db_name, sociedad_clave)
                        params_division = [sociedad_info.get('division', division)]

                    try:
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
                        WHERE c.CASI_DIVISION = ?
                          AND r.RASI_CUENTA IN ({cuentas_sql()})
                          AND c.CASI_FECHA >= ? AND c.CASI_FECHA < ?
                          {filtro_intercompany()}
                        GROUP BY YEAR(c.CASI_FECHA), MONTH(c.CASI_FECHA)
                        ORDER BY Anio, Mes
                        """
                        params = params_division + [desde, hasta] + param_intercompany()

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

                        # Las ventas manuales de ESTA fila (país + sociedad). Un país
                        # sin sociedades busca con la clave vacía, como antes.
                        clave_sociedad = _normalizar_sociedad(sociedad_clave)
                        manual_meses = set()
                        for key in manuales_por_pais.keys():
                            pais_key, sociedad_key, anio_key, mes_key = key.split('|')
                            if (pais_key == nombre_pais and sociedad_key == clave_sociedad
                                    and int(anio_key) == anio):
                                manual_meses.add(int(mes_key))

                        todos_meses = set(real_meses.keys()) | manual_meses

                        # DEFENSIVO (brief §3.1.3): una venta manual de Argentina
                        # con `sociedad` vacía/NULL no tiene fila propia; se imputa
                        # a la PRIMERA sociedad del catálogo (Sidesys, división 1),
                        # en vez de perderse. Se emite UNA sola vez: la primera
                        # sociedad del catálogo es la que la recibe. El usuario dijo
                        # que esas filas no existen; queda declarado en el reporte.
                        if (db_name == 'plataforma'
                                and sociedad_clave == sociedades_consulta[0][0]):
                            for fila in _manuales_sin_sociedad(
                                    nombre_pais, sigla, anio, manuales_por_pais,
                                    db_info, sociedad_clave, sociedad_info):
                                # El mes puede estar ya cubierto por una venta
                                # real o por la manual propia de la sociedad: en
                                # ese caso la fila ya existe y no se duplica.
                                if (fila['Mes'] in real_meses
                                        or fila['Mes'] in manual_meses):
                                    continue
                                filas_de_la_base.append(fila)

                        for mes in sorted(todos_meses):
                            real = real_meses.get(mes, {'transacciones': 0, 'importe_local': 0, 'importe_conversion': 0})
                            total_manual = manuales_por_pais.get(
                                f'{nombre_pais}|{clave_sociedad}|{anio}|{mes}', 0)

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

                            filas_de_la_base.append({
                                'Sigla': sigla,
                                'Base': db_name,
                                'Anio': anio,
                                'Mes': mes,
                                'Transacciones': real['transacciones'],
                                'Importe_DL': importe_usd,
                                'Pais': nombre_pais,
                                'Sociedad': sociedad_clave,
                                'SociedadLabel': (sociedad_info or {}).get('label'),
                                'Division': int(params_division[0]),
                            })
                    except Exception as e:
                        # Se sigue con las demas sociedades (para poder informar
                        # bien cual fallo) pero la base queda marcada.
                        logger.warning(f"No se pudo consultar {db_name}"
                                       f"{'/' + sociedad_clave if sociedad_clave else ''}: {e}")
                        fallo_alguna_sociedad = True

                # Argentina son DOS divisiones: si falla la de UNA sociedad, un
                # consolidado con la otra suelta seria un total incompleto sin que
                # nadie lo diga (peor que no tener el pais). Se descarta TODO lo de
                # la base y el aviso "consolidado incompleto" sale por
                # `bases_fallidas`.
                if db_name == 'plataforma' and fallo_alguna_sociedad:
                    raise RuntimeError('fallo la consulta de una division de Argentina: '
                                       'no se emite el pais a medias')

                data_global.extend(filas_de_la_base)

            except Exception as e:
                logger.warning(f"No se pudo consultar la base {db_name}: {e}")
                bases_fallidas.append(db_name)
                continue

        # Agregar países con solo manuales
        existentes = set()
        for item in data_global:
            existentes.add((item['Pais'], _normalizar_sociedad(item.get('Sociedad')),
                            item['Anio'], item['Mes']))

        # Los países cuyo servicio se CONSULTÓ (haya respondido o no). Este
        # respaldo es para países que NO se consultan (no están en
        # `bases_a_consultar`): si un país consultado quedó afuera de `data_global`
        # es porque su consulta falló, y entonces sus manuales tampoco pueden
        # aparecer sueltos (sería el total a medias que el brief prohíbe).
        paises_consultados = set()
        for db_info in bases_a_consultar.values():
            pais = db_info.get('label')
            if pais:
                paises_consultados.add(pais)

        for key, importe in manuales_por_pais.items():
            if importe <= 0:
                continue
            pais_key, sociedad_key, anio_str, mes_str = key.split('|')
            # Las ventas manuales se leen todas juntas: no colar las de un país
            # que este usuario no tiene permitido.
            if paises_permitidos and pais_key not in paises_permitidos:
                continue
            if pais_key in paises_consultados:
                continue
            anio_int = int(anio_str)
            mes_int = int(mes_str)
            if (pais_key, sociedad_key, anio_int, mes_int) not in existentes:
                sigla = pais_a_sigla.get(pais_key, 'XX')
                data_global.append({
                    'Sigla': sigla,
                    'Base': f'plataforma_{sigla.lower()}' if sigla != 'XX' else 'plataforma_xx',
                    'Anio': anio_int,
                    'Mes': mes_int,
                    'Transacciones': 0,
                    'Importe_DL': importe,
                    'Pais': pais_key,
                    'Sociedad': None,
                    'SociedadLabel': None,
                    'Division': None,
                })

        return {
            'success': True,
            'data': data_global,
            'total_registros': len(data_global),
            'bases_incluidas': sorted(bases_a_consultar.keys()),
            'bases_fallidas': sorted(bases_fallidas),
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


def _manuales_sin_sociedad(nombre_pais, sigla, anio, manuales_por_pais, db_info,
                           sociedad_clave, sociedad_info):
    """Filas de venta manual de Argentina SIN sociedad ('' o NULL).

    DEFENSIVO y declarado (brief §3.1.3): el usuario dijo que no existen. Si
    aparecen, se imputan a la sociedad que las recibe (`sociedad_clave`: la
    PRIMERA del catálogo, Sidesys/dividión 1) para no perderlas en silencio. Se
    llama UNA sola vez por base: la sociedad destino es la que las recibe.
    """
    filas = []
    for key, importe in manuales_por_pais.items():
        pais_key, sociedad_key, anio_key, mes_key = key.split('|')
        if pais_key != nombre_pais or sociedad_key != '' or int(anio_key) != anio:
            continue
        if sociedad_clave != SOCIEDAD_DEFENSIVA_ARGENTINA:
            # El nombre de la constante sólo documenta cuál es hoy la sociedad
            # destino (evita un `if` que se rompería si el catálogo cambia).
            logger.warning(f"⚠️ Venta manual sin sociedad de {nombre_pais}: se imputa a "
                           f"'{sociedad_clave}', no a "
                           f"'{SOCIEDAD_DEFENSIVA_ARGENTINA}'.")
        logger.warning(f"⚠️ Venta manual de {nombre_pais} SIN sociedad ({importe}) en "
                       f"{mes_key}/{anio}: se imputa a '{sociedad_clave}' (defensivo).")
        filas.append({
            'Sigla': sigla,
            'Base': 'plataforma',
            'Anio': anio,
            'Mes': int(mes_key),
            'Transacciones': 0,
            'Importe_DL': importe,
            'Pais': nombre_pais,
            'Sociedad': sociedad_clave,
            'SociedadLabel': (sociedad_info or {}).get('label'),
            'Division': (sociedad_info or {}).get('division'),
        })
    return filas
