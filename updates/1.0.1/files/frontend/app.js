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

// 🔴 Control para evitar ejecuciones múltiples
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
  if (drawerAbierto) {
    console.log('📂 Drawer ya está abierto');
    return;
  }
  console.log('📂 Abriendo drawer...');
  
  document.querySelectorAll('.drawer-module').forEach(m => {
    m.style.display = m.dataset.module === moduloActual ? '' : 'none';
  });
  
  const drawer = document.getElementById('drawer');
  const overlay = document.getElementById('drawer-overlay');
  
  if (drawer) {
    drawer.classList.add('open');
    drawerAbierto = true;
    console.log('✅ Drawer abierto');
  }
  if (overlay) overlay.classList.add('open');
}

function closeDrawer() {
  if (!drawerAbierto) {
    console.log('📂 Drawer ya está cerrado');
    return;
  }
  console.log('📂 Cerrando drawer...');
  
  const drawer = document.getElementById('drawer');
  const overlay = document.getElementById('drawer-overlay');
  
  if (drawer) {
    drawer.classList.remove('open');
    drawerAbierto = false;
    console.log('✅ Drawer cerrado');
  }
  if (overlay) overlay.classList.remove('open');
}

function toggleDrawer() {
  if (drawerAbierto) {
    closeDrawer();
  } else {
    openDrawer();
  }
}

// Inicializar drawer
const drawerClose = document.getElementById('drawer-close');
if (drawerClose) {
  drawerClose.addEventListener('click', (e) => {
    e.stopPropagation();
    closeDrawer();
  });
}

const drawerOverlay = document.getElementById('drawer-overlay');
if (drawerOverlay) {
  drawerOverlay.addEventListener('click', (e) => {
    e.stopPropagation();
    closeDrawer();
  });
}

// ============================================================
// DRAWER - TABS Y SUBTABS (CON PERSISTENCIA DE SECCIÓN DE STOCK)
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
    if (titulo) {
      titulo.textContent = tab.textContent;
      titulo.style.display = 'block';
    }
    
    const msg = document.getElementById('msg');
    if (msg) msg.innerHTML = '';
    
    const container = document.querySelector('.container');
    if (container) {
      container.classList.toggle('wide', tab.dataset.tab === 'stock-consolidado');
    }
    
    if (moduloActual === 'stock' && typeof navegarStock === 'function') {
      // 🔴 GUARDAR LA SECCIÓN SELECCIONADA EN localStorage
      try {
        localStorage.setItem('ultimaSeccionStock', tab.dataset.tab);
      } catch (e) { /* silencioso */ }
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
    if (titulo && tabPadre) {
      titulo.textContent = tabPadre.textContent;
      titulo.style.display = 'block';
    }
    
    const container = document.querySelector('.container');
    if (container) container.classList.remove('wide');
    
    if (moduloActual === 'stock' && tabPadre && typeof navegarStock === 'function') {
      // 🔴 GUARDAR LA SECCIÓN SELECCIONADA EN localStorage (subitem)
      try {
        localStorage.setItem('ultimaSeccionStock', tabPadre.dataset.tab);
      } catch (e) { /* silencioso */ }
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
  if (!baseInfo) {
    console.warn('Base no encontrada:', baseActiva);
    return;
  }
  
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
      return `<button class="base-opt${b.codigo === baseActiva ? ' active' : ''}" onclick="seleccionarBase('${codigo}')">
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
      if (!soc) {
        soc = baseInfo.sociedades[0];
        sociedadActiva = soc.codigo;
        window.sociedadActiva = sociedadActiva;
      }
      const socLabel = document.getElementById("sociedad-btn-label");
      if (socLabel) socLabel.textContent = soc.label;
      
      const socDropdown = document.getElementById("sociedad-dropdown");
      if (socDropdown) {
        socDropdown.innerHTML = baseInfo.sociedades.map(s => {
          const codigo = escapeHTML(s.codigo);
          const label = escapeHTML(s.label);
          return `<button class="base-opt${s.codigo === sociedadActiva ? ' active' : ''}" onclick="seleccionarSociedad('${codigo}')">
            ${label}
            <span class="check">✓</span>
          </button>`;
        }).join("");
      }
    } else {
      socPicker.style.display = "none";
    }
  }
}

function toggleBasePicker() {
  const dd = document.getElementById("base-dropdown");
  const ddSoc = document.getElementById("sociedad-dropdown");
  if (ddSoc) ddSoc.style.display = "none";
  if (dd) {
    dd.style.display = dd.style.display === "block" ? "none" : "block";
  }
}

function toggleSociedadPicker() {
  const dd = document.getElementById("sociedad-dropdown");
  const ddBase = document.getElementById("base-dropdown");
  if (ddBase) ddBase.style.display = "none";
  if (dd) {
    dd.style.display = dd.style.display === "block" ? "none" : "block";
  }
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
  sociedadActiva = baseInfo && baseInfo.sociedades && baseInfo.sociedades.length > 0 
    ? baseInfo.sociedades[0].codigo 
    : null;
  
  window.baseActiva = baseActiva;
  window.sociedadActiva = sociedadActiva;
  
  actualizarIndicadorBase();
  await cargarSelectsStock();
  
  const event = new CustomEvent('baseChanged', { detail: { base: baseActiva } });
  window.dispatchEvent(event);
  
  // 🔴 Eliminada la llamada a ejecutarReporte (ahora manejada en index.js)
  
  if (moduloActual === 'cxp' && typeof validarBaseGT === 'function') {
    setTimeout(() => {
      console.log('🔄 Re-validando GT desde seleccionarBase');
      validarBaseGT();
    }, 500);
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
  
  // 🔴 Eliminada la llamada a ejecutarReporte
}

// ============================================================
// STOCK - SELECTS
// ============================================================
async function cargarSelectsStock() {
  if (stockSelectsCargados) {
    console.log('ℹ️ Selects de stock ya cargados, omitiendo...');
    return;
  }
  
  if (cargandoSelects) {
    console.log('⏳ Selects de stock cargándose, esperando...');
    let espera = 0;
    while (cargandoSelects && espera < 50) {
      await new Promise(r => setTimeout(r, 100));
      espera++;
    }
    if (stockSelectsCargados) {
      console.log('✅ Selects cargados durante la espera');
      return;
    }
  }
  
  cargandoSelects = true;
  
  try {
    console.log('📦 Cargando selects de stock...');
    
    console.log('📡 Fetching /api/articulos...');
    const articulosRes = await fetch(`${API}/articulos`);
    if (!articulosRes.ok) {
      const text = await articulosRes.text();
      console.error('❌ Error en /api/articulos:', text.substring(0, 200));
      throw new Error(`Error ${articulosRes.status}`);
    }
    articulosCache = await articulosRes.json();
    console.log(`✅ ${articulosCache.length} artículos cargados`);
    
    const _sortCodigo = cod => { try { return (cod||"").split(".").map(Number); } catch(e) { return [0]; } };
    articulosCache.sort((a,b)=>{const ka=_sortCodigo(a.codigo),kb=_sortCodigo(b.codigo);for(let i=0;i<Math.max(ka.length,kb.length);i++){const d=(ka[i]||0)-(kb[i]||0);if(d!==0)return d;}return 0;});
    
    console.log('📡 Fetching /api/depositos...');
    const depositosRes = await fetch(`${API}/depositos`);
    if (!depositosRes.ok) {
      const text = await depositosRes.text();
      console.error('❌ Error en /api/depositos:', text.substring(0, 200));
      throw new Error(`Error ${depositosRes.status}`);
    }
    depositosCache = await depositosRes.json();
    console.log(`✅ ${depositosCache.length} depósitos cargados`);
    
    console.log('📡 Fetching /api/categorias...');
    categoriasCache = await fetch(`${API}/categorias`).then(r => r.json());
    console.log(`✅ ${categoriasCache.length} categorías cargadas`);

    // ✅ CORREGIDO: Sanitizar datos de API
    const artOptions = articulosCache.map(a => {
      const id = escapeHTML(a.id);
      const codigo = escapeHTML(a.codigo);
      const nombre = escapeHTML(a.nombre);
      const partidas = escapeHTML(a.con_partidas);
      return `<option value="${id}" data-partidas="${partidas}">${codigo} - ${nombre}</option>`;
    }).join("");
    
    const depOptions = depositosCache.map(d => {
      const id = escapeHTML(d.id);
      const nombre = escapeHTML(d.nombre);
      return `<option value="${id}">${id} - ${nombre}</option>`;
    }).join("");
    
    const catOptions = categoriasCache.map(c => {
      const codigo = escapeHTML(c.codigo);
      const nombre = escapeHTML(c.nombre);
      const defaultVal = escapeHTML(c.con_partidas_default);
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
      artModBuscar.innerHTML = `<option value="">Elegí un artículo...</option>` + 
        articulosCache.map(a => {
          const id = escapeHTML(a.id);
          const codigo = escapeHTML(a.codigo);
          const nombre = escapeHTML(a.nombre);
          return `<option value="${id}">${codigo} - ${nombre}</option>`;
        }).join("");
    }
    
    const depModBuscar = document.getElementById("dep-mod-buscar");
    if (depModBuscar) {
      depModBuscar.innerHTML = `<option value="">Elegí un depósito...</option>` + 
        depositosCache.map(d => {
          const id = escapeHTML(d.id);
          const nombre = escapeHTML(d.nombre);
          return `<option value="${id}">${id} - ${nombre}</option>`;
        }).join("");
    }

    const aeGrid = document.getElementById("ae-grid");
    const asGrid = document.getElementById("as-grid");
    const trmGrid = document.getElementById("trm-grid");
    
    if (aeGrid && typeof agregarFila === 'function') {
      agregarFila("ae");
    }
    if (asGrid && typeof agregarFila === 'function') {
      agregarFila("as");
    }
    if (trmGrid && typeof agregarFila === 'function') {
      agregarFila("trm");
    }
    
    const artCategoria = document.getElementById("art-categoria");
    if (artCategoria && typeof aplicarDefaultPartidas === 'function') {
      aplicarDefaultPartidas();
    }
    
    const seCompra = document.getElementById("art-se-compra");
    if (seCompra && typeof actualizarCamposOrigen === 'function') {
      actualizarCamposOrigen();
    }
    
    stockSelectsCargados = true;
    console.log('✅ Selects de stock cargados correctamente');
    
  } catch (e) {
    console.error('❌ Error cargando selects de stock:', e);
    const msg = document.getElementById('msg');
    if (msg) {
      msg.innerHTML = `<div class="msg error">⚠️ Error al cargar datos de stock: ${escapeHTML(e.message)}</div>`;
    }
  } finally {
    cargandoSelects = false;
  }
}

// ============================================================
// ACTUALIZACIÓN AUTOMÁTICA
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
  } catch (e) { /* silencioso */ }
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

  const icons = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  };

  const titles = {
    success: 'Éxito',
    error: 'Error',
    warning: 'Advertencia',
    info: 'Información'
  };

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
    <div class="toast-content">
      <div class="toast-title">${escapeHTML(title || titles[type] || 'Información')}</div>
      <div class="toast-message">${escapeHTML(message)}</div>
    </div>
    <button class="toast-close" onclick="this.closest('.toast').remove()">✕</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('hiding');
    setTimeout(() => {
      if (toast.parentNode) toast.remove();
    }, 300);
  }, duration);

  return toast;
}

function toastSuccess(message, title = 'Éxito') {
  showToast(message, 'success', title);
}

function toastError(message, title = 'Error') {
  showToast(message, 'error', title);
}

function toastWarning(message, title = 'Advertencia') {
  showToast(message, 'warning', title);
}

function toastInfo(message, title = 'Información') {
  showToast(message, 'info', title);
}

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
    setTimeout(() => {
      console.log('🔄 Re-validando GT desde baseChanged');
      validarBaseGT();
    }, 500);
  }
});

// ============================================================
// 🆕 FUNCIÓN DE COMPARACIÓN DE VERSIONES
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
// NOTIFICACIÓN DE ACTUALIZACIÓN (TIEMPO REAL) - CORREGIDA
// ============================================================

let notificacionVisible = false;

function verificarNotificacion() {
    console.log('🔍 Verificando notificaciones de actualización...');
    
    const versionInstalada = localStorage.getItem('appVersion');
    
    fetch('/api/update/notification')
        .then(response => response.json())
        .then(data => {
            if (data.has_update) {
                const versionRemota = data.version || '0.0.0';
                if (!versionInstalada || compararVersiones(versionInstalada, versionRemota) < 0) {
                    console.log('📢 Nueva versión disponible:', data.version);
                    mostrarNotificacion(data);
                } else {
                    console.log('✅ Ya tienes la versión más reciente instalada.');
                }
            } else {
                console.log('✅ No hay actualizaciones pendientes');
            }
        })
        .catch(error => {
            console.log('⚠️ Error verificando notificaciones:', error);
        });
}

function mostrarNotificacion(data) {
    if (notificacionVisible) return;
    
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
    
    document.getElementById('update-notification').style.display = 'block';
    notificacionVisible = true;
}

function cerrarNotificacion() {
    document.getElementById('update-notification').style.display = 'none';
    notificacionVisible = false;
}

function instalarActualizacion() {
    console.log('🔄 Iniciando actualización...');
    
    document.getElementById('update-progress').style.display = 'block';
    const btnActualizar = document.querySelector('#update-notification button:first-child');
    const btnMasTarde = document.querySelector('#update-notification button:last-child');
    if (btnActualizar) btnActualizar.disabled = true;
    if (btnMasTarde) btnMasTarde.disabled = true;
    
    actualizarProgreso(10, 'Iniciando actualización...');
    
    fetch('/api/update/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            actualizarProgreso(15, 'Descargando archivos...');
            pollEstadoActualizacion(data.version);
        } else {
            actualizarProgreso(0, '❌ Error: ' + (data.message || 'Error desconocido'));
            if (btnActualizar) btnActualizar.disabled = false;
            if (btnMasTarde) btnMasTarde.disabled = false;
        }
    })
    .catch(error => {
        actualizarProgreso(0, '❌ Error: ' + error.message);
        if (btnActualizar) btnActualizar.disabled = false;
        if (btnMasTarde) btnMasTarde.disabled = false;
    });
}

function pollEstadoActualizacion(versionEsperada) {
    const btnActualizar = document.querySelector('#update-notification button:first-child');
    const btnMasTarde = document.querySelector('#update-notification button:last-child');
    const inicio = Date.now();
    const TIMEOUT_MS = 5 * 60 * 1000;

    const intervalo = setInterval(() => {
        fetch('/api/update/status')
            .then(r => r.json())
            .then(estado => {
                if (estado.estado === 'descargando' || estado.estado === 'instalando') {
                    const pct = estado.estado === 'instalando' ? 90 : 50;
                    actualizarProgreso(pct, estado.mensaje || 'Actualizando...');
                    return;
                }

                if (estado.estado === 'completado') {
                    clearInterval(intervalo);
                    actualizarProgreso(100, '✅ ¡Actualización completada! Reiniciando...');
                    const nuevaVersion = estado.version || versionEsperada || '1.0.1';
                    localStorage.setItem('appVersion', nuevaVersion);
                    localStorage.setItem('lastUpdate', new Date().toISOString());
                    fetch('/api/reiniciar', { method: 'POST' }).catch(() => {});
                    setTimeout(() => location.reload(), 6000);
                    return;
                }

                if (estado.estado === 'error') {
                    clearInterval(intervalo);
                    actualizarProgreso(0, '❌ Error: ' + (estado.mensaje || estado.error || 'Falló la actualización'));
                    if (btnActualizar) btnActualizar.disabled = false;
                    if (btnMasTarde) btnMasTarde.disabled = false;
                    return;
                }

                if (Date.now() - inicio > TIMEOUT_MS) {
                    clearInterval(intervalo);
                    actualizarProgreso(0, '❌ Tiempo de espera agotado');
                    if (btnActualizar) btnActualizar.disabled = false;
                    if (btnMasTarde) btnMasTarde.disabled = false;
                }
            })
            .catch(() => { /* silencioso, reintenta */ });
    }, 1000);
}

function actualizarProgreso(porcentaje, mensaje) {
    document.getElementById('update-progress-bar').style.width = porcentaje + '%';
    document.getElementById('update-status').textContent = mensaje;
}

// ============================================================
// 🆕 OBTENER DATOS DEL USUARIO ACTUAL
// ============================================================

async function cargarUsuarioActual() {
    try {
        console.log('👤 Cargando datos del usuario actual...');
        const response = await fetch('/api/auth/current_user');
        if (!response.ok) {
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
        return null;
    } catch (error) {
        console.error('❌ Error cargando usuario:', error);
        return null;
    }
}

function esSuperAdmin() {
    try {
        const userData = JSON.parse(localStorage.getItem('user') || '{}');
        return userData.es_superadmin === true || userData.rol === 'superadmin';
    } catch {
        return false;
    }
}

function obtenerUsuarioActual() {
    try {
        return JSON.parse(localStorage.getItem('user') || 'null');
    } catch {
        return null;
    }
}

// ============================================================
// INICIAR VERIFICACIÓN DE NOTIFICACIONES
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(cargarUsuarioActual, 500);
    setTimeout(verificarNotificacion, 5000);
    setInterval(verificarNotificacion, 300000);
});

// ============================================================
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
window.baseActiva = baseActiva;
window.sociedadActiva = sociedadActiva;
window.BASES_DISPONIBLES_FRONT = BASES_DISPONIBLES_FRONT;
window.inicializarBase = inicializarBase;
window.inicializarDrawer = inicializarDrawer;
window.stockSelectsCargados = stockSelectsCargados;
window.cargandoSelects = cargandoSelects;

window.verificarNotificacion = verificarNotificacion;
window.mostrarNotificacion = mostrarNotificacion;
window.cerrarNotificacion = cerrarNotificacion;
window.instalarActualizacion = instalarActualizacion;
window.actualizarProgreso = actualizarProgreso;

window.sanitizarHTML = sanitizarHTML;
window.sanitizarAtributo = sanitizarAtributo;
window.escapeHTML = escapeHTML;

window.cargarUsuarioActual = cargarUsuarioActual;
window.esSuperAdmin = esSuperAdmin;
window.obtenerUsuarioActual = obtenerUsuarioActual;
window.cargarCXPInicial = cargarCXPInicial;

console.log('✅ app.js cargado correctamente (XSS sanitizado)');
console.log('📂 Estructura: frontend/modules/');
console.log('🔍 stockSelectsCargados:', stockSelectsCargados);
console.log('✅ Sistema de notificaciones de actualización activo');
console.log('✅ Funciones de usuario disponibles');
console.log('✅ Gestión de versiones en localStorage implementada');
console.log('✅ Siglas de países disponibles globalmente (cargadas desde paises.js)');