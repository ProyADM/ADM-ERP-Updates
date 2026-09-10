// ============================================================
// STOCK - EXCEL (CORREGIDO)
// ============================================================

function sanitizarValor(val) {
    if (val === undefined || val === null) return '';
    return escapeHTML(String(val));
}

function descargarPlantilla(tipo) {
  window.location.href = `${API}/excel/plantilla/${tipo}`;
}

async function cargarExcel(tipo, inputEl, prefix) {
  const file = inputEl.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("archivo", file);
  mostrarMsg("Procesando archivo...", true);

  let url = `${API}/excel/cargar/${tipo}`;
  if (tipo === "ajuste") {
    const signo = prefix === "ae" ? "E" : "S";
    url += `?signo=${signo}`;
  }

  const resp = await fetch(url, { method: "POST", body: formData });
  const data = await resp.json();
  inputEl.value = "";
  if (!resp.ok) { 
    mostrarMsg(`Error: ${sanitizarValor(data.error)}`, false); 
    return; 
  }

  if (tipo === "ajuste") {
    const tipoSanitizado = sanitizarValor(data.tipo);
    const numeroSanitizado = sanitizarValor(data.numero_comprobante);
    const cantidadSanitizada = sanitizarValor(data.cantidad_renglones);
    mostrarMsg(`Comprobante ${tipoSanitizado} #${numeroSanitizado} cargado con ${cantidadSanitizada} renglones.`, true);
  } else {
    const containerId = prefix === "trm" ? "trm-excel-resultados" : `${prefix}-excel-resultados`;
    mostrarResultadosLote(containerId, data.resultados);
    const exitosos = data.resultados.filter(r => !r.error).length;
    mostrarMsg(`${exitosos} de ${data.resultados.length} filas del Excel cargadas correctamente.`, exitosos === data.resultados.length);
  }
}

// ============================================================
// EXPORTAR FUNCIONES GLOBALES (EXCEL)
// ============================================================
window.descargarPlantilla = descargarPlantilla;
window.cargarExcel = cargarExcel;

console.log('✅ Stock - Excel cargado (XSS sanitizado)');