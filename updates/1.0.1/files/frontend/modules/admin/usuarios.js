// ============================================================
// ADMIN - VISTA USUARIOS (spec §5.1)
// ============================================================
// Celdas de `adminTabla`: las de datos van PELADAS (adminTabla las escapa) y las
// de markup van como `{html: '...'}` con los datos ya pasados por escapeHTML()
// acá. Nunca al revés: el default de adminTabla es escapar.
//
// Regla de datos (no negociable): `guardarUsuarioAdmin` manda un campo al PUT
// SOLO si su editor se pudo cargar y pintar (`_admPuedeEditar*`). Si el GET de
// bases/módulos/permisos/roles dio 403 o 503, el campo se OMITE del body.
// `gestor.editar_usuario(**data)` solo toca las claves presentes, así que omitir
// preserva lo que el usuario ya tenía; mandar `[]` por un editor que no se cargó
// le borraría las bases, los módulos o las excepciones de permisos, con toast de
// éxito y propagado al almacén central.

var _admUsuarios = [];
var _admRoles = [];
var _admBases = [];
var _admModulos = [];
var _admPermisos = {};
var _admEditandoUsuario = null;
var _admGuardando = false;
// Un editor está disponible solo si su GET dio ok Y dejó opciones para pintar.
var _admPuedeEditarRoles = false;
var _admPuedeEditarBases = false;
var _admPuedeEditarModulos = false;
var _admPuedeEditarPermisos = false;

function _admRefrescarChipSi503(r) {
  if (r && r.codigo === 503) refrescarChipAdmin();
}

async function cargarVistaUsuariosAdmin() {
  adminAviso('admin-usuarios', 'Cargando usuarios…');
  var rU = await adminFetch('/api/admin/usuarios');
  if (!rU.ok) {
    _admRefrescarChipSi503(rU);
    adminAviso('admin-usuarios', rU.error, 'error');
    return;
  }
  _admUsuarios = (rU.datos && rU.datos.usuarios) || [];
  var rR = await adminFetch('/api/admin/roles');
  _admRoles = (rR.ok && rR.datos.roles) || [];
  var rB = await adminFetch('/api/admin/bases');
  _admBases = (rB.ok && rB.datos.bases) || [];
  var rM = await adminFetch('/api/admin/modulos');
  _admModulos = (rM.ok && rM.datos.modulos) || [];
  var rP = await adminFetch('/api/admin/permisos');
  // `{valor, descripcion, verificado}` normalizado; sin admin.permisos.asignar queda {}
  _admPermisos = (rP.ok && rP.datos)
    ? (typeof adminNormalizarPermisos === 'function'
        ? adminNormalizarPermisos(rP.datos) : rP.datos)
    : {};
  _admRefrescarChipSi503(rR);                    // el chip no puede quedar verde
  _admRefrescarChipSi503(rB);                    // con el almacén caído
  _admRefrescarChipSi503(rM);
  _admRefrescarChipSi503(rP);
  _admPuedeEditarRoles = rR.ok && _admRoles.length > 0;
  _admPuedeEditarBases = rB.ok && _admBases.length > 0;
  _admPuedeEditarModulos = rM.ok && _admModulos.length > 0;
  _admPuedeEditarPermisos = rP.ok && Object.keys(_admPermisos).length > 0;
  renderVistaUsuariosAdmin();
}

function renderVistaUsuariosAdmin() {
  var body = adminBody('admin-usuarios');
  if (!body) return;
  body.innerHTML =
    '<div class="admin-toolbar">' +
      '<input type="text" id="admin-buscar-usuarios" placeholder="Buscar por usuario, nombre o email…">' +
      adminBoton('+ Nuevo usuario', "abrirFormUsuarioAdmin()", 'admin-btn-primario', 'admin.usuarios.crear') +
    '</div>' +
    '<div id="admin-usuario-form"></div>' +
    '<div id="admin-usuarios-tabla"></div>';
  var buscar = document.getElementById('admin-buscar-usuarios');
  if (buscar) {
    buscar.addEventListener('input', function () { buscarUsuariosAdmin(this.value); });
  }
  pintarTablaUsuariosAdmin(_admUsuarios);
  adminEngancharAcciones('admin-usuarios-tabla', manejarAccionUsuarioAdmin);
}

function buscarUsuariosAdmin(texto) {
  var t = (texto || '').trim().toLowerCase();
  if (!t) { pintarTablaUsuariosAdmin(_admUsuarios); return; }
  pintarTablaUsuariosAdmin(_admUsuarios.filter(function (u) {
    return [u.username, u.nombre, u.email].some(function (v) {
      return (v || '').toLowerCase().indexOf(t) >= 0;
    });
  }));
}

function pintarTablaUsuariosAdmin(lista) {
  var cont = document.getElementById('admin-usuarios-tabla');
  if (!cont) return;
  var filas = lista.map(function (u) {
    var estado = !u.activo
      ? '<span class="admin-chip admin-chip-gris">inactivo</span>'
      : (u.bloqueado
          ? '<span class="admin-chip admin-chip-warn">bloqueado</span>'
          : '<span class="admin-chip admin-chip-ok">activo</span>');
    var bases = (u.bases_permitidas || []).indexOf('*') >= 0
      ? 'todas' : (u.bases_permitidas || []).join(', ');
    // Al superadmin el backend le rechaza editar, eliminar y bloquear
    // (usuarios.py: "No puedes modificar al superadmin", "No se puede eliminar al
    // superadmin", "No se puede bloquear al superadmin"): no se ofrecen botones
    // que siempre terminan en 400.
    var acciones = u.es_superadmin
      ? '<span class="admin-chip admin-chip-gris">superadmin: sin acciones</span>'
      : adminBotonAccion('Editar', 'editar', u.username, '', 'admin.usuarios.editar') +
        (u.bloqueado
          ? adminBotonAccion('Desbloquear', 'desbloquear', u.username, '', 'admin.usuarios.bloquear')
          : adminBotonAccion('Bloquear', 'bloquear', u.username, '', 'admin.usuarios.bloquear')) +
        adminBotonAccion('Eliminar', 'eliminar', u.username, 'admin-btn-peligro', 'admin.usuarios.eliminar');
    return [
      { html: '<b>' + escapeHTML(u.username) + '</b>' },
      u.nombre || '—',
      u.email || '—',
      { html: (u.roles || []).map(function (r) {
          return '<span class="admin-chip">' + escapeHTML(r) + '</span>';
        }).join(' ') || '—' },
      bases || '—',
      { html: estado },
      (u.creado || '').slice(0, 10) || '—',
      { html: acciones }
    ];
  });
  cont.innerHTML = adminTabla(
    ['Usuario', 'Nombre', 'Email', 'Roles', 'Bases', 'Estado', 'Alta', 'Acciones'], filas);
  adminReaplicarPermisos();
}

async function manejarAccionUsuarioAdmin(accion, username) {
  if (accion === 'editar') return abrirFormUsuarioAdmin(username);
  if (accion === 'bloquear') return bloquearUsuarioAdmin(username);
  if (accion === 'desbloquear') return desbloquearUsuarioAdmin(username);
  if (accion === 'eliminar') return eliminarUsuarioAdmin(username);
}

// --- armado del formulario -------------------------------------------------

// Opciones de `adminMulti` para un editor de listas: las del catálogo más la
// opción sintética `*` ("Todas"/"Todos") cuando el usuario ya la tiene. `*` no
// está en el catálogo (BASES_DISPONIBLES / módulos) y sin esta opción el
// formulario abriría todo desmarcado y el guardado reemplazaría el `*` por `[]`.
function _htmlValoresSoloLectura(valores, etiquetaComodin) {
  var lista = valores || [];
  if (!lista.length) return '<span class="admin-chip admin-chip-gris">sin valores</span>';
  return lista.map(function (v) {
    return '<span class="admin-chip">' +
           escapeHTML(v === '*' && etiquetaComodin ? etiquetaComodin : v) + '</span>';
  }).join(' ');
}

// `permiso` y `que` son literales de este archivo; van escapados igual.
function _htmlEditorSoloLectura(permiso, que, valores, etiquetaComodin) {
  return '<div class="admin-aviso">Sin permiso <b>' + escapeHTML(permiso) +
         '</b>: no se pueden editar ' + escapeHTML(que) + '. Se conservan los valores actuales: ' +
         _htmlValoresSoloLectura(valores, etiquetaComodin) + '</div>';
}

// Solo se llama con el catálogo cargado (`_admPuedeEditarPermisos`).
function _htmlChecksPermisos(idMulti, seleccionados) {
  return Object.keys(_admPermisos).sort().map(function (grupo) {
    return '<div class="admin-grupo"><div class="admin-grupo-titulo">' + escapeHTML(grupo) +
           '</div><div class="admin-checks">' +
           adminMulti(idMulti, _admPermisos[grupo], seleccionados) + '</div></div>';
  }).join('');
}

function _htmlPermisosEditor(idMulti, actuales) {
  if (_admPuedeEditarPermisos) return _htmlChecksPermisos(idMulti, actuales);
  return _htmlEditorSoloLectura('admin.permisos.asignar', 'los permisos por usuario', actuales);
}

// Los cuatro editores de la edición (bases, módulos, permisos extra y
// restringidos) y los checks de activo/bloqueado se pintan SOLO en modo edición.
// En ALTA no: `POST /api/admin/usuarios` (`crear_usuario`) acepta únicamente
// username/email/nombre/roles y `Usuario.__init__` deja `bases_permitidas` y
// `modulos_permitidos` en [], así que pintarlos sería descartar en silencio lo
// que el admin tildó y la cuenta quedaría SIN base permitida: cada pedido suyo
// fallaría cerrado con 403 BASE_FORBIDDEN, con un "Usuario creado" verde encima.
// El alta es usuario de Windows + nombre + email + roles (spec §5.1); el resto
// se tilda en la edición que `guardarUsuarioAdmin` abre al crearlo.
function _htmlCamposEdicionUsuarioAdmin(base) {
  var basesActuales = base.bases_permitidas || [];
  var opcionesBases = _admPuedeEditarBases
    ? adminMulti('adminUsuariosBases',
        _admBases.map(function (b) {
          return { valor: b.id, etiqueta: b.nombre + ' (' + (b.pais || b.id) + ')' };
        }), basesActuales, { comodin: 'Todas las bases' })
    : _htmlEditorSoloLectura('admin.bases.config', 'las bases', basesActuales, 'Todas');
  var modulosActuales = base.modulos_permitidos || [];
  var opcionesModulos = _admPuedeEditarModulos
    ? adminMulti('adminUsuariosModulos',
        _admModulos.map(function (m) {
          return { valor: m.id, etiqueta: m.nombre };
        }), modulosActuales, { comodin: 'Todos los módulos' })
    : _htmlEditorSoloLectura('admin.modulos.config', 'los módulos', modulosActuales, 'Todos');
  return '<div class="admin-campo"><label>Bases permitidas</label>' + opcionesBases + '</div>' +
    '<div class="admin-campo"><label>Módulos permitidos</label>' + opcionesModulos + '</div>' +
    '<div class="admin-campo"><label>Permisos extra (se suman a los del rol)</label>' +
      _htmlPermisosEditor('adminUsuariosExtra', base.permisos_extra || []) + '</div>' +
    '<div class="admin-campo"><label>Permisos restringidos (se restan)</label>' +
      _htmlPermisosEditor('adminUsuariosRestringidos', base.permisos_restringidos || []) + '</div>' +
    // Activo/bloqueado tampoco existen en alta: la cuenta nace activa y
    // desbloqueada, y el POST no acepta esos campos.
    '<div class="admin-checks">' +
      '<label class="admin-check"><input type="checkbox" id="admin-usuario-activo"' +
        (base.activo ? ' checked' : '') + '> Activo</label>' +
      '<label class="admin-check"><input type="checkbox" id="admin-usuario-bloqueado"' +
        (base.bloqueado ? ' checked' : '') + '> Bloqueado</label>' +
    '</div>';
}

function htmlFormUsuarioAdmin(base, editando) {
  var opcionesRoles = _admPuedeEditarRoles
    ? '<div class="admin-checks">' + adminMulti('adminUsuariosRoles', _admRoles.map(function (r) {
        return { valor: r.id, etiqueta: r.nombre + ' (' + (r.permisos || []).length + ' permisos)' };
      }), base.roles || []) + '</div>'
    : _htmlEditorSoloLectura('admin.roles.ver', 'los roles', base.roles || []);
  return '' +
    '<div class="admin-panel">' +
      '<h4>' + (editando ? 'Editar ' + escapeHTML(base.username) : 'Nuevo usuario') + '</h4>' +
      (editando ? '' :
        '<div class="admin-campo"><label>Usuario de Windows</label>' +
        '<input type="text" id="admin-usuario-username" value="' + escapeHTML(base.username || '') + '"></div>') +
      '<div class="admin-campo"><label>Nombre</label>' +
        '<input type="text" id="admin-usuario-nombre" value="' + escapeHTML(base.nombre || '') + '"></div>' +
      '<div class="admin-campo"><label>Email</label>' +
        '<input type="text" id="admin-usuario-email" value="' + escapeHTML(base.email || '') + '"></div>' +
      '<div class="admin-campo"><label>Roles</label>' + opcionesRoles + '</div>' +
      (editando ? _htmlCamposEdicionUsuarioAdmin(base) : '') +
      '<div class="admin-toolbar" style="margin-top:14px">' +
        adminBotonAccion('Guardar', 'guardar', null, 'admin-btn-primario') +
        adminBotonAccion('Cancelar', 'cancelar', null, '') +
      '</div>' +
    '</div>';
}

async function abrirFormUsuarioAdmin(username) {
  var cont = document.getElementById('admin-usuario-form');
  if (!cont) return;
  _admEditandoUsuario = username || null;
  var base = null;
  if (username) {
    var r = await adminFetch('/api/admin/usuarios/' + encodeURIComponent(username));
    if (!r.ok) {
      // El error va DENTRO del contenedor del formulario: `adminAviso` reemplaza
      // todo el body de la vista y se llevaría puesto el buscador, la tabla y el
      // propio formulario. Así la tabla queda usable y el motivo se ve donde se
      // clickeó.
      _admEditandoUsuario = null;
      cont.innerHTML = '<div class="admin-aviso admin-aviso-error">' +
                       escapeHTML(r.error) + '</div>';
      _admRefrescarChipSi503(r);
      return;
    }
    base = _admUsuarios.filter(function (u) { return u.username === username; })[0] || null;
    base = Object.assign({}, base, r.datos);   // el detalle trae permisos_extra/restringidos
  }
  base = base || { username: '', nombre: '', email: '', roles: ['invitado'],
                   bases_permitidas: [], modulos_permitidos: [],
                   permisos_extra: [], permisos_restringidos: [], activo: true };
  cont.innerHTML = htmlFormUsuarioAdmin(base, !!username);
  adminEngancharAcciones('admin-usuario-form', function (accion) {
    if (accion === 'guardar') guardarUsuarioAdmin();
    else if (accion === 'cancelar') cerrarFormUsuarioAdmin();
  });
  // El check "Todas las bases" / "Todos los módulos" prende y apaga los
  // individuales. Se engancha después de pintar el formulario.
  if (typeof adminEngancharComodin === 'function') {
    adminEngancharComodin('adminUsuariosBases', cont);
    adminEngancharComodin('adminUsuariosModulos', cont);
  }
  if (typeof cont.scrollIntoView === 'function') cont.scrollIntoView({ block: 'nearest' });
}

function cerrarFormUsuarioAdmin() {
  var cont = document.getElementById('admin-usuario-form');
  if (cont) cont.innerHTML = '';
  _admEditandoUsuario = null;
}

async function guardarUsuarioAdmin() {
  if (_admGuardando) return;              // un doble click no manda dos altas
  _admGuardando = true;
  try {
    var cuerpo = {
      nombre: (document.getElementById('admin-usuario-nombre') || {}).value || '',
      email: (document.getElementById('admin-usuario-email') || {}).value || ''
    };
    // Solo lo que el editor pudo pintar. Omitir una clave preserva el valor que
    // el usuario ya tenía; mandar `[]` lo borraría (ver cabecera del archivo).
    if (_admPuedeEditarRoles) cuerpo.roles = adminLeerMulti('adminUsuariosRoles');
    var r;
    if (_admEditandoUsuario) {
      if (_admPuedeEditarBases) cuerpo.bases_permitidas = adminLeerMulti('adminUsuariosBases');
      if (_admPuedeEditarModulos) cuerpo.modulos_permitidos = adminLeerMulti('adminUsuariosModulos');
      if (_admPuedeEditarPermisos) {
        cuerpo.permisos_extra = adminLeerMulti('adminUsuariosExtra');
        cuerpo.permisos_restringidos = adminLeerMulti('adminUsuariosRestringidos');
      }
      var activo = document.getElementById('admin-usuario-activo');
      var bloqueado = document.getElementById('admin-usuario-bloqueado');
      if (activo) cuerpo.activo = activo.checked;
      if (bloqueado) cuerpo.bloqueado = bloqueado.checked;
      r = await adminFetch('/api/admin/usuarios/' + encodeURIComponent(_admEditandoUsuario),
                           { method: 'PUT', body: cuerpo });
    } else {
      var input = document.getElementById('admin-usuario-username');
      cuerpo.username = ((input || {}).value || '').trim();
      if (!cuerpo.username) { toastError('Escribí el usuario de Windows'); return; }
      r = await adminFetch('/api/admin/usuarios', { method: 'POST', body: cuerpo });
    }
    if (!r.ok) {
      toastError(r.error);
      _admRefrescarChipSi503(r);
      return;
    }
    if (_admEditandoUsuario) {
      toastSuccess('Usuario actualizado');
      cerrarFormUsuarioAdmin();
      await cargarVistaUsuariosAdmin();
    } else {
      // Alta: el POST no acepta bases/módulos/permisos ni activo/bloqueado (ver
      // `htmlFormUsuarioAdmin`), así que la cuenta nace SIN base permitida. Se
      // recarga la tabla —para que la fila nueva quede listada— y se reabre el
      // MISMO usuario en edición, igual que `roles.js` después de crear un rol:
      // el siguiente paso natural del admin es tildarle bases, módulos y permisos.
      toastSuccess('Usuario creado');
      await cargarVistaUsuariosAdmin();
      await abrirFormUsuarioAdmin(cuerpo.username);
    }
  } finally {
    _admGuardando = false;
  }
}

async function bloquearUsuarioAdmin(username) {
  if (!confirm('¿Bloquear a ' + username + '? No va a poder entrar hasta que lo desbloquees.')) return;
  var r = await adminFetch('/api/admin/usuarios/' + encodeURIComponent(username) + '/bloquear',
                           { method: 'POST' });
  if (!r.ok) { toastError(r.error); _admRefrescarChipSi503(r); return; }
  toastSuccess('Usuario bloqueado');
  await cargarVistaUsuariosAdmin();
}

async function desbloquearUsuarioAdmin(username) {
  var r = await adminFetch('/api/admin/usuarios/' + encodeURIComponent(username) + '/desbloquear',
                           { method: 'POST' });
  if (!r.ok) { toastError(r.error); _admRefrescarChipSi503(r); return; }
  toastSuccess('Usuario desbloqueado');
  await cargarVistaUsuariosAdmin();
}

async function eliminarUsuarioAdmin(username) {
  if (!confirm('¿Dar de baja a ' + username + '? El cambio se propaga a las demás PCs.')) return;
  var r = await adminFetch('/api/admin/usuarios/' + encodeURIComponent(username),
                           { method: 'DELETE' });
  if (!r.ok) { toastError(r.error); _admRefrescarChipSi503(r); return; }
  toastSuccess('Usuario dado de baja');
  await cargarVistaUsuariosAdmin();
}

window.cargarVistaUsuariosAdmin = cargarVistaUsuariosAdmin;
window.buscarUsuariosAdmin = buscarUsuariosAdmin;
window.abrirFormUsuarioAdmin = abrirFormUsuarioAdmin;
window.htmlFormUsuarioAdmin = htmlFormUsuarioAdmin;   // la Task 10 lo usa para el alta en un clic
window.cerrarFormUsuarioAdmin = cerrarFormUsuarioAdmin;
window.guardarUsuarioAdmin = guardarUsuarioAdmin;
window.bloquearUsuarioAdmin = bloquearUsuarioAdmin;
window.desbloquearUsuarioAdmin = desbloquearUsuarioAdmin;
window.eliminarUsuarioAdmin = eliminarUsuarioAdmin;

console.log('✅ admin/usuarios.js cargado');
