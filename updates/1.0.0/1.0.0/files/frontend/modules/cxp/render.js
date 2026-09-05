// ============================================================
// RENDER - RENDERIZADO DE FACTURAS (CON SANITIZACIÓN)
// ============================================================

import { agregarRenglon } from './renglones.js';
import { actualizarCotizacion, setupAC, cuentaAutoDesdeDesc } from './utils.js';
import { toggleEventualFact, aplicarEventualGlobal } from './eventuales.js';
import { eliminarFactura } from './eliminar.js';
import { initTooltips } from '../shared/tooltip-component.js';

// ============================================================
// FUNCIÓN DE SANITIZACIÓN
// ============================================================

function escapeHTML(str) {
    if (!str) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(str).replace(/[&<>"']/g, function(m) { return map[m]; });
}

function sanitizarValor(val) {
    if (val === undefined || val === null) return '';
    return escapeHTML(String(val));
}

export async function renderFacturas(facturas, ccosParam) {
    const container = document.getElementById('facturasContainer');
    if (!container) return;
    
    container.innerHTML = `<div class="card-title" style="margin:0 0 12px">3 · Revisá cada factura</div>`;

    if (ccosParam) window.cuentasList = ccosParam;
    if (!window.cuentasList?.length) {
        try {
            const response = await fetch('/api/centros_costo');
            if (response.ok) {
                window.cuentasList = await response.json();
            } else {
                throw new Error('HTTP ' + response.status);
            }
        } catch (e) {
            console.warn('⚠️ Usando centros de costo por defecto:', e);
            window.cuentasList = [
                {codigo: "001", nombre: "Centro de Costo 1", cco: "S"},
                {codigo: "002", nombre: "Centro de Costo 2", cco: "S"},
                {codigo: "003", nombre: "Centro de Costo 3", cco: "S"},
                {codigo: "004", nombre: "Centro de Costo 4", cco: "S"},
                {codigo: "005", nombre: "Centro de Costo 5", cco: "S"},
            ];
        }
    }
    
    let cuentasContables = [];
    try {
        const response = await fetch('/api/cuentas');
        console.log('📊 Respuesta /api/cuentas:', response.status);
        if (response.ok) {
            cuentasContables = await response.json();
            console.log('✅ Cuentas contables cargadas:', cuentasContables.length);
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (e) {
        console.warn('⚠️ Error cargando cuentas contables, usando datos por defecto:', e);
        cuentasContables = [
            {codigo: "520312", nombre: "Alquileres", cco: false},
            {codigo: "520319", nombre: "Gastos Varios", cco: false},
            {codigo: "520401", nombre: "Telefonía Fija", cco: false},
            {codigo: "520402", nombre: "Telefonía Celular", cco: false},
            {codigo: "520403", nombre: "Internet/Conectividad", cco: false},
            {codigo: "510101017", nombre: "Peaje/Estacionamiento", cco: true},
            {codigo: "510101018", nombre: "Combustible", cco: true},
            {codigo: "510101020", nombre: "Pasajes Aéreos/Transp.", cco: true},
            {codigo: "510101022", nombre: "Alojamiento", cco: true},
            {codigo: "510101023", nombre: "Alimentos/Refrigerios", cco: true},
            {codigo: "520301", nombre: "Papelería/Librería", cco: false},
            {codigo: "520302", nombre: "Insumos Oficina", cco: false},
            {codigo: "520310", nombre: "Seguros", cco: false},
            {codigo: "520316", nombre: "Honorarios Contables", cco: false},
            {codigo: "520317", nombre: "Honorarios Legales", cco: false},
            {codigo: "520318", nombre: "Honorarios Técnicos", cco: false},
            {codigo: "520801", nombre: "Gastos/Comisiones Bancarias", cco: false},
        ];
    }
    
    window._cuentasContables = cuentasContables;
    console.log('✅ Cuentas contables guardadas globalmente:', window._cuentasContables.length);

    for (let i = 0; i < facturas.length; i++) {
        const f = facturas[i];
        try {
            const div = document.createElement('div');
            div.className = 'factura-item';
            div.id = `fact-${i}`;

            // ✅ CORREGIDO: Sanitizar todos los valores
            const tipoBadge = f.tipo === 'FCP'
                ? `<span class="factura-badge badge-fcp">FCP</span>`
                : `<span class="factura-badge badge-fcc">FCC</span>`;

            const totalDisplay = f.total ? f.total.toFixed(2) : '';
            const brutoDisplay = f.imp_bruto ? f.imp_bruto.toFixed(2) : '';
            const ivaDisplay = f.imp_iva ? f.imp_iva.toFixed(2) : '0.00';
            
            // ✅ CORREGIDO: Sanitizar datos de usuario
            const nombreEmisor = sanitizarValor(f.nombre_emisor || '—');
            const nitEmisor = sanitizarValor(f.nit_emisor || '—');
            const archivo = sanitizarValor(f.archivo || `Pág. ${f.pagina}`);
            const numeroDte = sanitizarValor(f.numero_dte || '');
            const fecha = sanitizarValor(f.fecha || new Date().toISOString().split('T')[0]);
            const descAuto = sanitizarValor(f.descripcion_auto || '');
            const moneda = sanitizarValor(f.moneda || 'PS');
            const total = sanitizarValor(totalDisplay);
            const bruto = sanitizarValor(brutoDisplay);
            const iva = sanitizarValor(ivaDisplay);
            const esEventual = f.es_eventual ? 'checked' : '';
            const eventualNombre = sanitizarValor(f.eventual_nombre || f.nombre_emisor || '');
            const eventualNit = sanitizarValor(f.nit_emisor || '');
            const eventualLocalidad = sanitizarValor(f.eventual_localidad || 'GT');
            const eventualConocido = f.eventual_conocido;
            const proveedorId = f.es_eventual && f.proveedor_id ? sanitizarValor(f.proveedor_id) : '';
            
            // ✅ CORREGIDO: Construir HTML con valores sanitizados
            div.innerHTML = `
                <div class="factura-header">
                    <div>
                        ${tipoBadge}
                        <span style="margin-left:8px;font-size:13px;font-weight:600">${nombreEmisor}</span>
                        <span style="color:var(--muted);font-size:12px;margin-left:6px">NIT: ${nitEmisor}</span>
                    </div>
                    <span style="color:var(--muted);font-size:12px">${archivo}</span>
                </div>

                <div class="factura-grid">
                    <div class="factura-field">
                        <span class="lbl">Nro. DTE <span class="tag-auto">auto</span></span>
                        <input type="text" id="f${i}_ref" value="${numeroDte}" maxlength="15" data-tooltip="fechaFacturaInput">
                    </div>
                    <div class="factura-field">
                        <span class="lbl">Fecha <span class="tag-auto">auto</span></span>
                        <input type="date" id="f${i}_fecha" value="${fecha}" data-tooltip="fechaFacturaInput">
                    </div>
                    <div class="factura-field">
                        <span class="lbl">Tipo <span class="tag-auto">auto</span></span>
                        <select id="f${i}_tipo" data-tooltip="tipoFacturaSelect">
                            <option value="FCP" ${f.tipo==='FCP'?'selected':''}>FCP · Con IVA</option>
                            <option value="FCC" ${f.tipo==='FCC'?'selected':''}>FCC · Pequeño contrib.</option>
                        </select>
                    </div>
                    <div class="factura-field">
                        <span class="lbl">Moneda <span class="tag-auto">auto</span></span>
                        <select id="f${i}_moneda" onchange="actualizarCotizacion(${i})" data-tooltip="monedaFacturaSelect">
                            <option value="PS" ${moneda==='PS'?'selected':''}>PS · Quetzales</option>
                            <option value="DL" ${moneda==='DL'?'selected':''}>DL · Dólares</option>
                        </select>
                    </div>
                    <div class="factura-field" id="f${i}_cotiwrap" style="${moneda==='DL'?'':'display:none'}">
                        <span class="lbl">Cotización <span class="tag-auto">auto</span></span>
                        <input type="number" id="f${i}_coti" value="" step="0.00001" placeholder="Cargando…" data-tooltip="cotizacionInput">
                    </div>
                </div>

                <div class="factura-grid">
                    <div class="factura-field">
                        <span class="lbl">Total <span class="tag-auto">auto</span></span>
                        <input type="number" id="f${i}_total" value="${total}" step="0.01" oninput="recalcFact(${i})" data-tooltip="totalFacturaInput">
                    </div>
                    <div class="factura-field">
                        <span class="lbl">Bruto (sin IVA)</span>
                        <input type="number" id="f${i}_bruto" value="${bruto}" step="0.01" readonly data-tooltip="brutoFacturaInput">
                    </div>
                    <div class="factura-field">
                        <span class="lbl">IVA</span>
                        <input type="number" id="f${i}_iva" value="${iva}" step="0.01" readonly data-tooltip="ivaFacturaInput">
                    </div>
                </div>

                <div style="margin-top:10px">
                    <div style="margin-bottom:6px">
                        <span class="lbl">Descripción</span>
                        <input type="text" id="f${i}_desc" placeholder="Concepto del gasto" maxlength="100"
                            value="${descAuto}"
                            style="width:100%;font-size:12px;margin-top:3px;padding:5px 8px;border:1px solid var(--border);border-radius:4px;box-sizing:border-box"
                            data-tooltip="descripcionFacturaInput">
                    </div>
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
                        <span class="lbl">Renglones contables de gasto</span>
                        <button onclick="agregarRenglon(${i})" style="font-size:11px;padding:2px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg-card);cursor:pointer" data-tooltip="agregarRenglonBtn">+ Agregar</button>
                    </div>
                    <div id="f${i}_renglones"></div>
                </div>

                <div style="margin-top:10px;border-top:0.5px solid var(--border);padding-top:10px">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:0">
                        <input type="checkbox" id="f${i}_esev" onchange="toggleEventualFact(${i})" ${esEventual} data-tooltip="proveedorEventual">
                        <label for="f${i}_esev" style="font-size:12px;cursor:pointer;color:var(--text)">Proveedor eventual</label>
                        <div class="ac-wrap" id="f${i}_provwrap" style="flex:1;${esEventual?'':'display:none'}">
                            <input type="text" id="f${i}_provsearch" placeholder="Proveedor bajo el que se carga…" style="width:100%" data-tooltip="providHidden">
                            <ul class="ac-list" id="f${i}_provlist"></ul>
                        </div>
                        <input type="hidden" id="f${i}_provid" value="${proveedorId}">
                    </div>
                    <div id="f${i}_evpanel" style="${esEventual?'':'display:none'};margin-top:8px;padding:10px;background:#ede8fc;border:1px solid #c9b8f5;border-radius:6px">
                        <div style="font-size:10px;color:#6b40c4;font-weight:600;margin-bottom:6px">
                            DATOS DEL EMISOR REAL
                            ${eventualConocido ? '<span style="background:#d4f0e4;color:#1a7a52;font-size:9px;padding:2px 6px;border-radius:3px;margin-left:6px">✓ NIT conocido</span>' : '<span style="background:#fef3d8;color:#9a6200;font-size:9px;padding:2px 6px;border-radius:3px;margin-left:6px">⚠ NIT nuevo — completar</span>'}
                        </div>
                        <div class="factura-grid">
                            <div class="factura-field"><span class="lbl">Nombre emisor</span>
                                <input type="text" id="f${i}_evnom" value="${eventualNombre}" maxlength="90"></div>
                            <div class="factura-field"><span class="lbl">NIT <span class="tag-auto">auto</span></span>
                                <input type="text" id="f${i}_evnit" value="${eventualNit}" maxlength="15"></div>
                            <div class="factura-field"><span class="lbl">Localidad</span>
                                <input type="text" id="f${i}_evloc" value="${eventualLocalidad}" maxlength="50"></div>
                        </div>
                    </div>
                </div>

                <div style="margin-top:12px;padding-top:10px;border-top:0.5px solid var(--border);display:flex;justify-content:flex-end">
                    <button onclick="eliminarFactura(${i})" class="btn btn-danger btn-sm" style="background:#dc2626;color:white;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;display:flex;align-items:center;gap:6px" data-tooltip="eliminarFactura">
                        🗑️ Eliminar factura
                    </button>
                </div>
            `;
            container.appendChild(div);

            const ctaAuto = f.cuenta_fija || cuentaAutoDesdeDesc(f.descripcion_auto);
            const brutoAuto = f.imp_bruto || '';
            agregarRenglon(i, ctaAuto, brutoAuto);

            if (f.moneda === 'DL') actualizarCotizacion(i);
            document.getElementById(`f${i}_fecha`).addEventListener('change', () => {
                if (document.getElementById(`f${i}_moneda`).value === 'DL') actualizarCotizacion(i);
            });

            setupAC(`f${i}_provsearch`, `f${i}_provlist`, `f${i}_provid`,
                q => fetch(`/api/proveedores?q=${encodeURIComponent(q)}`).then(r => r.json()),
                p => `${p.id} · ${p.nombre}`);
                
        } catch(e) { 
            console.error(`❌ Error renderizando factura ${i}:`, e); 
        }
    }

    if (document.getElementById('toggleEventualGlobal')?.checked) aplicarEventualGlobal();
    
    setTimeout(() => {
        initTooltips();
        console.log('✅ Tooltips actualizados después de renderizar facturas');
    }, 400);
}