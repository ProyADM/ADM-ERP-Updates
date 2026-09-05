# debug_cliente.py - VERSIÓN CORREGIDA (SIN DUPLICACIÓN)
# ============================================================
# Script para depurar un cliente específico
# Usa EXISTS para evitar duplicación por SIST_RASI
# ============================================================

import pyodbc
import pandas as pd
from config import BASES_DISPONIBLES, SQL_SERVER, SQL_USERNAME, SQL_PASSWORD
from modules.reportes.routes import get_db_connection_base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_detalle_cliente(db_name, anio, mes, nombre_cliente):
    """
    Obtiene TODAS las transacciones de un cliente específico
    sin duplicación (usando EXISTS)
    """
    try:
        conn, division = get_db_connection_base(db_name)
        
        # ✅ Consulta SIN JOIN con SIST_RASI (solo EXISTS)
        query = """
        SELECT 
            -- Datos del asiento
            a.AASI_ASIENTO AS Asiento,
            a.AASI_RENGLON_ASI AS Renglon_Asiento,
            a.AASI_RENGLON_APE AS Renglon_Ape,
            a.AASI_SIGNO AS Signo,
            a.AASI_IMP_LOC AS Importe_Local,
            a.AASI_IMP_CON AS Importe_DL_Original,
            a.AASI_FECHA_REF AS Fecha_Referencia,
            
            -- Datos del comprobante
            c.CASI_FECHA AS Fecha_Comprobante,
            c.CASI_SUBDIARIO AS Subdiario,
            
            -- Datos del cliente
            cl.CLIE_NOMBRE AS Cliente,
            cl.CLIE_TIPO_CLI AS Tipo_Cliente,
            
            -- Datos del concepto (IMAE)
            i.IMAE_DESCRIPCION1 AS Concepto1,
            i.IMAE_DESCRIPCION2 AS Concepto2,
            i.IMAE_DESCRIPCION3 AS Concepto3,
            
            -- Cálculo del importe ajustado en USD
            CASE 
                WHEN a.AASI_SIGNO = 'D' THEN -a.AASI_IMP_CON 
                WHEN a.AASI_SIGNO = 'H' THEN a.AASI_IMP_CON 
                ELSE a.AASI_IMP_CON 
            END AS Importe_DL_Ajustado
            
        FROM SIST_AASI a
        INNER JOIN SIST_CASI c ON a.AASI_ASIENTO = c.CASI_ASIENTO
        INNER JOIN CCOB_RACC ra ON c.CASI_ASIENTO = ra.RACC_ASIENTO
        INNER JOIN CCOB_CTEC ct ON ra.RACC_CTACTE_CTEC = ct.CTEC_CTACTE_CTEC
        INNER JOIN CCOB_CLIE cl ON ct.CTEC_CLIENTE = cl.CLIE_CLIENTE
        LEFT JOIN CONT_IMAE i ON a.AASI_MAESTRO = i.IMAE_MAESTRO AND a.AASI_INSTANCIA = i.IMAE_INSTANCIA
        WHERE a.AASI_DIVISION = ?
          AND c.CASI_SUBDIARIO = 'VTA'
          AND YEAR(c.CASI_FECHA) = ?
          AND MONTH(c.CASI_FECHA) = ?
          AND cl.CLIE_NOMBRE LIKE ?
          AND EXISTS (
              SELECT 1 FROM SIST_RASI r 
              WHERE r.RASI_ASIENTO = a.AASI_ASIENTO 
                AND r.RASI_CUENTA IN ('410101', '410102')
          )
        ORDER BY c.CASI_FECHA, a.AASI_ASIENTO, a.AASI_RENGLON_ASI
        """
        
        df = pd.read_sql(query, conn, params=[division, anio, mes, f'%{nombre_cliente}%'])
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def main():
    # ============================================================
    # CONFIGURACIÓN - CAMBIA ESTOS VALORES
    # ============================================================
    db_name = 'plataforma_rd'        # Base a consultar
    anio = 2026
    mes = 1                          # 1 = Enero
    cliente_buscar = 'ACAP'          # Nombre del cliente a depurar
    # ============================================================
    
    print(f"\n🔍 Buscando transacciones de '{cliente_buscar}' en {db_name} - {anio}-{mes:02d}...\n")
    
    df = get_detalle_cliente(db_name, anio, mes, cliente_buscar)
    
    if df.empty:
        print(f"❌ No se encontraron transacciones para '{cliente_buscar}'")
        return
    
    # Mostrar total general
    total_general = df['Importe_DL_Ajustado'].sum()
    print(f"💰 Total para '{cliente_buscar}': ${total_general:,.2f} USD")
    print(f"📊 Total de transacciones (filas): {len(df)}")
    
    # Verificar si hay asientos duplicados (mismo Asiento + Renglon_Asiento)
    duplicados = df[df.duplicated(subset=['Asiento', 'Renglon_Asiento'], keep=False)]
    if not duplicados.empty:
        print(f"\n⚠️ ADVERTENCIA: Hay {len(duplicados)} filas duplicadas (mismo Asiento + Renglon):")
        print(duplicados[['Asiento', 'Renglon_Asiento', 'Importe_DL_Ajustado']].to_string(index=False))
    
    # Mostrar detalle de todas las transacciones
    print(f"\n📋 Detalle de transacciones ({len(df)} registros):")
    
    columnas_mostrar = [
        'Fecha_Comprobante',
        'Asiento',
        'Renglon_Asiento',
        'Importe_DL_Ajustado',
        'Concepto1',
        'Concepto2',
        'Cliente'
    ]
    
    # Filtrar solo columnas que existen
    columnas_existentes = [col for col in columnas_mostrar if col in df.columns]
    df_mostrar = df[columnas_existentes]
    print(df_mostrar.to_string(index=False))
    
    # Exportar a CSV
    archivo_csv = f'detalle_{cliente_buscar}_{db_name}_{anio}_{mes:02d}.csv'
    df.to_csv(archivo_csv, index=False, encoding='utf-8-sig')
    print(f"\n✅ Detalle completo exportado a: {archivo_csv}")
    
    print("\n" + "="*60)
    print("🔍 CÓMO INTERPRETAR LOS RESULTADOS:")
    print("="*60)
    print("1. Si ves duplicados (mismo Asiento + Renglon), el problema persiste.")
    print("2. Si no hay duplicados, el importe total debería ser correcto.")
    print("3. Compara el total con tus registros reales para este cliente.")
    print("4. Si el total no coincide, revisa qué transacciones están incluidas.")
    print("="*60)

if __name__ == "__main__":
    main()