# modules/cxp/parser.py
# ============================================================
# PARSER DE FACTURAS - SIDESYS ERP (CORREGIDO)
# ============================================================
# Este modulo es el acceso al PDF y al OCR. La LECTURA de los campos (total, fecha, tipo,
# impuesto especial, emisor) vive en `modules/cxp/campos.py`, que es stdlib puro y por eso
# se testea con los textos reales de las rendiciones: `parse_fel_page` delega ahi.

import os
import tempfile
import base64
import io
import pdfplumber
import pytesseract
from PIL import Image
from config import TESSERACT_PATH
from modules.cxp import campos
# `limpiar_texto_superpuesto` se muda a `campos.py` (es parte del preprocesado de la
# lectura) y se re-exporta aca porque los consumidores la importan de este modulo
# (`modules/cxp/__init__.py`). Se importa con el nombre publico a proposito.
from modules.cxp.campos import limpiar_texto_superpuesto

# Configurar Tesseract
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def extraer_texto_pagina(page):
    """Extrae texto de una página pdfplumber."""
    try:
        text = page.extract_text() or ""
        if text and len(text.strip()) > 50:
            return text
    except Exception as e:
        text = ""
    
    # Si no hay texto, intentar OCR
    try:
        img = page.to_image(resolution=200).original
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        if w < 1000:
            img = img.resize((w * 2, h * 2), Image.LANCZOS)
        img = img.convert("L")
        text = pytesseract.image_to_string(img, lang="spa+eng", config="--psm 6")
        return text
    except Exception as e:
        print(f"⚠️ OCR falló: {e}")
        return text

def ocr_image_bytes(img_bytes):
    """Extrae texto de una imagen usando Tesseract."""
    try:
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        if w < 1000:
            img = img.resize((w * 2, h * 2), Image.LANCZOS)
        img = img.convert("L")
        text = pytesseract.image_to_string(img, lang="spa+eng", config="--psm 6")
        return text
    except Exception as e:
        print(f"⚠️ OCR falló: {e}")
        return ""

def parse_fel_page(text):
    """Extrae campos de una página de factura FEL guatemalteca.

    La lectura de campos vive en `modules/cxp/campos.py` (stdlib puro, con los textos
    reales de las rendiciones como test): aca queda solo el acceso al PDF y al OCR.
    """
    return campos.parsear(text)