# modules/reportes/services/consolidado_pais_service.py
# ============================================================
# SERVICIO: CONSOLIDADO VENTAS POR PAÍS
# ============================================================

import pandas as pd
import logging
from .utils import get_db_connection, get_db_connection_base, limpiar_datos
from config import BASES_DISPONIBLES

logger = logging.getLogger(__name__)

def obtener_consolidado_pais(anio, base_override=None, sociedad_override=None):
    try:
        # Lista de clientes intercompany a excluir
        paises_excluir = [
            'SIDESYS COLOMBIA', 'SIDESYS COSTA RICA', 'SIDESYS ECUADOR',
            'SIDESYS GUATEMALA', 'SIDESYS HONDURAS', 'SIDESYS MEXICO', 'SIDESYS PARAGUAY'
        ]
        placeholders = ','.join(['?'] * len(paises_excluir))

        if base_override:
            bases_a_consultar = {base_override: BASES_DISPONIBLES.get(base_override, {})}
        else:
            bases_a_consultar = BASES_DISPONIBLES

        all_dfs = []

        for db_name, db_info in bases_a_consultar.items():
            try:
                conn = None
                if db_name == 'plataforma':
                    conn, _ = get_db_connection_base('plataforma')
                    query = f"""
                    SELECT 
                        a.AASI_DIVISION,
                        a.AASI_IMP_LOC AS IMPORTE_LOCAL,
                        a.AASI_IMP_CON AS IMPORTE_CONVERSION,
                        a.AASI_SIGNO,
                        MAX(c.CASI_FECHA) AS FECHA,
                        MAX(i.IMAE_DESCRIPCION2) AS CC_CLIENTE,
                        MAX(i.IMAE_DESCRIPCION3) AS CENTRO_COSTO,
                        MAX(c.CASI_SUBDIARIO) AS SUBDIARIO,
                        MAX(cl.CLIE_NOMBRE) AS CLIE_NOMBRE,
                        YEAR(MAX(c.CASI_FECHA)) AS AÑO,
                        MONTH(MAX(c.CASI_FECHA)) AS MES,
                        CASE 
                            WHEN a.AASI_SIGNO = 'D' THEN -a.AASI_IMP_CON
                            WHEN a.AASI_SIGNO = 'H' THEN a.AASI_IMP_CON
                            ELSE a.AASI_IMP_CON
                        END AS IMPORTE_DL,
                        'Argentina' AS PAIS
                    FROM SIST_AASI a
                    LEFT JOIN CONT_IMAE i ON a.AASI_MAESTRO = i.IMAE_MAESTRO AND a.AASI_INSTANCIA = i.IMAE_INSTANCIA
                    LEFT JOIN SIST_CASI c ON a.AASI_ASIENTO = c.CASI_ASIENTO
                    LEFT JOIN CCOB_RACC ra ON c.CASI_ASIENTO = ra.RACC_ASIENTO
                    LEFT JOIN CCOB_CTEC ct ON ra.RACC_CTACTE_CTEC = ct.CTEC_CTACTE_CTEC
                    LEFT JOIN CCOB_CLIE cl ON ct.CTEC_CLIENTE = cl.CLIE_CLIENTE
                    WHERE a.AASI_DIVISION IN (1, 2)
                      AND c.CASI_SUBDIARIO = 'VTA'
                      AND cl.CLIE_NOMBRE NOT IN ({placeholders})
                      AND YEAR(c.CASI_FECHA) = ?
                      AND EXISTS (
                          SELECT 1 FROM SIST_RASI r 
                          WHERE r.RASI_ASIENTO = a.AASI_ASIENTO 
                            AND r.RASI_CUENTA IN ('410101', '410102')
                      )
                    GROUP BY 
                        a.AASI_DIVISION,
                        a.AASI_IMP_LOC,
                        a.AASI_IMP_CON,
                        a.AASI_SIGNO,
                        a.AASI_ASIENTO,
                        a.AASI_RENGLON_ASI,
                        a.AASI_RENGLON_APE,
                        CASE 
                            WHEN a.AASI_SIGNO = 'D' THEN -a.AASI_IMP_CON
                            WHEN a.AASI_SIGNO = 'H' THEN a.AASI_IMP_CON
                            ELSE a.AASI_IMP_CON
                        END
                    ORDER BY MAX(c.CASI_FECHA) DESC
                    """
                    df = pd.read_sql(query, conn, params=paises_excluir + [anio])
                    conn.close()
                    if not df.empty:
                        all_dfs.append(df)
                    continue

                es_ecuador = db_name == 'plataforma_ec'
                campo_importe = "a.AASI_IMP_LOC" if es_ecuador else "a.AASI_IMP_CON"

                nombre_pais = db_info.get('label', db_name)
                if db_name == 'plataforma_ec':
                    nombre_pais = 'Ecuador'
                elif db_name == 'plataforma_rd':
                    nombre_pais = 'República Dominicana'
                elif db_name == 'plataforma_mx':
                    nombre_pais = 'México'
                elif db_name == 'plataforma_gt':
                    nombre_pais = 'Guatemala'
                elif db_name == 'plataforma_hn':
                    nombre_pais = 'Honduras'
                elif db_name == 'plataforma_cr':
                    nombre_pais = 'Costa Rica'
                elif db_name == 'plataforma_pe':
                    nombre_pais = 'Perú'
                elif db_name == 'plataforma_py':
                    nombre_pais = 'Paraguay'
                elif db_name == 'plataforma_co':
                    nombre_pais = 'Colombia'
                elif db_name == 'plataforma_uy':
                    nombre_pais = 'Uruguay'

                if not conn:
                    conn, division = get_db_connection_base(db_name)

                query = f"""
                SELECT 
                    a.AASI_DIVISION,
                    a.AASI_IMP_LOC AS IMPORTE_LOCAL,
                    a.AASI_IMP_CON AS IMPORTE_CONVERSION,
                    a.AASI_SIGNO,
                    MAX(c.CASI_FECHA) AS FECHA,
                    MAX(i.IMAE_DESCRIPCION2) AS CC_CLIENTE,
                    MAX(i.IMAE_DESCRIPCION3) AS CENTRO_COSTO,
                    MAX(c.CASI_SUBDIARIO) AS SUBDIARIO,
                    MAX(cl.CLIE_NOMBRE) AS CLIE_NOMBRE,
                    YEAR(MAX(c.CASI_FECHA)) AS AÑO,
                    MONTH(MAX(c.CASI_FECHA)) AS MES,
                    CASE 
                        WHEN a.AASI_SIGNO = 'D' THEN -{campo_importe}
                        WHEN a.AASI_SIGNO = 'H' THEN {campo_importe}
                        ELSE {campo_importe}
                    END AS IMPORTE_DL,
                    '{nombre_pais}' AS PAIS
                FROM SIST_AASI a
                LEFT JOIN CONT_IMAE i ON a.AASI_MAESTRO = i.IMAE_MAESTRO AND a.AASI_INSTANCIA = i.IMAE_INSTANCIA
                LEFT JOIN SIST_CASI c ON a.AASI_ASIENTO = c.CASI_ASIENTO
                LEFT JOIN CCOB_RACC ra ON c.CASI_ASIENTO = ra.RACC_ASIENTO
                LEFT JOIN CCOB_CTEC ct ON ra.RACC_CTACTE_CTEC = ct.CTEC_CTACTE_CTEC
                LEFT JOIN CCOB_CLIE cl ON ct.CTEC_CLIENTE = cl.CLIE_CLIENTE
                WHERE a.AASI_DIVISION = ?
                  AND c.CASI_SUBDIARIO = 'VTA'
                  AND cl.CLIE_NOMBRE NOT IN ({placeholders})
                  AND YEAR(c.CASI_FECHA) = ?
                  AND EXISTS (
                      SELECT 1 FROM SIST_RASI r 
                      WHERE r.RASI_ASIENTO = a.AASI_ASIENTO 
                        AND r.RASI_CUENTA IN ('410101', '410102')
                  )
                GROUP BY 
                    a.AASI_DIVISION,
                    a.AASI_IMP_LOC,
                    a.AASI_IMP_CON,
                    a.AASI_SIGNO,
                    a.AASI_ASIENTO,
                    a.AASI_RENGLON_ASI,
                    a.AASI_RENGLON_APE,
                    CASE 
                        WHEN a.AASI_SIGNO = 'D' THEN -{campo_importe}
                        WHEN a.AASI_SIGNO = 'H' THEN {campo_importe}
                        ELSE {campo_importe}
                    END
                ORDER BY MAX(c.CASI_FECHA) DESC
                """
                df = pd.read_sql(query, conn, params=[division] + paises_excluir + [anio])
                conn.close()
                if not df.empty:
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
            'AASI_DIVISION': 'count'
        }).reset_index()
        resumen_cliente.columns = ['Cliente', 'Total_Local', 'Total_USD', 'Total_DL', 'Transacciones']
        resumen_cliente = resumen_cliente.sort_values('Total_DL', ascending=False)

        resumen_centro = df_final.groupby('CENTRO_COSTO').agg({
            'IMPORTE_LOCAL': 'sum',
            'IMPORTE_CONVERSION': 'sum',
            'IMPORTE_DL': 'sum',
            'AASI_DIVISION': 'count'
        }).reset_index()
        resumen_centro.columns = ['Centro_Costo', 'Total_Local', 'Total_USD', 'Total_DL', 'Transacciones']
        resumen_centro = resumen_centro.sort_values('Total_DL', ascending=False)

        resumen_subdiario = df_final.groupby('SUBDIARIO').agg({
            'IMPORTE_LOCAL': 'sum',
            'IMPORTE_CONVERSION': 'sum',
            'IMPORTE_DL': 'sum',
            'AASI_DIVISION': 'count'
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
                'Division': int(row.get('AASI_DIVISION', 0)) if pd.notna(row.get('AASI_DIVISION', 0)) else 0,
                'Pais': str(row.get('PAIS', 'República Dominicana')),
                'Cliente': str(row.get('CC_CLIENTE', 'SIN CLIENTE')),
                'NombreCliente': str(row.get('CLIE_NOMBRE', 'SIN NOMBRE')),
                'CentroCosto': str(row.get('CENTRO_COSTO', 'SIN CENTRO')),
                'Fecha': fecha_str,
                'Anio': int(row.get('AÑO', 0)) if pd.notna(row.get('AÑO', 0)) else 0,
                'Mes': int(row.get('MES', 0)) if pd.notna(row.get('MES', 0)) else 0,
                'Signo': str(row.get('AASI_SIGNO', '')),
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