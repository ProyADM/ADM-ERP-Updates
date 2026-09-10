// ============================================================
// ELIMINAR - ELIMINACIÓN Y VALIDACIÓN
// ============================================================

import { mostrarMsg } from './ui.js';

export async function eliminarFactura(index) {
    const f = window.facturasData?.[index];
    if (!f) return;
    
    const tipo = document.getElementById(`f${index}_tipo`)?.value || 'FCP';
    const ref = document.getElementById(`f${index}_ref`)?.value || '';
    const fecha = document.getElementById(`f${index}_fecha`)?.value || '';
    
    if (!confirm(`¿Estás seguro de eliminar la factura ${tipo} ${ref} del ${fecha}?\n\n⚠️ Esta acción NO se puede deshacer.`)) return;
    
    const factEl = document.getElementById(`fact-${index}`);
    if (factEl) {
        factEl.style.opacity = '0.5';
        factEl.style.borderColor = '#f59e0b';
    }
    
    try {
        const res = await fetch('/api/eliminar_factura', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tipo_comp: tipo,
                numero_comp: parseInt(ref) || 0,
                division: window.divisionActiva || 7
            })
        }).then(r => r.json());
        
        if (res.ok) {
            if (factEl) {
                factEl.style.borderColor = '#16a34a';
                factEl.style.opacity = '0.3';
                factEl.innerHTML = `
                    <div style="padding:20px;text-align:center;color:#16a34a;">
                        <div style="font-size:32px;margin-bottom:8px;">✅</div>
                        <div style="font-weight:600;">Factura eliminada correctamente</div>
                        <div style="font-size:12px;color:#64748b;margin-top:4px;">
                            CTACTE: ${escapeHTML(res.ctacte_eliminado || 'N/A')} | Asiento: ${escapeHTML(res.asiento_eliminado || 'N/A')}
                        </div>
                    </div>
                `;
                setTimeout(() => window.facturasData?.splice(index, 1), 3000);
            }
            mostrarMsg(`✅ Factura ${tipo} ${ref} eliminada correctamente`, true);
        } else {
            throw new Error(res.error || 'Error al eliminar');
        }
    } catch (e) {
        console.error(e);
        if (factEl) {
            factEl.style.opacity = '1';
            factEl.style.borderColor = '#dc2626';
        }
        mostrarMsg(`❌ Error al eliminar: ${e.message}`, false);
    }
}

export async function validarIntegridad() {
    try {
        const res = await fetch(`/api/validar_integridad?division=${window.divisionActiva || 7}`).then(r => r.json());
        let msg = '🔍 Validación de integridad:\n\n';
        msg += `Facturas sin RCCP: ${res.facturas_sin_rccp}\n`;
        msg += `RASP sin CASI: ${res.rasp_sin_casi}\n`;
        msg += `CASI sin RASI: ${res.casi_sin_rasi}\n`;
        msg += `Asientos sin comentario: ${res.asientos_sin_comentario}\n`;
        msg += `Notas de débito sin RCCP: ${res.notas_debito_sin_rccp}\n\n`;
        msg += `Estado general: ${res.estado_general}`;
        
        if (res.total_problemas === 0) {
            mostrarMsg('✅ Integridad del sistema: OK - No hay datos fantasma', true);
        } else {
            mostrarMsg(`⚠️ Se encontraron ${res.total_problemas} problemas. Revisa la consola.`, false);
        }
        alert(msg);
    } catch (e) {
        console.error(e);
        mostrarMsg('❌ Error al validar integridad', false);
    }
}