// ============================================================
// STOCK - UTILITARIOS (CORREGIDO - XSS SANITIZADO)
// ============================================================

function sanitizarValor(val) {
    if (val === undefined || val === null) return '';
    return escapeHTML(String(val));
}

function mostrarMsg(texto, ok) {
  const msg = document.getElementById("msg");
  if (!msg) return;
  // ✅ CORREGIDO: Sanitizar texto antes de mostrarlo
  msg.innerHTML = `<div class="msg ${ok ? 'ok' : 'error'}">${sanitizarValor(texto)}</div>`;
}

function mostrarResultadosLote(containerId, resultados) {
  const container = document.getElementById(containerId);
  if (!container) return;
  
  // ✅ CORREGIDO: Sanitizar resultados
  const html = resultados.map(r => {
    const fila = sanitizarValor(r.fila);
    if (r.error) {
      const error = sanitizarValor(r.error);
      return `<div class="row-result error">Fila ${fila}: Error — ${error}</div>`;
    }
    if (r.tipo) {
      const tipo = sanitizarValor(r.tipo);
      const numero = sanitizarValor(r.numero_comprobante);
      const movimiento = sanitizarValor(r.movimiento);
      return `<div class="row-result ok">Fila ${fila}: ${tipo} #${numero} (mov. ${movimiento}) OK</div>`;
    }
    if (r.numero_transferencia !== undefined) {
      const numero = sanitizarValor(r.numero_transferencia);
      return `<div class="row-result ok">Fila ${fila}: Transferencia #${numero} OK</div>`;
    }
    if (r.articulo_id !== undefined) {
      const id = sanitizarValor(r.articulo_id);
      return `<div class="row-result ok">Fila ${fila}: Artículo creado, ID ${id} OK</div>`;
    }
    return `<div class="row-result ok">Fila ${fila}: OK</div>`;
  }).join("");
  container.innerHTML = html;
}

function mostrarResultadosLotePorBase(containerId, resultadosPorBase) {
  const container = document.getElementById(containerId);
  if (!container) return;
  
  // ✅ CORREGIDO: Sanitizar resultados por base
  const html = Object.entries(resultadosPorBase).map(([base, resultados]) => {
    const baseInfo = basesCache.find(b => b.codigo === base);
    const label = baseInfo ? sanitizarValor(baseInfo.label) : sanitizarValor(base);
    const filas = resultados.map(r => {
      const fila = sanitizarValor(r.fila);
      if (r.error) {
        const error = sanitizarValor(r.error);
        return `<div class="row-result error">Fila ${fila}: Error — ${error}</div>`;
      }
      if (r.articulo_id !== undefined) {
        const id = sanitizarValor(r.articulo_id);
        return `<div class="row-result ok">Fila ${fila}: Artículo creado, ID ${id} OK</div>`;
      }
      return `<div class="row-result ok">Fila ${fila}: OK</div>`;
    }).join("");
    return `<div class="base-group"><h3>${label}</h3>${filas}</div>`;
  }).join("");
  container.innerHTML = html;
}

function articuloOptionsHTML() {
  // ✅ CORREGIDO: Sanitizar datos de artículos
  return articulosCache.map(a => {
    const id = sanitizarValor(a.id);
    const codigo = sanitizarValor(a.codigo);
    const nombre = sanitizarValor(a.nombre);
    const partidas = sanitizarValor(a.con_partidas);
    return `<option value="${id}" data-partidas="${partidas}">${codigo} - ${nombre}</option>`;
  }).join("");
}

function depositoOptionsHTML() {
  // ✅ CORREGIDO: Sanitizar datos de depósitos
  return depositosCache.map(d => {
    const id = sanitizarValor(d.id);
    const nombre = sanitizarValor(d.nombre);
    return `<option value="${id}">${id} - ${nombre}</option>`;
  }).join("");
}

// Toast flotante (arriba a la derecha) para feedback que no pase desapercibido.
function mostrarToastFlotante(ok, mensaje) {
  const toast = document.createElement('div');
  toast.textContent = mensaje;
  toast.style.cssText = `position:fixed;top:66px;right:16px;z-index:30000;max-width:420px;padding:10px 14px;border-radius:8px;font-size:13px;font-weight:600;box-shadow:0 6px 20px rgba(0,0,0,.2);background:${ok ? '#16a34a' : '#dc2626'};color:#fff;`;
  document.body.appendChild(toast);
  setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 8000);
}

// Muestra el resultado de una operación en el contenedor visible de la sección
// (p.ej. #ae-resultados) más un toast flotante arriba a la derecha.
function mostrarResultadoSeccion(contenedorId, ok, mensaje) {
  const cont = document.getElementById(contenedorId);
  if (cont) {
    cont.textContent = '';
    const box = document.createElement('div');
    box.textContent = mensaje;
    box.style.cssText = `margin-top:10px;padding:9px 12px;border-radius:8px;font-size:13px;font-weight:600;background:${ok ? '#f0fdf4' : '#fef3f2'};border:1px solid ${ok ? '#86efac' : '#fecdc9'};color:${ok ? '#166534' : '#b42318'};`;
    cont.appendChild(box);
    cont.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  mostrarToastFlotante(ok, mensaje);
}

// ============================================================
// SELECTORES CON FILTRO POR TEXTO (buscar artículos escribiendo)
// ============================================================
function hacerSelectBuscable(select) {
  if (select.dataset.buscable) return;
  select.dataset.buscable = '1';
  select.style.display = 'none';

  const wrap = document.createElement('div');
  wrap.style.cssText = 'position:relative;display:inline-block;min-width:280px;max-width:100%;vertical-align:middle;';
  const input = document.createElement('input');
  input.type = 'text';
  input.autocomplete = 'off';
  input.placeholder = 'Escribí para filtrar…';
  input.style.cssText = 'width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;background:white;color:#1e293b;box-sizing:border-box;';
  const list = document.createElement('div');
  list.style.cssText = 'display:none;position:absolute;top:100%;left:0;right:0;z-index:2000;max-height:230px;overflow:auto;background:white;border:1px solid #cbd5e1;border-radius:6px;margin-top:2px;box-shadow:0 8px 20px rgba(0,0,0,.15);';

  function pintar(filtro) {
    list.textContent = '';
    const f = (filtro || '').trim().toLowerCase();
    const opciones = Array.from(select.options).filter(o => o.value !== '');
    const visibles = f ? opciones.filter(o => o.text.toLowerCase().includes(f)) : opciones;
    if (!visibles.length) {
      const aviso = document.createElement('div');
      aviso.textContent = 'Sin coincidencias';
      aviso.style.cssText = 'padding:7px 10px;color:#94a3b8;font-size:12px;';
      list.appendChild(aviso);
      return;
    }
    visibles.slice(0, 150).forEach(o => {
      const item = document.createElement('div');
      item.textContent = o.text;
      item.dataset.val = o.value;
      item.style.cssText = 'padding:6px 10px;cursor:pointer;font-size:12px;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
      item.addEventListener('mouseover', () => { item.style.background = '#eef2f7'; });
      item.addEventListener('mouseout', () => { item.style.background = ''; });
      item.addEventListener('mousedown', (e) => { e.preventDefault(); elegir(o.value); });
      list.appendChild(item);
    });
  }

  function elegir(valor) {
    select.value = valor;
    const sel = select.selectedOptions[0];
    input.value = sel ? sel.text : '';
    list.style.display = 'none';
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }

  input.addEventListener('focus', () => { list.style.display = 'block'; pintar(input.value); });
  input.addEventListener('input', () => { pintar(input.value); if (input.value.trim()) list.style.display = 'block'; });
  input.addEventListener('blur', () => setTimeout(() => { list.style.display = 'none'; }, 150));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const primero = list.querySelector('[data-val]');
      if (primero) elegir(primero.dataset.val);
    } else if (e.key === 'Escape') {
      list.style.display = 'none';
    }
  });

  wrap.appendChild(input);
  wrap.appendChild(list);
  select.parentNode.insertBefore(wrap, select.nextSibling);

  // No precargar el primer artículo en el campo: arranca vacío con el
  // placeholder hasta que el usuario elija/escriba. Solo se conserva una
  // selección previa real (placeholder con value="" o índice > 0).
  const primera = select.options[0];
  const tienePlaceholder = primera && primera.value === '';
  if (!tienePlaceholder && select.selectedIndex <= 0) {
    select.selectedIndex = -1;
    try { select.value = ''; } catch (e) { /* noop */ }
  }
  input.value = '';
}

function aplicarBuscadoresStock() {
  ['ae-articulo', 'as-articulo', 'tr-articulo', 'art-mod-buscar'].forEach(id => {
    const sel = document.getElementById(id);
    if (sel && !sel.dataset.buscable) hacerSelectBuscable(sel);
  });
}

// ============================================================
// EXPORTAR FUNCIONES GLOBALES (UTILITARIOS)
// ============================================================
window.mostrarMsg = mostrarMsg;
window.mostrarResultadoSeccion = mostrarResultadoSeccion;
window.mostrarToastFlotante = mostrarToastFlotante;
window.hacerSelectBuscable = hacerSelectBuscable;
window.aplicarBuscadoresStock = aplicarBuscadoresStock;
window.mostrarResultadosLote = mostrarResultadosLote;
window.mostrarResultadosLotePorBase = mostrarResultadosLotePorBase;
window.articuloOptionsHTML = articuloOptionsHTML;
window.depositoOptionsHTML = depositoOptionsHTML;
window.cargarSelectsStock = cargarSelectsStock;

console.log('✅ Stock - Utilitarios cargado (XSS sanitizado)');