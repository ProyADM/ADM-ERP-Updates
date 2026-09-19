// ============================================================
// ELIMINAR - ELIMINACIÓN Y VALIDACIÓN
// ============================================================

import { mostrarMsg } from './ui.js';

export async function eliminarFactura(index) {
    const f = window.facturasData?.[index];
    if (!f) return;

    // La baja se identifica por el NUMERO INTERNO que devolvio el alta. El Nro.
    // DTE del PDF (input f{i}_ref) NO es el numero interno: mandarlo borraba
    // otro comprobante.
    const nroInterno = parseInt(f.nro_interno, 10);
    if (!nroInterno) {
        mostrarMsg('⚠️ Esta factura no se cargó desde acá: no se puede eliminar. Cargala y volvé a intentar.', false);
        return;
    }

    const tipo = f.tipo_cargado || document.getElementById(`f${index}_tipo`)?.value || 'FCP';
    const fecha = document.getElementById(`f${index}_fecha`)?.value || '';
    const importe = document.getElementById(`f${index}_bruto`)?.value || '';
    const proveedor = document.getElementById(`f${index}_provsearch`)?.value || f.proveedor_nombre || '';

    const detalle = `¿Eliminar el comprobante ${tipo} ${nroInterno} del ${fecha}`
        + ` por ${importe} del proveedor ${proveedor}?\n\n⚠️ Esta acción NO se puede deshacer.`;
    if (!confirm(detalle)) return;

    const motivo = prompt('Motivo de la eliminación (obligatorio):');
    if (!motivo || !motivo.trim()) {
        mostrarMsg('⚠️ La eliminación necesita un motivo.', false);
        return;
    }

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
                nro_interno: nroInterno,
                division: window.divisionActiva || 7,
                motivo: motivo.trim()
            })
        }).then(r => r.json());

        if (res.ok) {
            // Se marca la factura como borrada en el MISMO objeto ANTES de tocar el
            // DOM (nada de `facturasData.splice(index, 1)`): la lista y el DOM
            // comparten el indice y el DOM no se vuelve a renderizar, asi que sacar
            // el elemento corria los indices y el proximo borrado mandaba el
            // `nro_interno` de OTRA factura (con dos facturas cargadas: borrar la 1
            // y despues la 3 borraba la 2). Es el escenario del incidente de
            // Guatemala. Y va PRIMERO: el re-render de abajo usa `escapeHTML`, y si
            // esa global no estuviera la excepcion caeria DESPUES de borrar en la
            // base y ANTES de marcar el objeto (la fila pareceria no borrada y un
            // segundo clic volveria a llamar al endpoint). Sin `nro_interno`, ese
            // segundo clic ya no llama.
            f.nro_interno = null;
            f.borrada = true;
            if (factEl) {
                factEl.style.borderColor = '#16a34a';
                factEl.style.opacity = '0.3';
                factEl.innerHTML = `
                    <div style="padding:20px;text-align:center;color:#16a34a;">
                        <div style="font-size:32px;margin-bottom:8px;">✅</div>
                        <div style="font-weight:600;">Comprobante eliminado correctamente</div>
                        <div style="font-size:12px;color:#64748b;margin-top:4px;">
                            CTACTE: ${escapeHTML(res.ctacte_eliminado || 'N/A')} | Asiento: ${escapeHTML(res.asiento_eliminado || 'N/A')}
                        </div>
                    </div>
                `;
            }
            mostrarMsg(`✅ Comprobante ${tipo} ${nroInterno} eliminado correctamente`, true);
        } else if (res.codigo === 'CXP_INT_BAJA_BLOQUEADA' && Array.isArray(res.bloqueos) && res.bloqueos.length) {
            // El servicio manda `bloqueos: [{tabla, filas, primer_id}]` (y ya los
            // nombra en `error`), pero el operador necesita el `filas`/`primer_id`
            // para saber QUE lo esta bloqueando: sin eso solo ve "no se puede
            // eliminar" y tiene que adivinar.
            const texto = res.bloqueos.map(b =>
                `${escapeHTML(String(b.tabla ?? '?'))} (${escapeHTML(String(b.filas ?? '?'))} fila/s,`
                + ` primer id ${escapeHTML(String(b.primer_id ?? 'NULL'))})`
            );
            const mostrados = texto.slice(0, 4).join(' · ');
            const resto = texto.length > 4 ? ` · (+${texto.length - 4} tabla/s más)` : '';
            throw new Error(`${res.error || 'La baja está bloqueada'} → Bloquean: ${mostrados}${resto}`);
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
