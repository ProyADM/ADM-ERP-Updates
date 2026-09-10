// ============================================================
// STOCK - TRANSFERENCIAS (CORREGIDO)
// ============================================================

function sanitizarValor(val) {
    if (val === undefined || val === null) return '';
    return escapeHTML(String(val));
}

async function cargarPartidasTransferencia() {
  const artSelect = document.getElementById("tr-articulo");
  const depSelect = document.getElementById("tr-origen");
  const usaPartidas = artSelect.options[artSelect.selectedIndex]?.dataset.partidas === "true";
  const label = document.getElementById("tr-partida-label");
  const select = document.getElementById("tr-partida");
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

async function hacerTransferenciaIndividual() {
  const fechaVal = document.getElementById("tr-fecha")?.value;
  const body = {
    articulo: parseInt(document.getElementById("tr-articulo").value),
    deposito_origen: parseInt(document.getElementById("tr-origen").value),
    deposito_destino: parseInt(document.getElementById("tr-destino").value),
    cantidad: parseFloat(document.getElementById("tr-cantidad").value),
    fecha: fechaVal || null,
    comentario: document.getElementById("tr-comentario")?.value.trim() || null,
  };
  const partidaSelect = document.getElementById("tr-partida");
  if (partidaSelect.style.display !== "none" && partidaSelect.value) {
    body.partida = parseInt(partidaSelect.value);
  }
  const resp = await fetch(`${API}/transferencia`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await resp.json();
  if (resp.ok) {
    const numeroSanitizado = sanitizarValor(data.numero_transferencia);
    mostrarResultadoSeccion("trm-resultados", true, `Transferencia #${numeroSanitizado} cargada correctamente.`);
    const cantInput = document.getElementById("tr-cantidad");
    if (cantInput) cantInput.value = '';
    const fechaInput = document.getElementById("tr-fecha");
    if (fechaInput) fechaInput.value = '';
  } else {
    mostrarResultadoSeccion("trm-resultados", false, `Error: ${data.error}`);
  }
}

async function cargarLoteTransferencia() {
  const filas = [];
  document.querySelectorAll(`#trm-grid tbody tr`).forEach(tr => {
    const fila = {
      articulo: parseInt(tr.querySelector(".f-articulo").value),
      deposito_origen: parseInt(tr.querySelector(".f-origen").value),
      deposito_destino: parseInt(tr.querySelector(".f-destino").value),
      cantidad: parseFloat(tr.querySelector(".f-cantidad").value),
    };
    const partidaInput = tr.querySelector(".f-partida");
    if (partidaInput && partidaInput.value) fila.partida = parseInt(partidaInput.value);
    filas.push(fila);
  });
  if (filas.length === 0) { mostrarToastFlotante(false, "No hay filas para cargar."); return; }
  const resp = await fetch(`${API}/transferencia/lote`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filas }) });
  const data = await resp.json();
  mostrarResultadosLote("trm-resultados", data.resultados);
  const exitosos = data.resultados.filter(r => !r.error).length;
  mostrarToastFlotante(exitosos === filas.length, `${exitosos} de ${filas.length} filas cargadas correctamente.`);
}

// ============================================================
// EXPORTAR FUNCIONES GLOBALES (TRANSFERENCIAS)
// ============================================================
window.cargarPartidasTransferencia = cargarPartidasTransferencia;
window.cargarLoteTransferencia = cargarLoteTransferencia;
window.hacerTransferenciaIndividual = hacerTransferenciaIndividual;

console.log('✅ Stock - Transferencias cargado (XSS sanitizado)');