// ============================================================
// ADMIN - VISTA AUDITORÍA (spec §5.4)
// ============================================================
// Celdas de `adminTabla`: las CUATRO columnas de la tabla de eventos son DATOS
// del almacén (fecha, acción, quién y el detalle ya armado como texto) y van
// PELADAS: `adminTabla` las escapa una sola vez. Pasarles `escapeHTML` acá las
// mostraría doble escapadas (`&amp;amp;`).
//
// Tope del servidor: `GET /api/admin/auditoria` acepta `limite` hasta 500
// (más grande lo deja en el default 100), así que el "Mostrar más" del cliente
// no puede pasar de 500 ni de a 100 por click.

var _admAuditoria = [];
var _admAuditoriaLimite = 100;

async function cargarVistaAuditoriaAdmin() {
  adminAviso('admin-auditoria', 'Cargando auditoría…');
  var r = await adminFetch('/api/admin/auditoria?dias=30&limite=' + _admAuditoriaLimite);
  if (!r.ok) {
    // Chequeo local (los scripts del panel comparten scope): un 503 no puede
    // dejar el chip verde mintiendo sobre el almacén.
    if (r.codigo === 503) refrescarChipAdmin();
    adminAviso('admin-auditoria', r.error, 'error');
    return;
  }
  _admAuditoria = (r.datos && r.datos.auditoria) || [];
  renderVistaAuditoriaAdmin();
}

function renderVistaAuditoriaAdmin() {
  var body = adminBody('admin-auditoria');
  if (!body) return;
  body.innerHTML =
    '<div class="admin-toolbar">' +
      '<input type="text" id="admin-buscar-auditoria" placeholder="Filtrar por acción o usuario…">' +
      adminBoton('Mostrar más', 'mostrarMasAuditoriaAdmin()', '') +
    '</div>' +
    '<div id="admin-auditoria-tabla"></div>';
  var buscar = document.getElementById('admin-buscar-auditoria');
  if (buscar) {
    buscar.addEventListener('input', function () { pintarTablaAuditoriaAdmin(this.value); });
  }
  pintarTablaAuditoriaAdmin('');
  adminReaplicarPermisos();
}

function pintarTablaAuditoriaAdmin(filtro) {
  var cont = document.getElementById('admin-auditoria-tabla');
  if (!cont) return;
  var t = (filtro || '').trim().toLowerCase();
  var eventos = _admAuditoria.filter(function (e) {
    if (!t) return true;
    return [e.accion, e.por, e.usuario, e.rol].some(function (v) {
      return (v || '').toString().toLowerCase().indexOf(t) >= 0;
    });
  });
  cont.innerHTML = adminTabla(['Cuándo', 'Acción', 'Quién', 'Detalle'],
    eventos.map(function (e) {
      var detalle = Object.keys(e).filter(function (k) {
        return ['accion', 'por', 'fecha'].indexOf(k) < 0;
      }).map(function (k) {
        var v = e[k];
        return k + ': ' + (v && typeof v === 'object' ? JSON.stringify(v) : String(v));
      }).join(' · ');
      // Datos pelados: `adminTabla` los escapa (una sola vez) en el `<td>`.
      return [String(e.fecha || '—'),
              e.accion || '—',
              e.por || '—',
              detalle];
    }));
}

async function mostrarMasAuditoriaAdmin() {
  _admAuditoriaLimite = Math.min(500, _admAuditoriaLimite + 100);
  await cargarVistaAuditoriaAdmin();
}

window.cargarVistaAuditoriaAdmin = cargarVistaAuditoriaAdmin;
window.pintarTablaAuditoriaAdmin = pintarTablaAuditoriaAdmin;
window.mostrarMasAuditoriaAdmin = mostrarMasAuditoriaAdmin;

console.log('✅ admin/auditoria.js cargado');
