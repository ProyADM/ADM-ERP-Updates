# modules/shared/utils.py
# ============================================================
# UTILIDADES - SIDESYS ERP (CORREGIDO)
# ============================================================

import base64
import re
import logging

logger = logging.getLogger(__name__)

# ============================================================
# VALIDACIONES
# ============================================================

def es_base64_valido(data: str) -> bool:
    """Verifica si una cadena es base64 válida"""
    try:
        if not data:
            return False
        base64.b64decode(data, validate=True)
        return True
    except Exception:
        return False

# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def to_base64(file):
    """
    Convierte un archivo a base64.
    
    Args:
        file: Objeto archivo (con método read)
    
    Returns:
        str: Cadena en base64
    
    Raises:
        ValueError: Si el archivo es inválido
    """
    try:
        if not file:
            raise ValueError("Archivo no proporcionado")
        
        if not hasattr(file, 'read'):
            raise ValueError("El objeto no es un archivo válido")
        
        return base64.b64encode(file.read()).decode('utf-8')
        
    except Exception as e:
        logger.error(f"Error en to_base64: {e}")
        raise ValueError(f"Error al convertir archivo a base64: {str(e)}")


def normalizar_fecha(s):
    """
    Convierte distintos formatos de fecha a YYYY-MM-DD.
    
    Formatos soportados:
    - YYYY-MM-DD
    - DD-MMM-YYYY (ej: 15-ene-2024)
    - DD/MM/YYYY
    - DD MM YYYY (con texto)
    
    Args:
        s: String con la fecha en varios formatos
    
    Returns:
        str: Fecha en formato YYYY-MM-DD, o el string original si no se pudo parsear
    """
    if not s:
        return ""
    
    # ✅ CORREGIDO: Limpiar y normalizar el string
    s = str(s).strip().upper()
    
    # Mapeo de meses
    meses = {
        'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12,
        'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
        'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
    }
    
    try:
        # Formato YYYY-MM-DD
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        
        # Formato DD-MMM-YYYY (ej: 15-ene-2024)
        m = re.search(r'(\d{1,2})[-/]([A-Z]{3,})[-/](\d{4})', s)
        if m:
            mes = meses.get(m.group(2), 1)
            return f"{m.group(3)}-{mes:02d}-{int(m.group(1)):02d}"
        
        # Formato DD/MM/YYYY
        m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
        if m:
            return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        
        # Formato DD MMM YYYY (ej: 15 ENERO 2024)
        m = re.search(r'(\d{1,2})\s+(?:DE\s+)?([A-Z]+)\s+(\d{4})', s)
        if m:
            mes = meses.get(m.group(2), 1)
            return f"{m.group(3)}-{mes:02d}-{int(m.group(1)):02d}"
        
        # Si no se pudo parsear, devolver el string original
        return s
        
    except Exception as e:
        logger.warning(f"Error al normalizar fecha '{s}': {e}")
        return s


def limpiar_texto(texto):
    """
    Limpia un texto eliminando caracteres especiales y espacios extra.
    
    Args:
        texto: String a limpiar
    
    Returns:
        str: Texto limpio
    """
    if not texto:
        return ""
    
    try:
        # ✅ CORREGIDO: Convertir a string
        texto = str(texto)
        
        # Eliminar caracteres de control (0x00-0x1F, 0x7F-0x9F)
        texto = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', texto)
        
        # Eliminar espacios múltiples
        texto = re.sub(r'\s+', ' ', texto)
        
        # Eliminar espacios al inicio y final
        texto = texto.strip()
        
        return texto
        
    except Exception as e:
        logger.warning(f"Error al limpiar texto: {e}")
        return str(texto) if texto else ""


def sanitizar_entrada(valor, max_length=None):
    """
    Sanitiza una entrada para prevenir inyecciones.
    
    Args:
        valor: Valor a sanitizar
        max_length: Longitud máxima permitida
    
    Returns:
        Valor sanitizado
    """
    if valor is None:
        return None
    
    try:
        # Convertir a string
        if not isinstance(valor, str):
            valor = str(valor)
        
        # Limpiar caracteres peligrosos
        valor = re.sub(r'[<>"\';&]', '', valor)
        
        # Truncar si es necesario
        if max_length and len(valor) > max_length:
            valor = valor[:max_length]
        
        return valor
        
    except Exception as e:
        logger.warning(f"Error al sanitizar entrada: {e}")
        return str(valor) if valor else ""