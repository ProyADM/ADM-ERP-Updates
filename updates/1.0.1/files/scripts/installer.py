# installer.py
# ============================================================
# INSTALADOR SIDESYS ERP - CON SELECCIÓN DE ARCHIVO
# ============================================================

import os
import sys
import shutil
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# ============================================================
# IMPORTAR CRYPTO UTILS
# ============================================================

try:
    from crypto_utils import desencriptar_env, obtener_clave_maestra
except ImportError:
    print("❌ No se encontró crypto_utils.py")
    print("   Asegúrate de que el archivo esté en el mismo directorio")
    sys.exit(1)

# ============================================================
# CONFIGURACIÓN
# ============================================================

APP_NAME = "SidesysERP"
INSTALL_DIR = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), APP_NAME)
ENV_FILE = os.path.join(INSTALL_DIR, ".env.local")
USERS_FILE = os.path.join(INSTALL_DIR, "users.json")
VERSION_FILE = os.path.join(INSTALL_DIR, "version.txt")

# ============================================================
# FUNCIONES PARA SELECCIONAR ARCHIVO
# ============================================================

def seleccionar_archivo_gui():
    """
    Abre un diálogo gráfico para seleccionar el archivo .env.encrypted
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        file_path = filedialog.askopenfilename(
            title="🔐 Seleccionar archivo de configuración encriptado",
            filetypes=[
                ("Archivos encriptados", "*.encrypted"),
                ("Todos los archivos", "*.*")
            ],
            defaultextension=".encrypted"
        )
        
        root.destroy()
        return file_path if file_path else None
    except:
        return None

def seleccionar_archivo_consola():
    """
    Solicita la ruta del archivo por consola
    """
    print("\n" + "=" * 60)
    print("  🔐 SELECCIONA EL ARCHIVO DE CONFIGURACIÓN")
    print("=" * 60)
    print()
    print("  Inserta el USB que contiene el archivo .env.encrypted")
    print("  Luego ingresa la ruta completa del archivo")
    print()
    print("  Ejemplo: E:\\env_config\\sidesys.env.encrypted")
    print()
    
    while True:
        ruta = input("  Ruta del archivo: ").strip()
        
        if not ruta:
            print("  ❌ Debes ingresar una ruta")
            continue
        
        if os.path.exists(ruta):
            if ruta.endswith('.encrypted'):
                return ruta
            else:
                print("  ⚠️ El archivo debe tener extensión .encrypted")
        else:
            print("  ❌ El archivo no existe. Verifica la ruta.")

def seleccionar_archivo():
    """
    Intenta primero con GUI, si falla usa consola
    """
    # Intentar con GUI
    archivo = seleccionar_archivo_gui()
    if archivo:
        return archivo
    
    # Fallback a consola
    return seleccionar_archivo_consola()

# ============================================================
# FUNCIONES DE INSTALACIÓN
# ============================================================

def crear_directorios():
    """Crea los directorios necesarios"""
    for path in [INSTALL_DIR]:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            print(f"📁 Creado directorio: {path}")
    return True

def verificar_dependencias():
    """Verifica que las dependencias estén instaladas"""
    try:
        import cryptography
        import bcrypt
        return True
    except ImportError as e:
        print(f"❌ Dependencia faltante: {e}")
        print("   Ejecuta: pip install cryptography bcrypt")
        return False

def instalar_dependencias():
    """Instala las dependencias necesarias"""
    print("📦 Instalando dependencias...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", 
                       "cryptography", "bcrypt"], 
                      capture_output=True, check=True)
        print("✅ Dependencias instaladas")
        return True
    except Exception as e:
        print(f"❌ Error instalando dependencias: {e}")
        return False

def desencriptar_y_configurar(encrypted_file: str) -> bool:
    """
    Desencripta el archivo y configura el sistema
    """
    print("\n🔐 Desencriptando configuración...")
    
    # Obtener clave maestra
    password = obtener_clave_maestra()
    # ✅ CORREGIDO: No imprimir la clave
    print(f"   ✅ Clave maestra cargada")
    
    # Desencriptar en memoria
    temp_env = os.path.join(tempfile.gettempdir(), "sidesys_env_temp.env")
    
    if not desencriptar_env(encrypted_file, temp_env, password):
        print("❌ Error al desencriptar")
        return False
    
    # Leer el contenido desencriptado
    with open(temp_env, 'r', encoding='utf-8') as f:
        env_content = f.read()
    
    # Eliminar archivo temporal INMEDIATAMENTE
    os.remove(temp_env)
    print("🗑️ Archivo temporal eliminado")
    
    # Guardar .env.local (encriptado en disco)
    from crypto_utils import derivar_clave_maestra
    from cryptography.fernet import Fernet
    
    key = derivar_clave_maestra(password)
    fernet = Fernet(key)
    
    encrypted_env = fernet.encrypt(env_content.encode())
    
    with open(ENV_FILE, 'wb') as f:
        f.write(encrypted_env)
    
    print(f"✅ .env.local guardado encriptado: {ENV_FILE}")
    return True

def crear_usuario_admin():
    """Crea el usuario administrador por defecto"""
    try:
        import bcrypt
        import json
        
        password_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        
        users = {
            "admin": {
                "username": "admin",
                "password": password_hash,
                "rol": "admin",
                "nombre": "Administrador",
                "email": "admin@sidesys.com",
                "creado": datetime.now().isoformat(),
                "activo": True
            }
        }
        
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Usuario admin creado: admin / admin123")
        print("   ⚠️ CAMBIA LA CONTRASEÑA EN LA PRIMERA EJECUCIÓN")
        return True
    except Exception as e:
        print(f"❌ Error creando usuario admin: {e}")
        return False

def guardar_version():
    """Guarda la versión del instalador"""
    version = "1.0.0"
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(f"Versión: {version}\n")
        f.write(f"Instalado: {datetime.now().isoformat()}\n")
        f.write(f"Host: {os.environ.get('COMPUTERNAME', 'UNKNOWN')}\n")
    print(f"✅ Versión guardada: {version}")

def mostrar_resumen_instalacion():
    """Muestra resumen de la instalación"""
    print("\n" + "=" * 60)
    print("  ✅ INSTALACIÓN COMPLETA")
    print("=" * 60)
    print()
    print(f"  📁 Directorio de datos: {INSTALL_DIR}")
    print(f"  🔑 Usuario admin: admin")
    print(f"  🔑 Contraseña admin: admin123")
    print()
    print("  🔒 DATOS SEGUROS:")
    print("  • El archivo .env.encrypted NO quedó guardado")
    print("  • El .env.local está ENCRIPTADO en disco")
    print("  • La clave maestra está en el instalador")
    print()
    print("  ⚠️ CAMBIA LA CONTRASEÑA DEL ADMIN EN LA PRIMERA EJECUCIÓN")
    print("=" * 60)

# ============================================================
# FUNCIÓN PRINCIPAL - CORREGIDO
# ============================================================

def main():
    print("\n" + "=" * 60)
    print("  🚀 INSTALADOR SIDESYS ERP")
    print("=" * 60)
    print()
    
    # Verificar dependencias
    if not verificar_dependencias():
        print("\n⚠️ Faltan dependencias. ¿Instalar ahora?")
        respuesta = input("  (S/N): ").strip().upper()
        if respuesta == 'S':
            if not instalar_dependencias():
                print("❌ No se pudieron instalar las dependencias")
                input("\nPresiona Enter para salir...")
                sys.exit(1)
        else:
            print("❌ Instalación cancelada")
            sys.exit(1)
    
    # Crear directorios
    crear_directorios()
    
    print("\n" + "=" * 60)
    print("  🔐 CONFIGURANDO SEGURIDAD")
    print("=" * 60)
    print()
    
    # ✅ CORREGIDO: No imprimir la clave
    master_key = obtener_clave_maestra()
    print("  ✅ Clave maestra cargada")
    print("  ℹ️ Esta clave funciona en TODAS las instalaciones")
    print()
    
    # Seleccionar archivo encriptado
    print("📁 Selecciona el archivo .env.encrypted")
    print("   (Debe estar en el USB que te proporcionó el administrador)")
    print()
    
    encrypted_file = seleccionar_archivo()
    
    if not encrypted_file:
        print("\n❌ No se seleccionó ningún archivo")
        input("\nPresiona Enter para salir...")
        sys.exit(1)
    
    print(f"\n✅ Archivo seleccionado: {encrypted_file}")
    
    # Desencriptar y configurar
    if not desencriptar_y_configurar(encrypted_file):
        print("\n❌ Error al desencriptar la configuración")
        print("   Verifica que el archivo sea válido")
        input("\nPresiona Enter para salir...")
        sys.exit(1)
    
    # Crear usuario admin
    crear_usuario_admin()
    
    # Guardar versión
    guardar_version()
    
    # Mostrar resumen
    mostrar_resumen_instalacion()
    
    print("\n🚀 Instalación completada exitosamente")
    print("   Retira el USB y guárdalo en un lugar seguro")
    print()
    input("Presiona Enter para salir...")

if __name__ == "__main__":
    main()