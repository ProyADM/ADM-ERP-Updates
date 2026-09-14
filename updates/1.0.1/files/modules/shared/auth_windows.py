# modules/shared/auth_windows.py
# ============================================================
# AUTENTICACIÓN DE WINDOWS - SIDESYS ERP (VERSIÓN CORREGIDA)
# ============================================================

import os
import sys
import subprocess
from datetime import datetime, timedelta
from flask import session, g

# ============================================================
# CONFIGURACIÓN (CORREGIDO)
# ============================================================

SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError(
        "❌ JWT_SECRET_KEY no definida en variables de entorno.\n"
        "   Agrega JWT_SECRET_KEY a .env.local o .env.production\n"
        "   Ejemplo: JWT_SECRET_KEY=tu_clave_secreta_2026"
    )
JWT_EXPIRATION = 24  # Horas

# ============================================================
# FUNCIONES DE VERIFICACIÓN DE DEPENDENCIAS
# ============================================================

def _tiene_jwt():
    try:
        import jwt
        return True
    except ImportError:
        return False

def _tiene_bcrypt():
    try:
        import bcrypt
        return True
    except ImportError:
        return False

def _tiene_win32():
    try:
        import win32security
        import win32api
        import win32con
        return True
    except ImportError:
        return False

def _tiene_ldap():
    try:
        import ldap3
        return True
    except ImportError:
        return False

# ============================================================
# 1. VERIFICACIÓN DE CREDENCIALES DE WINDOWS
# ============================================================

def verificar_credenciales_windows(username, password):
    """
    Verifica credenciales de Windows usando múltiples métodos:
    1. LDAP (si está en dominio)
    2. Win32 API (usuario local)
    3. Net Use (fallback)
    
    RETURNS: (success, message, user_info)
    """
    username = username.strip()
    
    # 1. Intentar con LDAP (dominio)
    success, msg, user_info = verificar_ldap(username, password)
    if success:
        return True, msg, user_info
    
    # 2. Intentar con Win32 API (local)
    success, msg, user_info = verificar_local_win32(username, password)
    if success:
        return True, msg, user_info
    
    # 3. Fallback: Net Use
    success, msg, user_info = verificar_net_use(username, password)
    if success:
        return True, msg, user_info
    
    return False, "Credenciales inválidas", None


# ============================================================
# 2. VERIFICACIÓN LDAP (ACTIVE DIRECTORY)
# ============================================================

def verificar_ldap(username, password):
    """
    Verifica credenciales contra Active Directory.
    Con timeout de socket corto: si el dominio no está accesible, se cae
    rápido al fallback local (Win32 / net use) en vez de esperar el default.
    """
    if not _tiene_ldap():
        return False, "LDAP no disponible", None

    import socket as _socket
    _timeout_prev = _socket.getdefaulttimeout()
    try:
        _socket.setdefaulttimeout(4)  # segundos para connect/search LDAP
        import ldap3

        server = ldap3.Server('domain.sidesys.com', get_info=ldap3.ALL)
        conn = ldap3.Connection(server, user=f'{username}@domain.sidesys.com', password=password)

        if conn.bind():
            conn.search(
                search_base='DC=domain,DC=sidesys,DC=com',
                search_filter=f'(sAMAccountName={username})',
                attributes=['displayName', 'mail', 'memberOf']
            )

            if conn.entries:
                user_info = {
                    'username': username,
                    'nombre': str(conn.entries[0].displayName) if conn.entries[0].displayName else username,
                    'email': str(conn.entries[0].mail) if conn.entries[0].mail else None,
                    'groups': [str(g) for g in conn.entries[0].memberOf] if conn.entries[0].memberOf else [],
                    'auth_type': 'ldap'
                }
                return True, "Autenticado vía LDAP", user_info

        return False, "Usuario no encontrado en LDAP", None
    except Exception as e:
        return False, f"Error LDAP: {str(e)}", None
    finally:
        _socket.setdefaulttimeout(_timeout_prev)


# ============================================================
# 3. VERIFICACIÓN LOCAL (WIN32 API)
# ============================================================

def verificar_local_win32(username, password):
    """
    Verifica credenciales de usuario local de Windows
    """
    if not _tiene_win32():
        return False, "Win32 API no disponible", None
    
    try:
        import win32security
        import win32con
        
        hToken = win32security.LogonUser(
            username,
            None,
            password,
            win32con.LOGON32_LOGON_INTERACTIVE,
            win32con.LOGON32_PROVIDER_DEFAULT
        )
        
        if hToken:
            user_info = {
                'username': username,
                'nombre': username,
                'email': None,
                'groups': [],
                'auth_type': 'local_win32'
            }
            return True, "Autenticado vía Win32 API", user_info
        
        return False, "Usuario local no encontrado", None
    except Exception as e:
        return False, f"Error Win32: {str(e)}", None


# ============================================================
# 4. VERIFICACIÓN NET USE (FALLBACK) - CORREGIDO
# ============================================================

def verificar_net_use(username, password):
    """
    Verifica credenciales usando Net Use (fallback)
    """
    try:
        clean_username = username.replace('\\', '\\\\')
        
        # ✅ CORREGIDO: Usar shell=False
        cmd = ['net', 'use', '\\\\localhost\\IPC$', f'/user:{clean_username}', password]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # ✅ CORREGIDO: Usar shell=False
            subprocess.run(['net', 'use', '\\\\localhost\\IPC$', '/delete', '/yes'], 
                          capture_output=True)
            user_info = {
                'username': username,
                'nombre': username,
                'email': None,
                'groups': [],
                'auth_type': 'net_use'
            }
            return True, "Autenticado vía Net Use", user_info
        
        return False, "Falló autenticación con Net Use", None
    except Exception as e:
        return False, f"Error Net Use: {str(e)}", None


# ============================================================
# 5. OBTENER USUARIO ACTUAL DE WINDOWS - CORREGIDO
# ============================================================

def get_current_windows_user():
    """
    Obtiene el usuario actual de Windows sin pedir contraseña
    """
    # Método 1: Win32 API
    if _tiene_win32():
        try:
            import win32security
            import win32api
            
            token = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(),
                win32security.TOKEN_QUERY
            )
            user_info = win32security.GetTokenInformation(
                token,
                win32security.TokenUser
            )
            username = win32security.LookupAccountSid(None, user_info[0])[0]
            return username
        except:
            pass
    
    # Método 2: Variables de entorno
    username = os.environ.get('USERNAME')
    if username:
        return username
    
    # Método 3: Whoami - CORREGIDO
    try:
        result = subprocess.run(['whoami'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\\')[-1]
    except:
        pass
    
    return None


# ============================================================
# 6. JWT TOKEN
# ============================================================

def generar_jwt(username, rol, user_info=None):
    """
    Genera un JWT token para la sesión
    """
    if not _tiene_jwt():
        raise ImportError("pyjwt no está instalado. Ejecuta: pip install pyjwt")
    
    import jwt
    
    payload = {
        'username': username,
        'rol': rol,
        'nombre': user_info.get('nombre', username) if user_info else username,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION),
        'iat': datetime.utcnow(),
        'auth_type': user_info.get('auth_type', 'windows') if user_info else 'windows'
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token


def verificar_jwt(token):
    """
    Verifica un JWT token
    """
    if not _tiene_jwt():
        return False, "pyjwt no instalado"
    
    import jwt
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return True, payload
    except jwt.ExpiredSignatureError:
        return False, "Token expirado"
    except jwt.InvalidTokenError:
        return False, "Token inválido"
    except Exception as e:
        return False, f"Error: {str(e)}"


# ============================================================
# 7. SESSION MANAGEMENT
# ============================================================

def crear_sesion(username, rol, user_info=None):
    """
    Crea una sesión segura con JWT
    """
    token = generar_jwt(username, rol, user_info)
    
    session['username'] = username
    session['rol'] = rol
    session['nombre'] = user_info.get('nombre', username) if user_info else username
    session['jwt'] = token
    session['auth_type'] = user_info.get('auth_type', 'windows') if user_info else 'windows'
    session['created'] = datetime.utcnow().isoformat()
    
    return token


def validar_sesion():
    """
    Valida la sesión actual
    """
    if 'jwt' not in session:
        return False, "No hay sesión activa"
    
    success, payload = verificar_jwt(session['jwt'])
    if not success:
        session.clear()
        return False, payload
    
    g.username = payload['username']
    g.rol = payload['rol']
    g.nombre = payload['nombre']
    
    return True, payload


def cerrar_sesion():
    """
    Cierra la sesión actual
    """
    session.clear()
    return True


# ============================================================
# 8. VERIFICAR DISPONIBILIDAD (PARA PRUEBAS)
# ============================================================

def check_auth_availability():
    """
    Verifica qué métodos de autenticación están disponibles
    """
    return {
        'jwt': _tiene_jwt(),
        'bcrypt': _tiene_bcrypt(),
        'ldap': _tiene_ldap(),
        'win32': _tiene_win32(),
        'windows_user': get_current_windows_user() is not None
    }