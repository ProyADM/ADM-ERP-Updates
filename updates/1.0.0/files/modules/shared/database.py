# modules/shared/database.py
# ============================================================
# BASE DE DATOS - SIDESYS ERP (CORREGIDO)
# ============================================================

import pyodbc
import sys
import logging
from flask import g
from config import SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD, BASES_DISPONIBLES, BASE_DEFAULT, SOCIEDAD_DEFAULT, SQL_ENCRYPT_ACTIVO

# Configurar logging
logger = logging.getLogger(__name__)

# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def _sql_literal(value):
    """Escapa un valor para SQL (solo usar cuando no se pueden usar parámetros)"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"

def get_db_context():
    """Obtiene el contexto actual de la base de datos"""
    try:
        server = g.db_server
        database = g.db_database
        division = g.division
        sucursal = g.sucursal
        return server, database, division, sucursal
    except (RuntimeError, AttributeError):
        return SQL_SERVER, BASE_DEFAULT, 5, 1

def set_contexto_base(base, sociedad=None):
    """Establece el contexto de la base de datos"""
    info = BASES_DISPONIBLES.get(base)
    if info is None:
        base = BASE_DEFAULT
        info = BASES_DISPONIBLES[base]
    
    g.db_database = base
    g.db_server = info.get("server") or SQL_SERVER
    g.db_username = info.get("user") or SQL_USERNAME
    g.db_password = info.get("password") or SQL_PASSWORD
    
    if "sociedades" in info:
        sociedad = sociedad or SOCIEDAD_DEFAULT
        soc_info = info["sociedades"].get(sociedad, info["sociedades"][SOCIEDAD_DEFAULT])
        g.division = soc_info["division"]
        g.sucursal = soc_info["sucursal"]
        g.sucursal_emp = soc_info.get("sucursal_emp", soc_info["sucursal"])
    else:
        g.division = info.get("division", 5)
        g.sucursal = info.get("sucursal", 1)
        # Sucursal empresa opcional (p.ej. RD: impresora 5 / empresa 4). Si no
        # está definida, coincide con la sucursal de impresión (comportamiento
        # histórico).
        g.sucursal_emp = info.get("sucursal_emp", g.sucursal)
    return base

def get_contexto_base():
    """Obtiene el contexto actual de la base de datos como diccionario"""
    try:
        return {
            'base': g.db_database,
            'server': g.db_server,
            'username': getattr(g, 'db_username', SQL_USERNAME),
            'division': g.division,
            'sucursal': g.sucursal
        }
    except (RuntimeError, AttributeError):
        return {
            'base': BASE_DEFAULT,
            'server': SQL_SERVER,
            'username': SQL_USERNAME,
            'division': 5,
            'sucursal': 1
        }

# ============================================================
# FUNCIÓN PRINCIPAL DE EJECUCIÓN SQL
# ============================================================

def run_sql(query, params=(), fetch=True, server_override=None, database_override=None, username_override=None, password_override=None, timeout=30):
    """
    Ejecuta una consulta SQL con parámetros (seguro contra inyección)
    
    Args:
        query: Consulta SQL con placeholders '?'
        params: Tupla de parámetros para la consulta
        fetch: Si debe devolver resultados
        server_override: Servidor alternativo
        database_override: Base de datos alternativa
        username_override: Usuario alternativo
        password_override: Contraseña alternativa
        timeout: Timeout de conexión en segundos
    
    Returns:
        Lista de diccionarios si fetch=True, None si fetch=False
    
    Raises:
        RuntimeError: Si hay error en la conexión o ejecución
    """
    try:
        # Resolver variables de conexión
        server = server_override if server_override not in (None, 'None') else getattr(g, 'db_server', SQL_SERVER)
        database = database_override if database_override not in (None, 'None') else getattr(g, 'db_database', BASE_DEFAULT)
        username = username_override if username_override not in (None, 'None') else getattr(g, 'db_username', SQL_USERNAME)
        password = password_override if password_override not in (None, 'None') else getattr(g, 'db_password', SQL_PASSWORD)

        # ✅ CORREGIDO: Validar parámetros de conexión
        if not server:
            raise RuntimeError("❌ Servidor SQL no definido. Revisa tu archivo .env")
        if not database:
            raise RuntimeError("❌ Base de datos no definida. Revisa tu archivo .env")
        if not username:
            raise RuntimeError("❌ Usuario SQL no definido. Revisa tu archivo .env")

        # Cadena de conexión para ODBC Driver
        conn_str = (
            f"DRIVER={{SQL Server}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
            + ("Encrypt=yes;" if SQL_ENCRYPT_ACTIVO else "")
        )
        
        conn = None
        try:
            # ✅ CORREGIDO: Timeout configurable
            conn = pyodbc.connect(conn_str, timeout=timeout)
            cursor = conn.cursor()
            
            # ✅ CORREGIDO: Validar que la consulta no esté vacía
            if not query or not query.strip():
                raise ValueError("Consulta SQL vacía")
            
            cursor.execute(query, params)
            
            if fetch:
                try:
                    # Los lotes multi-sentencia (p.ej. ajuste/transferencia: DML +
                    # BEGIN/COMMIT + SELECT final) dejan cursor.description en None
                    # porque pyodbc expone solo el PRIMER result set. Avanzar con
                    # nextset() hasta el primer set real; si nunca hay, la consulta
                    # no devuelve resultados (INSERT/UPDATE puro → []).
                    while cursor.description is None:
                        if not cursor.nextset():
                            break
                    if cursor.description is None:
                        conn.commit()
                        return []
                    columns = [column[0] for column in cursor.description]
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    conn.commit()
                    return results
                except pyodbc.ProgrammingError:
                    # Consulta no devuelve resultados (ej: INSERT sin SELECT)
                    conn.commit()
                    return []
            else:
                conn.commit()
                return None
                
        except pyodbc.OperationalError as e:
            # El detalle pyodbc (incluye SQL/estructura) SOLO al log del servidor.
            logger.error(f"[SQL ERROR de conexión] {database}: {e}")
            raise RuntimeError("Error de conexión a la base de datos")
        except pyodbc.IntegrityError as e:
            logger.error(f"[SQL ERROR de integridad] {database}: {e}")
            raise RuntimeError("Error de integridad de datos")
        except pyodbc.ProgrammingError as e:
            logger.error(f"[SQL ERROR de sintaxis] {database}: {e}")
            raise RuntimeError("Error en la consulta SQL")
        except pyodbc.Error as e:
            logger.error(f"[SQL ERROR] {database}: {e}")
            raise RuntimeError("Error ejecutando SQL")
        except Exception as e:
            logger.error(f"[SQL ERROR inesperado] {database}: {e}")
            raise RuntimeError("Error inesperado en la base de datos")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
                    
    except RuntimeError:
        # Re-lanzar errores ya formateados (sin detalles internos)
        raise
    except Exception as e:
        logger.error(f"[SQL ERROR crítico] {e}")
        raise RuntimeError("Error crítico en la base de datos")

def run_sql_db(database, query, params=(), fetch=True, server=None, username=None, password=None, timeout=30):
    """
    Ejecuta una consulta SQL en una base de datos específica
    
    Args:
        database: Nombre de la base de datos (DEBE estar en BASES_DISPONIBLES)
        query: Consulta SQL con placeholders '?'
        params: Tupla de parámetros
        fetch: Si debe devolver resultados
        server: Servidor (opcional)
        username: Usuario (opcional)
        password: Contraseña (opcional)
        timeout: Timeout de conexión
    
    Returns:
        Lista de diccionarios si fetch=True, None si fetch=False

    Raises:
        RuntimeError: Si la base no está en la whitelist o hay error
    """
    # 🔴 Validar base contra la whitelist (evita SSRF / inyección en
    # connection string por el parámetro `base` del request/Excel).
    if database not in BASES_DISPONIBLES:
        raise RuntimeError(
            f"Base de datos no permitida: '{database}'. "
            f"Bases válidas: {', '.join(BASES_DISPONIBLES.keys())}"
        )
    return run_sql(
        query, 
        params=params,
        fetch=fetch, 
        server_override=server, 
        database_override=database,
        username_override=username,
        password_override=password,
        timeout=timeout
    )