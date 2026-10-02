// ============================================================
// ADMIN - INICIALIZACIÓN, NAVEGACIÓN Y HELPERS COMPARTIDOS
// ============================================================
// El módulo se llama `admin` a propósito: los permisos del panel son `admin.*`
// y el gate explícito de `aplicarPermisosUI` exige `admin.acceso` (spec §4.1).

var ADMIN_VISTAS = ['admin-usuarios', 'admin-roles', 'admin-estado',
                    'admin-auditoria', 'admin-accesos', 'admin-diagnostico'];
var ADMIN_CARGADORES = {
  'admin-usuarios': 'cargarVistaUsuariosAdmin',
  'admin-roles': 'cargarVistaRolesAdmin',
  'admin-estado': 'cargarVistaEstadoAdmin',
  'admin-auditoria': 'cargarVistaAuditoriaAdmin',
  'admin-accesos': 'cargarVistaAccesosAdmin',
  'admin-diagnostico': 'cargarVistaDiagnosticoAdmin'
};
var _adminEstado = null;

// --- ciclo de vida ---------------------------------------------------------

function inicializarAdmin() {
  console.log('⚙️ Inicializando panel de administración...');
  refrescarChipAdmin();
  navegarAdmin('admin-usuarios');
  if (typeof closeDrawer === 'function') setTimeout(closeDrawer, 200);
}

// Cambia la vista VISIBLE del panel: mueve el `.active` de las `.section` de
// `#module-content` y del tab del drawer, con el mismo criterio que el handler
// del drawer de app.js. Hace falta porque el CSS del panel oculta todas las
// `.section` menos la `.active` (admin.css) y hasta ahora quien la movía era
// SÓLO ese handler: navegar por código (p. ej. el "Dar de alta" de la vista
// Accesos rechazados) pintaba la vista dentro de una sección oculta.
//
// El resaltado se toca SOLO dentro del bloque del propio módulo
// (`.drawer-module[data-module="admin"]`): antes se quitaba el `.active` de
// TODOS los `.drawer-tab` del documento y CxP —que confía en la clase
// declarativa de index.html y nunca la re-agrega— quedaba sin resaltar el resto
// de la sesión. Stock y Reportes se salvan porque la restauran al navegar.
//
// NO carga nada: la vista que necesite controlar la carga (una sola, no dos)
// llama a esto directo en vez de pasar por `navegarAdmin`.
function mostrarVistaAdmin(vista) {
  var destino = document.getElementById(vista);
  if (!destino) return;          // el template del panel no está montado: nada que mostrar
  var cont = document.getElementById('module-content');
  var secciones = (cont || document).querySelectorAll('.section');
  secciones.forEach(function (s) { s.classList.remove('active'); });
  destino.classList.add('active');
  var drawer = document.querySelector('.drawer-module[data-module="admin"]');
  if (drawer) {
    drawer.querySelectorAll('.drawer-tab').forEach(function (t) {
      if (t.getAttribute('data-tab') === vista) t.classList.add('active');
      else t.classList.remove('active');
    });
  }
}

function navegarAdmin(vista) {
  if (ADMIN_VISTAS.indexOf(vista) < 0) vista = 'admin-usuarios';
  // También al navegar entre vistas: §10 promete que el chip se refresca con la
  // navegación y el modo lectura (§7) viaja con él (`pintarChipAdmin`).
  refrescarChipAdmin();
  mostrarVistaAdmin(vista);
  var cargador = ADMIN_CARGADORES[vista];
  if (cargador && typeof window[cargador] === 'function') {
    window[cargador]();
  } else {
    adminAviso(vista, 'Esta vista todavía no está disponible en esta versión.');
  }
}

function adminEstadoActual() { return _adminEstado; }

// spec §7: en `degradado` el panel queda en SOLO LECTURA y el motivo va en el
// `title` de cada botón de escritura. En `local` NO se bloquea nada: sin
// almacén central escribir es legítimo (los cambios quedan en esta PC), y en
// `central`/`desconocido` tampoco. Es REVERSIBLE: al salir de `degradado` los
// botones se vuelven a habilitar y se les limpia el `title`. Sin argumento usa
// el último estado conocido (`adminEstadoActual()`).
function adminAplicarModoLectura(modo) {
  if (modo === undefined || modo === null) {
    var estado = adminEstadoActual() || {};
    modo = estado.modo;
  }
  var cont = document.getElementById('module-content');
  if (!cont) return;
  var bloqueado = modo === 'degradado';
  cont.querySelectorAll('button[data-perm]').forEach(function (b) {
    b.disabled = bloqueado;
    if (bloqueado) b.title = ADMIN_BANNER_TEXTO.degradado;
    else b.removeAttribute('title');
  });
}

// --- chip de estado y banner (spec §5.3 y §7) ------------------------------

var ADMIN_CHIP_CLASES = { central: 'admin-chip-ok', degradado: 'admin-chip-warn',
                          local: 'admin-chip-gris', desconocido: 'admin-chip-gris' };
var ADMIN_CHIP_TEXTO = { central: 'Almacén central', degradado: 'Almacén degradado',
                         local: 'Sin almacén (local)', desconocido: 'Estado desconocido' };
var ADMIN_BANNER_TEXTO = {
  degradado: 'El almacén no está disponible: se usa la última copia buena y no se puede guardar.',
  local: 'Esta PC no usa el almacén central: los cambios quedan solo acá.',
  desconocido: 'No se pudo consultar el estado del almacén central.'
};

async function refrescarChipAdmin() {
  var r = await adminFetch('/api/admin/config/estado');
  if (!r.ok) { pintarChipAdmin('desconocido', { mensaje: r.error }); return; }
  _adminEstado = r.datos;
  pintarChipAdmin(r.datos.modo, r.datos);
}

function pintarChipAdmin(modo, estado) {
  estado = estado || {};
  var chip = document.getElementById('admin-chip');
  var banner = document.getElementById('admin-banner');
  if (chip) {
    chip.className = 'admin-chip ' + (ADMIN_CHIP_CLASES[modo] || 'admin-chip-gris');
    var detalle = '';
    if (estado.ruta) detalle += ' · ' + estado.ruta;
    if (estado.sello) detalle += ' · sello ' + String(estado.sello).slice(0, 8);
    chip.textContent = (ADMIN_CHIP_TEXTO[modo] || modo || 'Estado desconocido') + detalle;
  }
  // §7: el modo lectura viaja con el chip (entrada al panel, vista Estado y
  // cada refresco por 503). Va ANTES del `return` del banner: el modo lectura no
  // depende de que el banner exista en el DOM.
  adminAplicarModoLectura(modo);
  if (!banner) return;
  if (modo === 'central') { banner.style.display = 'none'; return; }
  banner.style.display = 'block';
  banner.textContent = estado.mensaje || ADMIN_BANNER_TEXTO[modo] ||
                       ADMIN_BANNER_TEXTO.desconocido;
}

// --- helpers de render -----------------------------------------------------
// Regla: TODO lo que entra al innerHTML sale escapado con escapeHTML()
// (frontend/modules/shared/seguridad.js). La única excepción es explícita y
// deliberada: una celda `{html: '...'}` es HTML que la vista ya armó pasando
// sus datos por escapeHTML() (chips, botones). Nunca al revés: el default es
// escapar.

function adminBody(vista) {
  var id = (vista.indexOf('admin-') === 0 ? vista : 'admin-' + vista) + '-body';
  return document.getElementById(id);
}

function adminAviso(vista, mensaje, tipo) {
  var body = adminBody(vista);
  if (!body) return;
  body.innerHTML = '<div class="admin-aviso admin-aviso-' + (tipo || 'info') + '">' +
                   escapeHTML(mensaje) + '</div>';
}

function adminTabla(columnas, filas, idTabla) {
  // Celda: `{html: '...'}` = HTML deliberado de la vista (ya escapado por ella);
  // cualquier otra cosa se escapa acá. null/undefined → '' en vez del literal
  // "null" que daría String().
  function celdaHTML(celda) {
    if (celda !== null && typeof celda === 'object' && 'html' in celda) {
      return celda.html === null || celda.html === undefined ? '' : String(celda.html);
    }
    return escapeHTML(celda === null || celda === undefined ? '' : String(celda));
  }
  var html = '<table class="admin-tabla"' + (idTabla ? ' id="' + idTabla + '"' : '') +
             '><thead><tr>';
  columnas.forEach(function (c) { html += '<th>' + escapeHTML(c) + '</th>'; });
  html += '</tr></thead><tbody>';
  if (!filas.length) {
    html += '<tr><td class="admin-vacio" colspan="' + columnas.length + '">Sin datos</td></tr>';
  } else {
    filas.forEach(function (fila) {
      html += '<tr>';
      fila.forEach(function (celda) { html += '<td>' + celdaHTML(celda) + '</td>'; });
      html += '</tr>';
    });
  }
  return html + '</tbody></table>';
}

function adminBoton(texto, onclick, clase, permiso, tooltip) {
  return '<button class="admin-btn ' + (clase || '') + '"' +
         (permiso ? ' data-perm="' + permiso + '"' : '') +
         (tooltip ? ' data-tooltip="' + escapeHTML(tooltip) + '"' : '') +
         ' data-onclick="' + onclick + '">' + escapeHTML(texto) + '</button>';
}

function adminBotonAccion(texto, accion, dato, clase, permiso, tooltip) {
  return '<button class="admin-btn ' + (clase || '') + '"' +
         (permiso ? ' data-perm="' + permiso + '"' : '') +
         (tooltip ? ' data-tooltip="' + escapeHTML(tooltip) + '"' : '') +
         ' data-admin-accion="' + escapeHTML(accion) + '"' +
         (dato === undefined || dato === null ? ''
            : ' data-admin-dato="' + escapeHTML(dato) + '"') +
         '>' + escapeHTML(texto) + '</button>';
}

// Normaliza el catálogo de permisos al shape que consume `adminMulti`.
// El backend devuelve `{valor, descripcion, verificado}`; si llegara un string
// suelto (catálogo viejo), se arma el objeto igual y no se rompe el panel.
function adminNormalizarPermisos(grupos) {
  var salida = {};
  Object.keys(grupos || {}).forEach(function (grupo) {
    salida[grupo] = (grupos[grupo] || []).map(function (p) {
      if (p && typeof p === 'object') {
        return {
          valor: p.valor,
          etiqueta: p.etiqueta || p.valor,
          descripcion: p.descripcion || '',
          verificado: p.verificado !== false
        };
      }
      return { valor: String(p), etiqueta: String(p), descripcion: '', verificado: true };
    });
  });
  return salida;
}

function adminMulti(nombre, items, seleccionados, opciones) {
  seleccionados = seleccionados || [];
  opciones = opciones || {};
  var html = '';

  // Ayuda contextual opcional por lista (`opciones.tooltip` = clave del catálogo
  // de `shared/tooltips.js`). Sin clave no se agrega nada.
  var attrTooltip = opciones.tooltip
    ? ' data-tooltip="' + escapeHTML(opciones.tooltip) + '"' : '';

  // Check "todos" (comodín '*'): prende/apaga el resto. Se pinta primero y es el
  // único camino para activar `'*'` desde la UI — antes sólo se mostraba si el
  // valor ya venía en los datos, así que no había forma de darlo de alta.
  // El texto va en un <span>: como nodo suelto, la etiqueta no lo alcanzaba con
  // el layout de la tarjeta y quedaba centrado en medio de la fila.
  if (opciones.comodin) {
    var marcadoComodin = seleccionados.indexOf('*') >= 0;
    html += '<label class="admin-check admin-check-todos"><input type="checkbox"' +
            ' data-admin-todos="' + escapeHTML(nombre) + '"' + attrTooltip +
            (marcadoComodin ? ' checked' : '') + '>' +
            '<span>' + escapeHTML(opciones.comodin) + '</span></label>';
  }

  items.forEach(function (item) {
    var valor = (item && item.valor !== undefined) ? item.valor : item;
    var etiqueta = (item && item.etiqueta !== undefined) ? item.etiqueta : valor;
    var descripcion = (item && item.descripcion !== undefined) ? item.descripcion : '';
    // `verificado === false` = el backend no verifica este permiso hoy: se
    // atenúa la tarjeta y se le pone la insignia, para no documentar como real
    // algo que no controla nada.
    var sinEfecto = (item && item.verificado === false);
    var tildado = seleccionados.indexOf(valor) >= 0 ? ' checked' : '';
    var titulo = descripcion ? descripcion
      : (sinEfecto ? 'Este permiso todavía no controla nada en el sistema.' : '');
    // Tres líneas: nombre (identificador), descripción y, al pie, el identificador
    // crudo (para cruzarlo con la API y los logs) con la insignia aparte.
    var desc = (descripcion && descripcion !== etiqueta)
      ? '<span class="admin-check-desc">' + escapeHTML(descripcion) + '</span>'
      : '';
    var badge = sinEfecto ? '<span class="admin-check-badge">sin efecto todavía</span>' : '';
    // El `title` nativo se mantiene siempre; el ícono ⓘ con la ayuda extendida
    // solo cuando la lista trae una clave de tooltip.
    html += '<label class="admin-check' + (sinEfecto ? ' admin-check-gris' : '') + '"' +
            (titulo ? ' title="' + escapeHTML(titulo) + '"' : '') + '>' +
            '<input type="checkbox" data-admin-multi="' + escapeHTML(nombre) +
            '" value="' + escapeHTML(valor) + '"' + tildado + attrTooltip + '>' +
            '<span class="admin-check-texto">' +
              '<span class="admin-check-nombre"><code>' + escapeHTML(etiqueta) + '</code></span>' +
              desc +
              '<span class="admin-check-pie"><code>' + escapeHTML(valor) + '</code></span>' +
              badge +
            '</span></label>';
  });
  return html;
}

// Prende/apaga todos los checks individuales de un grupo y sincroniza el estado
// del check "todos". El que manda al guardar es `adminLeerMulti`.
function adminEngancharComodin(nombre, contenedor) {
  var raiz = (typeof contenedor === 'string') ? document.getElementById(contenedor) : contenedor;
  if (!raiz) return;
  var todos = raiz.querySelector('[data-admin-todos="' + nombre + '"]');
  if (!todos) return;
  var individuales = raiz.querySelectorAll('[data-admin-multi="' + nombre + '"]');

  function sincronizar() {
    if (todos.checked) {
      individuales.forEach(function (c) { c.checked = true; c.disabled = true; });
    } else {
      individuales.forEach(function (c) { c.disabled = false; });
    }
  }

  todos.onchange = sincronizar;
  individuales.forEach(function (c) {
    c.onchange = function () {
      var todosMarcados = Array.prototype.every.call(individuales, function (x) { return x.checked; });
      todos.checked = todosMarcados;
    };
  });
  sincronizar();
}

function adminLeerMulti(nombre) {
  var elegidos = [];
  var todos = document.querySelector('[data-admin-todos="' + nombre + '"]');
  // Con "todos" tildado se guarda el comodín '*' y NADA más: es la forma en que
  // el backend representa "todas las bases" (`bases_permitidas=['*']`), que es
  // distinto de enumerar las 11 — y lo único que habilita los reportes
  // multi-base (Ventas Globales, notificaciones).
  if (todos && todos.checked) return ['*'];
  document.querySelectorAll('[data-admin-multi="' + nombre + '"]').forEach(function (c) {
    if (c.checked) elegidos.push(c.value);
  });
  return elegidos;
}

// --- grupos de permisos plegables ------------------------------------------
// El admin ve 63 permisos repartidos en ~5 grupos: plegar los que no está
// usando deja la pantalla manejable. El estado (abierto/cerrado) se recuerda
// POR GRUPO en el navegador, con una clave por grupo: si un grupo deja de
// existir, su clave queda sin uso y no arrastra nada a los demás. Todo el
// acceso a `localStorage` va envuelto: si el navegador lo tiene bloqueado, el
// grupo simplemente arranca abierto (nunca se rompe el render del panel).

var ADMIN_GRUPO_PREFIJO = 'sidesys_admin_grupo_plegado_';

function adminLeerGrupoPlegado(grupo) {
  try {
    return window.localStorage.getItem(ADMIN_GRUPO_PREFIJO + grupo) === '1';
  } catch (e) {
    return false;
  }
}

function adminRecordarGrupoPlegado(grupo, plegado) {
  try {
    if (plegado) window.localStorage.setItem(ADMIN_GRUPO_PREFIJO + grupo, '1');
    else window.localStorage.removeItem(ADMIN_GRUPO_PREFIJO + grupo);
  } catch (e) { /* preferencia de UI: si no se puede guardar, no pasa nada */ }
}

function adminValorItem(item) {
  return (item && item.valor !== undefined) ? item.valor : item;
}

// Arma un grupo de permisos con encabezado plegable. Reemplaza el armado manual
// que hacían el editor de roles y el de usuarios (los dos usan este helper para
// que el comportamiento sea idéntico).
//
// `items` es la lista del grupo y `seleccionados` los permisos ya tildados; el
// contador cuenta sólo los que están marcados AHORA (antes de guardar).
function adminGrupoPlegable(grupo, items, seleccionados, idMulti, tooltipKey) {
  seleccionados = seleccionados || [];
  items = items || [];
  var tildados = items.filter(function (it) {
    return seleccionados.indexOf(adminValorItem(it)) >= 0;
  }).length;
  var plegado = adminLeerGrupoPlegado(grupo);
  var botonGrupo = adminBotonAccion('tildar/destildar todo', 'tildar-grupo', grupo, '',
                                    null, 'adminRolTildarGrupo');
  return '<div class="admin-grupo' + (plegado ? ' admin-grupo-plegado' : '') + '"' +
             ' data-admin-grupo="' + escapeHTML(grupo) + '">' +
      '<div class="admin-grupo-cabecera" role="button" tabindex="0"' +
           ' data-admin-plegar="' + escapeHTML(grupo) + '"' +
           (tooltipKey ? ' data-tooltip="' + escapeHTML(tooltipKey) + '"' : '') + '>' +
        '<span class="admin-grupo-flecha" aria-hidden="true">▾</span>' +
        '<span class="admin-grupo-nombre">' + escapeHTML(grupo) + '</span>' +
        '<span class="admin-grupo-cuenta">' + tildados + '/' + items.length + '</span>' +
        botonGrupo +
      '</div>' +
      '<div class="admin-checks">' +
        adminMulti(idMulti, items, seleccionados, { tooltip: tooltipKey }) +
      '</div></div>';
}

// Abre/cierra un grupo. Recibe el nombre del grupo o el nodo `.admin-grupo`.
function adminPlegarGrupo(objetivo, plegar) {
  var cont = (objetivo && objetivo.nodeType === 1)
    ? objetivo
    : document.querySelector('.admin-grupo[data-admin-grupo="' + objetivo + '"]');
  if (!cont) return;
  var grupo = cont.getAttribute('data-admin-grupo') || '';
  var debeQuedarPlegado = (plegar === undefined) ? !cont.classList.contains('admin-grupo-plegado')
                                                 : !!plegar;
  cont.classList.toggle('admin-grupo-plegado', debeQuedarPlegado);
  if (grupo) adminRecordarGrupoPlegado(grupo, debeQuedarPlegado);
}

// Abre o cierra TODOS los grupos a la vez. `plegar` sin argumento alterna: si hay
// alguno abierto los cierra todos, y si están todos cerrados los abre.
function adminPlegarTodosGrupos(plegar) {
  var grupos = document.querySelectorAll('.admin-grupo[data-admin-grupo]');
  if (!grupos.length) return;
  var debeQuedarPlegado;
  if (plegar === undefined) {
    debeQuedarPlegado = Array.prototype.some.call(grupos, function (g) {
      return !g.classList.contains('admin-grupo-plegado');
    });
  } else {
    debeQuedarPlegado = !!plegar;
  }
  grupos.forEach(function (g) { adminPlegarGrupo(g, debeQuedarPlegado); });
}

// Delega en el contenedor: el encabezado pliega, salvo que el clic venga de un
// botón adentro (tildar/destildar todo tiene que hacer SOLO eso).
function adminEngancharPlegado(contenedorId) {
  var cont = document.getElementById(contenedorId);
  if (!cont) return;
  cont.addEventListener('click', function (ev) {
    var boton = ev.target.closest && ev.target.closest('button');
    if (boton) return;
    var cabecera = ev.target.closest && ev.target.closest('[data-admin-plegar]');
    if (!cabecera) return;
    adminPlegarGrupo(cabecera.closest('.admin-grupo'));
  });
}

// Delega los clicks de los botones de acción de las vistas: se usan atributos
// data-* y se leen acá, así nunca se arma un onclick con datos del almacén.
function adminEngancharAcciones(contenedorId, manejador) {
  var cont = document.getElementById(contenedorId);
  if (!cont) return;
  cont.onclick = function (ev) {
    var boton = ev.target.closest('[data-admin-accion]');
    if (!boton) return;
    manejador(boton.getAttribute('data-admin-accion'),
              boton.getAttribute('data-admin-dato'));
  };
}

// Re-aplica la visibilidad por data-perm a lo recién renderizado y, con el
// último estado conocido, el modo lectura de §7. Cada vista llama a este helper
// al cerrar su render, así que es el punto donde los botones RECIÉN pintados
// —después de que llegó el refresco del chip— quedan en solo lectura.
function adminReaplicarPermisos() {
  if (typeof aplicarPermisosUI === 'function') {
    var user = (typeof obtenerUsuarioActual === 'function') ? obtenerUsuarioActual() : null;
    if (user) aplicarPermisosUI(user);
  }
  adminAplicarModoLectura();
  // Punto único por el que pasa TODO render del panel: acá se enganchan también
  // los íconos de ayuda (ⓘ) de lo recién pintado. `initTooltips` es idempotente,
  // así que llamarlo de nuevo no duplica nada. Si el módulo todavía no cargó, no
  // se hace nada (el panel funciona igual, solo sin íconos).
  if (typeof window.initTooltips === 'function') {
    try { window.initTooltips(); } catch (e) { console.warn('⚠️ Tooltips del panel:', e); }
  }
}

window.inicializarAdmin = inicializarAdmin;
window.navegarAdmin = navegarAdmin;
window.mostrarVistaAdmin = mostrarVistaAdmin;   // la Task 10 navega sin recargar
window.refrescarChipAdmin = refrescarChipAdmin;
window.adminEstadoActual = adminEstadoActual;
window.adminAplicarModoLectura = adminAplicarModoLectura;
window.adminAviso = adminAviso;
window.adminTabla = adminTabla;
window.adminBoton = adminBoton;
window.adminBotonAccion = adminBotonAccion;
window.adminMulti = adminMulti;
window.adminNormalizarPermisos = adminNormalizarPermisos;
window.adminLeerMulti = adminLeerMulti;
window.adminGrupoPlegable = adminGrupoPlegable;
window.adminPlegarGrupo = adminPlegarGrupo;
window.adminPlegarTodosGrupos = adminPlegarTodosGrupos;
window.adminEngancharPlegado = adminEngancharPlegado;
window.adminEngancharComodin = adminEngancharComodin;
window.adminEngancharAcciones = adminEngancharAcciones;
window.adminReaplicarPermisos = adminReaplicarPermisos;

console.log('✅ admin/index.js cargado');
