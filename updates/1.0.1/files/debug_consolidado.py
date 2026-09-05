# debug_consolidado.py
# ============================================================
# Script para depurar el reporte Consolidado Total
# ============================================================

import pyodbc
import pandas as pd
from config import BASES_DISPONIBLES, SQL_SERVER, SQL_USERNAME, SQL_PASSWORD
from modules.reportes.routes import get_db_connection_base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def consultar_base(db_name, anio):
    """Ejecuta la consulta en una base específica y retorna el DataFrame"""
    try:
        conn, division = get_db_connection_base(db_name)
        query = """
        SELECT 
            YEAR(c.CASI_FECHA) AS Anio,
            MONTH(c.CASI_FECHA) AS Mes,
            COUNT(*) AS Transacciones,
            ISNULL(SUM(
                CASE 
                    WHEN a.AASI_SIGNO = 'D' THEN -a.AASI_IMP_CON 
                    WHEN a.AASI_SIGNO = 'H' THEN a.AASI_IMP_CON 
                    ELSE a.AASI_IMP_CON 
                END
            ), 0) AS Importe_DL
        FROM SIST_AASI a
        INNER JOIN SIST_CASI c ON a.AASI_ASIENTO = c.CASI_ASIENTO
        INNER JOIN SIST_RASI r ON a.AASI_ASIENTO = r.RASI_ASIENTO
        INNER JOIN CCOB_RACC ra ON c.CASI_ASIENTO = ra.RACC_ASIENTO
        INNER JOIN CCOB_CTEC ct ON ra.RACC_CTACTE_CTEC = ct.CTEC_CTACTE_CTEC
        INNER JOIN CCOB_CLIE cl ON ct.CTEC_CLIENTE = cl.CLIE_CLIENTE
        WHERE a.AASI_DIVISION = ?
          AND c.CASI_SUBDIARIO = 'VTA'
          AND r.RASI_CUENTA IN ('410101', '410102')
          AND cl.CLIE_NOMBRE NOT LIKE '%SIDESYS%'
          AND YEAR(c.CASI_FECHA) = ?
        GROUP BY YEAR(c.CASI_FECHA), MONTH(c.CASI_FECHA)
        ORDER BY Anio, Mes
        """
        df = pd.read_sql(query, conn, params=[division, anio])
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error en {db_name}: {e}")
        return pd.DataFrame()

def main():
    anio = 2026  # Cambia el año si necesitas
    print(f"\n🔍 Consultando bases para el año {anio}...\n")
    
    total_general = 0
    resultados = {}
    
    for db_name in BASES_DISPONIBLES.keys():
        print(f"📡 Consultando: {db_name}...")
        df = consultar_base(db_name, anio)
        if not df.empty:
            total_base = df['Importe_DL'].sum()
            resultados[db_name] = {
                'total': total_base,
                'registros': len(df),
                'detalle': df.to_dict(orient='records')
            }
            print(f"   ✅ {db_name}: ${total_base:,.2f} USD ({len(df)} registros)")
            total_general += total_base
        else:
            print(f"   ⚠️ {db_name}: Sin datos o error")
    
    print("\n" + "="*50)
    print(f"💰 TOTAL GENERAL: ${total_general:,.2f} USD")
    print("="*50 + "\n")
    
    # Mostrar detalle por base si se desea
    for db, data in resultados.items():
        print(f"\n📊 Detalle de {db} (${data['total']:,.2f} USD):")
        for row in data['detalle']:
            print(f"   {row['Anio']}-{row['Mes']:02d}: ${row['Importe_DL']:,.2f} ({row['Transacciones']} transacciones)")

if __name__ == "__main__":
    main()