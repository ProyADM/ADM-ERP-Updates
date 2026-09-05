// ============================================================
// STOCK - CONSULTAR STOCK (VERSIÓN CORREGIDA - XSS SANITIZADO)
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

async function consultarStock() {
  const q = document.getElementById("stk-q").value.trim();
  const deposito = document.getElementById("stk-deposito").value;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (deposito) params.set("deposito", deposito);

  const tabla = document.getElementById("stk-tabla");
  const tbody = document.querySelector("#stk-tabla tbody");
  const tfoot = document.querySelector("#stk-tabla tfoot");
  
  if (!tbody) {
    console.warn('⚠️ No se encontró #stk-tabla tbody');
    return;
  }
  
  tbody.innerHTML = `<tr><td colspan="6" style="color:#999;text-align:center;padding:30px 16px;">⏳ Buscando...</td></tr>`;
  if (tfoot) tfoot.innerHTML = '';

  try {
    const rows = await fetch(`/api/stock?${params.toString()}`).then(r => r.json());

    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="color:#999;text-align:center;padding:30px 16px;">📭 Sin resultados</td></tr>`;
      if (tfoot) tfoot.innerHTML = '';
      const infoEl = document.getElementById('stock-result-count');
      if (infoEl) infoEl.textContent = '📊 0 resultados';
      return;
    }

    function sortCodigo(cod) {
      try {
        return String(cod).split(".").map(Number);
      } catch(e) {
        return [0];
      }
    }
    
    rows.sort((a, b) => {
      const ka = sortCodigo(a.codigo);
      const kb = sortCodigo(b.codigo);
      for (let i = 0; i < Math.max(ka.length, kb.length); i++) {
        const d = (ka[i] || 0) - (kb[i] || 0);
        if (d !== 0) return d;
      }
      return 0;
    });

    let infoEl = document.getElementById('stock-result-count');
    if (!infoEl) {
      infoEl = document.createElement('div');
      infoEl.id = 'stock-result-count';
      infoEl.style.cssText = 'margin-top:8px;font-size:13px;color:var(--ink-soft);font-weight:500;';
      const filters = document.querySelector('.stock-filters');
      if (filters) {
        filters.parentNode.insertBefore(infoEl, filters.nextSibling);
      }
    }
    infoEl.textContent = `📊 ${rows.length} resultado${rows.length !== 1 ? 's' : ''}`;

    let totalStock = 0;
    rows.forEach(r => totalStock += r.stock || 0);

    // ✅ CORREGIDO: Sanitizar todos los valores
    const tbodyHTML = rows.map(r => {
      const codigo = sanitizarValor(r.codigo);
      const nombre = sanitizarValor(r.nombre);
      const depositoNombre = sanitizarValor(r.deposito_nombre);
      const stockVal = sanitizarValor(r.stock);
      const articuloVal = sanitizarValor(r.articulo);
      const depositoVal = sanitizarValor(r.deposito);
      const stockClass = r.stock > 0 ? '600' : '400';
      const stockColor = r.stock > 0 ? 'var(--ok)' : 'var(--ink-soft)';
      return `<tr>
        <td style="text-align:center;"><input type="checkbox" class="stk-check" data-articulo="${articuloVal}" data-deposito="${depositoVal}" onchange="actualizarSeleccionBar()"></td>
        <td><strong>${codigo}</strong></td>
        <td>${nombre}</td>
        <td>${depositoNombre}</td>
        <td style="text-align:right;font-weight:${stockClass};color:${stockColor};">${stockVal}</td>
        <td class="stock-acciones" style="text-align:center;">
          <button class="small secondary" title="Ajuste de entrada" onclick="irAMovimiento('ae', ${articuloVal}, ${depositoVal})">+</button>
          <button class="small secondary" title="Ajuste de salida" onclick="irAMovimiento('as', ${articuloVal}, ${depositoVal})">−</button>
          <button class="small secondary" title="Transferencia" onclick="irAMovimiento('tr', ${articuloVal}, ${depositoVal})">⇄</button>
        </td>
      </tr>`;
    }).join("");
    tbody.innerHTML = tbodyHTML;
      
    if (tfoot) {
      const totalStockDisplay = totalStock.toLocaleString('es');
      tfoot.innerHTML = `
        <tr style="font-weight:700; background:#f0f4ff;">
          <td colspan="4" style="text-align:right; font-size:12px; color:var(--ink-soft); text-transform:uppercase; letter-spacing:0.04em; padding:10px 14px;">
            TOTAL STOCK
          </td>
          <td style="text-align:right; font-size:15px; color:#1d4ed8; font-weight:700; padding:10px 14px;">
            ${totalStockDisplay}
          </td>
          <td style="text-align:center; font-size:11px; color:var(--ink-soft); padding:10px 14px;">
            ${rows.length} artículos
          </td>
        </tr>
      `;
      tfoot.style.display = 'table-footer-group';
    }
      
    document.getElementById("stk-check-all").checked = false;
    actualizarSeleccionBar();
    
  } catch (e) {
    console.error('Error consultando stock:', e);
    const errorMsg = sanitizarValor(e.message);
    tbody.innerHTML = `<tr><td colspan="6" style="color:var(--err-ink);text-align:center;padding:30px 16px;">❌ Error al consultar: ${errorMsg}</td></tr>`;
    if (tfoot) tfoot.innerHTML = '';
    const infoEl = document.getElementById('stock-result-count');
    if (infoEl) infoEl.textContent = '❌ Error al cargar datos';
  }
}

function toggleTodosStock(checkAll) {
  document.querySelectorAll(".stk-check").forEach(c => c.checked = checkAll.checked);
  actualizarSeleccionBar();
}

function actualizarSeleccionBar() {
  const seleccionados = document.querySelectorAll(".stk-check:checked");
  const bar = document.getElementById("stk-seleccion-bar");
  if (bar) {
    bar.classList.toggle("show", seleccionados.length > 0);
    document.getElementById("stk-seleccion-count").textContent = `${seleccionados.length} seleccionado${seleccionados.length === 1 ? "" : "s"}`;
  }
}

function enviarSeleccionAMovimiento(prefix) {
  const seleccionados = [...document.querySelectorAll(".stk-check:checked")].map(c => ({
    articulo: c.dataset.articulo,
    deposito: c.dataset.deposito,
  }));
  if (seleccionados.length === 0) return;

  const tabId = prefix === "ae" ? "ajuste-e" : prefix === "as" ? "ajuste-s" : "transferencia";
  const grupo = prefix === "trm" ? "tr" : prefix;
  const subId = grupo + "-multiple";

  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  document.getElementById(tabId).classList.add("active");

  document.querySelectorAll(".drawer-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(`.drawer-tab[data-tab="${tabId}"]`).forEach(t => t.classList.add("active"));

  document.querySelectorAll(`.drawer-subitem[data-group="${grupo}"]`).forEach(s => s.classList.remove("active"));
  document.getElementById(subId)?.classList.add("active");
  document.querySelectorAll(`.subsection`).forEach(s => {
    if (s.id.startsWith(grupo + "-")) s.classList.remove("active");
  });
  document.getElementById(subId).classList.add("active");

  const gridId = prefix === "trm" ? "trm-grid" : prefix + "-grid";
  document.querySelector(`#${gridId} tbody`).innerHTML = "";
  seleccionados.forEach(s => agregarFila(prefix, s));

  document.getElementById("empty-state").style.display = "none";
  const titulo = document.getElementById("seccion-activa");
  if (titulo) {
    titulo.textContent = document.querySelector(`.drawer-tab[data-tab="${tabId}"]`)?.textContent || tabId;
    titulo.style.display = "block";
  }
  document.getElementById("msg").innerHTML = "";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function irAMovimiento(prefix, articuloId, depositoId) {
  const tabId = prefix === "ae" ? "ajuste-e" : prefix === "as" ? "ajuste-s" : "transferencia";
  const subId = prefix + "-individual";

  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  document.getElementById(tabId).classList.add("active");

  document.querySelectorAll(".drawer-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(`.drawer-tab[data-tab="${tabId}"]`).forEach(t => t.classList.add("active"));

  document.querySelectorAll(`.drawer-subitem[data-group="${prefix}"]`).forEach(s => s.classList.remove("active"));
  document.getElementById(subId)?.classList.add("active");
  document.querySelectorAll(`.subsection`).forEach(s => {
    if (s.id.startsWith(prefix + "-")) s.classList.remove("active");
  });
  document.getElementById(subId).classList.add("active");

  document.getElementById(prefix + "-articulo").value = articuloId;
  if (prefix === "tr") {
    document.getElementById("tr-origen").value = depositoId;
    cargarPartidasTransferencia();
  } else {
    document.getElementById(prefix + "-deposito").value = depositoId;
    if (prefix === "as") cargarPartidas();
  }

  document.getElementById("empty-state").style.display = "none";
  const titulo = document.getElementById("seccion-activa");
  if (titulo) {
    titulo.textContent = document.querySelector(`.drawer-tab[data-tab="${tabId}"]`)?.textContent || tabId;
    titulo.style.display = "block";
  }
  document.getElementById("msg").innerHTML = "";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ============================================================
// EXPORTAR FUNCIONES GLOBALES (CONSULTAR STOCK)
// ============================================================
window.consultarStock = consultarStock;
window.toggleTodosStock = toggleTodosStock;
window.actualizarSeleccionBar = actualizarSeleccionBar;
window.enviarSeleccionAMovimiento = enviarSeleccionAMovimiento;
window.irAMovimiento = irAMovimiento;
window.escapeHTML = escapeHTML;

console.log('✅ Stock - Consultar cargado (XSS sanitizado)');