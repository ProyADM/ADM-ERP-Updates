// ============================================================
// STOCK - ARTÍCULOS (CORREGIDO - XSS SANITIZADO)
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

function aplicarDefaultPartidas() {
  const catSelect = document.getElementById("art-categoria");
  if (!catSelect) return;
  const opt = catSelect.options[catSelect.selectedIndex];
  if (!opt) return;
  const def = opt.dataset.partidasDefault;
  if (def === "true") document.getElementById("art-con-partidas").checked = true;
  else if (def === "false") document.getElementById("art-con-partidas").checked = false;
}

function actualizarCamposOrigen() {
  const seCompra = document.getElementById("art-se-compra");
  const seVende = document.getElementById("art-se-vende");
  const wrap = document.getElementById("art-origen-wrap");
  if (seCompra && seVende && wrap) {
    wrap.style.display = (seCompra.checked || seVende.checked) ? "block" : "none";
  }
}

async function crearArticulo() {
  const nombreInput = document.getElementById("art-nombre");
  const codigoInput = document.getElementById("art-codigo");
  const categoriaSelect = document.getElementById("art-categoria");
  const conPartidasCheck = document.getElementById("art-con-partidas");
  const seCompraCheck = document.getElementById("art-se-compra");
  const seVendeCheck = document.getElementById("art-se-vende");
  const origenSelect = document.getElementById("art-origen");
  
  if (!nombreInput || !codigoInput) return;
  
  const body = {
    nombre: nombreInput.value.trim(),
    codigo: codigoInput.value.trim(),
    categoria: categoriaSelect ? categoriaSelect.value : "-",
    con_partidas: conPartidasCheck ? conPartidasCheck.checked : false,
    se_compra: seCompraCheck ? seCompraCheck.checked : true,
    se_vende: seVendeCheck ? seVendeCheck.checked : true,
    origen: origenSelect ? origenSelect.value : "local",
  };
  if (!body.nombre || !body.codigo) { mostrarMsg("Faltan nombre o código.", false); return; }

  const resp = await fetch(`${API}/articulo`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) { 
    mostrarMsg(`Error: ${sanitizarValor(data.error)}`, false); 
    return; 
  }

  mostrarMsg(`Artículo creado correctamente (ID ${data.articulo_id}).`, true);
  if (nombreInput) nombreInput.value = "";
  if (codigoInput) codigoInput.value = "";
  if (typeof cargarSelectsStock === 'function') cargarSelectsStock();
}

function actualizarCamposOrigenMod() {
  const seCompra = document.getElementById("art-mod-se-compra");
  const seVende = document.getElementById("art-mod-se-vende");
  const wrap = document.getElementById("art-mod-origen-wrap");
  if (seCompra && seVende && wrap) {
    wrap.style.display = (seCompra.checked || seVende.checked) ? "block" : "none";
  }
}

async function cargarArticuloParaModificar() {
  const idSelect = document.getElementById("art-mod-buscar");
  const form = document.getElementById("art-mod-form");
  if (!idSelect) return;
  const id = idSelect.value;
  if (!id) { if (form) form.style.display = "none"; return; }

  try {
    const data = await fetch(`${API}/articulo/${id}`).then(r => r.json());
    if (data.error) { 
      mostrarMsg(`Error: ${sanitizarValor(data.error)}`, false); 
      return; 
    }

    const nombreInput = document.getElementById("art-mod-nombre");
    const codigoInput = document.getElementById("art-mod-codigo");
    const categoriaSelect = document.getElementById("art-mod-categoria");
    const conPartidasCheck = document.getElementById("art-mod-con-partidas");
    const seCompraCheck = document.getElementById("art-mod-se-compra");
    const seVendeCheck = document.getElementById("art-mod-se-vende");
    const origenSelect = document.getElementById("art-mod-origen");
    
    if (nombreInput) nombreInput.value = data.nombre;
    if (codigoInput) codigoInput.value = data.codigo;
    if (categoriaSelect) categoriaSelect.value = data.categoria;
    if (conPartidasCheck) conPartidasCheck.checked = data.con_partidas;
    if (seCompraCheck) seCompraCheck.checked = data.se_compra;
    if (seVendeCheck) seVendeCheck.checked = data.se_vende;
    if (origenSelect) origenSelect.value = data.origen;
    actualizarCamposOrigenMod();
    if (form) form.style.display = "block";
  } catch (e) {
    mostrarMsg(`Error al cargar artículo: ${sanitizarValor(e.message)}`, false);
  }
}

async function guardarModificacionArticulo() {
  const idSelect = document.getElementById("art-mod-buscar");
  if (!idSelect) return;
  const id = idSelect.value;
  if (!id) return;
  
  const nombreInput = document.getElementById("art-mod-nombre");
  const codigoInput = document.getElementById("art-mod-codigo");
  const categoriaSelect = document.getElementById("art-mod-categoria");
  const conPartidasCheck = document.getElementById("art-mod-con-partidas");
  const seCompraCheck = document.getElementById("art-mod-se-compra");
  const seVendeCheck = document.getElementById("art-mod-se-vende");
  const origenSelect = document.getElementById("art-mod-origen");
  
  const body = {
    nombre: nombreInput ? nombreInput.value.trim() : "",
    codigo: codigoInput ? codigoInput.value.trim() : "",
    categoria: categoriaSelect ? categoriaSelect.value : "-",
    con_partidas: conPartidasCheck ? conPartidasCheck.checked : false,
    se_compra: seCompraCheck ? seCompraCheck.checked : true,
    se_vende: seVendeCheck ? seVendeCheck.checked : true,
    origen: origenSelect ? origenSelect.value : "local",
  };
  if (!body.nombre || !body.codigo) { mostrarMsg("Faltan nombre o código.", false); return; }

  const resp = await fetch(`${API}/articulo/${id}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) { 
    mostrarMsg(`Error: ${sanitizarValor(data.error)}`, false); 
    return; 
  }

  mostrarMsg("Artículo modificado correctamente.", true);
  if (typeof cargarSelectsStock === 'function') cargarSelectsStock();
}

function mostrarExcelModo(modo) {
  const modos = ["crear", "modificar"];
  modos.forEach(m => {
    const el = document.getElementById(`art-excel-${m}`);
    const btn = document.getElementById(`art-excel-btn-${m}`);
    if (el) el.style.display = m === modo ? "block" : "none";
    if (btn) btn.className = m === modo ? "small" : "small secondary";
  });
}

async function cargarExcelArticulos(inputEl, tipo) {
  if (!inputEl) return;
  const file = inputEl.files[0];
  if (!file) return;
  const basesElegidas = [...document.querySelectorAll(".multibase-check:checked")].map(c => c.value);

  const formData = new FormData();
  formData.append("archivo", file);
  basesElegidas.forEach(b => formData.append("bases", b));
  mostrarMsg("Procesando archivo...", true);

  const resp = await fetch(`${API}/excel/cargar/${tipo}`, { method: "POST", body: formData });
  const data = await resp.json();
  inputEl.value = "";
  if (!resp.ok) { 
    mostrarMsg(`Error: ${sanitizarValor(data.error)}`, false); 
    return; 
  }

  const containerMap = { articulos_modificar: "art-excel-mod-resultados" };
  const containerId = containerMap[tipo] || "art-excel-resultados";
  const accionMap = { articulos_modificar: "modificados" };
  const accion = accionMap[tipo] || "creados";

  if (data.resultados_por_base) {
    mostrarResultadosLotePorBase(containerId, data.resultados_por_base);
    const totalFilas = Object.values(data.resultados_por_base).reduce((acc, r) => acc + r.length, 0);
    const totalOk = Object.values(data.resultados_por_base).reduce((acc, r) => acc + r.filter(x => !x.error).length, 0);
    mostrarMsg(`${totalOk} de ${totalFilas} artículos ${accion} correctamente, en ${Object.keys(data.resultados_por_base).length} base(s).`, totalOk === totalFilas);
  } else {
    mostrarResultadosLote(containerId, data.resultados);
    const exitosos = data.resultados.filter(r => !r.error).length;
    mostrarMsg(`${exitosos} de ${data.resultados.length} artículos ${accion} correctamente.`, exitosos === data.resultados.length);
  }
  if (typeof cargarSelectsStock === 'function') cargarSelectsStock();
}

// ============================================================
// EXPORTAR FUNCIONES GLOBALES (ARTÍCULOS)
// ============================================================
window.crearArticulo = crearArticulo;
window.cargarArticuloParaModificar = cargarArticuloParaModificar;
window.guardarModificacionArticulo = guardarModificacionArticulo;
window.mostrarExcelModo = mostrarExcelModo;
window.cargarExcelArticulos = cargarExcelArticulos;
window.aplicarDefaultPartidas = aplicarDefaultPartidas;
window.actualizarCamposOrigen = actualizarCamposOrigen;
window.actualizarCamposOrigenMod = actualizarCamposOrigenMod;
window.escapeHTML = escapeHTML;

console.log('✅ Stock - Artículos cargado (XSS sanitizado)');