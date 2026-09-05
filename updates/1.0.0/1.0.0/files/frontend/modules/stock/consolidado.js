// ============================================================
// STOCK - CONSOLIDADO (CORREGIDO - XSS SANITIZADO)
// ============================================================

// ============================================================
// FUNCIÓN DE SANITIZACIÓN
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

// MAPEO DE DEPÓSITOS DE URUGUAY A PAÍSES PARA TRANSITO
const DEPOSITOS_TRANSITO = {
    7: { sigla: 'HN', nombre: 'Honduras' },
    10: { sigla: 'HN', nombre: 'Honduras' },
    14: { sigla: 'RD', nombre: 'República Dominicana' },
    9: { sigla: 'CO', nombre: 'Colombia' },
    13: { sigla: 'PE', nombre: 'Perú' },
    11: { sigla: 'PY', nombre: 'Paraguay' },
    12: { sigla: 'EC', nombre: 'Ecuador' },
};

const DEPOSITOS_FABRICA = {
    6: { sigla: 'UY-FAB', nombre: 'Fábrica 6' },
    8: { sigla: 'UY-FAB', nombre: 'Fábrica 8' },
};

const DEPOSITOS_ZF = {
    1: { sigla: 'UY-ZF', nombre: 'Zona Franca' },
};

// ============================================================
// FUNCIONES DE CONSOLIDADO
// ============================================================

async function buscarConsolidado(actualizarMarcas = false) {
  const q = document.getElementById("cons-q")?.value.trim() || "";
  const wrap = document.getElementById("cons-tabla-wrap");
  const loading = document.getElementById("cons-loading");
  const consBanner = document.getElementById("cons-banner");
  const chkErr = document.getElementById("cons-solo-errores");
  
  if (consBanner) consBanner.style.display = "none";
  const soloErroresAntes = chkErr ? chkErr.checked : false;
  if (chkErr) chkErr.checked = false;
  if (wrap) wrap.innerHTML = "";
  if (loading) loading.style.display = "block";

  const params = new URLSearchParams();
  if (q) params.set("q", q);

  // 🔴 DESACTIVADO: Llamadas a /marcas y /movidos (rutas no implementadas en backend)
  // Las notificaciones de "nuevos movimientos" están temporalmente deshabilitadas.
  // Si se desea reactivar, implementar las rutas en modules/stock/routes.py
  window._articulosMovidosEnCero = [];
  const basesConNuevos = new Set();

  let filas;
  try {
    const resp = await fetch(`${API}/stock/consolidado?${params.toString()}`);
    filas = await resp.json();
    if (filas && filas.error) throw new Error(filas.error);
  } catch (e) {
    if (loading) loading.style.display = "none";
    if (wrap) wrap.innerHTML = `<p style="color:var(--err-ink)">Error al consultar: ${sanitizarValor(e.message)}</p>`;
    return;
  }
  if (loading) loading.style.display = "none";

  if (!filas || filas.length === 0) {
    if (wrap) wrap.innerHTML = `<p style="color:var(--ink-soft);text-align:center;padding:24px 0">Sin resultados.</p>`;
    return;
  }

  filas = filas.map(f => ({ ...f, _total: f._total || 0 }));

  if (filas.length === 0) {
    if (wrap) wrap.innerHTML = `<p style="color:var(--ink-soft);text-align:center;padding:24px 0">Sin resultados con stock.</p>`;
    return;
  }

  const colsUY = ["ZF", "FABRICA", "TRANSITO"];
  const excluir = new Set(["codigo","nombre","inconsistente","primera_fila","_total","_siglas","_transito_tooltip",...colsUY]);
  const colsPais = Object.keys(filas[0]).filter(k => !excluir.has(k));
  const todasCols = [...colsUY, ...colsPais];

  const fmt = v => v > 0 ? `<b>${v.toLocaleString("es", {maximumFractionDigits:2})}</b>` : `<span style='color:#ccc'>—</span>`;
  const stickyBase = "position:sticky;z-index:2;";

  window._datosConsolidado = filas;

  const totCol = {};
  for (const c of todasCols) totCol[c] = filas.reduce((s, f) => s + (f[c] || 0), 0);
  const totTotal = filas.reduce((s, f) => s + (f._total || 0), 0);

  const thead = `<tr>
    <th style="${stickyBase}left:0;background:var(--surface-alt)">Código</th>
    <th style="${stickyBase}left:80px;background:var(--surface-alt);min-width:240px">Descripción</th>
    ${colsUY.map(c => `<th class="col-uy">${c}</th>`).join("")}
    ${colsPais.map(c => `<th class="col-pais">${c}</th>`).join("")}
    <th class="col-total">TOTAL</th>
  </tr>`;

  const tbody = filas.map(f => {
    // ✅ CORREGIDO: Sanitizar valores
    const codigo = sanitizarValor(f.codigo);
    const nombre = sanitizarValor(f.nombre);
    const siglas = f._siglas ? f._siglas.map(s => sanitizarValor(s)).join(", ") : "";
    const transitoValue = f.TRANSITO || 0;
    let transitoTooltip = f._transito_tooltip || '';
    if (transitoTooltip) {
      transitoTooltip = sanitizarValor(transitoTooltip.replace(/: \d+\.\d+/g, (match) => {
        return ': ' + Math.round(parseFloat(match.replace(': ', '')));
      }));
    }
    const tieneTooltip = transitoValue > 0 && transitoTooltip.length > 0;
    
    const celdas = todasCols.map(c => {
      const esUY = colsUY.includes(c);
      const valor = f[c] || 0;
      if (c === 'TRANSITO' && valor > 0 && tieneTooltip) {
        return `<td class="col-uy" title="${transitoTooltip}" style="cursor:help;border-bottom:1px dotted #999;text-decoration:underline dotted #999;">${fmt(valor)}</td>`;
      }
      if (c === 'TRANSITO' && valor > 0) {
        return `<td class="col-uy" title="TRANSITO (total)" style="cursor:help;">${fmt(valor)}</td>`;
      }
      return `<td class="${esUY ? "col-uy" : "col-pais"}">${fmt(valor)}</td>`;
    }).join("");

    const inc = f.inconsistente;
    const tieneNuevo = false; // 🔴 Desactivado: ya no se usa basesConNuevos
    const bgInc = inc ? "#fffbe6" : tieneNuevo ? "#edf7ed" : "var(--surface)";
    const colorInc = inc ? "#7a5800" : "var(--primary)";
    const titleInc = inc ? ' title="Nombres distintos entre países"' : "";
    const borderTop = f.primera_fila ? "" : "border-top:none;";
    const nuevoIndicador = ""; // 🔴 Desactivado

    const modalClick = inc ? ` onclick="window.abrirModalCorregir && window.abrirModalCorregir('${codigo}', event)"` : "";

    const codigoCell = f.primera_fila
      ? `<td style="${stickyBase}left:0;background:${bgInc};font-weight:700;color:${colorInc};${borderTop}${inc ? "cursor:pointer;" : ""}"${titleInc}${modalClick}>${inc ? "⚠ " : ""}${codigo}${nuevoIndicador}</td>`
      : `<td style="${stickyBase}left:0;background:${bgInc};border-top:none;border-bottom:1px solid var(--border)"></td>`;

    return `<tr style="${tieneNuevo ? `background:${bgInc};` : ""}">
      ${codigoCell}
      <td style="${stickyBase}left:80px;background:${bgInc};color:${inc ? "#7a5800" : "var(--ink)"};${f.primera_fila ? "" : "border-top:none;"}"${titleInc}>${nombre}${inc && f._siglas && f._siglas.length ? ` <span style="font-size:11px;opacity:0.9">(${siglas})</span>` : ""}</td>
      ${celdas}
      <td class="col-total">${fmt(f._total)}</td>
    </tr>`;
  }).join("");

  // 🔴 Sección de "movidos a cero" desactivada (porque no se obtienen datos)
  const tbodyCero = "";

  const tfoot = `<tr style="border-top:2px solid var(--border);font-weight:700;background:var(--surface-alt)">
    <td style="position:sticky;bottom:0;z-index:21;left:0;background:var(--surface-alt);font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.03em" colspan="2">Total</td>
    ${colsUY.map(c => `<td class="col-uy" style="position:sticky;bottom:0;z-index:21;background:var(--surface-alt);"><b>${totCol[c] > 0 ? totCol[c].toLocaleString("es",{maximumFractionDigits:2}) : "—"}</b></td>`).join("")}
    ${colsPais.map(c => `<td class="col-pais" style="position:sticky;bottom:0;z-index:21;background:var(--surface-alt);"><b>${totCol[c] > 0 ? totCol[c].toLocaleString("es",{maximumFractionDigits:2}) : "—"}</b></td>`).join("")}
    <td class="col-total" style="position:sticky;bottom:0;z-index:21;background:var(--surface-alt);"><b>${totTotal > 0 ? totTotal.toLocaleString("es",{maximumFractionDigits:2}) : "—"}</b></td>
  </tr>`;

  const inconsistentes = [...new Set(filas.filter(f => f.inconsistente && f.primera_fila).map(f => f.codigo))].length;
  const totalArticulos = filas.filter(f => f.primera_fila).length;
  const incTexto = inconsistentes > 0 ? ` · <span style="color:#7a5800">⚠ ${inconsistentes} con nombres distintos entre países</span>` : "";
  const vaciasTexto = ""; // 🔴 Desactivado
  
  const leyendaTransito = Object.entries(DEPOSITOS_TRANSITO).map(([dep, info]) => 
    `<span style="display:inline-block;margin:2px 6px 2px 0;font-size:11px;color:#64748b;">Dep ${dep}: ${info.sigla}</span>`
  ).join('');

  if (wrap) {
    wrap.innerHTML = `<div style="border:1px solid var(--border);border-radius:var(--radius-sm);overflow:auto;max-height:calc(100vh - 320px);">
      <table class="grid-editable cons-tabla" style="display:table;width:100%;border-collapse:collapse;">
        <thead style="position:sticky;top:0;z-index:20;">${thead}</thead>
        <tbody>${tbody}${tbodyCero}</tbody>
        <tfoot>${tfoot}</tfoot>
      </table>
    </div>
    <div style="margin-top:8px;display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;font-size:12px;color:var(--ink-soft)">
      <span>${totalArticulos} artículo${totalArticulos !== 1 ? "s" : ""} con stock${incTexto}${vaciasTexto}</span>
      <span style="border-left:1px solid var(--border);padding-left:12px;">📦 TRANSITO: ${leyendaTransito}</span>
    </div>`;
  }

  if (soloErroresAntes && chkErr) {
    chkErr.checked = true;
    filtrarSoloErrores();
  }
  // 🔴 Desactivado: no se actualizan marcas porque no hay rutas
  // if (actualizarMarcas) await _actualizarMarcasConsolidado();
}

function filtrarSoloErrores() {
  const soloErrores = document.getElementById("cons-solo-errores")?.checked || false;
  const tabla = document.querySelector(".cons-tabla tbody");
  if (!tabla) return;
  const datos = window._datosConsolidado || [];
  const codsInc = new Set(datos.filter(f => f.inconsistente).map(f => f.codigo).filter(Boolean));

  let codigoActual = null;
  Array.from(tabla.rows).forEach(tr => {
    const celdaCodigo = tr.cells[0];
    const textoCodigo = celdaCodigo ? celdaCodigo.textContent.replace("⚠ ", "").trim() : "";
    if (textoCodigo) codigoActual = textoCodigo;
    if (soloErrores) {
      tr.style.display = codsInc.has(codigoActual) ? "" : "none";
    } else {
      tr.style.display = "";
    }
  });
}

// ============================================================
// FUNCIONES DE TOAST Y POLLING (DESACTIVADAS)
// ============================================================

let _marcasConsolidadoGlobal = null;
let _toastVisibleGlobal = false;

function cerrarToast() {
  const toast = document.getElementById("stock-toast");
  if (toast) toast.style.display = "none";
  _toastVisibleGlobal = false;
}

function irConsolidadoDesdeToast() {
  // 🔴 Desactivado: ya no se usan marcas
  cerrarToast();
  if (typeof cambiarModulo === 'function') cambiarModulo('stock');
  document.querySelectorAll(".drawer-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  const tab = document.querySelector(".drawer-tab[data-tab='stock-consolidado']");
  if (tab) tab.classList.add("active");
  const consolidatedSection = document.getElementById("stock-consolidado");
  if (consolidatedSection) {
    consolidatedSection.classList.add("active");
    consolidatedSection.style.display = 'block';
  }
  const emptyState = document.getElementById("empty-state");
  if (emptyState) emptyState.style.display = "none";
  const seccionActiva = document.getElementById("seccion-activa");
  if (seccionActiva) {
    seccionActiva.textContent = "Stock Consolidado";
    seccionActiva.style.display = "block";
  }
  const msg = document.getElementById("msg");
  if (msg) msg.innerHTML = "";
  const container = document.querySelector(".container");
  if (container) container.classList.add("wide");
  buscarConsolidado(false); // 🔴 ya no se pasa true
}

// 🔴 Las siguientes funciones están desactivadas porque las rutas no existen en el backend
/*
async function _actualizarMarcasConsolidado() {
  // DESACTIVADO
}

async function _checkCambiosConsolidado() {
  // DESACTIVADO
}
*/

// ============================================================
// MODAL CORREGIR (sin cambios)
// ============================================================

let _codigoCorrigiendo = null;

function abrirModalCorregir(codigo, evt) {
  evt && evt.stopPropagation();
  _codigoCorrigiendo = codigo;

  const datos = window._datosConsolidado || [];
  const idx = datos.findIndex(f => f.codigo === codigo);
  const subFilas = [];
  if (idx >= 0) {
    subFilas.push(datos[idx]);
    for (let i = idx + 1; i < datos.length; i++) {
      if (datos[i].codigo !== "") break;
      subFilas.push(datos[i]);
    }
  }

  const titulo = document.getElementById("modal-corregir-titulo");
  const codigoEl = document.getElementById("modal-corregir-codigo");
  const nombreInput = document.getElementById("modal-corregir-nombre");
  const msgDiv = document.getElementById("modal-corregir-msg");
  const basesDiv = document.getElementById("modal-corregir-bases");
  const modal = document.getElementById("modal-corregir");

  if (titulo) titulo.textContent = "Corregir nombre";
  if (codigoEl) codigoEl.textContent = codigo;
  if (nombreInput) nombreInput.value = "";
  if (msgDiv) msgDiv.innerHTML = "";
  if (basesDiv) basesDiv.innerHTML = "";

  subFilas.forEach((fila, i) => {
    const siglas = fila._siglas || [];
    if (!siglas.length) return;
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:10px;padding:9px 14px;font-size:13.5px;" + (i < subFilas.length - 1 ? "border-bottom:1px solid var(--border)" : "");
    const siglasStr = sanitizarValor(JSON.stringify(siglas));
    const siglasDisplay = siglas.map(s => sanitizarValor(s)).join(", ");
    const nombreDisplay = sanitizarValor(fila.nombre);
    row.innerHTML = `
      <input type="checkbox" data-siglas='${siglasStr}' checked style="width:16px;height:16px;accent-color:var(--primary);flex-shrink:0">
      <div style="flex:1;min-width:0">
        <div style="font-weight:600;color:var(--ink-soft);font-size:11px;text-transform:uppercase;letter-spacing:.03em">${siglasDisplay}</div>
        <div style="color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${nombreDisplay}</div>
      </div>`;
    if (basesDiv) basesDiv.appendChild(row);
  });

  if (modal) modal.style.display = "flex";
  setTimeout(() => {
    const input = document.getElementById("modal-corregir-nombre");
    if (input) input.focus();
  }, 50);
}

function cerrarModalCorregir() {
  const modal = document.getElementById("modal-corregir");
  if (modal) modal.style.display = "none";
  _codigoCorrigiendo = null;
}

async function aplicarCorreccionModal() {
  const nombreInput = document.getElementById("modal-corregir-nombre");
  const msgDiv = document.getElementById("modal-corregir-msg");
  const btn = document.getElementById("modal-corregir-btn");
  
  if (!nombreInput) return;
  const nombre = nombreInput.value.trim();
  if (!nombre) {
    if (msgDiv) msgDiv.innerHTML = '<div class="msg error">Ingresa el nombre nuevo.</div>';
    return;
  }

  const checkboxes = document.querySelectorAll("#modal-corregir-bases input[type=checkbox]:checked");
  const siglasSeleccionadas = [];
  checkboxes.forEach(chk => siglasSeleccionadas.push(...JSON.parse(chk.dataset.siglas)));

  if (!siglasSeleccionadas.length) {
    if (msgDiv) msgDiv.innerHTML = '<div class="msg error">Selecciona al menos un pais.</div>';
    return;
  }

  const bases = Object.entries(BASES_DISPONIBLES_FRONT)
    .filter(([, info]) => siglasSeleccionadas.includes(info.sigla))
    .map(([base]) => base);

  if (btn) {
    btn.disabled = true;
    btn.textContent = "Aplicando...";
  }

  try {
    const r = await fetch(API + "/articulo/codigo/" + encodeURIComponent(_codigoCorrigiendo) + "/nombre", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre, bases })
    });
    const data = await r.json();

    if (data.error) {
      if (msgDiv) msgDiv.innerHTML = '<div class="msg error">' + sanitizarValor(data.error) + '</div>';
      return;
    }

    const res = data.resultados_por_base || {};
    const errores = Object.entries(res).filter(([, v]) => v.error);
    if (errores.length) {
      if (msgDiv) msgDiv.innerHTML = '<div class="msg error">' + errores.map(([b, v]) => sanitizarValor(b) + ": " + sanitizarValor(v.error)).join(", ") + '</div>';
    } else {
      cerrarModalCorregir();
      buscarConsolidado(false);
    }
  } catch (e) {
    if (msgDiv) msgDiv.innerHTML = '<div class="msg error">Error: ' + sanitizarValor(e.message) + '</div>';
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Aplicar";
    }
  }
}

// ============================================================
// EXPORTAR FUNCIONES GLOBALES (CONSOLIDADO)
// ============================================================
window.buscarConsolidado = buscarConsolidado;
window.filtrarSoloErrores = filtrarSoloErrores;
window.abrirModalCorregir = abrirModalCorregir;
window.cerrarModalCorregir = cerrarModalCorregir;
window.aplicarCorreccionModal = aplicarCorreccionModal;
window.cerrarToast = cerrarToast;
window.irConsolidadoDesdeToast = irConsolidadoDesdeToast;
window.escapeHTML = escapeHTML;

console.log('✅ Stock - Consolidado cargado (XSS sanitizado, sin llamadas a rutas inexistentes)');