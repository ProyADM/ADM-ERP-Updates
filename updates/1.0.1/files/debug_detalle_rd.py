# debug_detalle_rd.py - VERSIÓN CORREGIDA (sin columnas problemáticas)
# ============================================================
# Script para ver el detalle de transacciones de un mes específico
# ============================================================

import pyodbc
import pandas as pd
from config import BASES_DISPONIBLES, SQL_SERVER, SQL_USERNAME, SQL_PASSWORD
from modules.reportes.routes import get_db_connection_base
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_detalle_transacciones(db_name, anio, mes):
    """Obtiene el detalle de todas las transacciones para un mes específico"""
    try:
        conn, division = get_db_connection_base(db_name)
        
        # Consulta sin columnas que puedan no existir en todas las bases
        query = """
        SELECT 
            a.AASI_ASIENTO AS Asiento,
            a.AASI_RENGLON_ASI AS Renglon_Asiento,
            a.AASI_RENGLON_APE AS Renglon_Ape,
            a.AASI_SIGNO AS Signo,
            a.AASI_IMP_LOC AS Importe_Local,
            a.AASI_IMP_CON AS Importe_DL_Original,
            CASE 
                WHEN a.AASI_SIGNO = 'D' THEN -a.AASI_IMP_CON 
                WHEN a.AASI_SIGNO = 'H' THEN a.AASI_IMP_CON 
                ELSE a.AASI_IMP_CON 
            END AS Importe_DL_Ajustado,
            c.CASI_FECHA AS Fecha,
            c.CASI_SUBDIARIO AS Subdiario,
            r.RASI_CUENTA AS Cuenta,
            cl.CLIE_NOMBRE AS Cliente,
            cl.CLIE_TIPO_CLI AS Tipo_Cliente,
            i.IMAE_DESCRIPCION1 AS Concepto1,
            i.IMAE_DESCRIPCION2 AS Concepto2,
            i.IMAE_DESCRIPCION3 AS Concepto3,
            a.AASI_MAESTRO AS Maestro,
            a.AASI_INSTANCIA AS Instancia,
            a.AASI_FECHA_REF AS Fecha_Ref
        FROM SIST_AASI a
        INNER JOIN SIST_CASI c ON a.AASI_ASIENTO = c.CASI_ASIENTO
        INNER JOIN SIST_RASI r ON a.AASI_ASIENTO = r.RASI_ASIENTO
        INNER JOIN CCOB_RACC ra ON c.CASI_ASIENTO = ra.RACC_ASIENTO
        INNER JOIN CCOB_CTEC ct ON ra.RACC_CTACTE_CTEC = ct.CTEC_CTACTE_CTEC
        INNER JOIN CCOB_CLIE cl ON ct.CTEC_CLIENTE = cl.CLIE_CLIENTE
        LEFT JOIN CONT_IMAE i ON a.AASI_MAESTRO = i.IMAE_MAESTRO AND a.AASI_INSTANCIA = i.IMAE_INSTANCIA
        WHERE a.AASI_DIVISION = ?
          AND c.CASI_SUBDIARIO = 'VTA'
          AND r.RASI_CUENTA IN ('410101', '410102')
          AND YEAR(c.CASI_FECHA) = ?
          AND MONTH(c.CASI_FECHA) = ?
          AND cl.CLIE_NOMBRE NOT LIKE '%SIDESYS%'
        ORDER BY c.CASI_FECHA, a.AASI_ASIENTO
        """
        
        df = pd.read_sql(query, conn, params=[division, anio, mes])
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error en {db_name}: {e}")
        return pd.DataFrame()

def main():
    # Parámetros configurables
    db_name = 'plataforma_rd'
    anio = 2026
    mes = 1  # Enero
    
    print(f"\n🔍 Consultando detalle de {db_name} - {anio}-{mes:02d}...\n")
    
    df = get_detalle_transacciones(db_name, anio, mes)
    
    if df.empty:
        print("❌ No se encontraron transacciones o hubo un error.")
        return
    
    # Mostrar resumen
    total_general = df['Importe_DL_Ajustado'].sum()
    print(f"💰 Total general (USD): ${total_general:,.2f}")
    print(f"📊 Total de transacciones: {len(df)}")
    
    # Resumen por cliente (todos)
    print("\n📋 Resumen por Cliente (todos):")
    resumen_cliente = df.groupby('Cliente').agg({
        'Importe_DL_Ajustado': 'sum',
        'Asiento': 'count'
    }).reset_index()
    resumen_cliente.columns = ['Cliente', 'Total_USD', 'Cantidad']
    resumen_cliente = resumen_cliente.sort_values('Total_USD', ascending=False)
    print(resumen_cliente.to_string(index=False))
    
    # Resumen por tipo de cliente
    print("\n📋 Resumen por Tipo de Cliente:")
    resumen_tipo = df.groupby('Tipo_Cliente').agg({
        'Importe_DL_Ajustado': 'sum',
        'Asiento': 'count'
    }).reset_index()
    resumen_tipo.columns = ['Tipo_Cliente', 'Total_USD', 'Cantidad']
    print(resumen_tipo.to_string(index=False))
    
    # Resumen por cuenta contable
    print("\n📋 Resumen por Cuenta Contable:")
    resumen_cuenta = df.groupby('Cuenta').agg({
        'Importe_DL_Ajustado': 'sum',
        'Asiento': 'count'
    }).reset_index()
    resumen_cuenta.columns = ['Cuenta', 'Total_USD', 'Cantidad']
    print(resumen_cuenta.to_string(index=False))
    
    # Exportar a CSV para análisis detallado
    archivo_csv = f'detalle_{db_name}_{anio}_{mes:02d}.csv'
    df.to_csv(archivo_csv, index=False, encoding='utf-8-sig')
    print(f"\n✅ Detalle completo exportado a: {archivo_csv}")
    
    print("\n💡 Sugerencia: Abre el CSV en Excel y filtra por cliente o tipo de cliente.")
    print("   Busca clientes que no deberían estar en el reporte de ventas real.")
    print("   Luego podemos ajustar los filtros en el backend.")

if __name__ == "__main__":
    main()