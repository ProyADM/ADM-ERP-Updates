// ============================================================
// ADMIN - VISTA ACCESOS RECHAZADOS (spec §5.5)
// ============================================================
// Celdas de `adminTabla`: el usuario (`<b>…</b>`) y la columna de acciones son
// MARKUP → van como `{html: '...'}` con los datos ya pasados por `escapeHTML`
// (el usuario adentro del `<b>`; el botón lo escapa `adminBotonAccion`). PC,
// motivo, última vez y veces son DATOS → van PELADOS y los escapa `adminTabla`
// una sola vez (con `escapeHTML` acá saldrían doble escapados).
//
// El campo `usuario` que devuelve el endpoint conserva la grafía MÁS VIEJA vista
// del nombre de Windows SOLO cuando el usuario NO está en el almacén (el agrupado
// es por minúsculas y no pisa la primera grafía con la última tipeada). Cuando
// `ya_existe` es true devuelve la clave REAL del almacén: es la que necesita el
// "Ver usuario" de abajo, que abre el detalle con una búsqueda EXACTA
// (`GET /api/admin/usuarios/<clave>`) y con la grafía tecleada daría 404 en
// cuanto difiera aunque sea en mayúsculas.
//
// `ya_existe: false` → "Dar de alta" (abre el formulario de Usuarios prefijado
// con el usuario rechazado, reusando `htmlFormUsuarioAdmin`).
// `ya_existe: true`  → "Ver usuario" (abre ese usuario en edición).

var _admAccesos = [];

var _admAccesosMotivos = {
  USER_NOT_AUTHORIZED: 'No está dado de alta',
  USER_DISABLED: 'Su usuario está desactivado',
  USER_BLOCKED: 'Su usuario está bloqueado'
};

async function cargarVistaAccesosAdmin() {
  adminAviso('admin-accesos', 'Cargando intentos rechazados…');
  var r = await adminFetch('/api/admin/accesos-rechazados');
  if (!r.ok) {
    // Chequeo local (los scripts del panel comparten scope): un 503 no puede
    // dejar el chip verde mintiendo sobre el almacén.
    if (r.codigo === 503) refrescarChipAdmin();
    adminAviso('admin-accesos', r.error, 'error');
    return;
  }
  _admAccesos = (r.datos && r.datos.usuarios) || [];
  renderVistaAccesosAdmin();
}

function renderVistaAccesosAdmin() {
  var body = adminBody('admin-accesos');
  if (!body) return;
  if (!_admAccesos.length) {
    body.innerHTML = '<div class="admin-aviso">Todavía no hay intentos rechazados. ' +
      'Van a aparecer acá la primera vez que alguien intente entrar sin estar dado de alta ' +
      '(o con su usuario desactivado o bloqueado).</div>';
    return;
  }
  body.innerHTML =
    '<div class="admin-toolbar">' + adminBoton('Recargar', 'cargarVistaAccesosAdmin()', '') + '</div>' +
    '<div id="admin-accesos-tabla"></div>';
  document.getElementById('admin-accesos-tabla').innerHTML = adminTabla(
    ['Usuario de Windows', 'PC', 'Motivo', 'Última vez', 'Veces', ''],
    _admAccesos.map(function (a) {
      var accion = a.ya_existe
        ? adminBotonAccion('Ver usuario', 'ver-usuario', a.usuario, '', 'admin.usuarios.ver')
        : adminBotonAccion('Dar de alta', 'alta', a.usuario, 'admin-btn-primario',
                           'admin.usuarios.crear');
      return [{ html: '<b>' + escapeHTML(a.usuario) + '</b>' },
              a.pc || '—',
              _admAccesosMotivos[a.motivo] || a.motivo || '—',
              (a.ultimo || '').replace('T', ' ').slice(0, 19) || '—',
              String(a.veces || 0),
              { html: accion }];
    }));
  adminEngancharAcciones('admin-accesos-tabla', manejarAccionAccesoAdmin);
  adminReaplicarPermisos();
}

async function manejarAccionAccesoAdmin(accion, usuario) {
  if (accion === 'alta') return darDeAltaAccesoAdmin(usuario);
  if (accion === 'ver-usuario') return verUsuarioDesdeAccesoAdmin(usuario);
}

async function darDeAltaAccesoAdmin(usuario) {
  // Reusa el formulario de alta de la vista Usuarios, prefijado con el usuario
  // de Windows que intentó entrar (spec §5.5). No se reimplementa nada: el
  // formulario ya maneja el caso de catálogos sin cargar (roles/bases/módulos
  // en solo lectura) y el guardado omite las claves que no se pudieron pintar.
  //
  // La navegación NO pasa por `navegarAdmin`: ese helper ya dispara su propia
  // carga de Usuarios y acá hace falta UNA sola carga ESPERADA. Con dos carreras,
  // el render que llegue último reemplaza el `innerHTML` del cuerpo y se lleva
  // puesto el formulario recién pintado (con su `adminEngancharAcciones` colgado
  // de un nodo desprendido). `mostrarVistaAdmin` sólo cambia la vista visible,
  // que era justamente lo que `navegarAdmin` no hacía.
  mostrarVistaAdmin('admin-usuarios');
  await cargarVistaUsuariosAdmin();
  var cont = document.getElementById('admin-usuario-form');
  if (!cont) return;
  var base = { username: usuario, nombre: '', email: '', roles: ['invitado'],
               bases_permitidas: [], modulos_permitidos: [],
               permisos_extra: [], permisos_restringidos: [], activo: true };
  cont.innerHTML = htmlFormUsuarioAdmin(base, false);
  _admEditandoUsuario = null;
  var input = document.getElementById('admin-usuario-username');
  if (input) input.value = usuario;
  adminEngancharAcciones('admin-usuario-form', function (accion) {
    if (accion === 'guardar') guardarUsuarioAdmin();
    else if (accion === 'cancelar') cerrarFormUsuarioAdmin();
  });
  adminReaplicarPermisos();
  if (typeof cont.scrollIntoView === 'function') cont.scrollIntoView({ block: 'nearest' });
}

async function verUsuarioDesdeAccesoAdmin(usuario) {
  // Igual que el alta: cambiar la vista visible y UNA sola carga esperada.
  mostrarVistaAdmin('admin-usuarios');
  await cargarVistaUsuariosAdmin();
  await abrirFormUsuarioAdmin(usuario);
}

window.cargarVistaAccesosAdmin = cargarVistaAccesosAdmin;
window.darDeAltaAccesoAdmin = darDeAltaAccesoAdmin;
window.verUsuarioDesdeAccesoAdmin = verUsuarioDesdeAccesoAdmin;

console.log('✅ admin/accesos.js cargado');
