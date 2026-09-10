// ============================================================
// CONFIGURACIÓN GLOBAL
// ============================================================
const API = "/api";
let baseActiva = null;
let sociedadActiva = null;
let basesCache = [];
let BASES_DISPONIBLES_FRONT = {};
let articulosCache = [];
let depositosCache = [];
let categoriasCache = [];

let moduloActual = 'stock';
let _marcasConsolidado = null;
let _toastVisible = false;
let drawerAbierto = false;

let stockSelectsCargados = false;
let cargandoSelects = false;

// ============================================================
// FUNCIONES DE SANITIZACIÓN
// ============================================================
function sanitizarHTML(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function sanitizarAtributo(str) {
    if (!str) return '';
    return String(str).replace(/[^a-zA-Z0-9\-_]/g, '');
}

// ============================================================
// FETCH CON HEADERS DE BASE
// ============================================================
const _fetchOriginal = window.fetch;
window.fetch = function (url, options = {}) {
  if (typeof url === "string" && url.startsWith(API) && baseActiva) {
    const headers = { ...(options.headers || {}), "X-Base": baseActiva };
    if (sociedadActiva) headers["X-Sociedad"] = sociedadActiva;
    options = { ...options, headers };
  }
  return _fetchOriginal(url, options);
};

// ============================================================
// MÓDULOS
// ============================================================
function cambiarModulo(modulo) {
  console.log(`📂 Cambiando a módulo: ${modulo}`);
  // Si ya estamos en el módulo y su template ya está montado, NO re-renderizar:
  // solo refrescar los estados visuales. Sin esto, tocar el tab del módulo
  // activo (p.ej. para abrir el menú) reemplazaba el template y "recargaba" la
  // vista actual por detrás del drawer (perdía sección/reporte/scroll).
  if (modulo === moduloActual && typeof templateInicializado !== 'undefined' && templateInicializado[modulo]) {
    document.querySelectorAll('.module-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.module === modulo);
    });
    document.querySelectorAll('.drawer-module').forEach(m => {
      m.style.display = m.dataset.module === modulo ? '' : 'none';
    });
    console.log(`ℹ️ Ya estás en ${modulo} (template montado) — sin re-render`);
    return;
  }
  moduloActual = modulo;
  document.querySelectorAll('.module-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.module === modulo);
  });
  document.querySelectorAll('.drawer-module').forEach(m => {
    m.style.display = m.dataset.module === modulo ? '' : 'none';
  });
  const emptyState = document.getElementById('empty-state');
  if (emptyState) emptyState.style.display = 'none';
  const moduleContent = document.getElementById('module-content');
  if (moduleContent) moduleContent.style.display = 'block';
  if (typeof cargarTemplate === 'function') {
    cargarTemplate(modulo);
  } else {
    console.warn('⚠️ cargarTemplate no está disponible');
  }
}

function cargarCXPInicial() {
  console.log('📦 Cargando módulo CXP inicial...');
  const cxpElement = document.getElementById('cxp-facturas');
  if (!cxpElement) {
    if (typeof cargarTemplate === 'function') {
      cargarTemplate('cxp');
      console.log('✅ Template CXP cargado inicialmente');
    }
  } else {
    console.log('ℹ️ Template CXP ya está cargado');
  }
}

// ============================================================
// DRAWER - MANUAL (SOLO CON CLICK EN HAMBURGUESA)
// ============================================================
function openDrawer() {
  if (drawerAbierto) { console.log('📂 Drawer ya está abierto'); return; }
  console.log('📂 Abriendo drawer...');
  document.querySelectorAll('.drawer-module').forEach(m => {
    m.style.display = m.dataset.module === moduloActual ? '' : 'none';
  });
  const drawer = document.getElementById('drawer');
  const overlay = document.getElementById('drawer-overlay');
  if (drawer) { drawer.classList.add('open'); drawerAbierto = true; console.log('✅ Drawer abierto'); }
  if (overlay) overlay.classList.add('open');
}

function closeDrawer() {
  if (!drawerAbierto) { console.log('📂 Drawer ya está cerrado'); return; }
  console.log('📂 Cerrando drawer...');
  const drawer = document.getElementById('drawer');
  const overlay = document.getElementById('drawer-overlay');
  if (drawer) { drawer.classList.remove('open'); drawerAbierto = false; console.log('✅ Drawer cerrado'); }
  if (overlay) overlay.classList.remove('open');
}

function toggleDrawer() {
  if (drawerAbierto) closeDrawer(); else openDrawer();
}

const drawerClose = document.getElementById('drawer-close');
if (drawerClose) {
  drawerClose.addEventListener('click', (e) => { e.stopPropagation(); closeDrawer(); });
}
const drawerOverlay = document.getElementById('drawer-overlay');
if (drawerOverlay) {
  drawerOverlay.addEventListener('click', (e) => { e.stopPropagation(); closeDrawer(); });
}

// ============================================================
// DRAWER - TABS Y SUBTABS
// ============================================================
document.querySelectorAll('.drawer-tab').forEach(tab => {
  tab.addEventListener('click', (e) => {
    e.stopPropagation();
    console.log(`📌 Click en tab: ${tab.textContent}`);
    const group = tab.closest('.drawer-group');
    if (!group) return;
    const tieneSub = group.querySelector('.drawer-sub') !== null;
    if (tieneSub) {
      const yaEstaba = group.classList.contains('expanded');
      document.querySelectorAll('.drawer-group').forEach(g => g.classList.remove('expanded'));
      if (!yaEstaba) group.classList.add('expanded');
      return;
    }
    document.querySelectorAll('.drawer-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.drawer-group').forEach(g => g.classList.remove('expanded'));
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    tab.classList.add('active');
    const targetTab = document.getElementById(tab.dataset.tab);
    if (targetTab) targetTab.classList.add('active');
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.style.display = 'none';
    const titulo = document.getElementById('seccion-activa');
    if (titulo) { titulo.textContent = tab.textContent; titulo.style.display = 'block'; }
    const msg = document.getElementById('msg');
    if (msg) msg.innerHTML = '';
    const container = document.querySelector('.container');
    if (container) { container.classList.toggle('wide', tab.dataset.tab === 'stock-consolidado'); }
    if (moduloActual === 'stock' && typeof navegarStock === 'function') {
      try { localStorage.setItem('ultimaSeccionStock', tab.dataset.tab); } catch (e) {}
      navegarStock(tab.dataset.tab);
    }
    if (tab.dataset.tab === 'stock-consolidado') {
      if (typeof cerrarToast === 'function') cerrarToast();
      if (typeof buscarConsolidado === 'function') buscarConsolidado(true);
    }
    closeDrawer();
  });
});

document.querySelectorAll('.drawer-subitem').forEach(sub => {
  sub.addEventListener('click', (e) => {
    e.stopPropagation();
    console.log(`📌 Click en subitem: ${sub.textContent}`);
    const group = sub.dataset.group;
    if (!group) return;
    document.querySelectorAll(`.drawer-subitem[data-group="${group}"]`).forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.subsection').forEach(s => {
      if (s.id.startsWith(group + '-')) s.classList.remove('active');
    });
    sub.classList.add('active');
    const targetSub = document.getElementById(sub.dataset.sub);
    if (targetSub) targetSub.classList.add('active');
    document.querySelectorAll('.drawer-tab').forEach(t => t.classList.remove('active'));
    const parentGroup = sub.closest('.drawer-group');
    if (parentGroup) {
      const parentTab = parentGroup.querySelector('.drawer-tab');
      if (parentTab) parentTab.classList.add('active');
    }
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const tabPadre = sub.closest('.drawer-group')?.querySelector('.drawer-tab');
    if (tabPadre) {
      const targetSection = document.getElementById(tabPadre.dataset.tab);
      if (targetSection) targetSection.classList.add('active');
    }
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.style.display = 'none';
    const titulo = document.getElementById('seccion-activa');
    if (titulo && tabPadre) { titulo.textContent = tabPadre.textContent; titulo.style.display = 'block'; }
    const container = document.querySelector('.container');
    if (container) container.classList.remove('wide');
    if (moduloActual === 'stock' && tabPadre && typeof navegarStock === 'function') {
      try { localStorage.setItem('ultimaSeccionStock', tabPadre.dataset.tab); } catch (e) {}
      navegarStock(tabPadre.dataset.tab);
    }
    closeDrawer();
  });
});

// ============================================================
// BASES (CON SIGLAS)
// ============================================================
async function inicializarBase(baseForzada, sociedadForzada) {
  const data = await fetch(`${API}/bases`).then(r => r.json());
  basesCache = data.bases;
  BASES_DISPONIBLES_FRONT = Object.fromEntries(data.bases.map(b => [b.codigo, b]));
  baseActiva = baseForzada || data.default;
  sociedadActiva = sociedadForzada || data.sociedad_default;
  window.baseActiva = baseActiva;
  window.sociedadActiva = sociedadActiva;
  window.BASES_DISPONIBLES_FRONT = BASES_DISPONIBLES_FRONT;
  actualizarIndicadorBase();
  const multibaseChecklist = document.getElementById("multibase-checklist");
  if (multibaseChecklist) {
    multibaseChecklist.innerHTML = basesCache.map(b => {
      const codigo = escapeHTML(b.codigo);
      const label = escapeHTML(b.label);
      const sigla = window.siglaBase(codigo) || label;
      return `<label style="display:flex;align-items:center;gap:8px;text-transform:none;font-weight:500;margin-top:6px">
        <input type="checkbox" class="multibase-check" value="${codigo}" style="width:auto"> ${sigla}
      </label>`;
    }).join("");
  }
  const depMultibaseChecklist = document.getElementById("dep-multibase-checklist");
  if (depMultibaseChecklist) {
    depMultibaseChecklist.innerHTML = basesCache.map(b => {
      const codigo = escapeHTML(b.codigo);
      const label = escapeHTML(b.label);
      const sigla = window.siglaBase(codigo) || label;
      return `<label style="display:flex;align-items:center;gap:8px;text-transform:none;font-weight:500;margin-top:6px">
        <input type="checkbox" class="dep-multibase-check" value="${codigo}" style="width:auto"> ${sigla}
      </label>`;
    }).join("");
  }
  await cargarSelectsStock();
  const event = new CustomEvent('baseChanged', { detail: { base: baseActiva } });
  window.dispatchEvent(event);
}

function actualizarIndicadorBase() {
  const baseInfo = BASES_DISPONIBLES_FRONT[baseActiva];
  if (!baseInfo) { console.warn('Base no encontrada:', baseActiva); return; }
  const baseLabel = document.getElementById("base-btn-label");
  if (baseLabel) {
    const sigla = window.siglaBase(baseActiva) || baseInfo.label;
    baseLabel.textContent = sigla;
  }
  const baseDropdown = document.getElementById("base-dropdown");
  if (baseDropdown) {
    baseDropdown.innerHTML = basesCache.map(b => {
      const codigo = escapeHTML(b.codigo);
      const label = escapeHTML(b.label);
      const sigla = window.siglaBase(codigo) || label;
      return `<button class="base-opt${b.codigo === baseActiva ? ' active' : ''}" data-onclick="seleccionarBase('${codigo}')">
        ${sigla}
        <span class="check">✓</span>
      </button>`;
    }).join("");
  }
  const socPicker = document.getElementById("sociedad-picker");
  if (socPicker) {
    if (baseInfo.sociedades && baseInfo.sociedades.length > 0) {
      socPicker.style.display = "";
      let soc = baseInfo.sociedades.find(s => s.codigo === sociedadActiva);
      if (!soc) { soc = baseInfo.sociedades[0]; sociedadActiva = soc.codigo; window.sociedadActiva = sociedadActiva; }
      const socLabel = document.getElementById("sociedad-btn-label");
      if (socLabel) socLabel.textContent = soc.label;
      const socDropdown = document.getElementById("sociedad-dropdown");
      if (socDropdown) {
        socDropdown.innerHTML = baseInfo.sociedades.map(s => {
          const codigo = escapeHTML(s.codigo);
          const label = escapeHTML(s.label);
          return `<button class="base-opt${s.codigo === sociedadActiva ? ' active' : ''}" data-onclick="seleccionarSociedad('${codigo}')">
            ${label}
            <span class="check">✓</span>
          </button>`;
        }).join("");
      }
    } else { socPicker.style.display = "none"; }
  }
}

function toggleBasePicker() {
  const dd = document.getElementById("base-dropdown");
  const ddSoc = document.getElementById("sociedad-dropdown");
  if (ddSoc) ddSoc.style.display = "none";
  if (dd) { dd.style.display = dd.style.display === "block" ? "none" : "block"; }
}

function toggleSociedadPicker() {
  const dd = document.getElementById("sociedad-dropdown");
  const ddBase = document.getElementById("base-dropdown");
  if (ddBase) ddBase.style.display = "none";
  if (dd) { dd.style.display = dd.style.display === "block" ? "none" : "block"; }
}

document.addEventListener("click", e => {
  if (!e.target.closest("#base-picker") && !e.target.closest("#sociedad-picker")) {
    const baseDropdown = document.getElementById("base-dropdown");
    const sociedadDropdown = document.getElementById("sociedad-dropdown");
    if (baseDropdown) baseDropdown.style.display = "none";
    if (sociedadDropdown) sociedadDropdown.style.display = "none";
  }
});

async function seleccionarBase(codigo) {
  const baseDropdown = document.getElementById("base-dropdown");
  if (baseDropdown) baseDropdown.style.display = "none";
  baseActiva = codigo;
  const baseInfo = BASES_DISPONIBLES_FRONT[baseActiva];
  sociedadActiva = baseInfo && baseInfo.sociedades && baseInfo.sociedades.length > 0 ? baseInfo.sociedades[0].codigo : null;
  window.baseActiva = baseActiva;
  window.sociedadActiva = sociedadActiva;
  actualizarIndicadorBase();
  await cargarSelectsStock();
  const event = new CustomEvent('baseChanged', { detail: { base: baseActiva } });
  window.dispatchEvent(event);
  if (moduloActual === 'cxp' && typeof validarBaseGT === 'function') {
    setTimeout(() => { console.log('🔄 Re-validando GT desde seleccionarBase'); validarBaseGT(); }, 500);
  }
}

async function seleccionarSociedad(codigo) {
  const sociedadDropdown = document.getElementById("sociedad-dropdown");
  if (sociedadDropdown) sociedadDropdown.style.display = "none";
  sociedadActiva = codigo;
  window.sociedadActiva = sociedadActiva;
  actualizarIndicadorBase();
  await cargarSelectsStock();
  const event = new CustomEvent('baseChanged', { detail: { base: baseActiva } });
  window.dispatchEvent(event);
}

// ============================================================
// STOCK - SELECTS
// ============================================================
async function cargarSelectsStock() {
  // Semántica: "asegurar cargados Y aplicados al DOM". Aunque las caches ya
  // existan (arranque), se re-aplican las opciones porque el template del
  // módulo Stock puede haberse montado después (bug de combos vacíos).
  if (stockSelectsCargados) { console.log('ℹ️ Selects de stock ya cargados, omitiendo...'); aplicarSelectsStockDOM(); return; }
  if (cargandoSelects) {
    console.log('⏳ Selects de stock cargándose, esperando...');
    let espera = 0;
    while (cargandoSelects && espera < 50) { await new Promise(r => setTimeout(r, 100)); espera++; }
    if (stockSelectsCargados) { console.log('✅ Selects cargados durante la espera'); aplicarSelectsStockDOM(); return; }
  }
  cargandoSelects = true;
  try {
    console.log('📦 Cargando selects de stock...');
    console.log('📡 Fetching /api/articulos...');
    const articulosRes = await fetch(`${API}/articulos`);
    if (!articulosRes.ok) { const text = await articulosRes.text(); console.error('❌ Error en /api/articulos:', text.substring(0, 200)); throw new Error(`Error ${articulosRes.status}`); }
    articulosCache = await articulosRes.json();
    console.log(`✅ ${articulosCache.length} artículos cargados`);
    const _sortCodigo = cod => { try { return (cod||"").split(".").map(Number); } catch(e) { return [0]; } };
    articulosCache.sort((a,b)=>{const ka=_sortCodigo(a.codigo),kb=_sortCodigo(b.codigo);for(let i=0;i<Math.max(ka.length,kb.length);i++){const d=(ka[i]||0)-(kb[i]||0);if(d!==0)return d;}return 0;});
    console.log('📡 Fetching /api/depositos...');
    const depositosRes = await fetch(`${API}/depositos`);
    if (!depositosRes.ok) { const text = await depositosRes.text(); console.error('❌ Error en /api/depositos:', text.substring(0, 200)); throw new Error(`Error ${depositosRes.status}`); }
    depositosCache = await depositosRes.json();
    console.log(`✅ ${depositosCache.length} depósitos cargados`);
    console.log('📡 Fetching /api/categorias...');
    categoriasCache = await fetch(`${API}/categorias`).then(r => r.json());
    console.log(`✅ ${categoriasCache.length} categorías cargadas`);

    aplicarSelectsStockDOM();
    stockSelectsCargados = true;
    console.log('✅ Selects de stock cargados correctamente');
  } catch (e) {
    console.error('❌ Error cargando selects de stock:', e);
    const msg = document.getElementById('msg');
    if (msg) { msg.innerHTML = `<div class="msg error">⚠️ Error al cargar datos de stock: ${escapeHTML(e.message)}</div>`; }
  } finally { cargandoSelects = false; }
}

// ============================================================
// STOCK - SELECTS: APLICAR OPCIONES AL DOM (idempotente)
// ============================================================
function aplicarSelectsStockDOM() {
  // cargarSelectsStock() corre al iniciar la app cuando el template de Stock
  // aún no está en el DOM (solo el dashboard está montado). Los <select> de
  // Stock se crean al montar el módulo, y el guard (stockSelectsCargados)
  // impedía volver a aplicar las opciones → quedaban vacíos (combos
  // "Elegí un artículo/depósito..."). Esta función re-aplica las caches a los
  // selects presentes. Es idempotente: no duplica filas de grillas.
  if (!articulosCache.length && !depositosCache.length && !categoriasCache.length) {
    console.log('ℹ️ aplicarSelectsStockDOM: caches vacías, omitiendo');
    return;
  }
  const artOptions = articulosCache.map(a => {
    const id = escapeHTML(a.id); const codigo = escapeHTML(a.codigo); const nombre = escapeHTML(a.nombre); const partidas = escapeHTML(a.con_partidas);
    return `<option value="${id}" data-partidas="${partidas}">${codigo} - ${nombre}</option>`;
  }).join("");
  const depOptions = depositosCache.map(d => {
    const id = escapeHTML(d.id); const nombre = escapeHTML(d.nombre);
    return `<option value="${id}">${id} - ${nombre}</option>`;
  }).join("");
  const catOptions = categoriasCache.map(c => {
    const codigo = escapeHTML(c.codigo); const nombre = escapeHTML(c.nombre); const defaultVal = escapeHTML(c.con_partidas_default);
    return `<option value="${codigo}" data-partidas-default="${defaultVal}">${nombre}</option>`;
  }).join("");

  const aeArticulo = document.getElementById("ae-articulo");
  if (aeArticulo) aeArticulo.innerHTML = artOptions;
  const asArticulo = document.getElementById("as-articulo");
  if (asArticulo) asArticulo.innerHTML = artOptions;
  const trArticulo = document.getElementById("tr-articulo");
  if (trArticulo) trArticulo.innerHTML = artOptions;
  ["ae-deposito", "as-deposito", "tr-origen", "tr-destino"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = depOptions;
  });
  const stkDep = document.getElementById("stk-deposito");
  if (stkDep) stkDep.innerHTML = `<option value="">Todos</option>${depOptions}`;
  const artCat = document.getElementById("art-categoria");
  if (artCat) artCat.innerHTML = catOptions;
  const artModCat = document.getElementById("art-mod-categoria");
  if (artModCat) artModCat.innerHTML = catOptions;
  const artModBuscar = document.getElementById("art-mod-buscar");
  if (artModBuscar) {
    artModBuscar.innerHTML = `<option value="">Elegí un artículo...</option>` + articulosCache.map(a => {
      const id = escapeHTML(a.id); const codigo = escapeHTML(a.codigo); const nombre = escapeHTML(a.nombre);
      return `<option value="${id}">${codigo} - ${nombre}</option>`;
    }).join("");
  }
  const depModBuscar = document.getElementById("dep-mod-buscar");
  if (depModBuscar) {
    depModBuscar.innerHTML = `<option value="">Elegí un depósito...</option>` + depositosCache.map(d => {
      const id = escapeHTML(d.id); const nombre = escapeHTML(d.nombre);
      return `<option value="${id}">${id} - ${nombre}</option>`;
    }).join("");
  }
  // Primera fila de las grillas de ajuste/transferencia (solo si vacías,
  // para que la re-aplicación no duplique filas).
  ["ae", "as", "trm"].forEach(prefix => {
    const gridId = prefix === "trm" ? "trm-grid" : prefix + "-grid";
    const tbody = document.querySelector(`#${gridId} tbody`);
    if (tbody && tbody.rows.length === 0 && typeof agregarFila === 'function') {
      agregarFila(prefix);
    }
  });
  const artCategoria = document.getElementById("art-categoria");
  if (artCategoria && typeof aplicarDefaultPartidas === 'function') { aplicarDefaultPartidas(); }
  const seCompra = document.getElementById("art-se-compra");
  if (seCompra && typeof actualizarCamposOrigen === 'function') { actualizarCamposOrigen(); }
  // Convertir los desplegables de artículos en buscadores por texto (escribiendo).
  if (typeof window.aplicarBuscadoresStock === 'function') {
    window.aplicarBuscadoresStock();
  }
  console.log('✅ Selects de stock aplicados al DOM');
}

// ============================================================
// ACTUALIZACIÓN AUTOMÁTICA (VERSIÓN ANTIGUA, se mantiene)
// ============================================================
let lastVersion = null;
async function checkVersion() {
  try {
    const r = await fetch(`${API}/__version`);
    const data = await r.json();
    if (lastVersion === null) { lastVersion = data.version; return; }
    if (data.version !== lastVersion) {
      const banner = document.getElementById('update-banner');
      if (banner) banner.style.display = 'flex';
    }
  } catch (e) {}
}
checkVersion();
setInterval(checkVersion, 1500);

async function actualizarApp() {
  try { await fetch('/api/reiniciar', { method: 'POST' }); } catch {}
  setTimeout(() => location.reload(), 2000);
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
function showToast(message, type = 'info', title = '', duration = 4000) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const titles = { success: 'Éxito', error: 'Error', warning: 'Advertencia', info: 'Información' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
    <div class="toast-content">
      <div class="toast-title">${escapeHTML(title || titles[type] || 'Información')}</div>
      <div class="toast-message">${escapeHTML(message)}</div>
    </div>
    <button class="toast-close" data-onclick="this.closest('.toast').remove()">✕</button>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('hiding');
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 300);
  }, duration);
  return toast;
}

function toastSuccess(message, title = 'Éxito') { showToast(message, 'success', title); }
function toastError(message, title = 'Error') { showToast(message, 'error', title); }
function toastWarning(message, title = 'Advertencia') { showToast(message, 'warning', title); }
function toastInfo(message, title = 'Información') { showToast(message, 'info', title); }

// ============================================================
// INICIALIZAR DRAWER
// ============================================================
function inicializarDrawer() {
  console.log('✅ Drawer inicializado');
  console.log('🔍 Estado actual del drawer:', drawerAbierto ? 'ABIERTO' : 'CERRADO');
}

// ============================================================
// LISTENER PARA CAMBIO DE BASE
// ============================================================
document.addEventListener('baseChanged', function(e) {
  console.log('🔄 Base cambiada a:', e.detail.base);
  if (moduloActual === 'cxp' && typeof validarBaseGT === 'function') {
    setTimeout(() => { console.log('🔄 Re-validando GT desde baseChanged'); validarBaseGT(); }, 500);
  }
});

// ============================================================
// FUNCIÓN DE COMPARACIÓN DE VERSIONES
// ============================================================
function compararVersiones(v1, v2) {
    if (!v1 || !v2) return 0;
    const p1 = v1.split('.').map(Number);
    const p2 = v2.split('.').map(Number);
    for (let i = 0; i < Math.max(p1.length, p2.length); i++) {
        const n1 = p1[i] || 0;
        const n2 = p2[i] || 0;
        if (n1 < n2) return -1;
        if (n1 > n2) return 1;
    }
    return 0;
}

// ============================================================
// NOTIFICACIÓN DE ACTUALIZACIÓN + AUTO-REINICIO
// ============================================================
// Flujo: pop-up -> el usuario confirma -> el backend descarga el diff firmado y
// aplica -> el backend relanza la app (proceso desprendido) -> acá se espera a
// que el servidor vuelva y se recarga con la versión nueva.
// ============================================================
let notificacionVisible = false;
let actualizacionEnCurso = false;

// "Más tarde" silencia esa versión SOLO durante esta sesión de navegador: al
// recargar (o al reiniciar la app) el aviso vuelve a aparecer.
const UPDATE_SNOOZE_KEY = 'admUpdateSnooze';

function _leerSnooze() {
    try {
        const raw = sessionStorage.getItem(UPDATE_SNOOZE_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
}

function _guardarSnooze(version) {
    try {
        sessionStorage.setItem(UPDATE_SNOOZE_KEY, JSON.stringify({
            version: version,
            hasta: Date.now() + (8 * 60 * 60 * 1000)
        }));
    } catch (e) {}
}

function _snoozeActivo(version) {
    const s = _leerSnooze();
    if (!s || s.version !== version) return false;
    return Date.now() < (s.hasta || 0);
}

function verificarNotificacion() {
    // Sin sesión (pantalla de login remoto) no consultar actualizaciones.
    try {
        const u = obtenerUsuarioActual();
        if (!u) return;
    } catch (e) { return; }
    if (actualizacionEnCurso) return;
    console.log('🔍 Verificando notificaciones de actualización...');
    fetch('/api/version')
        .then(r => r.json())
        .then(versionData => {
            const versionInstalada = versionData.version; // version.txt o VERSION
            fetch('/api/update/notification')
                .then(response => response.json())
                .then(data => {
                    if (data.has_update) {
                        const versionRemota = data.version || '0.0.0';
                        if (compararVersiones(versionInstalada, versionRemota) < 0) {
                            if (_snoozeActivo(versionRemota)) {
                                console.log('😴 Versión silenciada por "Más tarde":', versionRemota);
                                return;
                            }
                            console.log('📢 Nueva versión disponible:', versionRemota);
                            mostrarNotificacion(data);
                        } else {
                            console.log('✅ Ya tienes la versión más reciente instalada.');
                        }
                    } else {
                        console.log('✅ No hay actualizaciones pendientes');
                    }
                })
                .catch(error => console.log('⚠️ Error en /update/notification:', error));
        })
        .catch(error => console.log('⚠️ Error en /api/version:', error));
}

function mostrarNotificacion(data) {
    if (notificacionVisible || actualizacionEnCurso) return;
    document.getElementById('update-version').textContent = data.version || 'N/A';
    document.getElementById('update-date').textContent = data.release_date || 'N/A';
    const ul = document.getElementById('update-changelog');
    ul.innerHTML = '';
    if (data.changelog && data.changelog.length > 0) {
        data.changelog.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            ul.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.textContent = 'Actualización disponible';
        ul.appendChild(li);
    }
    // C5 - aviso informativo de frescura (no impide instalar)
    const avisoBox = document.getElementById('update-bloqueado');
    if (avisoBox) {
        if (data.aviso) {
            avisoBox.textContent = '⚠️ ' + data.aviso;
            avisoBox.style.display = 'block';
        } else {
            avisoBox.style.display = 'none';
        }
    }
    document.getElementById('update-notification').style.display = 'block';
    notificacionVisible = true;
}

function cerrarNotificacion() {
    const v = document.getElementById('update-version').textContent;
    if (v && v !== '-' && !actualizacionEnCurso) {
        _guardarSnooze(v);
        console.log('😴 Actualización silenciada hasta recargar:', v);
    }
    document.getElementById('update-notification').style.display = 'none';
    notificacionVisible = false;
}

// El aviso de frescura (C5) viaja como campo `aviso` del update y se muestra
// dentro del propio pop-up: no bloquea la instalación, que es la vía normal
// para llegar a la versión nueva.

function instalarActualizacion() {
    if (actualizacionEnCurso) return;
    console.log('🔄 Iniciando actualización...');
    actualizacionEnCurso = true;
    document.getElementById('update-progress').style.display = 'block';
    const btnActualizar = document.getElementById('btn-actualizar-ahora');
    const btnMasTarde = document.getElementById('btn-mas-tarde');
    if (btnActualizar) btnActualizar.disabled = true;
    if (btnMasTarde) btnMasTarde.disabled = true;
    actualizarProgreso(5, 'Iniciando actualización...');

    fetch('/api/update/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            actualizarProgreso(10, 'Descargando archivos...');
            pollEstadoActualizacion(data.version);
        } else {
            actualizacionEnCurso = false;
            actualizarProgreso(0, '❌ Error: ' + (data.message || 'Error desconocido'));
            if (btnActualizar) btnActualizar.disabled = false;
            if (btnMasTarde) btnMasTarde.disabled = false;
        }
    })
    .catch(error => {
        actualizacionEnCurso = false;
        actualizarProgreso(0, '❌ Error: ' + error.message);
        if (btnActualizar) btnActualizar.disabled = false;
        if (btnMasTarde) btnMasTarde.disabled = false;
    });
}

function pollEstadoActualizacion(versionEsperada) {
    const inicio = Date.now();
    const TIMEOUT_MS = 10 * 60 * 1000;
    const intervalo = setInterval(() => {
        fetch('/api/update/status', { cache: 'no-store' })
            .then(r => r.json())
            .then(estado => {
                const est = estado.estado;
                if (est === 'descargando' || est === 'instalando') {
                    const m = /(\d+)\s*\/\s*(\d+)/.exec(estado.mensaje || '');
                    let pct = (est === 'instalando') ? 90 : 35;
                    if (m) {
                        const hechos = parseInt(m[1], 10);
                        const total = parseInt(m[2], 10);
                        if (total > 0) pct = 15 + Math.round((hechos / total) * 70);
                    }
                    actualizarProgreso(pct, estado.mensaje || 'Actualizando...');
                    return;
                }
                if (est === 'reiniciando') {
                    clearInterval(intervalo);
                    actualizarProgreso(100, '✅ Instalada. Reiniciando la aplicación...');
                    try {
                        localStorage.setItem('lastUpdate', new Date().toISOString());
                    } catch (e) {}
                    esperarReinicio(estado.version || versionEsperada);
                    return;
                }
                if (est === 'completado') {
                    // Sin auto-reinicio (el relanzador no pudo lanzarse): avisar.
                    clearInterval(intervalo);
                    actualizacionEnCurso = false;
                    actualizarProgreso(100, '✅ Instalada. Reiniciá la aplicación para aplicarla.');
                    return;
                }
                if (est === 'error') {
                    clearInterval(intervalo);
                    actualizacionEnCurso = false;
                    actualizarProgreso(0, '❌ Error: ' + (estado.mensaje || estado.error || 'Falló la actualización'));
                    return;
                }
                if (Date.now() - inicio > TIMEOUT_MS) {
                    clearInterval(intervalo);
                    actualizacionEnCurso = false;
                    actualizarProgreso(0, '❌ Tiempo de espera agotado');
                }
            })
            .catch(() => {
                // El servidor ya se está reiniciando: el status deja de responder.
                // Se pasa a esperar el reinicio en vez de abortar.
                const est = document.getElementById('update-status').textContent || '';
                if (!/Reiniciando/i.test(est)) {
                    actualizarProgreso(95, 'Reiniciando la aplicación...');
                }
                clearInterval(intervalo);
                esperarReinicio(versionEsperada);
            });
    }, 1000);
}

// Espera a que el servidor vuelva con la versión nueva y recarga la página.
function esperarReinicio(versionEsperada) {
    const inicio = Date.now();
    const LIMITE_MS = 5 * 60 * 1000;
    let intentos = 0;
    const timer = setInterval(async () => {
        intentos += 1;
        const segundos = Math.round((Date.now() - inicio) / 1000);
        actualizarProgreso(100, `Reiniciando... esperando al servidor (${segundos}s)`);
        try {
            const r = await fetch('/api/version', { cache: 'no-store' });
            if (r.ok) {
                const data = await r.json();
                const v = data.version;
                if (!versionEsperada || compararVersiones(v, versionEsperada) >= 0) {
                    clearInterval(timer);
                    actualizarProgreso(100, `✅ Versión ${v} instalada. Recargando...`);
                    setTimeout(() => location.reload(), 1200);
                    return;
                }
                console.log(`⏳ El servidor responde ${v}, se esperaba ${versionEsperada}`);
            }
        } catch (e) {
            // todavía no volvió: seguir esperando
        }
        if (Date.now() - inicio > LIMITE_MS) {
            clearInterval(timer);
            actualizarEnProgresoError(
                'La aplicación no volvió a responder. Reiniciala desde el acceso directo.');
        }
    }, 2000);
}

function actualizarEnProgresoError(mensaje) {
    actualizacionEnCurso = false;
    actualizarProgreso(0, '⚠️ ' + mensaje);
}

function actualizarProgreso(porcentaje, mensaje) {
    const barra = document.getElementById('update-progress-bar');
    const estado = document.getElementById('update-status');
    if (barra) barra.style.width = porcentaje + '%';
    if (estado) estado.textContent = mensaje;
}

// ============================================================
// OBTENER DATOS DEL USUARIO ACTUAL
// ============================================================
async function cargarUsuarioActual() {
    try {
        console.log('👤 Cargando datos del usuario actual...');
        const response = await fetch('/api/auth/current_user');
        if (!response.ok) {
            // Sin sesión (401/403): limpiar cualquier 'user' viejo que haya
            // quedado en localStorage (evita arrancar como si hubiera sesión
            // y que init no muestre la pantalla de login).
            try { localStorage.removeItem('user'); sessionStorage.removeItem('user'); } catch (e) {}
            console.warn('⚠️ No se pudo obtener usuario actual');
            return null;
        }
        const data = await response.json();
        if (data.success && data.user) {
            localStorage.setItem('user', JSON.stringify(data.user));
            sessionStorage.setItem('user', JSON.stringify(data.user));
            console.log('✅ Usuario cargado:', data.user.username);
            console.log('   Rol:', data.user.rol);
            console.log('   es_superadmin:', data.user.es_superadmin);
            console.log('   Permisos:', data.user.permisos?.length || 0);
            const event = new CustomEvent('userLoaded', { detail: { user: data.user } });
            window.dispatchEvent(event);
            return data.user;
        }
        try { localStorage.removeItem('user'); sessionStorage.removeItem('user'); } catch (e) {}
        return null;
    } catch (error) {
        try { localStorage.removeItem('user'); sessionStorage.removeItem('user'); } catch (e) {}
        console.error('❌ Error cargando usuario:', error);
        return null;
    }
}

function esSuperAdmin() {
    try {
        const userData = JSON.parse(localStorage.getItem('user') || '{}');
        return userData.es_superadmin === true || userData.rol === 'superadmin';
    } catch { return false; }
}

function obtenerUsuarioActual() {
    try { return JSON.parse(localStorage.getItem('user') || 'null'); } catch { return null; }
}

// ============================================================
// C9 - PERMISOS EN LA UI (ocultar tabs/acciones sin permiso)
// ============================================================
// El backend (C4) sigue siendo la fuente de verdad: esto solo oculta la UI
// para no mostrar acciones que luego devolverían 403.
function tienePermisoC9(user, permiso) {
    if (!user) return false;
    if (user.es_superadmin) return true;
    var ps = user.permisos || [];
    if (ps.indexOf('*') >= 0) return true;
    return ps.indexOf(permiso) >= 0;
}

function aplicarPermisosUI(user) {
    if (!user) return;
    var superUser = !!user.es_superadmin;
    var permisos = user.permisos || [];
    var modulos = user.modulos_permitidos || [];

    // 1) Pestañas de módulos: se ocultan si el usuario no tiene NINGÚN permiso
    //    del módulo (permisos "stock.*", "cxp.*", etc. o modulos_permitidos).
    document.querySelectorAll('.module-tab[data-module]').forEach(function (btn) {
        var mod = btn.getAttribute('data-module');
        if (!mod || mod === 'dashboard') return;
        var tieneModulo = superUser
            || modulos.indexOf('*') >= 0
            || modulos.indexOf(mod) >= 0
            || permisos.some(function (p) { return p.indexOf(mod + '.') === 0; });
        if (!tieneModulo) btn.style.display = 'none';
    });

    // 2) Acciones puntuales marcadas con data-perm="modulo.accion"
    document.querySelectorAll('[data-perm]').forEach(function (el) {
        var perm = el.getAttribute('data-perm');
        if (!perm) return;
        if (!tienePermisoC9(user, perm)) el.style.display = 'none';
    });
}

// Re-aplica permisos cuando se agregan nodos dinámicos con data-perm
// (contenido renderizado por innerHTML después del login/cambio de módulo).
if (!window._obsPermisosUI) {
    window._obsPermisosUI = new MutationObserver(function () {
        if (!document.querySelector('[data-perm]')) return;
        var user = obtenerUsuarioActual();
        if (user) aplicarPermisosUI(user);
    });
    document.addEventListener('DOMContentLoaded', function () {
        window._obsPermisosUI.observe(document.body, { childList: true, subtree: true });
    });
}

// ============================================================
// C9 - DELEGACIÓN DE CLICKS SIN onclick INLINE (CSP fuerte)
// ============================================================
// Los elementos usan data-onclick con expresiones del estilo:
//   "funcion()" | "funcion('a', 2)" | "window.fn('x')"
//   | "this.closest('.x').remove()" | "document.getElementById('id').click()"
//   | "event.stopPropagation()" | varias separadas por ';'
// Parser propio con whitelist: NUNCA usa eval ni new Function.

function _partirArgumentos(raw) {
    // Divide por comas respetando comillas simples/dobles.
    var args = [];
    var actual = '';
    var comilla = null;
    for (var i = 0; i < raw.length; i++) {
        var c = raw[i];
        if (comilla) {
            actual += c;
            if (c === comilla) comilla = null;
        } else if (c === "'" || c === '"') {
            comilla = c;
            actual += c;
        } else if (c === ',') {
            args.push(actual.trim());
            actual = '';
        } else {
            actual += c;
        }
    }
    if (actual.trim() !== '') args.push(actual.trim());
    return args;
}

function _convertirArgumento(token, el, evento) {
    if (token === 'this') return el;
    if (token === 'event') return evento;
    var am = token.match(/^(['"])((?:\\.|(?!\1)[\s\S])*)\1$/);
    if (am) return am[2];
    if (/^-?\d+(\.\d+)?$/.test(token)) return Number(token);
    if (token === 'true') return true;
    if (token === 'false') return false;
    if (token === 'null') return null;
    return undefined; // no soportado -> se descarta la llamada
}

function _ejecutarDataOnclick(expr, el, evento) {
    expr.split(';').forEach(function (parteRaw) {
        var parte = parteRaw.trim();
        if (!parte) return;

        // "window.abrirX && window.abrirX(...)" -> ejecuta la 2da si existe
        var guard = parte.indexOf('&&');
        if (guard > -1) {
            var izquierda = parte.slice(0, guard).trim().replace(/^window\./, '');
            parte = parte.slice(guard + 2).trim().replace(/^window\./, '');
            if (typeof window[izquierda] !== 'function') return;
        }
        parte = parte.replace(/^window\./, '');

        // "if(event.key==='Enter') fn()" (teclado) -> solo si coincide la tecla
        var mEnter = parte.match(/^if\s*\(\s*event\.key\s*===\s*'([^']+)'\s*\)\s*([\s\S]*)$/);
        if (mEnter) {
            if (evento && evento.key === mEnter[1]) parte = mEnter[2].trim();
            else return;
        }

        // Acciones DOM concretas y seguras (sin código arbitrario)
        var mDoc = parte.match(/^document\.getElementById\(['"]([^'"]+)['"]\)\.(click|remove|focus)\(\)$/);
        if (mDoc) {
            var elDoc = document.getElementById(mDoc[1]);
            if (elDoc && typeof elDoc[mDoc[2]] === 'function') elDoc[mDoc[2]]();
            return;
        }
        var mClose = parte.match(/^this\.closest\(['"]([^'"]+)['"]\)\.remove\(\)$/);
        if (mClose) {
            var cerca = el.closest ? el.closest(mClose[1]) : null;
            if (cerca && cerca.remove) cerca.remove();
            return;
        }
        if (parte === 'this.remove()') {
            if (el.remove) el.remove();
            return;
        }
        if (parte === 'event.stopPropagation()') {
            if (evento && evento.stopPropagation) evento.stopPropagation();
            return;
        }

        // Llamada genérica a función global: fn() o fn(arg1, arg2, ...)
        var m = parte.match(/^([A-Za-z_$][\w$]*)\s*\(([^)]*)\)$/);
        if (!m) {
            console.warn('[data-onclick] sintaxis no soportada:', parte);
            return;
        }
        if (typeof window[m[1]] !== 'function') {
            console.warn('[data-onclick] función no encontrada:', m[1]);
            return;
        }
        var rawArgs = m[2].trim();
        var argVals = [];
        if (rawArgs !== '') {
            var tokens = _partirArgumentos(rawArgs);
            var invalido = false;
            tokens.forEach(function (tok) {
                var v = _convertirArgumento(tok, el, evento);
                if (v === undefined) {
                    console.warn('[data-onclick] argumento no soportado:', tok);
                    invalido = true;
                } else {
                    argVals.push(v);
                }
            });
            if (invalido) return;
        }
        window[m[1]].apply(null, argVals);
    });
}

document.addEventListener('click', function (event) {
    var origen = event.target;
    var el = origen && origen.closest ? origen.closest('[data-onclick]') : null;
    if (!el) return;
    var expr = (el.getAttribute('data-onclick') || '').trim();
    if (!expr) return;
    _ejecutarDataOnclick(expr, el, event);
}, true);

// Delegación genérica para los demás eventos inline convertidos a
// data-onchange / data-oninput / data-onkeydown (mismo motor, sin eval).
// Fase de CAPTURA: hay listeners propios (p. ej. .drawer-tab) que hacen
// stopPropagation en burbuja y romperían la delegación si fuera burbuja.
function _delegarEventoUI(tipoEvento, attr) {
    document.addEventListener(tipoEvento, function (evento) {
        var origen = evento.target;
        var el = origen && origen.closest ? origen.closest('[' + attr + ']') : null;
        if (!el) return;
        var expr = (el.getAttribute(attr) || '').trim();
        if (!expr) return;
        _ejecutarDataOnclick(expr, el, evento);
    }, true);
}
_delegarEventoUI('change', 'data-onchange');
_delegarEventoUI('input', 'data-oninput');
_delegarEventoUI('keydown', 'data-onkeydown');


// ============================================================
// INICIAR VERIFICACIÓN DE NOTIFICACIONES
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(cargarUsuarioActual, 500);
    setTimeout(verificarNotificacion, 5000);
    setInterval(verificarNotificacion, 300000);
});

// ============================================================

// ============================================================
// C9/export: descarga .xlsx generado por el backend (openpyxl)
// ============================================================
window.descargarXlsx = async function (archivo, hoja, columnas, filas) {
    try {
        const resp = await fetch('/api/reportes/exportar_xlsx', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ archivo: archivo, hoja: hoja, columnas: columnas, filas: filas })
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = archivo;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        if (typeof toastError === 'function') toastError('Error al exportar: ' + (e && e.message ? e.message : e), 'Reportes');
    }
};


// ============================================================
// LOGIN REMOTO (C4): pantalla cuando no hay sesión (acceso por red)
// ============================================================
function mostrarLoginUI() {
    const ov = document.getElementById('login-overlay');
    if (ov) ov.style.display = 'flex';
    const msg = document.getElementById('login-msg');
    if (msg) msg.textContent = '';
    const user = document.getElementById('login-user');
    if (user) { try { user.focus(); } catch (e) {} }
}

async function enviarLoginRemoto() {
    const user = document.getElementById('login-user');
    const pass = document.getElementById('login-pass');
    const msg = document.getElementById('login-msg');
    if (!user || !pass) return;
    if (!user.value.trim() || !pass.value) {
        if (msg) msg.textContent = 'Ingresá usuario y contraseña';
        return;
    }
    if (msg) msg.textContent = 'Verificando…';
    try {
        const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user.value.trim(), password: pass.value })
        });
        const data = await resp.json();
        if (resp.ok && data && data.success) {
            window.location.reload();
            return;
        }
        if (msg) msg.textContent = (data && data.error) ? String(data.error) : 'Credenciales inválidas';
    } catch (e) {
        if (msg) msg.textContent = 'Error de conexión';
    }
}

window.mostrarLoginUI = mostrarLoginUI;
window.enviarLoginRemoto = enviarLoginRemoto;

// EXPORTAR FUNCIONES GLOBALES
// ============================================================
window.showToast = showToast;
window.toastSuccess = toastSuccess;
window.toastError = toastError;
window.toastWarning = toastWarning;
window.toastInfo = toastInfo;
window.cambiarModulo = cambiarModulo;
window.openDrawer = openDrawer;
window.closeDrawer = closeDrawer;
window.toggleDrawer = toggleDrawer;
window.toggleBasePicker = toggleBasePicker;
window.toggleSociedadPicker = toggleSociedadPicker;
window.seleccionarBase = seleccionarBase;
window.seleccionarSociedad = seleccionarSociedad;
window.actualizarApp = actualizarApp;
window.actualizarIndicadorBase = actualizarIndicadorBase;
window.cargarSelectsStock = cargarSelectsStock;
window.aplicarSelectsStockDOM = aplicarSelectsStockDOM;
window.baseActiva = baseActiva;
window.sociedadActiva = sociedadActiva;
window.BASES_DISPONIBLES_FRONT = BASES_DISPONIBLES_FRONT;
window.inicializarBase = inicializarBase;
window.inicializarDrawer = inicializarDrawer;
// Getter vivo: el snapshot booleano al cargar app.js siempre era `false` y los
// consumidores (templates.js/stock index.js) decidían mal si re-aplicar o no.
Object.defineProperty(window, 'stockSelectsCargados', { configurable: true, get() { return stockSelectsCargados; } });
window.cargandoSelects = cargandoSelects;
window.verificarNotificacion = verificarNotificacion;
window.mostrarNotificacion = mostrarNotificacion;
window.cerrarNotificacion = cerrarNotificacion;
window.instalarActualizacion = instalarActualizacion;
window.actualizarProgreso = actualizarProgreso;
window.sanitizarHTML = sanitizarHTML;
window.sanitizarAtributo = sanitizarAtributo;
window.cargarUsuarioActual = cargarUsuarioActual;
window.esSuperAdmin = esSuperAdmin;
window.obtenerUsuarioActual = obtenerUsuarioActual;
window.tienePermisoC9 = tienePermisoC9;
window.aplicarPermisosUI = aplicarPermisosUI;
window.cargarCXPInicial = cargarCXPInicial;

console.log('✅ app.js cargado correctamente (XSS sanitizado)');
console.log('📂 Estructura: frontend/modules/');
console.log('🔍 stockSelectsCargados:', stockSelectsCargados);
console.log('✅ Sistema de notificaciones de actualización activo');
console.log('✅ Funciones de usuario disponibles');
console.log('✅ Gestión de versiones en localStorage implementada');
console.log('✅ Siglas de países disponibles globalmente (cargadas desde paises.js)');