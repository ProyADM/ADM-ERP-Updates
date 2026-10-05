// ============================================================
// REPORTE: PENDIENTE DE COBRO
// ============================================================

let datosPendienteCobro = [];
let filtroRango = 'todos';
let filtroTipoCliente = 'todos';
// Fecha de corte del informe: '' = HOY (el informe de siempre). Con una fecha
// anterior, el backend devuelve el pendiente de cobro A ESA FECHA.
let fechaCorte = '';

// Vista agrupada por cliente (acordeón): grupos del render actual + cuáles están
// abiertos. Es un CONJUNTO (no un índice suelto) porque puede haber varios
// abiertos a la vez y TODOS arrancan cerrados (el usuario abre el que quiere).
let gruposPendienteCobro = [];
let gruposAbiertos = new Set();
// Los comprobantes que quedaron despues de aplicar los filtros: lo deja
// `prepararDatosPendienteCobro()` y lo usan las tarjetas de totales.
let datosFiltradosPendienteCobro = [];

// Arma `gruposPendienteCobro` con los datos ya filtrados, MANTENIENDO el orden
// de la BD (Cliente ASC, Fecha ASC). Si no queda ningún comprobante, el conjunto
// queda VACÍO (la vista muestra el cartel de "no hay datos"). Está separada del
// render para poder reiniciar el estado del acordeón con los grupos NUEVOS.
function prepararDatosPendienteCobro() {
    let datosFiltrados = datosPendienteCobro;
    if (filtroRango !== 'todos') {
        datosFiltrados = datosFiltrados.filter(row => row.Rango_Dias === filtroRango);
    }
    if (filtroTipoCliente === 'intercompany') {
        datosFiltrados = datosFiltrados.filter(row => row.TipoCliente === '5');
    } else if (filtroTipoCliente === 'cliente') {
        datosFiltrados = datosFiltrados.filter(row => row.TipoCliente !== '5' || row.TipoCliente === null || row.TipoCliente === '');
    }

    datosFiltradosPendienteCobro = datosFiltrados;

    const gruposMap = new Map();
    datosFiltrados.forEach(row => {
        const clave = row.Cliente || '';
        if (!gruposMap.has(clave)) gruposMap.set(clave, []);
        gruposMap.get(clave).push(row);
    });
    gruposPendienteCobro = Array.from(gruposMap, ([cliente, rows]) => {
        let sp = 0, sd = 0;
        rows.forEach(r => {
            sp += parseFloat(r.PESOS || 0);
            sd += parseFloat(r.DOLARES || 0);
        });
        return { cliente, rows, totalPesos: sp, totalDolares: sd };
    });
}

// Estado inicial del acordeón: los clientes con UNA sola factura arrancan con el
// detalle abierto (si no, su comprobante, su fecha y su tipo no se ven en ningún
// lado: la columna `N° Compr.` muestra la CANTIDAD). Los de dos o más arrancan
// cerrados. Se llama UNA VEZ por carga de datos o cambio de filtro, NUNCA desde
// el render: si se llamara en cada re-render, el usuario no podría cerrar un
// cliente de una sola factura (el clic re-renderiza y lo volvería a abrir).
// TODOS los clientes arrancan CERRADOS: el triangulo esta siempre y el usuario abre
// el que quiere (decision del 24/09/2026 del usuario, que revierte el "el de una sola
// factura arranca abierto" del brief anterior: con 19 clientes de una sola factura la
// lista quedaba larguisima). Se llama UNA VEZ por carga de datos o cambio de filtro,
// NUNCA desde el render: si se llamara en cada re-render, el usuario no podria cerrar
// un cliente (el clic re-renderiza y lo volveria a abrir).
function reiniciarGruposAbiertos() {
    gruposAbiertos = new Set();
}

export async function cargarPendienteCobro() {
    console.log('📊 Cargando reporte de Pendiente de Cobro...');
    
    const container = document.getElementById('reporte-pendiente-cobro');
    if (!container) {
        console.warn('⚠️ No se encontró #reporte-pendiente-cobro');
        return;
    }
    
    container.innerHTML = '<div style="text-align:center;padding:20px;color:#94a3b8;">⏳ Cargando datos...</div>';
    
    try {
        const base = window.baseActiva || 'plataforma_rd';
        // Con `fechaCorte` vacia la URL es la de siempre (el informe de HOY).
        const url = `/api/reportes/pendiente_cobro?base=${base}`
            + (fechaCorte ? `&fecha=${fechaCorte}` : '');
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        
        if (!data.success || data.error) {
            container.innerHTML = `<div style="color:#dc2626;padding:20px;text-align:center;">❌ ${escapeHTML(data.error || 'Error al cargar datos')}</div>`;
            return;
        }
        
        datosPendienteCobro = data.data || [];
        filtroRango = 'todos';
        filtroTipoCliente = 'todos';
        prepararDatosPendienteCobro();
        reiniciarGruposAbiertos();
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    } catch (e) {
        console.error('❌ Error cargando pendiente de cobro:', e);
        container.innerHTML = `<div style="color:#dc2626;padding:20px;text-align:center;">❌ Error: ${escapeHTML(e.message)}</div>`;
    }
}

function generarVistaPendienteCobro(datos) {
    // 🔴 AGRUPAR POR CLIENTE (preserva el orden de la BD: Cliente ASC, Fecha ASC)
    // Los filtros se aplican en UN solo lugar (`prepararDatosPendienteCobro`), que
    // deja `gruposPendienteCobro` y `datosFiltradosPendienteCobro`.
    prepararDatosPendienteCobro();
    // OJO: aca NO se reinicia el conjunto de abiertos. El reinicio va UNA vez por
    // carga de datos y por cambio de filtro (los otros tres puntos); si se hiciera
    // en el render, el clic sobre un cliente volveria a abrirlo (el clic
    // re-renderiza) y no se podria cerrar el de una sola factura. Medido: con el
    // reinicio aca, el probe 320 daba 10 fallos.
    if (gruposPendienteCobro.length === 0) {
        return `<div style="text-align:center;padding:30px;color:#94a3b8;">📭 No hay datos para los filtros seleccionados</div>`;
    }
    
    // 🔴 CALCULAR TOTALES (sobre los comprobantes filtrados)
    let totalPesos = 0;
    let totalDolares = 0;
    
    datosFiltradosPendienteCobro.forEach(row => {
        totalPesos += parseFloat(row.PESOS || 0);
        totalDolares += parseFloat(row.DOLARES || 0);
    });
    
    // 🔴 CONTAR CLIENTES (los de los comprobantes filtrados)
    const clientes = new Set(datosFiltradosPendienteCobro.map(r => r.Cliente));
    
    // 🔴 CONTAR REGISTROS POR RANGO (usando datos originales para los conteos)
    const rangoCounts = {
        '=< 30 días': datos.filter(r => r.Rango_Dias === '=< 30 días').length,
        '>30 días y <= 90 días': datos.filter(r => r.Rango_Dias === '>30 días y <= 90 días').length,
        '> 90 días': datos.filter(r => r.Rango_Dias === '> 90 días').length
    };
    
    // 🔴 CONTAR REGISTROS POR TIPO DE CLIENTE
    const intercompanyCount = datos.filter(r => r.TipoCliente === '5').length;
    const clienteCount = datos.filter(r => r.TipoCliente !== '5' || r.TipoCliente === null || r.TipoCliente === '').length;
    
    let html = `
        <!-- FILTROS -->
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap;padding:12px 16px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">
            <span style="font-weight:500;font-size:13px;color:#475569;">📋 Rango:</span>
            <button data-onclick="cambiarFiltroRango('todos')" 
                    class="btn-rango ${filtroRango === 'todos' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #d1d5db;background:${filtroRango === 'todos' ? '#2563eb' : 'white'};color:${filtroRango === 'todos' ? 'white' : '#475569'};cursor:pointer;font-size:12px;font-weight:500;">
                Todos (${datos.length})
            </button>
            <button data-onclick="cambiarFiltroRango('=< 30 días')" 
                    class="btn-rango ${filtroRango === '=< 30 días' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #16a34a;background:${filtroRango === '=< 30 días' ? '#16a34a' : 'white'};color:${filtroRango === '=< 30 días' ? 'white' : '#16a34a'};cursor:pointer;font-size:12px;font-weight:500;">
                ≤ 30 días (${rangoCounts['=< 30 días']})
            </button>
            <button data-onclick="cambiarFiltroRango('>30 días y <= 90 días')" 
                    class="btn-rango ${filtroRango === '>30 días y <= 90 días' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #f59e0b;background:${filtroRango === '>30 días y <= 90 días' ? '#f59e0b' : 'white'};color:${filtroRango === '>30 días y <= 90 días' ? 'white' : '#f59e0b'};cursor:pointer;font-size:12px;font-weight:500;">
                30-90 días (${rangoCounts['>30 días y <= 90 días']})
            </button>
            <button data-onclick="cambiarFiltroRango('> 90 días')" 
                    class="btn-rango ${filtroRango === '> 90 días' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #dc2626;background:${filtroRango === '> 90 días' ? '#dc2626' : 'white'};color:${filtroRango === '> 90 días' ? 'white' : '#dc2626'};cursor:pointer;font-size:12px;font-weight:500;">
                > 90 días (${rangoCounts['> 90 días']})
            </button>
            
            <span style="font-weight:500;font-size:13px;color:#475569;margin-left:16px;">👤 Tipo:</span>
            <button data-onclick="cambiarFiltroTipoCliente('todos')" 
                    class="btn-tipo ${filtroTipoCliente === 'todos' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #d1d5db;background:${filtroTipoCliente === 'todos' ? '#2563eb' : 'white'};color:${filtroTipoCliente === 'todos' ? 'white' : '#475569'};cursor:pointer;font-size:12px;font-weight:500;">
                Todos (${datos.length})
            </button>
            <button data-onclick="cambiarFiltroTipoCliente('cliente')" 
                    class="btn-tipo ${filtroTipoCliente === 'cliente' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #2563eb;background:${filtroTipoCliente === 'cliente' ? '#2563eb' : 'white'};color:${filtroTipoCliente === 'cliente' ? 'white' : '#2563eb'};cursor:pointer;font-size:12px;font-weight:500;">
                Clientes (${clienteCount})
            </button>
            <button data-onclick="cambiarFiltroTipoCliente('intercompany')" 
                    class="btn-tipo ${filtroTipoCliente === 'intercompany' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #7c3aed;background:${filtroTipoCliente === 'intercompany' ? '#7c3aed' : 'white'};color:${filtroTipoCliente === 'intercompany' ? 'white' : '#7c3aed'};cursor:pointer;font-size:12px;font-weight:500;">
                Intercompany (${intercompanyCount})
            </button>
            
            <span style="font-weight:500;font-size:13px;color:#475569;margin-left:16px;">📅 Pendiente al:</span>
            <input type="date" id="fecha-corte-cobro" value="${fechaCorte || fechaHoyISO()}"
                   max="${fechaHoyISO()}" data-onchange="cambiarFechaCorte(this)"
                   title="Elegí una fecha para ver el pendiente de cobro a ese día (por defecto, hoy)"
                   style="width:150px;height:28px;flex:0 0 auto;padding:2px 8px;border-radius:4px;border:1px solid #d1d5db;font-size:12px;color:#334155;background:white;">
            ${fechaCorte ? '<button data-onclick="volverAFechaHoy()" title="Volver al pendiente de hoy" style="padding:4px 12px;border-radius:4px;border:1px solid #2563eb;background:#2563eb;color:white;cursor:pointer;font-size:12px;font-weight:600;">Hoy</button>' : ''}
            <span style="flex:1"></span>
            <button data-onclick="exportarCobroExcel()" title="Descargar el detalle a Excel (.xlsx)" style="padding:5px 14px;border-radius:6px;border:none;background:#16a34a;color:white;cursor:pointer;font-size:12px;font-weight:600;">📥 Exportar Excel</button>
            <button data-onclick="enviarCobroPorCorreo()" title="Enviar el mismo Excel por correo (Outlook de esta PC)" style="padding:5px 14px;border-radius:6px;border:none;background:#0ea5e9;color:white;cursor:pointer;font-size:12px;font-weight:600;">✉️ Enviar por correo</button>
            <button data-onclick="refrescarPendienteCobro()" title="Recargar datos de la base activa" style="padding:5px 14px;border-radius:6px;border:1px solid #94a3b8;background:white;color:#334155;cursor:pointer;font-size:12px;font-weight:600;">↻ Actualizar</button>
        </div>
        
        ${fechaCorte ? `<div style="margin-bottom:12px;padding:8px 12px;border-radius:8px;background:#fffbeb;border:1px solid #fcd34d;color:#92400e;font-size:12px;font-weight:600;">📅 Mostrando el pendiente de cobro AL ${formatearFechaCorte(fechaCorte)} (no el de hoy).</div>` : ''}
        
        <!-- TOTALES -->
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;">
            <div style="background:#f0f4ff;padding:12px 16px;border-radius:8px;border:1px solid #93c5fd;">
                <div style="font-size:11px;color:#64748b;">Total Clientes</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${clientes.size}</div>
            </div>
            <div style="background:#f0fdf4;padding:12px 16px;border-radius:8px;border:1px solid #86efac;">
                <div style="font-size:11px;color:#64748b;">Total Comprobantes</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${datosFiltradosPendienteCobro.length}</div>
            </div>
            <div style="background:#fef3f2;padding:12px 16px;border-radius:8px;border:1px solid #fecdc9;">
                <div style="font-size:11px;color:#64748b;">Total PESOS</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${formatearNumero(totalPesos)}</div>
            </div>
            <div style="background:#fef3f2;padding:12px 16px;border-radius:8px;border:1px solid #fecdc9;">
                <div style="font-size:11px;color:#64748b;">Total DOLARES</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${formatearNumero(totalDolares)}</div>
            </div>
        </div>
        
        <!-- TABLA AGRUPADA POR CLIENTE -->
        <div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:8px;">
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
                <thead style="background:#f8fafc;">
                    <tr style="border-bottom:2px solid #e2e8f0;">
                        <th style="padding:6px 10px;text-align:left;font-weight:600;color:#475569;min-width:220px;">Cliente</th>
                        <th style="padding:6px 10px;text-align:center;font-weight:600;color:#475569;min-width:110px;">N° Comprob.</th>
                        <th style="padding:6px 10px;text-align:right;font-weight:600;color:#475569;min-width:140px;">PESOS</th>
                        <th style="padding:6px 10px;text-align:right;font-weight:600;color:#475569;min-width:140px;">DOLARES</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    gruposPendienteCobro.forEach((g, gi) => {
        // Un grupo existe sólo si tiene al menos una fila, así que SIEMPRE tiene
        // detalle: todos los clientes llevan triángulo y son clickeables.
        const tieneDetalle = true;
        const abierto = gruposAbiertos.has(gi);
        const nombreCliente = escapeHTML(g.cliente || '—');
        
        html += `
            <tr ${tieneDetalle ? `data-onclick="toggleCliente(${gi})"` : ''} title="${tieneDetalle ? 'Clic para ver detalle' : ''}"
                style="cursor:${tieneDetalle ? 'pointer' : 'default'};border-bottom:1px solid #f1f5f9;background:${abierto ? '#eef2f7' : (gi % 2 === 0 ? '#fafafa' : 'white')};">
                <td style="padding:7px 10px;font-weight:600;font-size:12px;">
                    <span style="display:inline-block;width:18px;color:${tieneDetalle ? '#64748b' : 'transparent'};">${tieneDetalle ? (abierto ? '▾' : '▸') : ''}</span>
                    ${nombreCliente}
                </td>
                <td style="padding:7px 10px;text-align:center;font-size:12px;color:#475569;">${g.rows.length}</td>
                <td style="padding:7px 10px;text-align:right;font-weight:${g.totalPesos !== 0 ? '600' : '400'};color:${g.totalPesos < 0 ? '#dc2626' : g.totalPesos > 0 ? '#1e293b' : '#94a3b8'};">
                    ${formatearNumero(g.totalPesos)}
                </td>
                <td style="padding:7px 10px;text-align:right;font-weight:${g.totalDolares !== 0 ? '600' : '400'};color:${g.totalDolares < 0 ? '#dc2626' : g.totalDolares > 0 ? '#1e293b' : '#94a3b8'};">
                    ${formatearNumero(g.totalDolares)}
                </td>
            </tr>
        `;
        
        if (abierto) {
            html += `
            <tr style="border-bottom:1px solid #f1f5f9;background:#fbfcfe;">
                <td colspan="4" style="padding:2px 12px 10px 26px;">
                    <table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:6px;">
                        <thead>
                            <tr style="background:#eef2f7;border-bottom:1px solid #e2e8f0;">
                                <th style="padding:4px 8px;text-align:left;font-weight:600;color:#475569;">Fecha</th>
                                <th style="padding:4px 8px;text-align:left;font-weight:600;color:#475569;">Comprobante</th>
                                <th style="padding:4px 8px;text-align:center;font-weight:600;color:#475569;">Tipo</th>
                                <th style="padding:4px 8px;text-align:right;font-weight:600;color:#475569;">PESOS</th>
                                <th style="padding:4px 8px;text-align:right;font-weight:600;color:#475569;">DOLARES</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            g.rows.forEach(row => {
                const pesos = parseFloat(row.PESOS || 0);
                const dolares = parseFloat(row.DOLARES || 0);
                const esIntercompany = row.TipoCliente === '5';
                const tipoLabel = esIntercompany ? 'Intercompany' : 'Cliente';
                const tipoColor = esIntercompany ? '#7c3aed' : '#2563eb';
                let fechaStr = '—';
                if (row.Fecha) {
                    const fecha = new Date(row.Fecha);
                    if (!isNaN(fecha)) {
                        fechaStr = fecha.toLocaleDateString('es-ES', { year: 'numeric', month: '2-digit', day: '2-digit' });
                    }
                }
                const rango = row.Rango_Dias || '=< 30 días';
                let rowColor = '';
                if (rango === '> 90 días') rowColor = '#fef2f2';
                else if (rango === '>30 días y <= 90 días') rowColor = '#fffbeb';
                html += `
                        <tr style="border-bottom:1px solid #f1f5f9;background:${rowColor || 'white'};">
                            <td style="padding:5px 8px;font-size:11px;color:#64748b;">${fechaStr}</td>
                            <td style="padding:5px 8px;font-size:11px;color:#1e293b;font-weight:500;">${escapeHTML(row.Comprobante || '—')}</td>
                            <td style="padding:5px 8px;text-align:center;">
                                <span style="padding:1px 8px;border-radius:4px;font-size:10px;font-weight:600;background:${tipoColor}22;color:${tipoColor};">${tipoLabel}</span>
                            </td>
                            <td style="padding:5px 8px;text-align:right;font-weight:${pesos !== 0 ? '600' : '400'};color:${pesos < 0 ? '#dc2626' : pesos > 0 ? '#1e293b' : '#94a3b8'};">
                                ${formatearNumero(pesos)}
                            </td>
                            <td style="padding:5px 8px;text-align:right;font-weight:${dolares !== 0 ? '600' : '400'};color:${dolares < 0 ? '#dc2626' : dolares > 0 ? '#1e293b' : '#94a3b8'};">
                                ${formatearNumero(dolares)}
                            </td>
                        </tr>
                `;
            });
            html += `
                        </tbody>
                    </table>
                </td>
            </tr>
            `;
        }
    });
    
    // FILA DE TOTALES
    html += `
                </tbody>
                <tfoot style="background:#f1f5f9;border-top:2px solid #e2e8f0;">
                    <tr style="font-weight:700;background:#f8fafc;">
                        <td style="padding:8px 10px;text-align:right;font-size:13px;color:#1e293b;" colspan="2">TOTALES</td>
                        <td style="padding:8px 10px;text-align:right;font-size:13px;color:#1e293b;">${formatearNumero(totalPesos)}</td>
                        <td style="padding:8px 10px;text-align:right;font-size:13px;color:#1e293b;">${formatearNumero(totalDolares)}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
    `;
    
    return html;
}

// Alternar el detalle de un cliente (acordeón: varios abiertos a la vez)
window.toggleCliente = function(idx) {
    const g = gruposPendienteCobro && gruposPendienteCobro[idx];
    if (!g) return;
    if (gruposAbiertos.has(idx)) gruposAbiertos.delete(idx);
    else gruposAbiertos.add(idx);
    const container = document.getElementById('reporte-pendiente-cobro');
    if (container) {
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    }
};

// FUNCIONES DE FILTRO
window.cambiarFiltroRango = function(rango) {
    filtroRango = rango;
    prepararDatosPendienteCobro();
    reiniciarGruposAbiertos();
    const container = document.getElementById('reporte-pendiente-cobro');
    if (container) {
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    }
};

window.cambiarFiltroTipoCliente = function(tipo) {
    filtroTipoCliente = tipo;
    prepararDatosPendienteCobro();
    reiniciarGruposAbiertos();
    const container = document.getElementById('reporte-pendiente-cobro');
    if (container) {
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    }
};

window.refrescarPendienteCobro = cargarPendienteCobro;

// Cambiar la fecha de corte recarga el informe A ESA FECHA ('' = hoy).
//
// Acepta el VALOR o el propio `<input>`: el atributo de la pantalla le pasa el
// ELEMENTO (`this`), no `this.value`.
// OJO: el motor de `data-on*` de `app.js` (`_convertirArgumento`) NO soporta `this.value`
// ni ninguna otra propiedad: solo `this`, `event`, textos, numeros y booleanos. Con
// `this.value` devolvia `undefined`, la llamada se DESCARTABA en silencio y el selector
// no hacia nada (el informe seguia mostrando hoy). Medido el 02/10/2026.
window.cambiarFechaCorte = function(valor) {
    if (valor && typeof valor === 'object' && 'value' in valor) valor = valor.value;
    fechaCorte = (valor || '').trim();
    return cargarPendienteCobro();
};

// Volver al informe de siempre (el pendiente de HOY).
window.volverAFechaHoy = function() {
    fechaCorte = '';
    return cargarPendienteCobro();
};

// 'AAAA-MM-DD' -> 'DD-MM-AAAA' para el aviso en pantalla.
function formatearFechaCorte(iso) {
    const partes = String(iso || '').split('-');
    if (partes.length !== 3) return iso;
    return `${partes[2]}-${partes[1]}-${partes[0]}`;
}

// La fecha LOCAL de hoy en ISO (AAAA-MM-DD). NO se usa `toISOString()`: pasa a UTC y de
// noche adelanta un dia (mismo criterio que `fechaHoyConGuiones` de `app.js`).
function fechaHoyISO() {
    const hoy = new Date();
    const dos = (n) => String(n).padStart(2, '0');
    return `${hoy.getFullYear()}-${dos(hoy.getMonth() + 1)}-${dos(hoy.getDate())}`;
}

function formatearNumero(valor) {
    if (valor === undefined || valor === null || isNaN(valor)) return '0,00';
    const num = typeof valor === 'string' ? parseFloat(valor) : valor;
    const signo = num < 0 ? '-' : '';
    const absNum = Math.abs(num);
    const partes = absNum.toFixed(2).split('.');
    const entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return signo + entero + ',' + partes[1];
}

// ============================================================
// EXPORTAR A EXCEL (.xlsx vía backend)
// ============================================================
// Brief 05/10/2026: el .xlsx pasa a ser el PIVOTE de las dos hojas (Clientes e
// Interco), con el formato del libro de referencia del usuario. El detalle plano
// de 14 columnas y su autofiltro se reemplazaron: ver el bloque "EL PIVOTE DE
// COBRO" mas abajo.
//
// Lo que se exporta es lo que el usuario tiene en PANTALLA: los mismos
// comprobantes que `prepararDatosPendienteCobro()` dejo en
// `datosFiltradosPendienteCobro` (filtro de Rango, de Cliente/Intercompany y la
// fecha de corte elegida). No se recalcula nada por otro camino.

// El corte del informe como `dd-mm-aaaa` (como el titulo del Excel de
// referencia, "Cobranza Sidesys 02-10-2026"), o la fecha de HOY cuando no hay
// corte elegido. `fechaCorte` es la fecha LOCAL en ISO (AAAA-MM-DD).
function fechaCorteConGuiones() {
    const partes = String(fechaCorte || '').split('-');
    const hoy = new Date();
    const dos = (n) => String(n).padStart(2, '0');
    if (partes.length !== 3) {
        return `${dos(hoy.getDate())}-${dos(hoy.getMonth() + 1)}-${hoy.getFullYear()}`;
    }
    return `${partes[2]}-${partes[1]}-${partes[0]}`;
}

// ============================================================
// EL PIVOTE DE COBRO (dos hojas: Clientes e Interco)
// ============================================================
// Brief 05/10/2026 (el usuario, con sus .xlsx `RD - Pendiente de Cobro (base)`):
// "el formato en excel no es amigable al usuario, me gustaria que fuesen como los
// .xlsx que te adjunto. quiero que respetes el formato dichos excel con la misma
// separacion, hojas y diseno de tablas". El detalle plano de 14 columnas se
// reemplaza por DOS hojas, el formato del libro de referencia.
//
// Lo que se replico, medido en `_investigacion_gt/_dump_referencia.txt` (hojas
// `Pend Cobro (Clientes)` y `Pend Cobro (Interco)` del libro del usuario):
//   - `CLIE_TIPO_CLI` en la celda A1 con su valor al lado (el filtro del libro);
//   - el filtro de clientes / intercompany de la PANTALLA manda que va en cada
//     hoja (`TipoCliente === '5'` es intercompany);
//   - Clientes: `CLIENTE | FECHA | COMPROBANTE` + un par `PESOS`/`DOLARES` por
//     ANIO presente, una fila por cliente con su total y sus COMPROBANTES
//     PLEGADOS debajo (nivel 1), y `Total general` al pie;
//   - Interco: la misma tabla con los clientes tipo 5;
//   - cuadricula APAGADA y SIN autofiltro (`sin_cuadricula: true`), como el libro.
//
// DOS DIFERENCIAS DECIDIDAS CON EL USUARIO (05/10/2026), para que quede escrito:
//   1. El encabezado va APLANADO en UNA fila (`2025 PESOS`, `2025 DOLARES`) en
//      lugar de las dos filas del libro (el anio arriba, PESOS/DOLARES abajo):
//      el motor escribe una sola fila de encabezado y el usuario eligio no
//      extenderlo.
//   2. La ultima columna de dolares (la del libro, que trae el total del cliente)
//      se calcula como la suma de los DOLARES de TODOS los anios de esa fila: en
//      el libro quedaba fuera del rango de anios y no tenia etiqueta.
const ANCHO_PIVOTE_CLIENTE = 36;
const ANCHO_PIVOTE_FECHA = 19;
const ANCHO_PIVOTE_COMPROBANTE = 17;
const ANCHO_PIVOTE_IMPORTE = 15;
const ANCHO_PIVOTE_DOLARES_TOTAL = 18;
const FORMATO_PIVOTE_IMPORTE = '#,##0.00';

// PENDIENTE (declarado): el libro de referencia lleva en su PRIMERA fila el
// indicador del filtro (`A1=CLIE_TIPO_CLI`, `B1=1`/`5`/`Varios elementos`), con la
// tabla arrancando en la fila 3. Aca NO se replica todavia: el motor escribe el
// encabezado en la fila 1 y agregar filas libres obliga a corregir el encabezado,
// los formatos y las negritas de `_exportar_hoja` (hoy fijos en `1` y
// `indice + 2`). Es lo unico del formato de referencia que queda sin replicar.

// El anio de un comprobante, de su FECHA (`AAAA-MM-DD`). Sin fecha valida no hay
// anio: esa fila no cae en ninguna columna de anio (pero suma en el total de
// dolares de la fila, que no depende del anio).
function anioDeFecha(fecha) {
    const partes = String(fecha || '').split('-');
    if (partes.length !== 3) return null;
    const anio = parseInt(partes[0], 10);
    return isNaN(anio) ? null : anio;
}

const IMPORTE_PIVOTE = (valor) => {
    const numero = parseFloat(valor);
    return isNaN(numero) ? 0 : numero;
};

// Los anios que traen los datos, de menor a mayor (las columnas del pivote).
function aniosDeCobro(datos) {
    const anios = [];
    datos.forEach(fila => {
        const anio = anioDeFecha(fila.Fecha);
        if (anio !== null && anios.indexOf(anio) < 0) anios.push(anio);
    });
    return anios.sort((a, b) => a - b);
}

// La clave de agrupacion de un comprobante: fecha + comprobante. Dos filas con la
// misma fecha y el mismo comprobante son el MISMO comprobante (el servicio puede
// traerlo en dos lineas) y se suman, no se repiten.
function claveComprobante(fila) {
    return String(fila.Fecha || '') + '|' + String(fila.Comprobante || '');
}

// El encabezado de las dos hojas: las tres columnas de texto + un par
// PESOS/DOLARES por anio + la columna de dolares totales de la fila.
function columnasPivoteCobro(anios) {
    const columnas = ['Cliente', 'Fecha', 'Comprobante'];
    anios.forEach(anio => {
        columnas.push(String(anio) + ' PESOS');
        columnas.push(String(anio) + ' DOLARES');
    });
    columnas.push('DOLARES');
    return columnas;
}

function formatosPivoteCobro(columnas) {
    return columnas.map((_c, indice) => (indice < 3 ? '' : FORMATO_PIVOTE_IMPORTE));
}

function anchosPivoteCobro(columnas) {
    return columnas.map((_c, indice) => {
        if (indice === 0) return ANCHO_PIVOTE_CLIENTE;
        if (indice === 1) return ANCHO_PIVOTE_FECHA;
        if (indice === 2) return ANCHO_PIVOTE_COMPROBANTE;
        if (indice === columnas.length - 1) return ANCHO_PIVOTE_DOLARES_TOTAL;
        return ANCHO_PIVOTE_IMPORTE;
    });
}

// Los importes de una fila: los pares PESOS/DOLARES por anio y, al final, la suma
// de los dolares de TODOS los anios (la columna sin anio del libro).
function importesDeFila(porAnio, anios) {
    const importes = [];
    let dolaresTotales = 0;
    anios.forEach(anio => {
        const delAnio = porAnio[String(anio)] || { pesos: 0, dolares: 0 };
        importes.push(delAnio.pesos);
        importes.push(delAnio.dolares);
        dolaresTotales += delAnio.dolares;
    });
    importes.push(dolaresTotales);
    return importes;
}

// Suma un importe a la celda (anio, moneda) de un acumulador.
function acumular(porAnio, anio, pesos, dolares) {
    if (anio === null) return;
    const clave = String(anio);
    if (!porAnio[clave]) porAnio[clave] = { pesos: 0, dolares: 0 };
    porAnio[clave].pesos += pesos;
    porAnio[clave].dolares += dolares;
}

// Las dos hojas del libro de Cobro. `datos` son los comprobantes que la pantalla
// tiene filtrados (`datosFiltradosPendienteCobro`): la hoja de Clientes lleva los
// que NO son intercompany y la de Interco los tipo '5'.
function armarHojasPivoteCobro(datos) {
    const deClientes = datos.filter(fila => String(fila.TipoCliente) !== '5');
    const deInterco = datos.filter(fila => String(fila.TipoCliente) === '5');
    return {
        clientes: hojaPivoteClientes(deClientes),
        interco: hojaPivoteInterco(deInterco)
    };
}

// La letra de Excel de una columna (0-based -> A, B, ... Z, AA...).
function letraColumnaCobro(indice) {
    let letra = '';
    let numero = indice + 1;
    while (numero > 0) {
        const resto = (numero - 1) % 26;
        letra = String.fromCharCode(65 + resto) + letra;
        numero = Math.floor((numero - 1) / 26);
    }
    return letra;
}

// Brief 05/10/2026: "las columnas que no tienen importe que no se muestren" y
// "total general y total por el cliente que tenga formula".
//
// `columnasOcultas`: los rotulos de las columnas de importe que dan TODO cero en la
// hoja (no se borran: se ocultan, y siguen existiendo). Los TEXTOS (Cliente, Fecha,
// Comprobante) no se ocultan nunca.
//
// `formulas`: matriz alineada con `filas` (`null` = queda el valor):
//   - la columna de DOLARES de cada fila sin anio: la suma de los DOLARES de sus
//     anios;
//   - la fila del TOTAL GENERAL: cada columna suma SOLO las filas de cliente (las
//     visibles: los comprobantes estan plegados dentro y sumarlos contaria dos
//     veces).
function formulasPivoteCobro(filas, columnas, anios, filasDeCliente, filaTotal) {
    const columnasDeImporte = columnas.map((_c, indice) => indice).filter(i => i >= 3);
    const ultimaColumna = columnas.length - 1;
    const columnaDolaresDeAnio = (indiceAnio) => 4 + indiceAnio * 2;
    return filas.map((_fila, indice) => columnas.map((_c, columna) => {
        if (indice === filaTotal) {
            if (columna < 3) return null;
            // El pie: suma las filas de CLIENTE (no los comprobantes plegados).
            const celdas = filasDeCliente.map(i => letraColumnaCobro(columna) + (i + 2));
            return celdas.length ? '=SUM(' + celdas.join(',') + ')' : null;
        }
        if (columnasDeImporte.indexOf(columna) < 0) return null;
        if (columna === ultimaColumna) {
            // La ultima columna (sin anio): la suma de los DOLARES de sus anios.
            if (!anios.length) return null;
            const desde = letraColumnaCobro(columnaDolaresDeAnio(0)) + (indice + 2);
            const hasta = letraColumnaCobro(columnaDolaresDeAnio(anios.length - 1)) + (indice + 2);
            return anios.length === 1 ? '=SUM(' + desde + ')' : '=SUM(' + desde + ':' + hasta + ')';
        }
        return null;
    }));
}

// Las columnas de importe que dan todo CERO en la hoja (sus celdas de datos, sin
// contar el pie): se ocultan. Un texto nunca entra.
function columnasVaciasPivoteCobro(filas, columnas) {
    const vacias = [];
    for (let columna = 3; columna < columnas.length; columna++) {
        const todoCero = filas.every(fila => {
            const valor = fila[columna];
            return valor === '' || valor === null || valor === undefined
                || parseFloat(valor) === 0;
        });
        if (todoCero) vacias.push(columnas[columna]);
    }
    return vacias;
}

// La hoja de CLIENTES: un bloque por cliente (su fila con los totales, VISIBLE) y
// los comprobantes de ese cliente PLEGADOS debajo (nivel 1), como el libro.
function hojaPivoteClientes(datos) {
    const anios = aniosDeCobro(datos);
    const columnas = columnasPivoteCobro(anios);

    // Un grupo por cliente, con sus comprobantes adentro.
    const porCliente = {};
    const orden = [];
    datos.forEach(fila => {
        const cliente = fila.Cliente || 'Sin Cliente';
        if (!porCliente[cliente]) {
            porCliente[cliente] = { comprobantes: {}, orden: [], total: {} };
            orden.push(cliente);
        }
        const grupo = porCliente[cliente];
        const clave = claveComprobante(fila);
        if (!grupo.comprobantes[clave]) {
            grupo.comprobantes[clave] = { fecha: fila.Fecha || '', comprobante: fila.Comprobante || '',
                                          porAnio: {} };
            grupo.orden.push(clave);
        }
        const pesos = IMPORTE_PIVOTE(fila.PESOS);
        const dolares = IMPORTE_PIVOTE(fila.DOLARES);
        const anio = anioDeFecha(fila.Fecha);
        acumular(grupo.comprobantes[clave].porAnio, anio, pesos, dolares);
        acumular(grupo.total, anio, pesos, dolares);
    });

    const filas = [];
    const filasOcultas = [];
    const filasNegrita = [];
    const totalGeneral = {};

    orden.forEach(cliente => {
        const grupo = porCliente[cliente];
        // La fila del CLIENTE: su nombre y los totales (es la que queda a la
        // vista con el grupo plegado, o sea el `summary` del esquema).
        filasNegrita.push(filas.length);
        filas.push([cliente, '', ''].concat(importesDeFila(grupo.total, anios)));
        // Los COMPROBANTES: una fila por fecha+comprobante, plegada.
        grupo.orden.forEach(clave => {
            const comprobante = grupo.comprobantes[clave];
            filasOcultas.push(filas.length);
            filas.push([cliente, comprobante.fecha, comprobante.comprobante]
                       .concat(importesDeFila(comprobante.porAnio, anios)));
        });
        anios.forEach(anio => {
            const delAnio = grupo.total[String(anio)];
            if (!delAnio) return;
            acumular(totalGeneral, anio, delAnio.pesos, delAnio.dolares);
        });
    });

    filasNegrita.push(filas.length);
    const filaTotalClientes = filas.length;
    filas.push(['Total general', '', ''].concat(importesDeFila(totalGeneral, anios)));

    return {
        hoja: 'Pend Cobro (Clientes)',
        columnas: columnas,
        filas: filas,
        opciones: {
            formatos: formatosPivoteCobro(columnas),
            anchos: anchosPivoteCobro(columnas),
            filas_negrita: filasNegrita,
            filas_ocultas: filasOcultas,
            // Brief 05/10/2026: las columnas de importe que dan todo cero no se
            // muestran (se OCULTAN: siguen existiendo y sumando).
            columnas_ocultas: columnasVaciasPivoteCobro(filas, columnas),
            // Y los totales llevan FORMULA (la de cada cliente y la del pie).
            formulas: formulasPivoteCobro(filas, columnas, anios, filasNegrita,
                                          filaTotalClientes),
            sin_cuadricula: true,
            // Brief 05/10/2026: "formato tabla" en todas las hojas (el estilo azul
            // del catalogo de Excel). El motor lo aplica; el estilo por defecto es
            // `TableStyleMedium2` (el "Medio 2" de la captura del usuario).
            tabla: true
        }
    };
}

// La hoja de INTERCO: la misma tabla, con los clientes tipo '5'.
function hojaPivoteInterco(datos) {
    const anios = aniosDeCobro(datos);
    const columnas = columnasPivoteCobro(anios);
    const porCliente = {};
    const orden = [];
    datos.forEach(fila => {
        const cliente = fila.Cliente || 'Sin Cliente';
        if (!porCliente[cliente]) {
            porCliente[cliente] = { comprobantes: {}, orden: [], total: {} };
            orden.push(cliente);
        }
        const grupo = porCliente[cliente];
        const clave = claveComprobante(fila);
        if (!grupo.comprobantes[clave]) {
            grupo.comprobantes[clave] = { fecha: fila.Fecha || '', comprobante: fila.Comprobante || '',
                                          porAnio: {} };
            grupo.orden.push(clave);
        }
        const pesos = IMPORTE_PIVOTE(fila.PESOS);
        const dolares = IMPORTE_PIVOTE(fila.DOLARES);
        const anio = anioDeFecha(fila.Fecha);
        acumular(grupo.comprobantes[clave].porAnio, anio, pesos, dolares);
        acumular(grupo.total, anio, pesos, dolares);
    });

    const filas = [];
    const filasOcultas = [];
    const filasNegrita = [];
    const totalGeneral = {};
    orden.forEach(cliente => {
        const grupo = porCliente[cliente];
        filasNegrita.push(filas.length);
        filas.push([cliente, '', ''].concat(importesDeFila(grupo.total, anios)));
        grupo.orden.forEach(clave => {
            const comprobante = grupo.comprobantes[clave];
            filasOcultas.push(filas.length);
            filas.push([cliente, comprobante.fecha, comprobante.comprobante]
                       .concat(importesDeFila(comprobante.porAnio, anios)));
        });
        anios.forEach(anio => {
            const delAnio = grupo.total[String(anio)];
            if (!delAnio) return;
            acumular(totalGeneral, anio, delAnio.pesos, delAnio.dolares);
        });
    });
    filasNegrita.push(filas.length);
    const filaTotalInterco = filas.length;
    filas.push(['Total general', '', ''].concat(importesDeFila(totalGeneral, anios)));

    return {
        hoja: 'Pend Cobro (Interco)',
        columnas: columnas,
        filas: filas,
        opciones: {
            formatos: formatosPivoteCobro(columnas),
            anchos: anchosPivoteCobro(columnas),
            filas_negrita: filasNegrita,
            filas_ocultas: filasOcultas,
            // Las columnas sin importe, ocultas (igual que la hoja de Clientes).
            columnas_ocultas: columnasVaciasPivoteCobro(filas, columnas),
            // Los totales con formula (igual que la hoja de Clientes).
            formulas: formulasPivoteCobro(filas, columnas, anios, filasNegrita,
                                          filaTotalInterco),
            sin_cuadricula: true,
            // Brief 05/10/2026: formato de tabla, igual que la hoja de Clientes.
            tabla: true
        }
    };
}

// El ARMADO del Excel, en UNA sola funcion: lo usan la descarga
// (`exportarCobroExcel`) y el envio por correo (`enviarCobroPorCorreo`). Si cada
// accion armara su tabla, el adjunto del correo y el archivo descargado se
// separarian con el primer cambio. Devuelve
// `{archivo, hoja, hojas}` o `null` si no hay nada que exportar (y avisa por toast).
function armarExcelCobro() {
    const datos = datosFiltradosPendienteCobro || [];
    if (datos.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para exportar', 'Reportes');
        return null;
    }

    // Brief 05/10/2026: el detalle plano de 14 columnas se reemplaza por las DOS
    // hojas del libro de referencia. Una hoja sin datos NO se manda (el usuario
    // pidio solo `Clientes` + `Interco`): si una queda vacia, el libro sale con la
    // otra.
    const armadas = armarHojasPivoteCobro(datos);
    const hojas = [];
    if (armadas.clientes.filas.length > 1) hojas.push(armadas.clientes);
    if (armadas.interco.filas.length > 1) hojas.push(armadas.interco);
    if (hojas.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para exportar', 'Reportes');
        return null;
    }

    // Brief 05/10/2026: "GT - Pendiente de cobro al 04-10-2026" (las siglas del
    // pais de la base activa), el MISMO nombre para el archivo exportado y para el
    // adjunto y el asunto del correo. `fechaCorteConGuiones` ya devuelve la fecha
    // LOCAL del corte elegido (o la de hoy): el nombre dice a que fecha es el
    // informe, que es lo que evita confundir dos corridas de fechas distintas.
    const archivo = window.nombreInformeConSiglas('Pendiente de cobro',
                                                  fechaCorteConGuiones()) + '.xlsx';
    return { archivo: archivo, hoja: hojas[0].hoja, hojas: hojas };
}

function exportarCobroExcel() {
    const armado = armarExcelCobro();
    if (!armado) return;

    if (typeof window.descargarXlsx !== 'function') {
        if (typeof toastError === 'function') toastError('Exportación no disponible', 'Reportes');
        return;
    }
    // Brief 05/10/2026: las dos hojas viajan en `hojas` (el motor arma el libro).
    window.descargarXlsx(armado.archivo, armado.hoja, [], [],
                         { hojas: armado.hojas });
    if (typeof toastSuccess === 'function') toastSuccess('✅ Reporte exportado', 'Reportes');
}

// ============================================================
// ENVIAR POR CORREO (Outlook de esta PC; el adjunto es el MISMO .xlsx)
// ============================================================
// El dialogo del correo, el armado del adjunto y el envio viven en `app.js`
// (`window.pedirCorreoYEnviar`): aca solo se le pasa SU tabla, la misma que baja
// la descarga (`armarExcelCobro`), y el prefijo del asunto del informe.
// Brief 05/10/2026: "GT - Pendiente de cobro al 04/10/2026" (las siglas del pais
// de la base activa), el MISMO nombre para el asunto y para el archivo.
//
// OJO (defecto real medido el 05/10/2026): el prefijo se armaba al CARGAR el modulo,
// cuando `window.baseActiva` todavia es `null` (la setea `app.js` al inicializar), y
// quedaba con las siglas de la base POR DEFECTO. Ahora se arma al mandar el correo.
function enviarCobroPorCorreo() {
    const armado = armarExcelCobro();
    if (!armado) return;
    if (typeof window.pedirCorreoYEnviar !== 'function') {
        if (typeof toastError === 'function') toastError('El envío por correo no está disponible', 'Reportes');
        return;
    }
    // El asunto por defecto se arma ADENTRO del dialogo, con la fecha del dia.
    const asunto = window.prefijoInformeConSiglas('Pendiente de cobro')
        || 'Pendiente de cobro al ';
    window.pedirCorreoYEnviar(armado.archivo, armado.hoja, [], [],
                              { hojas: armado.hojas }, asunto);
}

// El boton de la pantalla (`data-onclick="exportarCobroExcel()"`) y el de
// correo los resuelve el motor de `data-on*` de `app.js` por NOMBRE en `window`.
window.exportarCobroExcel = exportarCobroExcel;
window.enviarCobroPorCorreo = enviarCobroPorCorreo;
window.armarExcelCobro = armarExcelCobro;