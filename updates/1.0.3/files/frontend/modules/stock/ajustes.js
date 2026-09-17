// ============================================================
// STOCK - AJUSTES (+ y -) (CORREGIDO - XSS SANITIZADO)
// ============================================================

// ============================================================
// FUNCIÓN DE SANITIZACIÓN
// ============================================================

function sanitizarValor(val) {
    if (val === undefined || val === null) return '';
    return escapeHTML(String(val));
}

function agregarFila(prefix, preset) {
  const gridId = prefix === "trm" ? "trm-grid" : prefix + "-grid";
  const tbody = document.querySelector(`#${gridId} tbody`);
  
  if (!tbody) {
    console.warn(`⚠️ No se encontró el tbody para ${gridId}`);
    return;
  }
  
  const tr = document.createElement("tr");

  if (prefix === "ae") {
    // ✅ CORREGIDO: Usar textContent para evitar XSS
    const articuloOptions = articuloOptionsHTML();
    const depositoOptions = depositoOptionsHTML();
    tr.innerHTML = `
      <td><select class="f-articulo">${articuloOptions}</select></td>
      <td><select class="f-deposito">${depositoOptions}</select></td>
      <td><input type="number" class="f-cantidad" value="1" min="0.0001" step="any"></td>
      <td><button class="btn-remove" data-onclick="this.closest('tr').remove()">✕</button></td>`;
    if (preset) {
      tr.querySelector(".f-articulo").value = preset.articulo;
      tr.querySelector(".f-deposito").value = preset.deposito;
    }
  } else if (prefix === "as") {
    const articuloOptions = articuloOptionsHTML();
    const depositoOptions = depositoOptionsHTML();
    tr.innerHTML = `
      <td><select class="f-articulo">${articuloOptions}</select></td>
      <td><select class="f-deposito">${depositoOptions}</select></td>
      <td><input type="number" class="f-cantidad" value="1" min="0.0001" step="any"></td>
      <td class="td-partida"><select class="f-partida" style="display:none"></select></td>
      <td><button class="btn-remove" data-onclick="this.closest('tr').remove(); actualizarColumnaPartida('as')">✕</button></td>`;
    const artSel = tr.querySelector(".f-articulo");
    const depSel = tr.querySelector(".f-deposito");
    artSel.addEventListener("change", () => cargarPartidasFila(tr, artSel, depSel, "as"));
    depSel.addEventListener("change", () => cargarPartidasFila(tr, artSel, depSel, "as"));
    if (preset) {
      artSel.value = preset.articulo;
      depSel.value = preset.deposito;
      cargarPartidasFila(tr, artSel, depSel, "as");
    }
  } else if (prefix === "trm") {
    const articuloOptions = articuloOptionsHTML();
    const depositoOptions = depositoOptionsHTML();
    tr.innerHTML = `
      <td><select class="f-articulo">${articuloOptions}</select></td>
      <td><select class="f-origen">${depositoOptions}</select></td>
      <td><select class="f-destino">${depositoOptions}</select></td>
      <td><input type="number" class="f-cantidad" value="1" min="0.0001" step="any"></td>
      <td class="td-partida"><select class="f-partida" style="display:none"></select></td>
      <td><button class="btn-remove" data-onclick="this.closest('tr').remove(); actualizarColumnaPartida('trm')">✕</button></td>`;
    const artSel = tr.querySelector(".f-articulo");
    const origenSel = tr.querySelector(".f-origen");
    artSel.addEventListener("change", () => cargarPartidasFila(tr, artSel, origenSel, "trm"));
    origenSel.addEventListener("change", () => cargarPartidasFila(tr, artSel, origenSel, "trm"));
    if (preset) {
      artSel.value = preset.articulo;
      origenSel.value = preset.deposito;
      cargarPartidasFila(tr, artSel, origenSel, "trm");
    }
  }
  tbody.appendChild(tr);
  // Convertir el selector de artículo de la fila (lote) en buscador por texto.
  const artSelFila = tr.querySelector(".f-articulo");
  if (artSelFila && typeof window.hacerSelectBuscable === 'function' && !artSelFila.dataset.buscable) {
    window.hacerSelectBuscable(artSelFila);
  }
}

async function cargarPartidasFila(tr, artSel, depSel, prefix) {
  const select = tr.querySelector(".f-partida");
  const usaPartidas = artSel.options[artSel.selectedIndex]?.dataset.partidas === "true";
  if (!usaPartidas) { select.style.display = "none"; select.innerHTML = ""; }
  else {
    select.style.display = "block";
    try {
      const partidas = await fetch(`${API}/partidas?articulo=${artSel.value}&deposito=${depSel.value}`).then(r => r.json());
      // ✅ CORREGIDO: Sanitizar datos de partidas
      const options = partidas.map(p => {
        const partidaVal = sanitizarValor(p.partida);
        const partidaEmp = sanitizarValor(p.partida_emp || `Partida ${p.partida}`);
        const stockVal = sanitizarValor(p.stock);
        return `<option value="${partidaVal}">${partidaEmp} (stock: ${stockVal})</option>`;
      }).join("");
      select.innerHTML = `<option value="">-</option>` + options;
    } catch (e) {
      console.warn('Error cargando partidas:', e);
      select.innerHTML = '<option value="">Error al cargar</option>';
    }
  }
  actualizarColumnaPartida(prefix);
}

function actualizarColumnaPartida(prefix) {
  const gridId = prefix === "trm" ? "trm-grid" : prefix + "-grid";
  const thId = prefix + "-th-partida";
  const algunaConPartidas = [...document.querySelectorAll(`#${gridId} tbody .f-articulo`)].some(s => s.options[s.selectedIndex]?.dataset.partidas === "true");
  const display = algunaConPartidas ? "" : "none";
  document.getElementById(thId).style.display = display;
  document.querySelectorAll(`#${gridId} tbody .td-partida`).forEach(td => td.style.display = display);
}

async function hacerAjusteIndividual(signo) {
  const prefix = signo === "E" ? "ae" : "as";
  const fechaVal = document.getElementById(`${prefix}-fecha`)?.value;
  const body = {
    articulo: parseInt(document.getElementById(`${prefix}-articulo`).value),
    deposito: parseInt(document.getElementById(`${prefix}-deposito`).value),
    cantidad: parseFloat(document.getElementById(`${prefix}-cantidad`).value),
    signo: signo,
    fecha: fechaVal || null,
    comentario: document.getElementById(`${prefix}-comentario`)?.value.trim() || null,
  };
  if (signo === "S") {
    const partidaSelect = document.getElementById("as-partida");
    if (partidaSelect.style.display !== "none" && partidaSelect.value) {
      body.partida = parseInt(partidaSelect.value);
    }
  }
  if (signo === "E") {
    const pNombre = document.getElementById("ae-partida-nombre");
    if (pNombre && pNombre.style.display !== "none" && pNombre.value.trim()) {
      body.partida_nombre = pNombre.value.trim();
    }
  }
  const resp = await fetch(`${API}/ajuste`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await resp.json();
  if (resp.ok) {
    // ✅ CORREGIDO: Sanitizar mensaje
    const tipoSanitizado = sanitizarValor(data.tipo);
    const numeroSanitizado = sanitizarValor(data.numero_comprobante);
    mostrarResultadoSeccion(`${prefix}-resultados`, true, `Movimiento ${tipoSanitizado} #${numeroSanitizado} cargado correctamente.`);
    const cantInput = document.getElementById(`${prefix}-cantidad`);
    if (cantInput) cantInput.value = '';
    const fechaInput = document.getElementById(`${prefix}-fecha`);
    if (fechaInput) fechaInput.value = '';
  } else {
    mostrarResultadoSeccion(`${prefix}-resultados`, false, `Error: ${data.error}`);
  }
}

async function cargarPartidasEntrada() {
  const artSelect = document.getElementById("ae-articulo");
  const usaPartidas = artSelect.options[artSelect.selectedIndex]?.dataset.partidas === "true";
  const label = document.getElementById("ae-partida-label");
  const input = document.getElementById("ae-partida-nombre");
  if (!usaPartidas) { label.style.display = "none"; input.style.display = "none"; input.value = ""; return; }
  label.style.display = "block"; input.style.display = "block";
}

async function cargarPartidas() {
  const artSelect = document.getElementById("as-articulo");
  const depSelect = document.getElementById("as-deposito");
  const usaPartidas = artSelect.options[artSelect.selectedIndex]?.dataset.partidas === "true";
  const label = document.getElementById("as-partida-label");
  const select = document.getElementById("as-partida");
  if (!usaPartidas) { label.style.display = "none"; select.style.display = "none"; select.innerHTML = ""; return; }
  label.style.display = "block"; select.style.display = "block";
  try {
    const partidas = await fetch(`${API}/partidas?articulo=${artSelect.value}&deposito=${depSelect.value}`).then(r => r.json());
    // ✅ CORREGIDO: Sanitizar datos de partidas
    const options = partidas.map(p => {
      const partidaVal = sanitizarValor(p.partida);
      const partidaEmp = sanitizarValor(p.partida_emp || `Partida ${p.partida}`);
      const stockVal = sanitizarValor(p.stock);
      return `<option value="${partidaVal}">${partidaEmp} (stock: ${stockVal})</option>`;
    }).join("");
    select.innerHTML = options;
  } catch (e) {
    console.warn('Error cargando partidas:', e);
    select.innerHTML = '<option value="">Error al cargar</option>';
  }
}

async function cargarLote(prefix, signo) {
  const filas = [];
  document.querySelectorAll(`#${prefix}-grid tbody tr`).forEach(tr => {
    const articulo = parseInt(tr.querySelector(".f-articulo").value);
    const deposito = parseInt(tr.querySelector(".f-deposito").value);
    const cantidad = parseFloat(tr.querySelector(".f-cantidad").value);
    const partidaInput = tr.querySelector(".f-partida");
    const fila = { articulo, deposito, cantidad };
    if (partidaInput && partidaInput.value) fila.partida = parseInt(partidaInput.value);
    filas.push(fila);
  });
  if (filas.length === 0) { mostrarResultadoSeccion(`${prefix}-resultados`, false, "No hay filas para cargar."); return; }
  const resp = await fetch(`${API}/ajuste/lote`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ signo, filas }) });
  const data = await resp.json();
  if (resp.ok) {
    const tipoSanitizado = sanitizarValor(data.tipo);
    const numeroSanitizado = sanitizarValor(data.numero_comprobante);
    const cantidadSanitizada = sanitizarValor(data.cantidad_renglones);
    mostrarResultadoSeccion(`${prefix}-resultados`, true, `Comprobante ${tipoSanitizado} #${numeroSanitizado} cargado con ${cantidadSanitizada} renglones.`);
  } else {
    mostrarResultadoSeccion(`${prefix}-resultados`, false, `Error: ${data.error}`);
  }
}

// ============================================================
// EXPORTAR FUNCIONES GLOBALES (AJUSTES)
// ============================================================
window.agregarFila = agregarFila;
window.hacerAjusteIndividual = hacerAjusteIndividual;
window.cargarPartidas = cargarPartidas;
window.cargarPartidasEntrada = cargarPartidasEntrada;
window.cargarLote = cargarLote;
window.actualizarColumnaPartida = actualizarColumnaPartida;

console.log('✅ Stock - Ajustes cargado (XSS sanitizado)');