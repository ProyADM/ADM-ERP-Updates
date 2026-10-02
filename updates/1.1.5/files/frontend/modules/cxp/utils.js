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

// Estilo INLINE del badge "sin tipo" (no hay clase en el CSS para este estado y
// no se agrega CSS: el archivo usa estilos inline para lo puntual). Tiene que
// ganarle a `.badge-fcp`/`.badge-fcc`, que van con `!important`.
const AVISO_TIPO_STYLE = 'background:#fee2e2;color:#b91c1c;font-size:10px;font-weight:700;padding:3px 10px;border-radius:12px;text-transform:uppercase;letter-spacing:0.03em';

export function actualizarBadgeTipo(i) {
    const badge = document.getElementById(`f${i}_tipobadge`);
    const aviso = document.getElementById(`f${i}_tipoaviso`);
    const tipo = document.getElementById(`f${i}_tipo`)?.value || '';
    if (badge) {
        if (tipo === 'FCP') {
            badge.className = 'factura-badge badge-fcp';
            badge.removeAttribute('style');
            badge.textContent = 'FCP';
        } else if (tipo === 'FCC') {
            badge.className = 'factura-badge badge-fcc';
            badge.removeAttribute('style');
            badge.textContent = 'FCC';
        } else {
            // Sin tipo elegido: el badge NO puede decir FCC (el default viejo) ni
            // FCP (el primer option del select). Dice que falta elegir.
            badge.className = 'factura-badge';
            badge.setAttribute('style', AVISO_TIPO_STYLE);
            badge.textContent = '⚠ Sin tipo';
        }
    }
    // El aviso del parser (por que no se pudo leer la leyenda) se oculta recien
    // cuando el operador elige: es el mismo criterio que el badge.
    if (aviso) aviso.style.display = tipo ? 'none' : 'block';
}

export function recalcFact(i) {
    const totalInput = document.getElementById(`f${i}_total`);
    const tipoSelect = document.getElementById(`f${i}_tipo`);
    if (!totalInput || !tipoSelect) return;
    
    // El badge del tipo y el aviso del parser los mueve el mismo cambio del
    // select que dispara este recalculo: si no, quedarian diciendo "sin tipo"
    // con el select ya en FCP (la contradiccion entre indicadores que corrige
    // esta guarda).
    actualizarBadgeTipo(i);
    const total = parseFloat(totalInput.value) || 0;
    const tipo = tipoSelect.value;
    const especialInput = document.getElementById(`f${i}_especial`);
    let especial = parseFloat(especialInput?.value) || 0;
    if (tipo === 'FCC') especial = 0;          // en FCC el total es el bruto: no se separa nada
    // En FCC el impuesto especial no existe (el total ES el bruto), asi que el
    // campo se DESHABILITA para que se vea que no aplica, pero NO se borra:
    // borrarlo hacia que un ida y vuelta FCC -> FCP dejara la factura sin su IDP
    // y el alta volviera a fallar con CXP_VAL_IVA (el fallo que esta etapa
    // elimina), obligando al operador a re-tipear el importe.
    if (especialInput) especialInput.disabled = (tipo === 'FCC');
    
    let base, iva, bruto;
    if (tipo === 'FCC') {
        base = total; iva = 0; bruto = total;
    } else {
        // El impuesto especial (IDP, turismo) es un gasto que va DENTRO del
        // bruto: se resta del total antes de separar la base y el 12%.
        const subtotal = Math.max(total - especial, 0);
        base = Math.round((subtotal / 1.12) * 100) / 100;
        iva = Math.round((subtotal - base) * 100) / 100;
        bruto = Math.round((base + especial) * 100) / 100;
    }
    
    const brutoInput = document.getElementById(`f${i}_bruto`);
    const ivaInput = document.getElementById(`f${i}_iva`);
    if (brutoInput) brutoInput.value = bruto.toFixed(2);
    if (ivaInput) ivaInput.value = iva.toFixed(2);
    
    const cont = document.getElementById(`f${i}_renglones`);
    if (cont && cont.children.length === 1) {
        const inp = cont.children[0].querySelector('input[type=number]');
        // Se reescribe si esta VACIO o si el importe lo puso la pantalla
        // (`data-auto="1"`). Lo que el operador tipeo a mano se respeta: al
        // tipear, el `oninput` del renglon limpia el marcador.
        if (inp && (!inp.value || inp.dataset.auto === '1')) inp.value = bruto.toFixed(2);
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