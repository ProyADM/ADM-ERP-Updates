// ============================================================
// ADMIN - INICIALIZACIÓN, NAVEGACIÓN Y HELPERS COMPARTIDOS
// ============================================================
// El módulo se llama `admin` a propósito: los permisos del panel son `admin.*`
// y el gate explícito de `aplicarPermisosUI` exige `admin.acceso` (spec §4.1).

var ADMIN_VISTAS = ['admin-usuarios', 'admin-roles', 'admin-estado',
                    'admin-auditoria', 'admin-accesos'];
var ADMIN_CARGADORES = {
  'admin-usuarios': 'cargarVistaUsuariosAdmin',
  'admin-roles': 'cargarVistaRolesAdmin',
  'admin-estado': 'cargarVistaEstadoAdmin',
  'admin-auditoria': 'cargarVistaAuditoriaAdmin',
  'admin-accesos': 'cargarVistaAccesosAdmin'
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

function adminBoton(texto, onclick, clase, permiso) {
  return '<button class="admin-btn ' + (clase || '') + '"' +
         (permiso ? ' data-perm="' + permiso + '"' : '') +
         ' data-onclick="' + onclick + '">' + escapeHTML(texto) + '</button>';
}

function adminBotonAccion(texto, accion, dato, clase, permiso) {
  return '<button class="admin-btn ' + (clase || '') + '"' +
         (permiso ? ' data-perm="' + permiso + '"' : '') +
         ' data-admin-accion="' + escapeHTML(accion) + '"' +
         (dato === undefined || dato === null ? ''
            : ' data-admin-dato="' + escapeHTML(dato) + '"') +
         '>' + escapeHTML(texto) + '</button>';
}

function adminMulti(nombre, items, seleccionados) {
  seleccionados = seleccionados || [];
  return items.map(function (item) {
    var valor = (item && item.valor !== undefined) ? item.valor : item;
    var etiqueta = (item && item.etiqueta !== undefined) ? item.etiqueta : valor;
    var tildado = seleccionados.indexOf(valor) >= 0 ? ' checked' : '';
    return '<label class="admin-check"><input type="checkbox" data-admin-multi="' +
           escapeHTML(nombre) + '" value="' + escapeHTML(valor) + '"' + tildado + '> ' +
           escapeHTML(etiqueta) + '</label>';
  }).join('');
}

function adminLeerMulti(nombre) {
  var elegidos = [];
  document.querySelectorAll('[data-admin-multi="' + nombre + '"]').forEach(function (c) {
    if (c.checked) elegidos.push(c.value);
  });
  return elegidos;
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
window.adminLeerMulti = adminLeerMulti;
window.adminEngancharAcciones = adminEngancharAcciones;
window.adminReaplicarPermisos = adminReaplicarPermisos;

console.log('✅ admin/index.js cargado');
