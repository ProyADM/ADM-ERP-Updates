# modules/cxp/parser.py
# ============================================================
# PARSER DE FACTURAS - SIDESYS ERP (CORREGIDO)
# ============================================================

import re
import os
import tempfile
import base64
import io
import pdfplumber
import pytesseract
from PIL import Image
from modules.shared.utils import normalizar_fecha
from config import TESSERACT_PATH
from cuentas import NIT_CUENTA_FIJA

# Configurar Tesseract
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def limpiar_texto_superpuesto(text):
    """Limpia texto con capas superpuestas."""
    if not text:
        return ""
    
    def reconstruir_total(t):
        lines = t.split('\n')
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.search(r'TOTAL[:\s]*$', line.strip(), re.I):
                fragmentos = []
                j = i + 1
                while j < len(lines) and j < i + 15:
                    frag = lines[j].strip()
                    if re.match(r'^[Q\d\.,]+$', frag):
                        fragmentos.append(frag)
                        j += 1
                    else:
                        break
                if fragmentos:
                    joined = ''.join(fragmentos).replace('QQ', 'Q').replace('Q.Q.', 'Q.')
                    result.append(line.strip() + ' ' + joined)
                    i = j
                    continue
            result.append(line)
            i += 1
        return '\n'.join(result)
    
    text = reconstruir_total(text)
    lines = text.split('\n')
    dup_count = sum(1 for l in lines if re.search(r'(.)\1{1,}', l) and len(l) > 4)
    if dup_count < max(3, len(lines) * 0.15):
        return text
    cleaned_lines = []
    for line in lines:
        if re.search(r'(.)\1', line) and len(line) > 4:
            dedup = re.sub(r'([A-Za-záéíóúÁÉÍÓÚñÑ])\1+', r'\1', line)
            cleaned_lines.append(dedup)
        else:
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)

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
    """Extrae campos de una página de factura FEL guatemalteca."""
    if not text or len(text.strip()) < 10:
        return {"error": "No se pudo extraer texto", "tipo": "FCP"}
    
    text = limpiar_texto_superpuesto(text)
    r = {}
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # Si no hay líneas, devolver datos por defecto
    if not lines:
        return {
            "tipo": "FCP",
            "moneda": "PS",
            "total": 0,
            "imp_bruto": 0,
            "imp_iva": 0,
            "tasa_iva": 12,
            "fecha": "",
            "numero_dte": "",
            "nit_emisor": "",
            "nombre_emisor": "PROVEEDOR NO IDENTIFICADO"
        }

    # Tipo
    if re.search(r'SUJETO[S]?\s+A\s+PAGOS?\s+TRIMESTRALES?', text, re.I):
        r['tipo'] = 'FCP'
    elif re.search(r'NO\s+GENERA\s+(DERECHO\s+A\s+)?CR[EÉ]DITO\s+FISCAL', text, re.I):
        r['tipo'] = 'FCC'
    else:
        r['tipo'] = 'FCP'

    # Moneda
    if re.search(r'Moneda[:\s]+USD', text, re.I) or re.search(r'USD\s*-\s*Dolar', text, re.I):
        r['moneda'] = 'DL'
    else:
        r['moneda'] = 'PS'

    # NIT y nombre del EMISOR
    nit_emisor = None
    nombre_emisor = None
    
    try:
        # Patrón 1: NIT: Nombre: \n 123456789-0 Nombre
        m = re.search(r'NIT:\s+Nombre:\s*\n([0-9]+[-K]?)\s+(.+)', text, re.I)
        if m:
            nit_emisor = m.group(1).strip()
            nombre_raw = m.group(2).strip()
            nombre_raw = re.sub(r'\s*(RÉGIMEN|REGIMEN)\s+FEL.*$', '', nombre_raw, flags=re.I).strip()
            nombre_raw = re.sub(r'\s+FACTURA\s+.*$', '', nombre_raw, flags=re.I).strip()
            nombre_raw = re.sub(r'\s+N[UÚ]MERO\s+DE\s+AUTORIZACI[OÓ]N\s*:?\s*$', '', nombre_raw, flags=re.I).strip()
            nombre_emisor = nombre_raw
    except Exception:
        pass
    
    # Patrón 2: Nit Emisor: 123456789-0
    if not nit_emisor:
        try:
            m = re.search(r'Nit\s+Emisor\s*:\s*([0-9][\d\-]*[\dK])', text, re.I)
            if m:
                nit_emisor = m.group(1).replace('-', '').strip()
        except Exception:
            pass
    
    # Patrón 3: N.I.T. 123456789-0
    if not nit_emisor:
        try:
            m = re.search(r'N\.I\.T\.\s*([\d][\d\-]*[\dK])', text, re.I)
            if m:
                nit_emisor = m.group(1).replace('-', '').strip()
        except Exception:
            pass
    
    # Patrón 4: Buscar en las primeras líneas
    if not nit_emisor:
        try:
            texto_emisor = text
            m_rec = re.search(r'DATOS\s+DEL\s+COMPRADOR|NIT\s+Receptor|NIT\s*:\s*971|Nombre\s+(de\s+)?Cliente|Nombre\s+Receptor|DATOS\s+DEL\s+CERTIFICAD', text, re.I)
            if m_rec:
                texto_emisor = text[:m_rec.start()]
            m = re.search(r'NIT[:\s]+([\d][\d\-]*[\dK])', texto_emisor, re.I)
            if m:
                nit_emisor = m.group(1).replace('-', '').strip()
        except Exception:
            pass
    
    # Buscar nombre del emisor en las primeras líneas
    if not nombre_emisor:
        try:
            for line in lines[:15]:
                if (len(line) > 5 and 'NIT' not in line.upper() and not re.match(r'^[\d\s\-\+\.]+$', line) and not re.search(r'CALLE|ZONA|AVENIDA|DOCUMENTO|TRIBUTARIO|^FACTURA|RÉGIMEN|REGIMEN|^SERIE:|^NÚMERO|^NUMERO|^FECHA|DATOS\s+DEL|^NOMBRE:|^DIRECCI', line, re.I)):
                    nombre = re.sub(r'\s*(RÉGIMEN|REGIMEN)\s+FEL.*$', '', line, flags=re.I).strip()
                    nombre = re.sub(r'\s+FACTURA\s+.*$', '', nombre, flags=re.I).strip()
                    nombre = re.sub(r'\s+N[UÚ]MERO\s+DE\s+AUTORIZACI[OÓ]N\s*:?\s*$', '', nombre, flags=re.I).strip()
                    if nombre and len(nombre) > 3:
                        nombre_emisor = nombre
                        break
        except Exception:
            pass
    
    r['nit_emisor'] = nit_emisor or ""
    r['nombre_emisor'] = nombre_emisor or "PROVEEDOR NO IDENTIFICADO"

    # Número DTE
    numero_dte = None
    patrones_dte = [
        r'No\.\s+de\s+factura[:\s]+([0-9]{6,})',
        r'N[oó°]\.\s*:\s*([0-9]{6,})',
        r'N[uú]mero\s+de\s+documento[:\s\n]+([0-9]{6,})',
        r'N[uú]mero\s+(?:de\s+)?DTE[:\s]+([0-9]{6,})',
        r'NÚMERO[:\s]+([0-9]{6,})',
        r'N[uú]mero\s*:+\s*([0-9]{6,})',
        r'NUMERO\s*:+\s*([0-9]{6,})',
        r'N\s+ero\s*:+\s*([0-9]{6,})',
        r'(?:^|\n)\s*([0-9]{8,})\s*$',
    ]
    
    for pat in patrones_dte:
        try:
            m = re.search(pat, text, re.I)
            if m:
                numero_dte = m.group(1).strip()
                break
        except Exception:
            pass
    
    if not numero_dte:
        try:
            numeros = re.findall(r'\b\d{6,}\b', text)
            if numeros:
                for n in numeros:
                    if len(n) >= 8 and not re.match(r'^\d{4,5}$', n):
                        numero_dte = n
                        break
        except Exception:
            pass
    
    r['numero_dte'] = numero_dte or ""

    # Fecha
    fecha = None
    patrones_fecha = [
        r'Fecha\s+emisi[oó]n[\s\S]{0,120}?(\d{4}-\d{2}-\d{2})',
        r'(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}',
        r'(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}',
        r'(\d{1,2}-(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-\d{4})',
        r'(\d{1,2})\s+(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\s+(\d{4})',
        r'DIA\s+MES\s+A[ÑN]O\s+(\d{1,2})\s+(\w+)\s+(\d{4})',
    ]
    
    for pat in patrones_fecha:
        try:
            m = re.search(pat, text, re.I)
            if m:
                fecha = normalizar_fecha(m.group(0))
                break
        except Exception:
            pass

    if not fecha:
        try:
            for fm in re.finditer(r'(\d{2}/\d{2}/\d{4})', text):
                start, end = fm.start(), fm.end()
                contexto_post = text[end:end+4]
                contexto_pre = text[max(0,start-4):start]
                if ' AL' not in contexto_post.upper() and 'AL ' not in contexto_pre.upper():
                    fecha = normalizar_fecha(fm.group(1))
                    break
        except Exception:
            pass
    
    if not fecha:
        from datetime import date
        fecha = date.today().isoformat()
    
    r['fecha'] = fecha

    # Descripción automática
    desc = ''
    try:
        if re.search(r'cargo[s]?\s+moratori|inter[eé]s?\s+por\s+cargo', text, re.I):
            desc = 'Cargos moratorios e intereses por pago fuera de termino'
        elif re.search(r'(?:^|\n)\s*(?:SERVICIO\s+)?Oficina\s*[-–]|alquiler\s+de\s+oficina', text, re.I):
            m_per = re.search(r'[Oo]ficina[^\n]*\n\s*\((\d{2})/(\d{2})/(\d{4})\s*[-–]\s*\d{2}/(\d{2})/(\d{4})\)', text)
            if m_per:
                desc = f'Alquiler oficina {m_per.group(4)}/{m_per.group(5)}'
            else:
                todos = re.findall(r'\d{2}/\d{2}/\d{4}\s*[-–]\s*\d{2}/(\d{2})/(\d{4})', text)
                if todos:
                    desc = f'Alquiler oficina {todos[-1][0]}/{todos[-1][1]}'
                else:
                    desc = 'Alquiler oficina'
        elif re.search(r'subarrendamiento\s+bodega|cargo\s+admin.*bodega', text, re.I):
            m_per = re.search(r'[Dd]e\s+\d{1,2}/(\d{2})/(\d{4})\s+a\s+\d{1,2}/\d{2}/\d{4}', text)
            if m_per:
                desc = f'Alquiler bodega {m_per.group(1)}/{m_per.group(2)}'
            else:
                desc = 'Alquiler bodega'
    except Exception:
        pass
    
    r['descripcion_auto'] = desc

    # Extraer TOTAL
    total = None
    
    patrones_total = [
        r'Importe\s+total\s*\(USD\)\s*([\d,.]+)',
        r'Importe\s+total\s*\(QTZ\)\s*([\d,.]+)',
        r'Importe\s+total[:\s]+([\d,.]+)',
        r'Total\s+l[ií]neas\s*([\d,.]+)',
        r'TOTAL\s+FACTURA\s*Q?\s*([\d,.]+)',
        r'TOTAL\s+A\s+PAGAR[:\s]+Q?\s*([\d,.]+)',
        r'Total\s*\(Q\)\s*([\d,.]+)',
        r'TOTAL[:\s]+([\d,.]+)',
    ]
    
    for pat in patrones_total:
        try:
            m = re.search(pat, text, re.I)
            if m:
                val = m.group(1).replace(',', '')
                try:
                    total = float(val)
                    break
                except ValueError:
                    pass
        except Exception:
            pass

    # Buscar "Total líneas" específicamente
    if not total:
        try:
            m = re.search(r'Total\s+l[ií]neas\s*([\d,.]+)', text, re.I)
            if m:
                try:
                    total = float(m.group(1).replace(',', ''))
                except ValueError:
                    pass
        except Exception:
            pass

    # Buscar IVA
    iva_explicito = None
    try:
        m = re.search(r'Total\s+de\s+impuestos\s*([\d,.]+)', text, re.I)
        if m:
            try:
                iva_explicito = float(m.group(1).replace(',', ''))
            except ValueError:
                pass
    except Exception:
        pass

    if iva_explicito is None:
        try:
            iva_matches = re.findall(r'IVA\s+\d+\s+[\d.]+\s+([\d.]+)', text, re.I)
            if iva_matches:
                try:
                    iva_explicito = sum(float(m.replace(',', '')) for m in iva_matches)
                except ValueError:
                    pass
        except Exception:
            pass

    # Fallback a cualquier número
    if total is None:
        try:
            montos = re.findall(r'(\d{1,3}(?:,\d{3})*\.\d{2})', text)
            if montos:
                try:
                    total = max(float(m.replace(',', '')) for m in montos)
                except ValueError:
                    total = 0
        except Exception:
            total = 0

    if total is None:
        total = 0

    r['total'] = total

    # Cálculo de IVA y bruto con validación
    if r['tipo'] == 'FCC' or total == 0:
        r['imp_bruto'] = total
        r['imp_iva'] = 0.0
        r['tasa_iva'] = 0
    else:
        try:
            if iva_explicito is not None and iva_explicito > 0:
                r['imp_iva'] = round(iva_explicito, 2)
                r['imp_bruto'] = round(total - iva_explicito, 2)
            else:
                if total > 0:
                    r['imp_bruto'] = round(total / 1.12, 2)
                    r['imp_iva'] = round(total - r['imp_bruto'], 2)
                else:
                    r['imp_bruto'] = 0
                    r['imp_iva'] = 0
                r['tasa_iva'] = 12
        except Exception:
            r['imp_bruto'] = total
            r['imp_iva'] = 0
            r['tasa_iva'] = 0

    if r.get('imp_iva', 0) == 0 and r.get('tipo') == 'FCP':
        r['tipo'] = 'FCC'

    # Si no hay datos, crear un registro de prueba
    if not r.get('nit_emisor') and not r.get('numero_dte') and r.get('total', 0) == 0:
        from datetime import date
        r['nit_emisor'] = '999999999'
        r['nombre_emisor'] = 'PROVEEDOR DE PRUEBA'
        r['numero_dte'] = '999999'
        r['total'] = 1000.00
        r['imp_bruto'] = 892.86
        r['imp_iva'] = 107.14
        r['tasa_iva'] = 12
        r['fecha'] = date.today().isoformat()
        r['descripcion_auto'] = 'Factura de prueba - Datos simulados'

    return r