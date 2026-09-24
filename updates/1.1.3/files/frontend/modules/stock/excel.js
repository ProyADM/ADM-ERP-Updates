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

  // Las cargas de MOVIMIENTOS llevan clave de idempotencia, igual que los
  // formularios: el backend deriva una clave por fila del archivo
  // (<clave>:<numero de fila>). Mientras el envio CONSERVE su clave, reintentar
  // el mismo envio no duplica: las filas que ya entraron se devuelven del
  // registro de la clave y solo se aplican las que faltan. La clave recien se
  // cierra cuando la carga termino bien Y ninguna fila quedo con error; si se
  // vuelve a subir el archivo como envio NUEVO (clave nueva) las filas que ya
  // habian entrado no se re-aplican solo si el envio anterior conservo la clave,
  // que es justo lo que garantiza `todas_ok`.
  const conIdempotencia = tipo === "ajuste" || tipo === "transferencia";
  const envio = `excel:${tipo}:${prefix}`;

  const resp = await fetch(url, {
    method: "POST",
    body: formData,
    headers: conIdempotencia ? { "X-Idempotencia": claveDeEnvio(envio) } : {}
  });
  const data = await resp.json();
  inputEl.value = "";
  if (!resp.ok) {
    if (conIdempotencia && resp.status === 409 && data.codigo === 'STK_VAL_CLAVE_REUTILIZADA') {
      // La clave quedo pegada a OTRO contenido: se olvida para que el proximo
      // envio genere una clave nueva.
      olvidarEnvio(envio);
      mostrarMsg(MENSAJE_CLAVE_REUTILIZADA, false);
      return;
    }
    mostrarMsg(`Error: ${sanitizarValor(data.error)}`, false);
    return;
  }
  // Con filas fallidas la clave queda guardada para poder reintentar el mismo
  // envio sin duplicar las que ya entraron (el ajuste no tiene `todas_ok`: es
  // un solo comprobante y sale todo o nada).
  if (conIdempotencia) cerrarEnvio(envio, data.todas_ok !== false);

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