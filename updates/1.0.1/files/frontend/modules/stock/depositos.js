// ============================================================
// STOCK - DEPÓSITOS (CORREGIDO)
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

function cargarDepositoParaModificar() {
  const idSelect = document.getElementById("dep-mod-buscar");
  const form = document.getElementById("dep-mod-form");
  if (!idSelect) return;
  const id = idSelect.value;
  if (!id) { if (form) form.style.display = "none"; return; }

  const dep = depositosCache.find(d => String(d.id) === String(id));
  if (!dep) { mostrarMsg("Depósito no encontrado.", false); return; }

  const nombreInput = document.getElementById("dep-mod-nombre");
  if (nombreInput) nombreInput.value = dep.nombre;
  if (form) form.style.display = "block";
}

async function guardarModificacionDeposito() {
  const idSelect = document.getElementById("dep-mod-buscar");
  if (!idSelect) return;
  const id = idSelect.value;
  if (!id) return;
  
  const nombreInput = document.getElementById("dep-mod-nombre");
  if (!nombreInput) return;
  const nombre = nombreInput.value.trim();
  if (!nombre) { mostrarMsg("Falta el nombre.", false); return; }

  const basesElegidas = [...document.querySelectorAll(".dep-multibase-check:checked")].map(c => c.value);

  const url = basesElegidas.length > 0 ? `${API}/deposito/${id}/nombre/multibases` : `${API}/deposito/${id}/nombre`;
  const body = basesElegidas.length > 0 ? { nombre, bases: basesElegidas } : { nombre };

  const btn = document.querySelector("#dep-mod-form button");
  if (!btn) return;
  const btnText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Guardando...";
  mostrarMsg("Aplicando cambios en todas las bases...", true);

  const resp = await fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  btn.disabled = false;
  btn.textContent = btnText;
  const data = await resp.json();
  if (!resp.ok) { 
    mostrarMsg(`Error: ${sanitizarValor(data.error)}`, false); 
    return; 
  }

  if (data.resultados_por_base) {
    const ok = Object.values(data.resultados_por_base).filter(r => !r.error).length;
    const total = Object.keys(data.resultados_por_base).length;
    // ✅ CORREGIDO: Sanitizar resultados
    const html = Object.entries(data.resultados_por_base).map(([base, r]) => {
      const baseSanitizado = sanitizarValor(base);
      if (r.error) {
        return `<div class="row-result error">${baseSanitizado}: ${sanitizarValor(r.error)}</div>`;
      }
      return `<div class="row-result ok">${baseSanitizado}: OK</div>`;
    }).join("");
    const msg = document.getElementById("msg");
    if (msg) msg.innerHTML = `<div class="msg ${ok === total ? 'ok' : 'error'}">${html}</div>`;
  } else {
    mostrarMsg("Depósito modificado correctamente.", true);
  }
  if (typeof cargarSelectsStock === 'function') cargarSelectsStock();
}

// ============================================================
// EXPORTAR FUNCIONES GLOBALES (DEPÓSITOS)
// ============================================================
window.cargarDepositoParaModificar = cargarDepositoParaModificar;
window.guardarModificacionDeposito = guardarModificacionDeposito;
window.escapeHTML = escapeHTML;

console.log('✅ Stock - Depósitos cargado (XSS sanitizado)');