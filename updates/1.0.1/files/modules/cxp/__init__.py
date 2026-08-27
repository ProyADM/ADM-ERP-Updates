# modules/cxp/__init__.py
# ============================================================
# MÓDULO CXP - SIDESYS ERP
# ============================================================

from .routes import cxp_bp
from .parser import parse_fel_page, extraer_texto_pagina, limpiar_texto_superpuesto, ocr_image_bytes

__all__ = [
    'cxp_bp',
    'parse_fel_page',
    'extraer_texto_pagina',
    'limpiar_texto_superpuesto',
    'ocr_image_bytes'
]