// ============================================================
// STOCK - UTILITARIOS (CORREGIDO - XSS SANITIZADO)
// ============================================================

function escapeHTML(str) {
    if (!str) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(str).replace(/[&<>"']/g, function(m) { return map[m]; });
}

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

// ============================================================
// EXPORTAR FUNCIONES GLOBALES (UTILITARIOS)
// ============================================================
window.mostrarMsg = mostrarMsg;
window.mostrarResultadosLote = mostrarResultadosLote;
window.mostrarResultadosLotePorBase = mostrarResultadosLotePorBase;
window.articuloOptionsHTML = articuloOptionsHTML;
window.depositoOptionsHTML = depositoOptionsHTML;
window.cargarSelectsStock = cargarSelectsStock;
window.escapeHTML = escapeHTML;

console.log('✅ Stock - Utilitarios cargado (XSS sanitizado)');