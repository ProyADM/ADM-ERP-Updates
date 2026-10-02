// ============================================================
// MAIN - FUNCIONES PRINCIPALES (CON SANITIZACIÓN)
// ============================================================

import { mostrarMsg, mostrarProgreso, ocultarProgreso } from './ui.js';
import { renderFacturas } from './render.js';

// ============================================================
// FUNCIÓN DE SANITIZACIÓN
// ============================================================

function sanitizarValor(val) {
    if (val === undefined || val === null) return '';
    return escapeHTML(String(val));
}

export function handleFiles(files) {
    if (!files || files.length === 0) {
        console.warn('⚠️ No hay archivos para procesar');
        return;
    }
    
    console.log('📂 handleFiles llamado con', files.length, 'archivos');
    window.currentFiles = Array.from(files);
    
    const fileNameEl = document.getElementById('fileName');
    const fileInfoEl = document.getElementById('fileInfo');
    
    if (fileNameEl) {
        // ✅ CORREGIDO: Sanitizar nombres de archivo
        const nombres = window.currentFiles.map(f => sanitizarValor(f.name)).join(', ');
        fileNameEl.textContent = window.currentFiles.length === 1 
            ? sanitizarValor(window.currentFiles[0].name)
            : `${window.currentFiles.length} archivos seleccionados`;
    }
    if (fileInfoEl) {
        fileInfoEl.style.display = 'flex';
    }
    
    mostrarProgreso(`📎 ${window.currentFiles.length} archivo(s) seleccionado(s). Procesando...`, 10);
    
    console.log('🔄 Llamando a parsearFacturas automáticamente...');
    setTimeout(() => {
        parsearFacturas();
    }, 300);
}

export function toBase64(file) {
    return new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result.split(',')[1]);
        r.onerror = rej;
        r.readAsDataURL(file);
    });
}

export async function parsearFacturas() {
    const files = window.currentFiles || [];
    if (!files || files.length === 0) {
        mostrarMsg('⚠️ Primero selecciona un archivo PDF o imagen', false);
        ocultarProgreso();
        return;
    }
    
    console.log('🔄 parsearFacturas iniciado con', files.length, 'archivos');
    mostrarProgreso(`📄 Procesando archivo 1 de ${files.length}...`, 20);
    
    const btn = document.getElementById('btnParsear');
    if (btn) {
        btn.innerHTML = '<span class="spinner"></span>Procesando…';
        btn.disabled = true;
    }
    
    try {
        window.facturasData = [];
        let totalFacturas = 0;
        
        for (let idx = 0; idx < files.length; idx++) {
            const file = files[idx];
            const progreso = 20 + ((idx / files.length) * 50);
            // ✅ CORREGIDO: Sanitizar nombre de archivo
            const nombreSanitizado = sanitizarValor(file.name);
            mostrarProgreso(`📄 Procesando ${nombreSanitizado} (${idx + 1}/${files.length})...`, progreso);
            
            console.log(`📄 Procesando archivo ${idx + 1}/${files.length}: ${file.name}`);
            const b64 = await toBase64(file);
            const res = await fetch('/api/parsear_pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_b64: b64, file_type: file.type || 'application/pdf' })
            }).then(r => r.json());
            
            if (!res.ok) throw new Error(`${file.name}: ${res.error || 'Error al parsear'}`);
            if (res.facturas && res.facturas.length > 0) {
                console.log(`✅ ${res.facturas.length} facturas encontradas en ${file.name}`);
                res.facturas.forEach(f => { 
                    f.archivo = file.name; 
                    window.facturasData.push(f); 
                    totalFacturas++;
                });
            } else {
                console.warn(`⚠️ No se detectaron facturas en ${file.name}`);
            }
        }
        
        if (window.facturasData.length === 0) {
            mostrarMsg('⚠️ No se detectaron facturas en los archivos', false);
            if (btn) { btn.innerHTML = '✨ Extraer facturas'; btn.disabled = false; }
            ocultarProgreso();
            return;
        }
        
        console.log(`📊 Total de facturas detectadas: ${window.facturasData.length}`);
        mostrarProgreso(`✅ ${window.facturasData.length} facturas detectadas. Cargando datos...`, 75);
        
        let ccos = [];
        try {
            const response = await fetch('/api/centros_costo');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            ccos = await response.json();
            console.log('✅ Centros de costo cargados:', ccos.length);
        } catch (e) {
            console.warn('⚠️ Usando centros de costo por defecto:', e.message);
            ccos = [
                {codigo: "001", nombre: "Centro de Costo 1", cco: "S"},
                {codigo: "002", nombre: "Centro de Costo 2", cco: "S"},
                {codigo: "003", nombre: "Centro de Costo 3", cco: "S"},
                {codigo: "004", nombre: "Centro de Costo 4", cco: "S"},
                {codigo: "005", nombre: "Centro de Costo 5", cco: "S"},
            ];
        }
        
        window.cuentasList = ccos;
        mostrarProgreso(`📋 Renderizando ${window.facturasData.length} facturas...`, 90);
        await renderFacturas(window.facturasData, ccos);
        
        const rendicionConfig = document.getElementById('rendicionConfig');
        const btnCargarTodo = document.getElementById('btnCargarTodo');
        if (rendicionConfig) rendicionConfig.style.display = 'block';
        if (btnCargarTodo) btnCargarTodo.style.display = 'block';
        
        mostrarProgreso(`✅ ${window.facturasData.length} factura(s) procesadas correctamente`, 100);
        mostrarMsg(`✅ ${window.facturasData.length} factura(s) procesadas correctamente`, true);
        
        setTimeout(() => ocultarProgreso(), 2500);
        
    } catch (e) {
        console.error('❌ Error en parsearFacturas:', e);
        mostrarMsg(`❌ Error: ${sanitizarValor(e.message)}`, false);
        ocultarProgreso();
    } finally {
        if (btn) { 
            btn.innerHTML = '✨ Extraer facturas'; 
            btn.disabled = false; 
        }
    }
}

export async function cargarTodo() {
    const btn = document.getElementById('btnCargar');
    if (!btn) return;
    btn.innerHTML = '<span class="spinner"></span>Cargando…';
    btn.disabled = true;

    mostrarProgreso('📦 Cargando facturas en el sistema...', 10);

    let ok = 0, errores = [];
    const total = window.facturasData.length;
    
    for (let i = 0; i < total; i++) {
        const f = window.facturasData[i];
        // Las facturas ya eliminadas quedan en la lista marcadas (`borrada`), sin
        // sacarlas (sacarlas corria los indices y el borrado siguiente mandaba el
        // `nro_interno` de OTRA factura): al re-cargar hay que SALTARLAS. Sin esto,
        // `getRenglones(i)` viene vacio para una fila ya borrada y "Cargar todas"
        // sumaba un error falso ("falta cuenta contable") justo despues de una baja.
        if (f.borrada) continue;
        const progreso = 10 + ((i / total) * 80);
        mostrarProgreso(`📦 Cargando factura ${i + 1} de ${total}...`, progreso);
        
        const tipo = document.getElementById(`f${i}_tipo`)?.value || '';

        // El tipo NO se adivina: si el parser no pudo leer la leyenda, el select
        // arranca con la opcion vacia y aca se pide el tipo antes de mandar nada.
        // Antes el default era 'FCP' y un operador que "arreglaba" el badge a FCC
        // cargaba en silencio un FCP real como pequeno contribuyente (IVA 0 y sin
        // ninguna fila de impuesto); y un default 'FCP' mandaba `bruto = total,
        // iva = 0`, que el servicio rechazaba con un mensaje sobre el IVA.
        if (!tipo) {
            errores.push(`Factura ${i+1}: elegí el tipo de factura (FCP con IVA o FCC pequeño contribuyente).`);
            const factEl = document.getElementById(`fact-${i}`);
            if (factEl) factEl.style.borderColor = '#f5b8b8';
            continue;
        }

        const esEv = document.getElementById(`f${i}_esev`)?.checked || false;
        const provId = esEv
            ? (parseInt(document.getElementById(`f${i}_provid`)?.value) || parseInt(document.getElementById('empId')?.value) || null)
            : (f.proveedor_id || null);

        if (!provId) {
            // ✅ CORREGIDO: Sanitizar mensaje de error
            errores.push(`Factura ${i+1}: falta proveedor.`);
            const factEl = document.getElementById(`fact-${i}`);
            if (factEl) factEl.style.borderColor = '#f5b8b8';
            continue;
        }

        const bruto = parseFloat(document.getElementById(`f${i}_bruto`)?.value) || 0;
        const iva = parseFloat(document.getElementById(`f${i}_iva`)?.value) || 0;
        // El impuesto especial se manda tal cual lo cargó el usuario; en FCC no
        // aplica (ahí el total es el bruto y no hay nada que separar).
        const especial = parseFloat(document.getElementById(`f${i}_especial`)?.value) || 0;
        const renglones = getRenglones(i);

        if (!renglones.length) {
            errores.push(`Factura ${i+1}: falta cuenta contable.`);
            const factEl = document.getElementById(`fact-${i}`);
            if (factEl) factEl.style.borderColor = '#f5b8b8';
            continue;
        }

        const payload = {
            division: window.divisionActiva || 7,
            proveedor_id: provId,
            proveedor_nombre: esEv
                ? (document.getElementById(`f${i}_provsearch`)?.value || document.getElementById('empSearch')?.value || '')
                : (f.proveedor_nombre || ''),
            cuenta_prov: f.cuenta_prov || '',
            // D3: los dos van VACIOS si el operador no puso fecha (antes caian en la de
            // hoy, en silencio). `fecha_vto` no lo produce el parser: aca el vacio es el
            // estado inicial. El servicio valida `fecha`, asi que el alta se frena.
            fecha: document.getElementById(`f${i}_fecha`)?.value || '',
            fecha_vto: document.getElementById(`f${i}_fecha`)?.value || '',
            ref_prov: document.getElementById(`f${i}_ref`)?.value.trim() || '',
            descripcion: document.getElementById(`f${i}_desc`)?.value.trim() || '',
            cond_pago: document.getElementById('rendCondPago')?.value || '00',
            moneda: document.getElementById(`f${i}_moneda`)?.value || 'PS',
            cotizacion: parseFloat(document.getElementById(`f${i}_coti`)?.value) || 1,
            tipo_comp: tipo,
            imp_bruto: bruto,
            imp_iva: iva,
            imp_especial: tipo === 'FCC' ? 0 : especial,
            tasa_iva: tipo === 'FCC' ? 0 : 12,
            renglones: renglones,
        };

        if (esEv) {
            payload.eventual = {
                nombre: document.getElementById(`f${i}_evnom`)?.value || f.nombre_emisor || '',
                nit: document.getElementById(`f${i}_evnit`)?.value || f.nit_emisor || '',
                domicilio: '',
                localidad: document.getElementById(`f${i}_evloc`)?.value || 'Guatemala',
            };
        }

        try {
            const res = await fetch('/api/cargar_factura', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(r => r.json());
            if (res.ok) {
                ok++;
                // La respuesta del alta trae el numero INTERNO del comprobante:
                // sin el, la pantalla no puede borrar esta factura (la baja se
                // identifica por numero interno, no por el Nro. DTE del PDF).
                f.nro_interno = res.nro_comprobante;
                f.tipo_cargado = res.tipo;
                f.ctacte = res.ctacte;
                const factEl = document.getElementById(`fact-${i}`);
                if (factEl) {
                    factEl.style.borderColor = '#a3d9c0';
                    factEl.style.opacity = '0.6';
                }
            } else {
                // ✅ CORREGIDO: Sanitizar error de API
                errores.push(`Factura ${i+1}: ${sanitizarValor(res.error)}`);
                const factEl = document.getElementById(`fact-${i}`);
                if (factEl) factEl.style.borderColor = '#f5b8b8';
            }
        } catch(e) {
            errores.push(`Factura ${i+1}: ${sanitizarValor(e.message)}`);
        }
    }

    btn.innerHTML = '⬆ Cargar todas las facturas';
    btn.disabled = false;
    
    if (errores.length === 0) {
        mostrarProgreso(`✅ ${ok} factura(s) cargadas exitosamente.`, 100);
        mostrarMsg(`✅ ${ok} factura(s) cargadas exitosamente.`, true);
        setTimeout(() => ocultarProgreso(), 2000);
    } else {
        // ✅ CORREGIDO: Sanitizar mensaje de errores
        const erroresSanitizados = errores.map(e => sanitizarValor(e)).join(' | ');
        mostrarProgreso(`⚠️ ${ok} ok · ${errores.length} errores`, 100);
        mostrarMsg(`${ok} ok · Errores: ${erroresSanitizados}`, false);
        setTimeout(() => ocultarProgreso(), 3000);
    }
}

export function limpiarRendicion() {
    window.currentFiles = [];
    window.facturasData = [];
    const fileInput = document.getElementById('fileInput');
    if (fileInput) fileInput.value = '';
    const fileInfo = document.getElementById('fileInfo');
    if (fileInfo) fileInfo.style.display = 'none';
    const fileName = document.getElementById('fileName');
    if (fileName) fileName.textContent = '';
    const facturasContainer = document.getElementById('facturasContainer');
    if (facturasContainer) facturasContainer.innerHTML = '';
    const rendicionConfig = document.getElementById('rendicionConfig');
    if (rendicionConfig) rendicionConfig.style.display = 'none';
    const btnCargarTodo = document.getElementById('btnCargarTodo');
    if (btnCargarTodo) btnCargarTodo.style.display = 'none';
    const empSearch = document.getElementById('empSearch');
    if (empSearch) empSearch.value = '';
    const empId = document.getElementById('empId');
    if (empId) empId.value = '';
    const toggleEventualGlobal = document.getElementById('toggleEventualGlobal');
    if (toggleEventualGlobal) toggleEventualGlobal.checked = false;
    const eventualGlobalPanel = document.getElementById('eventualGlobalPanel');
    if (eventualGlobalPanel) eventualGlobalPanel.style.display = 'none';
    ocultarProgreso();
    console.log('✅ Rendición limpiada');
}

export async function debugPDF() {
    if (!window.currentFiles?.length) return;
    const btn = document.getElementById('btnDebug');
    if (!btn) return;
    btn.textContent = 'Procesando…';
    btn.disabled = true;
    
    mostrarProgreso('🔍 Extrayendo texto raw del PDF...', 30);
    
    try {
        for (let idx = 0; idx < window.currentFiles.length; idx++) {
            const file = window.currentFiles[idx];
            const progreso = 30 + ((idx / window.currentFiles.length) * 60);
            const nombreSanitizado = sanitizarValor(file.name);
            mostrarProgreso(`🔍 Procesando ${nombreSanitizado} (${idx + 1}/${window.currentFiles.length})...`, progreso);
            
            const b64 = await toBase64(file);
            const res = await fetch('/api/debug_pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_b64: b64 })
            }).then(r => r.json());
            console.log(`=== ${file.name} ===`);
            res.forEach(p => console.log(`--- Pág ${p.pagina} ---\n${p.texto}`));
        }
        mostrarProgreso('✅ Texto extraído correctamente. Revisá la consola (F12)', 100);
        alert('Texto copiado a consola del navegador (F12)');
        setTimeout(() => ocultarProgreso(), 2000);
    } catch (e) {
        console.error('❌ Error en debugPDF:', e);
        mostrarMsg(`❌ Error: ${sanitizarValor(e.message)}`, false);
        ocultarProgreso();
    } finally {
        btn.textContent = '🔍 Ver texto raw';
        btn.disabled = false;
    }
}