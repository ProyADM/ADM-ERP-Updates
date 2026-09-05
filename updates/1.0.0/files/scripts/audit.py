# audit.py
# ============================================================
# AUDITORÍA AUTOMÁTICA DE SEGURIDAD - SIDESYS ERP
# ============================================================
# Ejecuta: python audit.py
# Genera: informe_auditoria_YYYYMMDD_HHMMSS.json
# ============================================================

import os
import re
import json
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Directorios a excluir
EXCLUIR_DIRECTORIOS = [
    'venv', '__pycache__', '.git', 'node_modules', 
    'build', 'dist', 'backups', 'updates',
    'tesseract', 'data', 'logs'
]

# Archivos a excluir
EXCLUIR_ARCHIVOS = [
    '*.pyc', '*.pyo', '*.pyd', '.DS_Store',
    '*.log', '*.tmp', '*.swp', '*.bak',
    '*.zip', '*.tar.gz', '*.rar'
]

# Extensiones a analizar
EXTENSIONES_ANALIZAR = [
    '.py', '.js', '.html', '.css', '.json', '.txt', '.md',
    '.env', '.conf', '.cfg', '.ini', '.yml', '.yaml', '.sh', '.bat'
]

# ============================================================
# PATRONES DE BÚSQUEDA (VULNERABILIDADES)
# ============================================================

PATRONES_CRITICOS = {
    'hardcoded_password': {
        'patron': r'(password|passwd|pwd)\s*=\s*["\']([^"\']+)["\']',
        'nivel': 'CRITICO',
        'descripcion': 'Contraseña hardcodeada en el código'
    },
    'hardcoded_secret': {
        'patron': r'(secret|SECRET|key|KEY|token|TOKEN)\s*=\s*["\']([^"\']+)["\']',
        'nivel': 'CRITICO',
        'descripcion': 'Clave/Secreto hardcodeado en el código'
    },
    'debug_true': {
        'patron': r'debug\s*=\s*True',
        'nivel': 'CRITICO',
        'descripcion': 'Debug activado en producción'
    },
    'sql_injection': {
        'patron': r'execute\s*\(\s*["\'].*?\+\s*.*?["\']',
        'nivel': 'CRITICO',
        'descripcion': 'Posible SQL Injection (concatenación)'
    },
    
    'subprocess_shell': {
        'patron': r'subprocess\.(Popen|call|run|check_output)\s*\([^)]*shell\s*=\s*True',
        'nivel': 'ALTO',
        'descripcion': 'subprocess con shell=True - posible inyección de comandos'
    },
    'pickle_load': {
        'patron': r'pickle\.loads?',
        'nivel': 'ALTO',
        'descripcion': 'Uso de pickle - posible ejecución de código arbitrario'
    },
    'cors_all': {
        'patron': r'CORS\s*\([^)]*origins\s*=\s*["\']\*["\']',
        'nivel': 'ALTO',
        'descripcion': 'CORS permite cualquier origen (*)'
    },
    'session_cookie': {
        'patron': r'SESSION_COOKIE_HTTPONLY\s*=\s*False',
        'nivel': 'ALTO',
        'descripcion': 'Cookies de sesión sin HttpOnly'
    },
    'insecure_cookie': {
        'patron': r'SESSION_COOKIE_SECURE\s*=\s*False',
        'nivel': 'ALTO',
        'descripcion': 'Cookies de sesión sin Secure (no HTTPS)'
    },
}

PATRONES_MEDIO = {
    'env_file': {
        'patron': r'\.env(\.local|\.production|\.staging)?',
        'nivel': 'MEDIO',
        'descripcion': 'Archivo .env presente - asegurar que está en .gitignore'
    },
    'debug_print': {
        'patron': r'(print|console\.log)\s*\(.*?(password|pass|pwd|secret|key|token)',
        'nivel': 'MEDIO',
        'descripcion': 'Impresión de datos sensibles en logs'
    },
    'try_except_broad': {
        'patron': r'except\s*:',
        'nivel': 'MEDIO',
        'descripcion': 'Excepción genérica (except:) - oculta errores'
    },
    'deprecated_module': {
        'patron': r'import\s+(cgi|cgitb|imp|distutils|smtpd)',
        'nivel': 'MEDIO',
        'descripcion': 'Módulo deprecado o inseguro importado'
    },
    'http_url': {
        'patron': r'http://[^"\'\s]+',
        'nivel': 'MEDIO',
        'descripcion': 'URL HTTP (no seguro) en el código'
    },
}

PATRONES_BAJO = {
    'no_docstring': {
        'patron': r'def\s+\w+\s*\([^)]*\)\s*:\s*(?!#)',
        'nivel': 'BAJO',
        'descripcion': 'Función sin docstring'
    },
    'long_function': {
        'patron': None,  # Procesamiento especial
        'nivel': 'BAJO',
        'descripcion': 'Función demasiado larga (> 50 líneas)'
    },
    'commented_code': {
        'patron': r'^#\s*(def|class|if|for|while|import)',
        'nivel': 'BAJO',
        'descripcion': 'Código comentado - limpiar'
    },
}

# ============================================================
# FUNCIONES DE AUDITORÍA
# ============================================================

class AuditoriaSeguridad:
    def __init__(self, directorio_raiz: str = "."):
        self.directorio_raiz = Path(directorio_raiz).resolve()
        self.resultados = {
            'metadata': {
                'fecha': datetime.now().isoformat(),
                'directorio': str(self.directorio_raiz),
                'version': '1.0.0'
            },
            'resumen': {
                'total_archivos': 0,
                'archivos_analizados': 0,
                'archivos_excluidos': 0,
                'vulnerabilidades_criticas': 0,
                'vulnerabilidades_altas': 0,
                'vulnerabilidades_medias': 0,
                'vulnerabilidades_bajas': 0
            },
            'estructura': {},
            'archivos_sensibles': [],
            'vulnerabilidades': [],
            'archivos_ignorados': [],
            'recomendaciones': [],
            'archivos_por_extension': {},
            'lineas_totales': 0
        }
    
    def _debe_excluir(self, ruta: Path) -> bool:
        """Verifica si el archivo o directorio debe ser excluido"""
        # Verificar directorios excluidos
        for excl in EXCLUIR_DIRECTORIOS:
            if excl in str(ruta):
                return True
        
        # Verificar extensiones excluidas
        for excl in EXCLUIR_ARCHIVOS:
            if ruta.match(excl):
                return True
        
        return False
    
    def _extension_permitida(self, ruta: Path) -> bool:
        """Verifica si la extensión del archivo debe ser analizada"""
        # Siempre analizar archivos sin extensión que sean relevantes
        if ruta.name in ['Dockerfile', 'docker-compose.yml', 'Makefile', '.gitignore']:
            return True
            
        for ext in EXTENSIONES_ANALIZAR:
            if ruta.suffix.lower() == ext or ruta.name.endswith(ext):
                return True
        return False
    
    def _analizar_archivo(self, ruta: Path) -> Dict:
        """Analiza un archivo en busca de vulnerabilidades"""
        resultados = {
            'archivo': str(ruta.relative_to(self.directorio_raiz)),
            'tamanio': ruta.stat().st_size,
            'extension': ruta.suffix,
            'hash': hashlib.md5(ruta.read_bytes()).hexdigest(),
            'vulnerabilidades': [],
            'lineas': 0,
            'funciones': []
        }
        
        try:
            contenido = ruta.read_text(encoding='utf-8', errors='ignore')
            lineas = contenido.split('\n')
            resultados['lineas'] = len(lineas)
            self.resultados['lineas_totales'] += len(lineas)
            
            # Contar archivos por extensión
            ext = ruta.suffix or 'sin_extension'
            if ext not in self.resultados['archivos_por_extension']:
                self.resultados['archivos_por_extension'][ext] = 0
            self.resultados['archivos_por_extension'][ext] += 1
            
            # Buscar vulnerabilidades críticas
            for nombre, patron_info in PATRONES_CRITICOS.items():
                patron = patron_info['patron']
                matches = []
                for i, linea in enumerate(lineas, 1):
                    if re.search(patron, linea, re.IGNORECASE):
                        matches.append({
                            'linea': i,
                            'texto': linea.strip()[:100]
                        })
                
                if matches:
                    resultados['vulnerabilidades'].append({
                        'tipo': nombre,
                        'nivel': patron_info['nivel'],
                        'descripcion': patron_info['descripcion'],
                        'ocurrencias': matches
                    })
            
            # Buscar vulnerabilidades medias
            for nombre, patron_info in PATRONES_MEDIO.items():
                patron = patron_info['patron']
                matches = []
                for i, linea in enumerate(lineas, 1):
                    if re.search(patron, linea, re.IGNORECASE):
                        matches.append({
                            'linea': i,
                            'texto': linea.strip()[:100]
                        })
                
                if matches:
                    resultados['vulnerabilidades'].append({
                        'tipo': nombre,
                        'nivel': patron_info['nivel'],
                        'descripcion': patron_info['descripcion'],
                        'ocurrencias': matches
                    })
            
            # Buscar funciones (para análisis de complejidad)
            funciones = []
            for i, linea in enumerate(lineas, 1):
                if re.match(r'^\s*def\s+(\w+)\s*\(', linea):
                    nombre_func = re.search(r'def\s+(\w+)', linea)
                    if nombre_func:
                        funciones.append({
                            'nombre': nombre_func.group(1),
                            'linea': i
                        })
            
            resultados['funciones'] = funciones
            
            # Archivos sensibles
            if '.env' in ruta.name:
                self.resultados['archivos_sensibles'].append({
                    'archivo': str(ruta.relative_to(self.directorio_raiz)),
                    'razon': 'Archivo de configuración .env'
                })
            
            if ruta.suffix in ['.pem', '.key', '.crt', '.csr']:
                self.resultados['archivos_sensibles'].append({
                    'archivo': str(ruta.relative_to(self.directorio_raiz)),
                    'razon': 'Archivo de clave/certificado'
                })
            
            if ruta.suffix == '.db' or ruta.name.endswith('.sqlite'):
                self.resultados['archivos_sensibles'].append({
                    'archivo': str(ruta.relative_to(self.directorio_raiz)),
                    'razon': 'Archivo de base de datos'
                })
            
            if 'password' in contenido.lower() or 'secret' in contenido.lower():
                # Verificar que no sea una falsa alarma (como en este script)
                if 'audit.py' not in str(ruta):
                    self.resultados['archivos_sensibles'].append({
                        'archivo': str(ruta.relative_to(self.directorio_raiz)),
                        'razon': 'Posible credencial en el código'
                    })
            
        except Exception as e:
            resultados['error'] = str(e)
        
        return resultados
    
    def _analizar_estructura(self, ruta: Path, nivel: int = 0) -> Dict:
        """Analiza la estructura de carpetas"""
        estructura = {
            'nombre': ruta.name,
            'nivel': nivel,
            'tipo': 'directorio',
            'archivos': [],
            'subdirectorios': []
        }
        
        try:
            for item in sorted(ruta.iterdir()):
                if self._debe_excluir(item):
                    continue
                
                if item.is_dir():
                    sub = self._analizar_estructura(item, nivel + 1)
                    estructura['subdirectorios'].append(sub)
                else:
                    if self._extension_permitida(item):
                        estructura['archivos'].append({
                            'nombre': item.name,
                            'extension': item.suffix,
                            'tamanio': item.stat().st_size
                        })
        except PermissionError:
            pass
        
        return estructura
    
    def _generar_recomendaciones(self):
        """Genera recomendaciones basadas en los hallazgos"""
        recomendaciones = set()
        
        # Verificar vulnerabilidades críticas
        for vuln in self.resultados['vulnerabilidades']:
            if vuln['nivel'] == 'CRITICO':
                if 'hardcoded_password' in vuln['tipo']:
                    recomendaciones.add('🔴 Mover contraseñas a variables de entorno (.env)')
                if 'hardcoded_secret' in vuln['tipo']:
                    recomendaciones.add('🔴 Mover secretos/keys a variables de entorno (.env)')
                if 'debug_true' in vuln['tipo']:
                    recomendaciones.add('🔴 Desactivar DEBUG en producción (FLASK_DEBUG=False)')
                if 'sql_injection' in vuln['tipo']:
                    recomendaciones.add('🔴 Usar consultas parametrizadas en lugar de concatenación')
                if 'eval_usage' in vuln['tipo'] or 'exec_usage' in vuln['tipo']:
                    recomendaciones.add('🔴 Evitar eval()/exec() - usar alternativas seguras')
                if 'os_system' in vuln['tipo']:
                    recomendaciones.add('🔴 Evitar os.system() - usar subprocess con shell=False')
                if 'subprocess_shell' in vuln['tipo']:
                    recomendaciones.add('🔴 Usar shell=False en subprocess')
                if 'cors_all' in vuln['tipo']:
                    recomendaciones.add('🔴 Restringir CORS a orígenes específicos')
        
        # Verificar archivos sensibles
        if self.resultados['archivos_sensibles']:
            recomendaciones.add('🔴 Verificar que los archivos sensibles estén en .gitignore')
        
        # Verificar si existe .env
        if not any('.env' in str(a['archivo']) for a in self.resultados['archivos_sensibles']):
            recomendaciones.add('🟡 Crear archivo .env con las variables de entorno necesarias')
        
        # Verificar si existe .gitignore (buscar en archivos analizados)
        gitignore_exists = False
        for root, dirs, files in os.walk(self.directorio_raiz):
            if '.gitignore' in files:
                gitignore_exists = True
                break
        
        if not gitignore_exists:
            recomendaciones.add('🔴 Crear archivo .gitignore para excluir archivos sensibles')
        
        self.resultados['recomendaciones'] = sorted(list(recomendaciones))
    
    def ejecutar(self) -> Dict:
        """Ejecuta la auditoría completa"""
        print("=" * 60)
        print("  🔍 AUDITORÍA DE SEGURIDAD - SIDESYS ERP")
        print("=" * 60)
        print()
        
        # 1. Analizar estructura
        print("📂 Analizando estructura de directorios...")
        self.resultados['estructura'] = self._analizar_estructura(self.directorio_raiz)
        
        # 2. Recorrer archivos para análisis
        print("🔍 Analizando archivos en busca de vulnerabilidades...")
        archivos_analizados = 0
        archivos_excluidos = 0
        
        for root, dirs, files in os.walk(self.directorio_raiz):
            # Excluir directorios
            dirs[:] = [d for d in dirs if d not in EXCLUIR_DIRECTORIOS]
            
            for file in files:
                ruta = Path(root) / file
                
                if self._debe_excluir(ruta):
                    archivos_excluidos += 1
                    self.resultados['archivos_ignorados'].append(str(ruta))
                    continue
                
                if self._extension_permitida(ruta):
                    archivos_analizados += 1
                    resultado = self._analizar_archivo(ruta)
                    
                    if resultado['vulnerabilidades']:
                        for vuln in resultado['vulnerabilidades']:
                            vuln['archivo'] = resultado['archivo']
                            self.resultados['vulnerabilidades'].append(vuln)
                            
                            # Actualizar resumen
                            if vuln['nivel'] == 'CRITICO':
                                self.resultados['resumen']['vulnerabilidades_criticas'] += 1
                            elif vuln['nivel'] == 'ALTO':
                                self.resultados['resumen']['vulnerabilidades_altas'] += 1
                            elif vuln['nivel'] == 'MEDIO':
                                self.resultados['resumen']['vulnerabilidades_medias'] += 1
                            elif vuln['nivel'] == 'BAJO':
                                self.resultados['resumen']['vulnerabilidades_bajas'] += 1
        
        self.resultados['resumen']['total_archivos'] = archivos_analizados + archivos_excluidos
        self.resultados['resumen']['archivos_analizados'] = archivos_analizados
        self.resultados['resumen']['archivos_excluidos'] = archivos_excluidos
        
        # 3. Generar recomendaciones
        print("💡 Generando recomendaciones...")
        self._generar_recomendaciones()
        
        print()
        print("=" * 60)
        print("  ✅ AUDITORÍA COMPLETADA")
        print("=" * 60)
        
        return self.resultados
    
    def guardar_informe(self, archivo_salida: str = None):
        """Guarda el informe en un archivo JSON"""
        if archivo_salida is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo_salida = f"informe_auditoria_{timestamp}.json"
        
        with open(archivo_salida, 'w', encoding='utf-8') as f:
            json.dump(self.resultados, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Informe guardado en: {archivo_salida}")
        return archivo_salida
    
    def imprimir_resumen(self):
        """Imprime un resumen de la auditoría en consola"""
        r = self.resultados['resumen']
        print()
        print("=" * 60)
        print("  📊 RESUMEN DE AUDITORÍA")
        print("=" * 60)
        print()
        print(f"  📂 Total archivos: {r['total_archivos']}")
        print(f"  📄 Archivos analizados: {r['archivos_analizados']}")
        print(f"  🚫 Archivos excluidos: {r['archivos_excluidos']}")
        print()
        print(f"  🔴 Vulnerabilidades críticas: {r['vulnerabilidades_criticas']}")
        print(f"  🟠 Vulnerabilidades altas: {r['vulnerabilidades_altas']}")
        print(f"  🟡 Vulnerabilidades medias: {r['vulnerabilidades_medias']}")
        print(f"  🟢 Vulnerabilidades bajas: {r['vulnerabilidades_bajas']}")
        print()
        print(f"  📁 Archivos sensibles: {len(self.resultados['archivos_sensibles'])}")
        print(f"  💡 Recomendaciones: {len(self.resultados['recomendaciones'])}")
        print()
        
        # Mostrar extensiones más comunes
        if self.resultados['archivos_por_extension']:
            print("  📊 Archivos por extensión:")
            sorted_ext = sorted(self.resultados['archivos_por_extension'].items(), key=lambda x: x[1], reverse=True)[:5]
            for ext, count in sorted_ext:
                print(f"    {ext}: {count}")
        print()
        print("=" * 60)
        
        # Mostrar recomendaciones principales
        if self.resultados['recomendaciones']:
            print()
            print("  💡 RECOMENDACIONES PRINCIPALES:")
            print()
            for i, rec in enumerate(self.resultados['recomendaciones'][:5], 1):
                print(f"  {i}. {rec}")
            if len(self.resultados['recomendaciones']) > 5:
                print(f"  ... y {len(self.resultados['recomendaciones']) - 5} más (ver informe)")
        
        print()
        print("=" * 60)

# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    import sys
    
    # Directorio a auditar
    directorio = sys.argv[1] if len(sys.argv) > 1 else "."
    
    print()
    print("🔍 Iniciando auditoría de seguridad...")
    print(f"📂 Directorio: {os.path.abspath(directorio)}")
    print()
    
    # Ejecutar auditoría
    auditor = AuditoriaSeguridad(directorio)
    resultados = auditor.ejecutar()
    
    # Guardar informe
    auditor.guardar_informe()
    
    # Mostrar resumen
    auditor.imprimir_resumen()