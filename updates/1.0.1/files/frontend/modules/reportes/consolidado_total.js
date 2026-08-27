// ============================================================
// REPORTE: CONSOLIDADO VENTAS GLOBAL
// ============================================================

export async function cargarConsolidadoTotal() {
    console.log('📊 Cargando reporte de Consolidado Total de Ventas...');
    
    const container = document.getElementById('reporte-consolidado-total');
    if (!container) {
        console.warn('⚠️ No se encontró #reporte-consolidado-total');
        return;
    }
    
    container.innerHTML = '<div style="text-align:center;padding:20px;color:#94a3b8;">⏳ Cargando datos...</div>';
    
    try {
        const response = await fetch('/api/reportes/consolidado_ventas_global');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        
        if (!data.success || data.error) {
            container.innerHTML = `<div style="color:#dc2626;padding:20px;text-align:center;">❌ ${data.error || 'Error al cargar datos'}</div>`;
            return;
        }
        
        container.innerHTML = generarTablaConsolidadoTotal(data.data || []);
    } catch (e) {
        console.error('❌ Error cargando consolidado total:', e);
        container.innerHTML = `<div style="color:#dc2626;padding:20px;text-align:center;">❌ Error: ${e.message}</div>`;
    }
}

function generarTablaConsolidadoTotal(datos) {
    if (!datos || datos.length === 0) {
        return '<div style="text-align:center;padding:30px;color:#94a3b8;">📭 No hay datos de ventas globales</div>';
    }
    
    // Agrupar por base de origen
    const grupos = {};
    datos.forEach(row => {
        const base = row.Base_Origen || 'Sin Base';
        if (!grupos[base]) {
            grupos[base] = { base: base, total: 0, registros: 0 };
        }
        const importe = parseFloat(row['Importe local'] || row['Importe origen'] || 0);
        grupos[base].total += importe;
        grupos[base].registros += 1;
    });
    
    const resumen = Object.values(grupos).sort((a, b) => b.total - a.total);
    const totalGeneral = resumen.reduce((acc, r) => acc + r.total, 0);
    
    let html = `
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;">
            <div style="background:#f0f4ff;padding:12px 16px;border-radius:8px;border:1px solid #93c5fd;">
                <div style="font-size:11px;color:#64748b;">Total Ventas Global</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${totalGeneral.toFixed(2)}</div>
            </div>
            <div style="background:#f0fdf4;padding:12px 16px;border-radius:8px;border:1px solid #86efac;">
                <div style="font-size:11px;color:#64748b;">Total Bases</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${resumen.length}</div>
            </div>
            <div style="background:#fef3f2;padding:12px 16px;border-radius:8px;border:1px solid #fecdc9;">
                <div style="font-size:11px;color:#64748b;">Total Registros</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">${datos.length}</div>
            </div>
        </div>
        
        <div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:8px;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                    <tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0;">
                        <th style="padding:8px 12px;text-align:left;font-weight:600;color:#475569;">Base / País</th>
                        <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569;">Registros</th>
                        <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569;">Total Ventas</th>
                        <th style="padding:8px 12px;text-align:center;font-weight:600;color:#475569;">% Participación</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    resumen.forEach((row, i) => {
        const porcentaje = totalGeneral > 0 ? (row.total / totalGeneral * 100) : 0;
        const nombre = row.base.replace('plataforma_', '').toUpperCase() || row.base;
        
        html += `
            <tr style="border-bottom:1px solid #f1f5f9;${i % 2 === 0 ? 'background:#fafafa;' : ''}">
                <td style="padding:8px 12px;font-weight:500;">🌐 ${nombre}</td>
                <td style="padding:8px 12px;text-align:right;">${row.registros}</td>
                <td style="padding:8px 12px;text-align:right;font-variant-numeric:tabular-nums;font-weight:600;">
                    ${row.total.toFixed(2)}
                </td>
                <td style="padding:8px 12px;text-align:center;">
                    <div style="display:flex;align-items:center;gap:8px;justify-content:center;">
                        <span style="font-weight:600;">${porcentaje.toFixed(1)}%</span>
                        <div style="flex:1;max-width:100px;height:6px;background:#e2e8f0;border-radius:4px;overflow:hidden;">
                            <div style="height:100%;width:${Math.min(porcentaje, 100)}%;background:#2563eb;border-radius:4px;"></div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    });
    
    html += `</tbody>
            <tfoot>
                <tr style="background:#f8fafc;border-top:2px solid #e2e8f0;font-weight:600;">
                    <td style="padding:8px 12px;text-align:left;">TOTAL GLOBAL</td>
                    <td style="padding:8px 12px;text-align:right;">${datos.length}</td>
                    <td style="padding:8px 12px;text-align:right;">${totalGeneral.toFixed(2)}</td>
                    <td style="padding:8px 12px;text-align:center;">100%</td>
                </tr>
            </tfoot>
        </table>
    </div>`;
    
    return html;
}