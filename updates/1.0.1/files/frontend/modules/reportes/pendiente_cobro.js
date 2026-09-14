// ============================================================
// REPORTE: PENDIENTE DE COBRO
// ============================================================

let datosPendienteCobro = [];
let filtroRango = 'todos';
let filtroTipoCliente = 'todos';

// Vista agrupada por cliente (acordeón): grupos del render actual + cuál está abierto.
let gruposPendienteCobro = [];
let grupoAbierto = -1;

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
        const response = await fetch(`/api/reportes/pendiente_cobro?base=${base}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        
        if (!data.success || data.error) {
            container.innerHTML = `<div style="color:#dc2626;padding:20px;text-align:center;">❌ ${escapeHTML(data.error || 'Error al cargar datos')}</div>`;
            return;
        }
        
        datosPendienteCobro = data.data || [];
        filtroRango = 'todos';
        filtroTipoCliente = 'todos';
        grupoAbierto = -1;
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    } catch (e) {
        console.error('❌ Error cargando pendiente de cobro:', e);
        container.innerHTML = `<div style="color:#dc2626;padding:20px;text-align:center;">❌ Error: ${escapeHTML(e.message)}</div>`;
    }
}

function generarVistaPendienteCobro(datos) {
    // 🔴 APLICAR FILTROS (SIN ALTERAR EL ORDEN ORIGINAL)
    let datosFiltrados = datos;
    if (filtroRango !== 'todos') {
        datosFiltrados = datosFiltrados.filter(row => row.Rango_Dias === filtroRango);
    }
    
    if (filtroTipoCliente === 'intercompany') {
        datosFiltrados = datosFiltrados.filter(row => row.TipoCliente === '5');
    } else if (filtroTipoCliente === 'cliente') {
        datosFiltrados = datosFiltrados.filter(row => row.TipoCliente !== '5' || row.TipoCliente === null || row.TipoCliente === '');
    }
    
    if (datosFiltrados.length === 0) {
        gruposPendienteCobro = [];
        grupoAbierto = -1;
        return `<div style="text-align:center;padding:30px;color:#94a3b8;">📭 No hay datos para los filtros seleccionados</div>`;
    }
    
    // 🔴 CALCULAR TOTALES (sobre los comprobantes filtrados)
    let totalPesos = 0;
    let totalDolares = 0;
    
    datosFiltrados.forEach(row => {
        totalPesos += parseFloat(row.PESOS || 0);
        totalDolares += parseFloat(row.DOLARES || 0);
    });
    
    const clientes = new Set(datosFiltrados.map(r => r.Cliente));
    
    // 🔴 AGRUPAR POR CLIENTE (preserva el orden de la BD: Cliente ASC, Fecha ASC)
    const gruposMap = new Map();
    datosFiltrados.forEach(row => {
        const clave = row.Cliente || '';
        if (!gruposMap.has(clave)) gruposMap.set(clave, []);
        gruposMap.get(clave).push(row);
    });
    const grupos = Array.from(gruposMap, ([cliente, rows]) => {
        let sp = 0, sd = 0;
        rows.forEach(r => {
            sp += parseFloat(r.PESOS || 0);
            sd += parseFloat(r.DOLARES || 0);
        });
        return { cliente, rows, totalPesos: sp, totalDolares: sd };
    });
    gruposPendienteCobro = grupos;
    if (grupoAbierto >= grupos.length) grupoAbierto = -1;
    
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
            
            <span style="flex:1"></span>
            <button data-onclick="refrescarPendienteCobro()" title="Recargar datos de la base activa" style="padding:5px 14px;border-radius:6px;border:1px solid #94a3b8;background:white;color:#334155;cursor:pointer;font-size:12px;font-weight:600;">↻ Actualizar</button>
        </div>
        
        <!-- TOTALES -->
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;">
            <div style="background:#f0f4ff;padding:12px 16px;border-radius:8px;border:1px solid #93c5fd;">
                <div style="font-size:11px;color:#64748b;">Total Clientes</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${clientes.size}</div>
            </div>
            <div style="background:#f0fdf4;padding:12px 16px;border-radius:8px;border:1px solid #86efac;">
                <div style="font-size:11px;color:#64748b;">Total Comprobantes</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${datosFiltrados.length}</div>
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
    
    grupos.forEach((g, gi) => {
        const tieneDetalle = g.rows.length > 1;
        const abierto = tieneDetalle && grupoAbierto === gi;
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

// Alternar el detalle de un cliente (acordeón: uno abierto a la vez)
window.toggleCliente = function(idx) {
    const g = gruposPendienteCobro && gruposPendienteCobro[idx];
    if (!g || g.rows.length <= 1) return;
    grupoAbierto = (grupoAbierto === idx) ? -1 : idx;
    const container = document.getElementById('reporte-pendiente-cobro');
    if (container) {
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    }
};

// FUNCIONES DE FILTRO
window.cambiarFiltroRango = function(rango) {
    filtroRango = rango;
    grupoAbierto = -1;
    const container = document.getElementById('reporte-pendiente-cobro');
    if (container) {
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    }
};

window.cambiarFiltroTipoCliente = function(tipo) {
    filtroTipoCliente = tipo;
    grupoAbierto = -1;
    const container = document.getElementById('reporte-pendiente-cobro');
    if (container) {
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    }
};

window.refrescarPendienteCobro = cargarPendienteCobro;

function formatearNumero(valor) {
    if (valor === undefined || valor === null || isNaN(valor)) return '0,00';
    const num = typeof valor === 'string' ? parseFloat(valor) : valor;
    const signo = num < 0 ? '-' : '';
    const absNum = Math.abs(num);
    const partes = absNum.toFixed(2).split('.');
    const entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return signo + entero + ',' + partes[1];
}