// ============================================================
// UTILS - FUNCIONES DE UTILIDAD
// ============================================================

export function setupAC(inputId, listId, hiddenId, fetchFn, labelFn, onSelect) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    let timer;
    input.addEventListener('input', e => {
        clearTimeout(timer);
        const q = e.target.value.trim();
        if (q.length < 2) { 
            const list = document.getElementById(listId);
            if (list) list.classList.remove('open');
            return; 
        }
        timer = setTimeout(async () => {
            try {
                const data = await fetchFn(q);
                const list = document.getElementById(listId);
                if (!list) return;
                list.innerHTML = '';
                data.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = labelFn(item);
                    li.addEventListener('mousedown', () => {
                        const hidden = document.getElementById(hiddenId);
                        if (hidden) hidden.value = item.id;
                        input.value = labelFn(item);
                        list.classList.remove('open');
                        if (onSelect) onSelect(item);
                    });
                    list.appendChild(li);
                });
                list.classList.toggle('open', data.length > 0);
            } catch (e) {
                console.warn('Error en autocomplete:', e);
            }
        }, 260);
    });
}

export function recalcFact(i) {
    const totalInput = document.getElementById(`f${i}_total`);
    const tipoSelect = document.getElementById(`f${i}_tipo`);
    if (!totalInput || !tipoSelect) return;
    
    const total = parseFloat(totalInput.value) || 0;
    const tipo = tipoSelect.value;
    let bruto, iva;
    if (tipo === 'FCC') { 
        bruto = total; 
        iva = 0; 
    } else { 
        bruto = Math.round((total / 1.12) * 100) / 100;
        iva = Math.round((total - bruto) * 100) / 100;
    }
    
    const brutoInput = document.getElementById(`f${i}_bruto`);
    const ivaInput = document.getElementById(`f${i}_iva`);
    if (brutoInput) brutoInput.value = bruto.toFixed(2);
    if (ivaInput) ivaInput.value = iva.toFixed(2);
    
    const cont = document.getElementById(`f${i}_renglones`);
    if (cont && cont.children.length === 1) {
        const inp = cont.children[0].querySelector('input[type=number]');
        if (inp && !inp.value) inp.value = bruto.toFixed(2);
    }
}

export async function actualizarCotizacion(i) {
    const monedaSelect = document.getElementById(`f${i}_moneda`);
    if (!monedaSelect) return;
    
    const moneda = monedaSelect.value;
    const wrap = document.getElementById(`f${i}_cotiwrap`);
    const cotiInput = document.getElementById(`f${i}_coti`);
    
    if (moneda === 'PS') {
        // 🔴 SI ES PS, COTIZACIÓN = 1 (SIN CONSULTAR)
        if (wrap) wrap.style.display = 'none';
        if (cotiInput) cotiInput.value = '1';
        console.log(`✅ Cotización para factura ${i} (PS) = 1`);
    } else {
        // 🔴 SI ES DL, BUSCAR COTIZACIÓN
        if (wrap) wrap.style.display = 'block';
        const fecha = document.getElementById(`f${i}_fecha`)?.value;
        if (fecha) {
            try {
                const r = await fetch(`/api/cotizacion?moneda=${moneda}&fecha=${fecha}`);
                const data = await r.json();
                if (cotiInput) cotiInput.value = data.cotizacion;
                console.log(`✅ Cotización para factura ${i} (${moneda}) = ${data.cotizacion}`);
            } catch (e) {
                console.warn(`⚠️ Error obteniendo cotización para ${moneda}:`, e);
                if (cotiInput) cotiInput.value = '1';
            }
        }
    }
}

export function cuentaAutoDesdeDesc(desc) {
    if (!desc) return '';
    const d = desc.toLowerCase();
    if (d.includes('alquiler') || d.includes('arrendamiento') || d.includes('bodega')) return '520312';
    if (d.includes('gasolina') || d.includes('combustible')) return '510101018';
    if (d.includes('peaje') || d.includes('estacionamiento') || d.includes('parqueo')) return '510101017';
    if (d.includes('pasaje') || d.includes('transporte') || d.includes('uber') || d.includes('cabify')) return '510101020';
    if (d.includes('alojamiento') || d.includes('hotel')) return '510101022';
    if (d.includes('alimento') || d.includes('refrigerio') || d.includes('comida')) return '510101023';
    if (d.includes('cargo') || d.includes('moratoria') || d.includes('inter')) return '520319';
    return '';
}