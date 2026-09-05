# modules/reportes/services/ventas_manuales_service.py
# ============================================================
# SERVICIO: VENTAS MANUALES (CRUD, importación, listado)
# AHORA GUARDA CADA MONEDA COMO UNA FILA INDEPENDIENTE
# TODAS LAS OPERACIONES USAN LA BASE ACTIVA (TABLA CENTRALIZADA)
# ============================================================

import pandas as pd
import logging
from datetime import datetime
from .utils import get_db_connection, get_db_connection_base, asegurar_tabla_ventas_manuales, obtener_cotizacion_por_mes

logger = logging.getLogger(__name__)

def convertir_ps_a_usd(base, pais, fecha_registro, importe_ps):
    """
    Convierte un monto en pesos (PS) a USD usando la cotización de la fecha de registro.
    Si no hay cotización para esa fecha, busca la última cotización anterior disponible.
    Retorna el monto en USD o None si no se pudo convertir.
    """
    if importe_ps is None or importe_ps <= 0:
        return None
    if not fecha_registro:
        return None

    try:
        # Parsear fecha
        if isinstance(fecha_registro, str):
            fecha_dt = datetime.strptime(fecha_registro, '%Y-%m-%d')
        else:
            fecha_dt = fecha_registro

        anio = fecha_dt.year
        mes = fecha_dt.month

        # Obtener cotización de la fecha en la base correspondiente
        cotizacion = obtener_cotizacion_por_mes(anio, mes, base_referencia=base)
        if cotizacion is not None and cotizacion > 0:
            importe_usd = importe_ps / cotizacion
            logger.info(f"✅ Conversión PS→USD: {importe_ps} PS / {cotizacion} = {importe_usd} USD (base: {base}, fecha: {fecha_registro})")
            return importe_usd
        else:
            logger.warning(f"⚠️ No se encontró cotización para {base} en {fecha_registro}. No se pudo convertir PS a USD.")
            return None
    except Exception as e:
        logger.error(f"Error convirtiendo PS a USD: {e}")
        return None

def listar_ventas_manuales(base=None, anio=None, mes=None):
    """Lista registros de VENTAS_MANUALES con filtros opcionales"""
    try:
        asegurar_tabla_ventas_manuales()
        conn, _ = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM VENTAS_MANUALES WHERE 1=1"
        params = []
        if base:
            query += " AND base = ?"
            params.append(base)
        if anio:
            query += " AND anio = ?"
            params.append(int(anio))
        if mes:
            query += " AND mes = ?"
            params.append(int(mes))
        query += " ORDER BY fecha_registro DESC, id DESC"
        cursor.execute(query, params)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        result = [dict(zip(columns, row)) for row in rows]
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Error listando ventas manuales: {e}")
        return []

def crear_venta_manual(base, sociedad, anio, mes, pais, importe_usd, importe_ps, fecha_registro, comentario='', usuario='anonimo', centro_costo=None):
    """
    Inserta una o dos ventas manuales:
    - Si importe_usd > 0: inserta una fila con ese valor (importe_ps = 0)
    - Si importe_ps > 0: lo convierte a USD e inserta otra fila con el resultado (importe_ps = original)
    """
    try:
        asegurar_tabla_ventas_manuales()

        importe_usd_original = importe_usd or 0
        importe_ps_original = importe_ps or 0

        if importe_usd_original == 0 and importe_ps_original == 0:
            return {'success': False, 'error': 'Debe ingresar al menos un importe (USD o PS)'}

        conn, _ = get_db_connection()
        cursor = conn.cursor()
        insertados = 0
        errores = []

        # 1. Insertar parte en USD (si existe)
        if importe_usd_original > 0:
            try:
                cursor.execute("""
                    INSERT INTO VENTAS_MANUALES 
                        (base, sociedad, anio, mes, pais, centro_costo, importe_usd, importe_ps, fecha_registro, comentario, usuario)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (base, sociedad, anio, mes, pais, centro_costo, importe_usd_original, 0, fecha_registro, comentario, usuario))
                insertados += 1
                logger.info(f"✅ Insertada venta manual en USD: {importe_usd_original} USD")
            except Exception as e:
                errores.append(f"Error insertando USD: {str(e)}")

        # 2. Insertar parte en PS (si existe) → convertir a USD
        if importe_ps_original > 0:
            usd_convertido = convertir_ps_a_usd(base, pais, fecha_registro, importe_ps_original)
            if usd_convertido is not None and usd_convertido > 0:
                try:
                    cursor.execute("""
                        INSERT INTO VENTAS_MANUALES 
                            (base, sociedad, anio, mes, pais, centro_costo, importe_usd, importe_ps, fecha_registro, comentario, usuario)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (base, sociedad, anio, mes, pais, centro_costo, usd_convertido, importe_ps_original, fecha_registro, comentario, usuario))
                    insertados += 1
                    logger.info(f"✅ Insertada venta manual en PS convertida: {importe_ps_original} PS → {usd_convertido} USD")
                except Exception as e:
                    errores.append(f"Error insertando PS convertido: {str(e)}")
            else:
                errores.append(f"No se pudo convertir PS a USD. El monto en PS se omite.")

        conn.commit()
        conn.close()

        if insertados == 0:
            return {'success': False, 'error': 'No se pudo insertar ninguna venta manual. ' + ' '.join(errores)}
        else:
            return {
                'success': True,
                'message': f'Venta(s) manual(es) creada(s): {insertados} registro(s) insertado(s)',
                'insertados': insertados,
                'errores': errores if errores else None
            }

    except Exception as e:
        logger.error(f"Error creando venta manual: {e}")
        return {'success': False, 'error': str(e)}

def eliminar_venta_manual(venta_id):
    """Elimina una venta manual por ID"""
    try:
        asegurar_tabla_ventas_manuales()
        conn, _ = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM VENTAS_MANUALES WHERE id = ?", (venta_id,))
        conn.commit()
        conn.close()
        return {'success': True, 'message': 'Eliminada'}
    except Exception as e:
        logger.error(f"Error eliminando venta manual: {e}")
        return {'success': False, 'error': str(e)}

def importar_ventas_manuales(df, usuario='anonimo'):
    """
    Importa múltiples ventas manuales desde un DataFrame (pandas)
    Cada fila puede generar 1 o 2 registros (uno por moneda).
    """
    try:
        asegurar_tabla_ventas_manuales()
        # Validar columnas
        required = ['base', 'anio', 'mes', 'pais', 'fecha_registro']
        missing = [c for c in required if c not in df.columns]
        if missing:
            return {'success': False, 'error': f'Faltan columnas: {", ".join(missing)}'}

        if 'importe_usd' not in df.columns:
            df['importe_usd'] = 0
        if 'importe_ps' not in df.columns:
            df['importe_ps'] = 0

        insertados = 0
        errores = []

        # Usar una conexión única a la base activa para todos los inserts
        conn, _ = get_db_connection()
        cursor = conn.cursor()

        for idx, row in df.iterrows():
            base = row['base']
            anio = int(row['anio'])
            mes = int(row['mes'])
            pais = row['pais']
            importe_usd_original = float(row['importe_usd']) if pd.notna(row['importe_usd']) else 0
            importe_ps_original = float(row['importe_ps']) if pd.notna(row['importe_ps']) else 0
            fecha_registro = pd.to_datetime(row['fecha_registro']).strftime('%Y-%m-%d')
            sociedad = row.get('sociedad') if pd.notna(row.get('sociedad')) else None
            centro_costo = row.get('centro_costo') if pd.notna(row.get('centro_costo')) else None
            comentario = row.get('comentario') if pd.notna(row.get('comentario')) else ''

            if importe_usd_original == 0 and importe_ps_original == 0:
                errores.append(f"Fila {idx+2}: Ambos importes son 0, se omite.")
                continue

            fila_insertados = 0

            # 1. Insertar parte en USD (si existe)
            if importe_usd_original > 0:
                try:
                    cursor.execute("""
                        INSERT INTO VENTAS_MANUALES 
                            (base, sociedad, anio, mes, pais, centro_costo, importe_usd, importe_ps, fecha_registro, comentario, usuario)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (base, sociedad, anio, mes, pais, centro_costo, importe_usd_original, 0, fecha_registro, comentario, usuario))
                    fila_insertados += 1
                except Exception as e:
                    errores.append(f"Fila {idx+2} (USD): {str(e)}")

            # 2. Insertar parte en PS (si existe)
            if importe_ps_original > 0:
                usd_convertido = convertir_ps_a_usd(base, pais, fecha_registro, importe_ps_original)
                if usd_convertido is not None and usd_convertido > 0:
                    try:
                        cursor.execute("""
                            INSERT INTO VENTAS_MANUALES 
                                (base, sociedad, anio, mes, pais, centro_costo, importe_usd, importe_ps, fecha_registro, comentario, usuario)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (base, sociedad, anio, mes, pais, centro_costo, usd_convertido, importe_ps_original, fecha_registro, comentario, usuario))
                        fila_insertados += 1
                    except Exception as e:
                        errores.append(f"Fila {idx+2} (PS): {str(e)}")
                else:
                    errores.append(f"Fila {idx+2}: No se pudo convertir PS a USD. Se omite.")

            insertados += fila_insertados

        conn.commit()
        conn.close()

        return {
            'success': True,
            'message': f'Importación completada: {insertados} registros insertados.',
            'insertados': insertados,
            'errores': errores if errores else None
        }

    except Exception as e:
        logger.error(f"Error importando ventas manuales: {e}")
        return {'success': False, 'error': str(e)}