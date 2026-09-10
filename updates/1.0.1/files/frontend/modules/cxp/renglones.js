// ============================================================
// RENGLONES - AGREGAR, ELIMINAR, SINCRONIZAR
// ============================================================

// 🔴 CORREGIDO: Ahora es exportable
export function sincronizarBruto(i) {
    const cont = document.getElementById(`f${i}_renglones`);
    if (!cont) return;
    let suma = 0;
    for (const div of cont.children) {
        const inp = div.querySelector('input[type=number]');
        if (inp) suma += parseFloat(inp.value) || 0;
    }
    const tipo = document.getElementById(`f${i}_tipo`)?.value || 'FCP';
    const total = parseFloat(document.getElementById(`f${i}_total`)?.value) || 0;
    
    let brutoEsperado, iva;
    if (tipo === 'FCC') {
        brutoEsperado = total;
        iva = 0;
    } else {
        brutoEsperado = Math.round((total / 1.12) * 100) / 100;
        iva = Math.round((total - brutoEsperado) * 100) / 100;
    }

    const brutoInput = document.getElementById(`f${i}_bruto`);
    const ivaInput = document.getElementById(`f${i}_iva`);
    if (brutoInput) brutoInput.value = suma > 0 ? suma.toFixed(2) : brutoEsperado.toFixed(2);
    if (ivaInput) ivaInput.value = iva.toFixed(2);
    if (brutoInput) {
        const warn = suma > 0 && Math.abs(suma - brutoEsperado) > 0.05;
        brutoInput.style.borderColor = warn ? '#e07b00' : '';
        brutoInput.title = warn ? `⚠ Suma renglones (${suma.toFixed(2)}) ≠ bruto esperado (${brutoEsperado.toFixed(2)})` : '';
    }
}

export function agregarRenglon(i, cta='', importe='', cco='') {
    const cont = document.getElementById(`f${i}_renglones`);
    if (!cont) return;
    
    const r = cont.children.length;
    const cuentasContables = window._cuentasContables || [];
    const centrosCosto = window.cuentasList || [];
    
    const div = document.createElement('div');
    div.id = `f${i}_renglon_${r}`;
    div.style.cssText = 'display:flex;gap:6px;align-items:flex-start;margin-bottom:6px;flex-wrap:wrap;';
    
    // ============================================================
    // CUENTA CONTABLE CON BUSCADOR
    // ============================================================
    const ctaContainer = document.createElement('div');
    ctaContainer.style.cssText = 'flex:2;min-width:200px;position:relative;';
    
    // Input de búsqueda
    const ctaInput = document.createElement('input');
    ctaInput.type = 'text';
    ctaInput.id = `f${i}_r${r}_cta_input`;
    ctaInput.placeholder = 'Buscar cuenta contable...';
    ctaInput.style.cssText = `
        width: 100%;
        font-size: 12px;
        padding: 5px 30px 5px 8px;
        border: 1px solid var(--border, #ccc);
        border-radius: 4px;
        box-sizing: border-box;
        background: white;
        outline: none;
    `;
    ctaInput.autocomplete = 'off';
    ctaContainer.appendChild(ctaInput);
    
    // Botón de flecha
    const ctaBtn = document.createElement('button');
    ctaBtn.innerHTML = '▼';
    ctaBtn.style.cssText = `
        position: absolute;
        right: 2px;
        top: 50%;
        transform: translateY(-50%);
        background: transparent;
        border: none;
        color: #666;
        cursor: pointer;
        font-size: 14px;
        padding: 2px 6px;
        border-radius: 3px;
        transition: background 0.2s;
    `;
    ctaBtn.title = 'Ver todas las cuentas';
    ctaBtn.onmouseenter = () => { ctaBtn.style.background = '#e8e8e8'; };
    ctaBtn.onmouseleave = () => { ctaBtn.style.background = 'transparent'; };
    ctaContainer.appendChild(ctaBtn);
    
    // Select oculto
    const ctaSelect = document.createElement('select');
    ctaSelect.id = `f${i}_r${r}_cta`;
    ctaSelect.style.display = 'none';
    cuentasContables.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.codigo;
        opt.textContent = `${c.codigo} · ${c.nombre}`;
        opt.dataset.cco = c.cco ? 'true' : 'false';
        if (c.codigo === cta) opt.selected = true;
        ctaSelect.appendChild(opt);
    });
    ctaContainer.appendChild(ctaSelect);
    
    // Lista desplegable
    const ctaList = document.createElement('div');
    ctaList.id = `f${i}_r${r}_cta_list`;
    ctaList.style.cssText = `
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        z-index: 999;
        background: white;
        border: 1px solid var(--border, #ccc);
        border-radius: 4px;
        max-height: 200px;
        overflow-y: auto;
        display: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        margin-top: 2px;
    `;
    ctaContainer.appendChild(ctaList);
    
    // Función de filtrado
    function filtrarCuentas(search) {
        ctaList.innerHTML = '';
        const term = search.toLowerCase().trim();
        let resultados = cuentasContables;
        
        if (term) {
            resultados = cuentasContables.filter(c => 
                c.codigo.toLowerCase().includes(term) || 
                c.nombre.toLowerCase().includes(term)
            );
        }
        
        if (resultados.length === 0) {
            const empty = document.createElement('div');
            empty.textContent = 'No se encontraron cuentas';
            empty.style.cssText = 'padding:8px 12px; color: #999; font-size: 12px;';
            ctaList.appendChild(empty);
        } else {
            resultados.forEach(c => {
                const item = document.createElement('div');
                item.textContent = `${c.codigo} · ${c.nombre}`;
                item.style.cssText = `
                    padding: 6px 12px;
                    cursor: pointer;
                    font-size: 12px;
                    border-bottom: 1px solid #f0f0f0;
                    transition: background 0.15s;
                `;
                item.onmouseenter = () => { item.style.background = '#e8f0fe'; };
                item.onmouseleave = () => { item.style.background = 'transparent'; };
                item.onmousedown = () => {
                    ctaInput.value = `${c.codigo} · ${c.nombre}`;
                    ctaSelect.value = c.codigo;
                    ctaList.style.display = 'none';
                    ctaSelect.dispatchEvent(new Event('change'));
                };
                ctaList.appendChild(item);
            });
        }
        ctaList.style.display = 'block';
    }
    
    // Eventos del buscador de cuentas
    ctaInput.addEventListener('input', function() { filtrarCuentas(this.value); });
    ctaBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (ctaList.style.display === 'block') {
            ctaList.style.display = 'none';
        } else {
            filtrarCuentas(ctaInput.value);
        }
    });
    ctaInput.addEventListener('focus', function() { if (!this.value) filtrarCuentas(''); });
    ctaInput.addEventListener('blur', function() { setTimeout(() => { ctaList.style.display = 'none'; }, 200); });
    ctaInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            const firstItem = ctaList.querySelector('div:not(:empty)');
            if (firstItem) firstItem.onmousedown();
        }
    });
    
    if (cta) {
        const opt = cuentasContables.find(c => c.codigo === cta);
        if (opt) { ctaInput.value = `${cta} · ${opt.nombre}`; ctaSelect.value = cta; }
    }
    div.appendChild(ctaContainer);
    
    // ============================================================
    // IMPORTE
    // ============================================================
    const impInput = document.createElement('input');
    impInput.type = 'number';
    impInput.id = `f${i}_r${r}_imp`;
    impInput.value = importe;
    impInput.placeholder = 'Importe bruto';
    impInput.step = '0.01';
    impInput.style.cssText = 'flex:1;min-width:100px;font-size:12px;padding:5px 8px;border:1px solid var(--border, #ccc);border-radius:4px;box-sizing:border-box;outline:none;';
    impInput.oninput = () => sincronizarBruto(i);
    div.appendChild(impInput);
    
    // ============================================================
    // CENTRO DE COSTO CON BUSCADOR
    // ============================================================
    const ccoContainer = document.createElement('div');
    ccoContainer.id = `f${i}_r${r}_ccowrap_container`;
    ccoContainer.style.cssText = 'flex:1;min-width:140px;position:relative;';
    
    const needsCco = cta ? (cuentasContables.find(c => c.codigo === cta)?.cco || false) : false;
    ccoContainer.style.display = needsCco ? 'inline-block' : 'none';
    
    // Input de búsqueda
    const ccoInput = document.createElement('input');
    ccoInput.type = 'text';
    ccoInput.id = `f${i}_r${r}_ccowrap_input`;
    ccoInput.placeholder = 'Buscar CCO...';
    ccoInput.style.cssText = `
        width: 100%;
        font-size: 12px;
        padding: 5px 30px 5px 8px;
        border: 1px solid var(--border, #ccc);
        border-radius: 4px;
        box-sizing: border-box;
        background: white;
        outline: none;
        display: ${needsCco ? 'block' : 'none'};
    `;
    ccoInput.autocomplete = 'off';
    ccoContainer.appendChild(ccoInput);
    
    // Botón de flecha
    const ccoBtn = document.createElement('button');
    ccoBtn.innerHTML = '▼';
    ccoBtn.style.cssText = `
        position: absolute;
        right: 2px;
        top: 50%;
        transform: translateY(-50%);
        background: transparent;
        border: none;
        color: #666;
        cursor: pointer;
        font-size: 14px;
        padding: 2px 6px;
        border-radius: 3px;
        transition: background 0.2s;
        display: ${needsCco ? 'block' : 'none'};
    `;
    ccoBtn.title = 'Ver todos los centros de costo';
    ccoBtn.onmouseenter = () => { ccoBtn.style.background = '#e8e8e8'; };
    ccoBtn.onmouseleave = () => { ccoBtn.style.background = 'transparent'; };
    ccoContainer.appendChild(ccoBtn);
    
    // Select oculto
    const ccoSelect = document.createElement('select');
    ccoSelect.id = `f${i}_r${r}_ccowrap`;
    ccoSelect.style.display = 'none';
    centrosCosto.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.codigo;
        opt.textContent = c.nombre;
        if (c.codigo === cco) opt.selected = true;
        ccoSelect.appendChild(opt);
    });
    ccoContainer.appendChild(ccoSelect);
    
    // Lista desplegable
    const ccoList = document.createElement('div');
    ccoList.id = `f${i}_r${r}_ccowrap_list`;
    ccoList.style.cssText = `
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        z-index: 999;
        background: white;
        border: 1px solid var(--border, #ccc);
        border-radius: 4px;
        max-height: 200px;
        overflow-y: auto;
        display: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        margin-top: 2px;
    `;
    ccoContainer.appendChild(ccoList);
    
    // Función de filtrado
    function filtrarCCO(search) {
        ccoList.innerHTML = '';
        const term = search.toLowerCase().trim();
        let resultados = centrosCosto;
        if (term) {
            resultados = centrosCosto.filter(c => 
                c.codigo.toLowerCase().includes(term) || 
                c.nombre.toLowerCase().includes(term)
            );
        }
        if (resultados.length === 0) {
            const empty = document.createElement('div');
            empty.textContent = 'No se encontraron centros de costo';
            empty.style.cssText = 'padding:8px 12px; color: #999; font-size: 12px;';
            ccoList.appendChild(empty);
        } else {
            resultados.forEach(c => {
                const item = document.createElement('div');
                item.textContent = `${c.codigo} - ${c.nombre}`;
                item.style.cssText = `
                    padding: 6px 12px;
                    cursor: pointer;
                    font-size: 12px;
                    border-bottom: 1px solid #f0f0f0;
                    transition: background 0.15s;
                `;
                item.onmouseenter = () => { item.style.background = '#e8f0fe'; };
                item.onmouseleave = () => { item.style.background = 'transparent'; };
                item.onmousedown = () => {
                    ccoInput.value = `${c.codigo} - ${c.nombre}`;
                    ccoSelect.value = c.codigo;
                    ccoList.style.display = 'none';
                };
                ccoList.appendChild(item);
            });
        }
        ccoList.style.display = 'block';
    }
    
    // Eventos del buscador de CCO
    ccoInput.addEventListener('input', function() { filtrarCCO(this.value); });
    ccoBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (ccoList.style.display === 'block') {
            ccoList.style.display = 'none';
        } else {
            filtrarCCO(ccoInput.value);
        }
    });
    ccoInput.addEventListener('focus', function() { if (!this.value) filtrarCCO(''); });
    ccoInput.addEventListener('blur', function() { setTimeout(() => { ccoList.style.display = 'none'; }, 200); });
    ccoInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            const firstItem = ccoList.querySelector('div:not(:empty)');
            if (firstItem) firstItem.onmousedown();
        }
    });
    
    if (cco) {
        const opt = centrosCosto.find(c => c.codigo === cco);
        if (opt) { ccoInput.value = `${cco} - ${opt.nombre}`; ccoSelect.value = cco; }
    }
    
    // Mostrar/ocultar CCO según la cuenta seleccionada
    ctaSelect.addEventListener('change', function() {
        const selected = this.options[this.selectedIndex];
        const needsCco = selected?.dataset?.cco === 'true';
        ccoContainer.style.display = needsCco ? 'inline-block' : 'none';
        ccoInput.style.display = needsCco ? 'block' : 'none';
        ccoBtn.style.display = needsCco ? 'block' : 'none';
        if (!needsCco) { ccoInput.value = ''; ccoSelect.value = ''; }
    });
    div.appendChild(ccoContainer);
    
    // ============================================================
    // BOTÓN ELIMINAR
    // ============================================================
    if (r > 0) {
        const delBtn = document.createElement('button');
        delBtn.textContent = '✕';
        delBtn.style.cssText = 'font-size:11px;padding:2px 6px;border:1px solid var(--border, #ccc);border-radius:4px;background:var(--bg-card, #f5f5f5);cursor:pointer;color:var(--muted, #999);height:30px;align-self:center;';
        delBtn.onclick = () => eliminarRenglon(i, r);
        div.appendChild(delBtn);
    }
    
    cont.appendChild(div);
}

export function eliminarRenglon(i, r) {
    const el = document.getElementById(`f${i}_renglon_${r}`);
    if (el) { el.remove(); sincronizarBruto(i); }
}

export function getRenglones(i) {
    const cont = document.getElementById(`f${i}_renglones`);
    if (!cont) return [];
    const result = [];
    for (const div of cont.children) {
        const ctaSel = div.querySelector('select[id$="_cta"]');
        const impInp = div.querySelector('input[type=number]');
        const ccoSel = div.querySelector('select[id$="_ccowrap"]');
        const cta = ctaSel?.value || '';
        const imp = parseFloat(impInp?.value) || 0;
        const cco = ccoSel?.value || '';
        if (cta && imp > 0) result.push({ cuenta: cta, importe: imp, cco });
    }
    return result;
}