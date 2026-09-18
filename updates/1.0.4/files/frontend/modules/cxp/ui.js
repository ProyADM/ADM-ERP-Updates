// ============================================================
// UI - MENSAJES, PROGRESO Y VALIDACIONES (CORREGIDO)
// ============================================================

// ============================================================
// FUNCIÓN DE SANITIZACIÓN
// ============================================================

function sanitizarValor(val) {
    if (val === undefined || val === null) return '';
    return escapeHTML(String(val));
}

export function mostrarMsg(msg, ok) {
    const banner = document.getElementById('cxpBanner');
    if (!banner) return;
    // ✅ CORREGIDO: Usar textContent en lugar de innerHTML
    banner.textContent = msg;
    banner.className = 'banner ' + (ok ? 'ok' : 'err');
    banner.style.display = 'block';
    setTimeout(() => { banner.style.display = 'none'; }, 8000);
}

export function mostrarProgreso(mensaje, porcentaje = null) {
    const container = document.getElementById('cxpProgreso');
    if (!container) {
        const dropZone = document.getElementById('dropZone');
        if (dropZone) {
            const prog = document.createElement('div');
            prog.id = 'cxpProgreso';
            prog.style.cssText = `
                margin-top: 12px;
                padding: 10px 14px;
                background: #f0f4ff;
                border-radius: 8px;
                border: 1px solid #93c5fd;
                display: none;
                font-size: 13px;
                color: #1e293b;
            `;
            prog.innerHTML = `
                <div style="display:flex;align-items:center;gap:10px;">
                    <span class="spinner-small" id="cxpSpinner"></span>
                    <span id="cxpProgresoTexto"></span>
                </div>
                <div id="cxpBarraProgreso" style="margin-top:8px;height:4px;background:#e2e8f0;border-radius:4px;overflow:hidden;display:none;">
                    <div id="cxpBarraProgresoFill" style="height:100%;width:0%;background:#2563eb;border-radius:4px;transition:width 0.3s;"></div>
                </div>
            `;
            dropZone.parentNode.insertBefore(prog, dropZone.nextSibling);
        }
    }
    
    const el = document.getElementById('cxpProgreso');
    if (!el) return;
    
    el.style.display = 'block';
    const texto = document.getElementById('cxpProgresoTexto');
    if (texto) {
        // ✅ CORREGIDO: Usar textContent en lugar de innerHTML
        texto.textContent = sanitizarValor(mensaje);
    }
    
    const barra = document.getElementById('cxpBarraProgreso');
    const fill = document.getElementById('cxpBarraProgresoFill');
    
    if (porcentaje !== null && porcentaje >= 0 && porcentaje <= 100) {
        barra.style.display = 'block';
        fill.style.width = porcentaje + '%';
    } else {
        barra.style.display = 'none';
    }
}

export function ocultarProgreso() {
    const el = document.getElementById('cxpProgreso');
    if (el) el.style.display = 'none';
}

export function validarBaseGT() {
    const base = window.baseActiva || 'plataforma_rd';
    const modulo = document.getElementById('cxp-facturas');
    if (!modulo) return false;
    
    let msg = document.getElementById('cxp-gt-only');
    
    if (base !== 'plataforma_gt') {
        const cards = modulo.querySelectorAll('.card');
        cards.forEach(c => c.style.display = 'none');
        const btnCargarTodo = document.getElementById('btnCargarTodo');
        if (btnCargarTodo) btnCargarTodo.style.display = 'none';
        const facturasContainer = document.getElementById('facturasContainer');
        if (facturasContainer) facturasContainer.style.display = 'none';
        
        if (!msg) {
            msg = document.createElement('div');
            msg.id = 'cxp-gt-only';
            msg.style.cssText = 'padding:40px 20px; text-align:center; background:#fef3f2; border-radius:8px; border:1px solid #fecdc9; margin:20px 0;';
            // ✅ CORREGIDO: HTML fijo con datos sanitizados
            const baseLabel = window.BASES_DISPONIBLES_FRONT?.[base]?.label || base;
            msg.innerHTML = `
                <div style="font-size:48px; margin-bottom:12px;">⚠️</div>
                <h3 style="color:#b42318; margin:0 0 8px 0;">Cargador de Facturas exclusivo para Guatemala</h3>
                <p style="color:#64748b; margin:0;">Seleccioná la base <strong>"Guatemala"</strong> para utilizar esta funcionalidad.</p>
                <p style="color:#64748b; font-size:12px; margin-top:8px;">Base actual: <strong>${escapeHTML(baseLabel)}</strong></p>
            `;
            modulo.prepend(msg);
        }
        msg.style.display = 'block';
        return false;
    }
    
    const cards = modulo.querySelectorAll('.card');
    cards.forEach(c => c.style.display = 'block');
    const facturasContainer = document.getElementById('facturasContainer');
    if (facturasContainer) facturasContainer.style.display = 'block';
    const btnCargarTodo = document.getElementById('btnCargarTodo');
    if (btnCargarTodo && window.facturasData?.length > 0) btnCargarTodo.style.display = 'block';
    if (msg) msg.style.display = 'none';
    return true;
}

export async function cargarCondicionesPago() {
    const sel = document.getElementById("rendCondPago");
    if (!sel) return;
    
    try {
        const API = window.API || '/api';
        window.condiciones = await fetch(`${API}/condiciones_pago`).then(r => r.json());
        sel.innerHTML = '';
        window.condiciones.forEach(c => {
            const o = document.createElement('option');
            // ✅ CORREGIDO: Usar textContent en lugar de innerHTML
            o.value = c.id;
            o.textContent = `${c.id} · ${c.nombre}`;
            sel.appendChild(o);
        });
        if (sel.querySelector('option[value="00"]')) sel.value = '00';
        setTimeout(() => validarBaseGT(), 300);
    } catch (e) {
        console.warn('Error cargando condiciones de pago:', e);
    }
}