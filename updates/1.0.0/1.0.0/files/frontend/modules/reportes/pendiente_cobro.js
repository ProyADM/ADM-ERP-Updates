// ============================================================
// REPORTE: PENDIENTE DE COBRO
// ============================================================

let datosPendienteCobro = [];
let filtroRango = 'todos';
let filtroTipoCliente = 'todos';

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
            container.innerHTML = `<div style="color:#dc2626;padding:20px;text-align:center;">❌ ${data.error || 'Error al cargar datos'}</div>`;
            return;
        }
        
        datosPendienteCobro = data.data || [];
        filtroRango = 'todos';
        filtroTipoCliente = 'todos';
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    } catch (e) {
        console.error('❌ Error cargando pendiente de cobro:', e);
        container.innerHTML = `<div style="color:#dc2626;padding:20px;text-align:center;">❌ Error: ${e.message}</div>`;
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
        return `<div style="text-align:center;padding:30px;color:#94a3b8;">📭 No hay datos para los filtros seleccionados</div>`;
    }
    
    // 🔴 CALCULAR TOTALES
    let totalPesos = 0;
    let totalDolares = 0;
    
    datosFiltrados.forEach(row => {
        totalPesos += parseFloat(row.PESOS || 0);
        totalDolares += parseFloat(row.DOLARES || 0);
    });
    
    const clientes = new Set(datosFiltrados.map(r => r.Cliente));
    
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
            <button onclick="cambiarFiltroRango('todos')" 
                    class="btn-rango ${filtroRango === 'todos' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #d1d5db;background:${filtroRango === 'todos' ? '#2563eb' : 'white'};color:${filtroRango === 'todos' ? 'white' : '#475569'};cursor:pointer;font-size:12px;font-weight:500;">
                Todos (${datos.length})
            </button>
            <button onclick="cambiarFiltroRango('=< 30 días')" 
                    class="btn-rango ${filtroRango === '=< 30 días' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #16a34a;background:${filtroRango === '=< 30 días' ? '#16a34a' : 'white'};color:${filtroRango === '=< 30 días' ? 'white' : '#16a34a'};cursor:pointer;font-size:12px;font-weight:500;">
                ≤ 30 días (${rangoCounts['=< 30 días']})
            </button>
            <button onclick="cambiarFiltroRango('>30 días y <= 90 días')" 
                    class="btn-rango ${filtroRango === '>30 días y <= 90 días' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #f59e0b;background:${filtroRango === '>30 días y <= 90 días' ? '#f59e0b' : 'white'};color:${filtroRango === '>30 días y <= 90 días' ? 'white' : '#f59e0b'};cursor:pointer;font-size:12px;font-weight:500;">
                30-90 días (${rangoCounts['>30 días y <= 90 días']})
            </button>
            <button onclick="cambiarFiltroRango('> 90 días')" 
                    class="btn-rango ${filtroRango === '> 90 días' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #dc2626;background:${filtroRango === '> 90 días' ? '#dc2626' : 'white'};color:${filtroRango === '> 90 días' ? 'white' : '#dc2626'};cursor:pointer;font-size:12px;font-weight:500;">
                > 90 días (${rangoCounts['> 90 días']})
            </button>
            
            <span style="font-weight:500;font-size:13px;color:#475569;margin-left:16px;">👤 Tipo:</span>
            <button onclick="cambiarFiltroTipoCliente('todos')" 
                    class="btn-tipo ${filtroTipoCliente === 'todos' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #d1d5db;background:${filtroTipoCliente === 'todos' ? '#2563eb' : 'white'};color:${filtroTipoCliente === 'todos' ? 'white' : '#475569'};cursor:pointer;font-size:12px;font-weight:500;">
                Todos (${datos.length})
            </button>
            <button onclick="cambiarFiltroTipoCliente('cliente')" 
                    class="btn-tipo ${filtroTipoCliente === 'cliente' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #2563eb;background:${filtroTipoCliente === 'cliente' ? '#2563eb' : 'white'};color:${filtroTipoCliente === 'cliente' ? 'white' : '#2563eb'};cursor:pointer;font-size:12px;font-weight:500;">
                Clientes (${clienteCount})
            </button>
            <button onclick="cambiarFiltroTipoCliente('intercompany')" 
                    class="btn-tipo ${filtroTipoCliente === 'intercompany' ? 'active' : ''}" 
                    style="padding:4px 14px;border-radius:4px;border:1px solid #7c3aed;background:${filtroTipoCliente === 'intercompany' ? '#7c3aed' : 'white'};color:${filtroTipoCliente === 'intercompany' ? 'white' : '#7c3aed'};cursor:pointer;font-size:12px;font-weight:500;">
                Intercompany (${intercompanyCount})
            </button>
        </div>
        
        <!-- TOTALES -->
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;">
            <div style="background:#f0f4ff;padding:12px 16px;border-radius:8px;border:1px solid #93c5fd;">
                <div style="font-size:11px;color:#64748b;">Total Clientes</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${clientes.size}</div>
            </div>
            <div style="background:#f0fdf4;padding:12px 16px;border-radius:8px;border:1px solid #86efac;">
                <div style="font-size:11px;color:#64748b;">Total Registros</div>
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
        
        <!-- 🔴 TABLA - SIN REORDENAMIENTO ADICIONAL -->
        <div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:8px;max-height:500px;overflow-y:auto;">
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
                <thead style="position:sticky;top:0;z-index:10;background:#f8fafc;">
                    <tr style="border-bottom:2px solid #e2e8f0;">
                        <th style="padding:6px 10px;text-align:left;font-weight:600;color:#475569;min-width:180px;">Cliente</th>
                        <th style="padding:6px 10px;text-align:center;font-weight:600;color:#475569;min-width:80px;">Tipo</th>
                        <th style="padding:6px 10px;text-align:left;font-weight:600;color:#475569;min-width:100px;">Fecha</th>
                        <th style="padding:6px 10px;text-align:left;font-weight:600;color:#475569;min-width:120px;">Comprobante</th>
                        <th style="padding:6px 10px;text-align:right;font-weight:600;color:#475569;min-width:130px;">PESOS</th>
                        <th style="padding:6px 10px;text-align:right;font-weight:600;color:#475569;min-width:130px;">DOLARES</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    // 🔴 USAR LOS DATOS FILTRADOS EN EL ORDEN QUE VIENEN DE LA BD (ya ordenados por Cliente ASC, Fecha ASC)
    // NO REORDENAR NUEVAMENTE
    
    datosFiltrados.forEach((row, i) => {
        const pesos = parseFloat(row.PESOS || 0);
        const dolares = parseFloat(row.DOLARES || 0);
        
        const esIntercompany = row.TipoCliente === '5';
        const tipoLabel = esIntercompany ? 'Intercompany' : 'Cliente';
        const tipoColor = esIntercompany ? '#7c3aed' : '#2563eb';
        
        // Formatear fecha
        let fechaStr = '—';
        if (row.Fecha) {
            const fecha = new Date(row.Fecha);
            fechaStr = fecha.toLocaleDateString('es-ES', { year: 'numeric', month: '2-digit', day: '2-digit' });
        }
        
        const rango = row.Rango_Dias || '=< 30 días';
        let rowColor = '';
        if (rango === '> 90 días') rowColor = '#fef2f2';
        else if (rango === '>30 días y <= 90 días') rowColor = '#fffbeb';
        
        html += `
            <tr style="border-bottom:1px solid #f1f5f9;${i % 2 === 0 ? `background:${rowColor || '#fafafa'};` : `background:${rowColor || 'white'};`}">
                <td style="padding:6px 10px;font-weight:500;font-size:12px;">${row.Cliente || '—'}</td>
                <td style="padding:6px 10px;text-align:center;">
                    <span style="padding:2px 10px;border-radius:4px;font-size:10px;font-weight:600;background:${tipoColor}22;color:${tipoColor};">
                        ${tipoLabel}
                    </span>
                </td>
                <td style="padding:6px 10px;font-size:11px;color:#64748b;">${fechaStr}</td>
                <td style="padding:6px 10px;font-size:11px;color:#64748b;font-weight:500;">${row.Comprobante || '—'}</td>
                <td style="padding:6px 10px;text-align:right;font-weight:${pesos !== 0 ? '600' : '400'};color:${pesos < 0 ? '#dc2626' : pesos > 0 ? '#1e293b' : '#94a3b8'};">
                    ${formatearNumero(pesos)}
                </td>
                <td style="padding:6px 10px;text-align:right;font-weight:${dolares !== 0 ? '600' : '400'};color:${dolares < 0 ? '#dc2626' : dolares > 0 ? '#1e293b' : '#94a3b8'};">
                    ${formatearNumero(dolares)}
                </td>
            </tr>
        `;
    });
    
    // FILA DE TOTALES
    html += `
                </tbody>
                <tfoot style="position:sticky;bottom:0;z-index:10;background:#f1f5f9;border-top:2px solid #e2e8f0;">
                    <tr style="font-weight:700;background:#f8fafc;">
                        <td style="padding:8px 10px;text-align:right;font-size:13px;color:#1e293b;" colspan="4">TOTALES</td>
                        <td style="padding:8px 10px;text-align:right;font-size:13px;color:#1e293b;">${formatearNumero(totalPesos)}</td>
                        <td style="padding:8px 10px;text-align:right;font-size:13px;color:#1e293b;">${formatearNumero(totalDolares)}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
    `;
    
    return html;
}

// FUNCIONES DE FILTRO
window.cambiarFiltroRango = function(rango) {
    filtroRango = rango;
    const container = document.getElementById('reporte-pendiente-cobro');
    if (container) {
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    }
};

window.cambiarFiltroTipoCliente = function(tipo) {
    filtroTipoCliente = tipo;
    const container = document.getElementById('reporte-pendiente-cobro');
    if (container) {
        container.innerHTML = generarVistaPendienteCobro(datosPendienteCobro);
    }
};

function formatearNumero(valor) {
    if (valor === undefined || valor === null || isNaN(valor)) return '0,00';
    const num = typeof valor === 'string' ? parseFloat(valor) : valor;
    const signo = num < 0 ? '-' : '';
    const absNum = Math.abs(num);
    const partes = absNum.toFixed(2).split('.');
    const entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return signo + entero + ',' + partes[1];
}