// ============================================================
// COTIZACIONES - CORREGIDO (XSS SANITIZADO)
// ============================================================

// Función de sanitización
function getPaisesDisponibles() {
    return [
        { id: 'GT', label: 'Guatemala', base: 'plataforma_gt' },
        { id: 'HN', label: 'Honduras', base: 'plataforma_hn' },
        { id: 'RD', label: 'República Dominicana', base: 'plataforma_rd' },
        { id: 'UY', label: 'Uruguay', base: 'plataforma_ur' },
        { id: 'CO', label: 'Colombia', base: 'plataforma_co' },
        { id: 'PE', label: 'Perú', base: 'plataforma_pe' },
        { id: 'PY', label: 'Paraguay', base: 'plataforma_py' },
        { id: 'EC', label: 'Ecuador', base: 'plataforma_ec' },
        { id: 'MX', label: 'México', base: 'plataforma_mx' },
        { id: 'CR', label: 'Costa Rica', base: 'plataforma_cr' },
        { id: 'AR', label: 'Argentina', base: 'plataforma' }
    ];
}

function getPaisesSeleccionados() {
    const paises = getPaisesDisponibles();
    const seleccionados = [];
    paises.forEach(p => {
        const checkbox = document.getElementById(`coti${p.id}`);
        if (checkbox && checkbox.checked) {
            seleccionados.push(p);
        }
    });
    return seleccionados;
}

async function cargarHistoricoCoti() {
    const div = document.getElementById('cotiHistorico');
    if (!div) {
        console.warn('⚠️ No se encontró #cotiHistorico');
        return;
    }
    
    div.innerHTML = '<div style="text-align:center;padding:20px;color:#94a3b8;">⏳ Cargando datos...</div>';
    
    try {
        const data = await fetch('/api/cotizaciones/historico').then(r => r.json());
        const html = generarResumenMensual(data);
        div.innerHTML = html;
    } catch(e) {
        div.innerHTML = `<div style="color:#dc2626;padding:20px;text-align:center;">❌ Error al cargar: ${escapeHTML(e.message)}</div>`;
        console.error('Error cargando histórico:', e);
    }
}

function generarResumenMensual(data) {
    const paises = getPaisesDisponibles();
    const anioSeleccionado = parseInt(document.getElementById('selectorAnio')?.value || new Date().getFullYear());
    
    const paisesActivos = paises.filter(p => {
        if (p.id === 'EC') return true;
        const rows = data[p.id];
        return rows && !rows.error && rows.length > 0;
    });
    
    if (paisesActivos.length === 0) {
        return `<div style="text-align:center;padding:30px;color:#94a3b8;">
            📭 No hay cotizaciones cargadas aún.
        </div>`;
    }
    
    const mesesMap = new Map();
    for (let mes = 1; mes <= 12; mes++) {
        const key = `${anioSeleccionado}-${String(mes).padStart(2, '0')}`;
        mesesMap.set(key, {
            key: key,
            numero: mes,
            anio: anioSeleccionado,
            valores: {}
        });
    }
    
    paisesActivos.forEach(p => {
        const rows = data[p.id] || [];
        rows.forEach(row => {
            const fecha = new Date(row.fecha + 'T00:00:00');
            const anio = fecha.getFullYear();
            const mes = fecha.getMonth() + 1;
            const key = `${anio}-${String(mes).padStart(2, '0')}`;
            
            if (mesesMap.has(key)) {
                const mesData = mesesMap.get(key);
                const fechaNum = fecha.getTime();
                if (!mesData.valores[p.id] || fechaNum > mesData.valores[p.id].fecha) {
                    mesData.valores[p.id] = {
                        valor: p.id === 'EC' ? 1.0 : parseFloat(row.cotizacion).toFixed(5),
                        fecha: fechaNum,
                        fechaStr: row.fecha
                    };
                }
            }
        });
    });
    
    paisesActivos.forEach(p => {
        if (p.id === 'EC') {
            mesesMap.forEach(mes => {
                if (!mes.valores['EC']) {
                    const fecha = new Date(anioSeleccionado, mes.numero - 1, 1);
                    mes.valores['EC'] = {
                        valor: '1.00000',
                        fecha: fecha.getTime(),
                        fechaStr: fecha.toISOString().split('T')[0]
                    };
                }
            });
        }
    });
    
    const meses = Array.from(mesesMap.values())
        .sort((a, b) => a.numero - b.numero);
    
    const añosConDatos = [...new Set(
        Object.entries(data)
            .filter(([key, val]) => key !== 'EC' && val && !val.error && val.length > 0)
            .flatMap(([key, val]) => val.map(r => new Date(r.fecha + 'T00:00:00').getFullYear()))
    )].sort((a, b) => b - a);
    
    const añosDisponibles = añosConDatos.length > 0 ? añosConDatos : [new Date().getFullYear()];
    const nombresMeses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    const nombresCortos = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    
    let html = `
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap;">
            <span style="font-weight:500;font-size:13px;color:#475569;">📅 Año:</span>
            <select id="selectorAnio" data-onchange="cambiarAnioCotizaciones()" style="padding:4px 12px;border:1px solid #d1d5db;border-radius:4px;font-size:13px;background:white;cursor:pointer;">
    `;
    
    añosDisponibles.forEach(a => {
        html += `<option value="${a}" ${a === anioSeleccionado ? 'selected' : ''}>${a}</option>`;
    });
    html += `</select>
            <span style="font-size:12px;color:#94a3b8;">${meses.length} meses</span>
        </div>
        
        <div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:8px;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                    <tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0;">
                        <th style="padding:8px 12px;text-align:left;font-weight:600;color:#475569;position:sticky;left:0;background:#f8fafc;z-index:2;min-width:100px;">País</th>
    `;
    
    meses.forEach(mes => {
        const esMesActual = mes.numero === new Date().getMonth() + 1;
        html += `<th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569;min-width:90px;font-size:12px;${esMesActual ? 'background:#dbeafe;' : ''}">
            ${mes.numero}
            <div style="font-weight:400;font-size:9px;color:#94a3b8;">${nombresCortos[mes.numero - 1]}</div>
        </th>`;
    });
    html += `</tr></thead><tbody>`;
    
    paisesActivos.forEach(p => {
        const tieneError = data[p.id]?.error;
        const esEcuador = p.id === 'EC';
        const paisId = escapeHTML(p.id);
        const paisLabel = escapeHTML(p.label);
        
        html += `<tr style="border-bottom:1px solid #f1f5f9;">`;
        html += `<td style="padding:8px 12px;font-weight:500;color:#1e293b;position:sticky;left:0;background:white;z-index:1;">
            ${paisId} ${tieneError ? '⚠️' : ''}
            ${esEcuador ? '<span style="font-size:10px;color:#16a34a;">(USD)</span>' : ''}
        </td>`;
        
        meses.forEach(mes => {
            const valor = mes.valores[p.id];
            const esMesActual = mes.numero === new Date().getMonth() + 1;
            
            if (tieneError) {
                html += `<td style="padding:8px 12px;text-align:right;color:#dc2626;font-size:12px;">⚠️</td>`;
            } else if (valor) {
                const valorStr = escapeHTML(valor.valor);
                const fechaStr = escapeHTML(valor.fechaStr || '');
                html += `<td style="padding:8px 12px;text-align:right;font-variant-numeric:tabular-nums;${esMesActual ? 'background:#f0f4ff;' : ''}">
                    ${valorStr}
                    <div style="font-size:8px;color:#94a3b8;">${fechaStr}</div>
                </td>`;
            } else {
                html += `<td style="padding:8px 12px;text-align:right;color:#94a3b8;font-size:12px;">—</td>`;
            }
        });
        html += `</tr>`;
    });
    
    html += `</tbody></table></div>`;
    
    const paisesError = Object.entries(data).filter(([key, value]) => value.error && key !== 'EC');
    if (paisesError.length > 0) {
        const errores = paisesError.map(([k]) => k).join(', ');
        const detalle = escapeHTML(paisesError[0][1].error || 'No se pudo conectar');
        html += `<div style="margin-top:12px;padding:8px 12px;background:#fef3f2;border:1px solid #fecdc9;border-radius:6px;font-size:12px;color:#b42318;">
            ⚠️ Error en: ${escapeHTML(errores)} — ${detalle}
        </div>`;
    }
    
    return html;
}

function cambiarAnioCotizaciones() {
    cargarHistoricoCoti();
}

async function guardarCotizacion() {
    const fecha = document.getElementById('cotiDate').value;
    const valorRaw = document.getElementById('cotiValor').value.replace(',', '.');
    const valor = parseFloat(valorRaw);
    if (!fecha || !valor) return mostrarMsg('Completá fecha y cotización.', false);
    
    const seleccionados = getPaisesSeleccionados();
    if (!seleccionados.length) return mostrarMsg('Seleccioná al menos un país.', false);
    
    const bases = seleccionados.map(p => p.id);

    const res = await fetch('/api/cotizaciones/guardar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify([{fecha, cotizacion: valor, bases}])
    }).then(r => r.json());

    if (res.ok) {
        const basesStr = bases.join(', ');
        mostrarMsg(`✅ Cotización ${valor} para ${escapeHTML(basesStr)} guardada.`, true);
        cargarHistoricoCoti();
        document.getElementById('cotiValor').value = '';
    } else {
        const errores = res.errores?.join(' | ') || 'Error al guardar';
        mostrarMsg(escapeHTML(errores), false);
    }
}

// Estado de la importación pendiente de confirmar (preview → importar)
let _importPendiente = null;

async function importarExcelCoti() {
    const file = document.getElementById('cotiExcel').files[0];
    if (!file) return mostrarMsg('Seleccioná un archivo Excel.', false);
    
    // Limpiar resultado anterior y ocultar el área de preview.
    const prevResult = document.getElementById('cotiPreview');
    if (prevResult) { prevResult.innerHTML = ''; prevResult.style.display = 'none'; }
    
    // La selección de países es opcional si la planilla trae la columna "País".
    const seleccionados = getPaisesSeleccionados();
    const bases = seleccionados.map(p => p.id);
    
    const b64 = await toBase64(file);
    
    // 1) PREVIEW (dry_run): no escribe nada; muestra qué se va a importar.
    let res;
    try {
        res = await fetch('/api/cotizaciones/importar_excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_b64: b64, bases, dry_run: true })
        }).then(r => r.json());
    } catch (e) {
        return mostrarMsg('Error al previsualizar: ' + e.message, false);
    }
    
    if (!res.ok || res.error) {
        return mostrarMsg(res.error || 'No se pudo previsualizar el archivo.', false);
    }
    if (!res.filas_validas || res.filas_validas <= 0) {
        return mostrarMsg('El archivo no tiene filas válidas para importar.', false);
    }
    
    _importPendiente = { b64, bases };
    mostrarModalConfirmacion(res);
}

function mostrarModalConfirmacion(res) {
    cerrarModalImport();
    
    const porPais = res.por_pais || {};
    const paisesHtml = Object.keys(porPais).length
        ? Object.entries(porPais).map(([sigla, n]) => `<b>${escapeHTML(sigla)}</b>: ${n}`).join(' · ')
        : '—';
    
    let erroresHtml = '';
    if (res.errores && res.errores.length) {
        const primeras = res.errores.slice(0, 5).map(e => escapeHTML(e)).join('<br>');
        erroresHtml = `
            <div style="margin-bottom:12px;padding:8px 10px;background:#fef3f2;border:1px solid #fecdc9;border-radius:6px;font-size:12px;color:#b42318;">
                ⚠️ ${res.errores.length} fila(s) ignorada(s) (no se importarán):<br>${primeras}${res.errores.length > 5 ? '<br>…' : ''}
            </div>`;
    }
    
    const overlay = document.createElement('div');
    overlay.id = 'modal-confirmar-import-coti';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:20000;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;';
    overlay.innerHTML = `
        <div style="background:#fff;border-radius:12px;padding:22px 24px;max-width:520px;width:95%;box-shadow:0 12px 40px rgba(0,0,0,.25);font-size:13px;color:#1e293b;max-height:90vh;overflow-y:auto;">
            <h3 style="margin:0 0 12px;font-size:16px;">⚠️ ¿Importar cotizaciones?</h3>
            <div style="margin-bottom:10px;">Se van a importar <b>${res.filas_validas}</b> fila(s). Desglose por país destino:</div>
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;margin-bottom:12px;font-weight:600;line-height:1.7;">${paisesHtml}</div>
            ${erroresHtml}
            <div style="font-size:12px;color:#64748b;margin-bottom:16px;">Revisá que los países destinos sean los correctos antes de confirmar.</div>
            <div style="display:flex;justify-content:flex-end;gap:8px;">
                <button data-onclick="cancelarImportarCoti()" style="padding:7px 16px;border-radius:6px;border:1px solid #cbd5e1;background:white;color:#334155;cursor:pointer;font-weight:600;">Cancelar</button>
                <button data-onclick="confirmarImportarCoti()" style="padding:7px 16px;border-radius:6px;border:none;background:#2563eb;color:white;cursor:pointer;font-weight:600;">Sí, importar</button>
            </div>
        </div>`;
    document.body.appendChild(overlay);
}

function cerrarModalImport() {
    const overlay = document.getElementById('modal-confirmar-import-coti');
    if (overlay) overlay.remove();
}

window.confirmarImportarCoti = async function() {
    if (!_importPendiente) return;
    const { b64, bases } = _importPendiente;
    cerrarModalImport();
    mostrarSpinnerImport('⏳ Importando cotizaciones… no cierres la ventana.');
    try {
        const res = await fetch('/api/cotizaciones/importar_excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_b64: b64, bases })
        }).then(r => r.json());
        
        cargarHistoricoCoti();
        const inputFile = document.getElementById('cotiExcel');
        if (inputFile) inputFile.value = '';
        
        mostrarResultadoImport(res);
    } catch (e) {
        mostrarMsg('Error al importar: ' + e.message, false);
    } finally {
        ocultarSpinnerImport();
        _importPendiente = null;
    }
};

// Muestra el resultado final de la importación bajo el botón "Importar"
// (#cotiPreview), con estilo persistente hasta la próxima importación.
function mostrarResultadoImport(res) {
    const prev = document.getElementById('cotiPreview');
    if (!prev) return;
    
    const nIgnoradas = (res.errores && res.errores.length) ? res.errores.length : 0;
    let inner = '';
    
    if (res.insertados > 0) {
        inner = `<div style="padding:10px 14px;border-radius:8px;background:#f0fdf4;border:1px solid #86efac;color:#166534;font-size:13px;font-weight:600;">
            ✅ Se importaron ${res.insertados} cotización(es).</div>`;
        if (nIgnoradas > 0) {
            const primeras = res.errores.slice(0, 3).map(e => escapeHTML(e)).join('<br>');
            inner += `<div style="margin-top:6px;padding:8px 12px;border-radius:8px;background:#fef3f2;border:1px solid #fecdc9;color:#b42318;font-size:12px;">
                ⚠️ ${nIgnoradas} fila(s) ignorada(s):<br>${primeras}${nIgnoradas > 3 ? '<br>…' : ''}</div>`;
        }
    } else if (nIgnoradas) {
        const primeras = res.errores.slice(0, 3).map(e => escapeHTML(e)).join('<br>');
        inner = `<div style="padding:10px 14px;border-radius:8px;background:#fef3f2;border:1px solid #fecdc9;color:#b42318;font-size:13px;">
            ❌ No se importó nada. ${nIgnoradas} fila(s) inválida(s):<br>${primeras}${nIgnoradas > 3 ? '<br>…' : ''}</div>`;
    } else {
        inner = `<div style="padding:10px 14px;border-radius:8px;background:#fef3f2;border:1px solid #fecdc9;color:#b42318;font-size:13px;">
            ❌ ${escapeHTML(res.error || 'Error al importar')}</div>`;
    }
    
    prev.innerHTML = inner;
    prev.style.display = 'block';
    prev.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

window.cancelarImportarCoti = function() {
    cerrarModalImport();
    _importPendiente = null;
};

function mostrarSpinnerImport(mensaje) {
    ocultarSpinnerImport();
    const overlay = document.createElement('div');
    overlay.id = 'coti-import-spinner';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:21000;background:rgba(15,23,42,.6);display:flex;flex-direction:column;align-items:center;justify-content:center;color:white;font-size:15px;font-weight:600;gap:14px;';
    const style = document.createElement('style');
    style.textContent = '@keyframes cotiSpin { to { transform: rotate(360deg); } }';
    const anim = document.createElement('div');
    anim.style.cssText = 'width:34px;height:34px;border:4px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:cotiSpin 0.9s linear infinite;';
    const texto = document.createElement('span');
    texto.textContent = mensaje || '⏳ Importando cotizaciones…';
    overlay.appendChild(style);
    overlay.appendChild(anim);
    overlay.appendChild(texto);
    document.body.appendChild(overlay);
}

function ocultarSpinnerImport() {
    const overlay = document.getElementById('coti-import-spinner');
    if (overlay) overlay.remove();
}

function toBase64(file) {
    return new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result.split(',')[1]);
        r.onerror = rej;
        r.readAsDataURL(file);
    });
}

function mostrarMsg(msg, ok) {
    const div = document.getElementById('msg');
    if (!div) return;
    div.textContent = msg;
    div.className = `msg ${ok ? 'ok' : 'error'}`;
    div.style.display = 'block';
    setTimeout(() => { div.style.display = 'none'; }, 8000);
}

window.cargarHistoricoCoti = cargarHistoricoCoti;
window.guardarCotizacion = guardarCotizacion;
window.importarExcelCoti = importarExcelCoti;
window.getPaisesDisponibles = getPaisesDisponibles;
window.getPaisesSeleccionados = getPaisesSeleccionados;
window.cambiarAnioCotizaciones = cambiarAnioCotizaciones;
window.toBase64 = toBase64;
window.mostrarMsg = mostrarMsg;

console.log('✅ Cotizaciones.js actualizado - XSS sanitizado');