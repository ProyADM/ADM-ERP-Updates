// ============================================================
// ADMIN - VISTA ROLES Y PERMISOS (spec §5.2)
// ============================================================
// Celdas de `adminTabla`: las de datos van PELADAS (adminTabla las escapa) y las
// de markup van como `{html: '...'}` con los datos ya pasados por escapeHTML()
// acá. Nunca al revés: el default de adminTabla es escapar.
//
// Regla de datos (no negociable): `guardarRolAdmin` manda `permisos` al PUT
// SOLO si el catálogo de permisos se pudo cargar y pintar
// (`_admRolPuedeEditarPermisos`). Si `GET /api/admin/permisos` dio 403 (falta
// `admin.permisos.asignar`) o 503, el formulario no tiene checkboxes y
// `adminLeerMulti('adminRolPermisos')` devolvería `[]`: mandarlo borraría TODOS
// los permisos del rol en el almacén compartido, propagado a todas las PCs.
// `gestor.editar_rol(rol_id, **kwargs)` hace `update(kwargs)` a ciegas —solo
// toca las claves presentes—, así que omitir `permisos` los preserva. Sin
// catálogo el editor queda en solo lectura (chips con los permisos actuales y
// el motivo) y no ofrece Guardar.
//
// Regla del backend que la UI refleja: `gestor.editar_rol` rechaza el rol
// `superadmin` con ValueError (400). Se muestra en solo lectura (D5) y no hay
// botón de borrar (D2).

var _admListaRoles = [];
var _admPermisosGrupos = {};
var _admRolEditando = null;
var _admRolGuardando = false;
// El editor de permisos sirve solo si su GET dio ok Y trajo grupos con permisos
// para pintar. Los nombres de este archivo llevan el prefijo `_admRol` a
// propósito: `usuarios.js` ya declara `_admPuedeEditarPermisos` y
// `_admRefrescarChipSi503`, y en un script clásico todo `var`/`function` de
// nivel superior es el MISMO global (el segundo archivo pisaría al primero).
var _admRolPuedeEditarPermisos = false;

// Mismo criterio que en `usuarios.js`: un 503 —también el de un GET— no puede
// dejar el chip verde mintiendo sobre el almacén.
function _admRolRefrescarChipSi503(r) {
  if (r && r.codigo === 503) refrescarChipAdmin();
}

// Permisos actuales en solo lectura (chips escapados): cuando el editor no se
// puede pintar se muestran estos en vez de un campo vacío.
function _admRolChipsPermisos(permisos) {
  var lista = permisos || [];
  if (!lista.length) return '<span class="admin-chip admin-chip-gris">sin permisos</span>';
  return '<div class="admin-checks">' + lista.map(function (p) {
    return '<span class="admin-chip">' + escapeHTML(p) + '</span>';
  }).join(' ') + '</div>';
}

async function cargarVistaRolesAdmin() {
  adminAviso('admin-roles', 'Cargando roles…');
  var rR = await adminFetch('/api/admin/roles');
  if (!rR.ok) {
    _admRolRefrescarChipSi503(rR);
    adminAviso('admin-roles', rR.error, 'error');
    return;
  }
  _admListaRoles = (rR.datos && rR.datos.roles) || [];
  var rP = await adminFetch('/api/admin/permisos');
  // `{valor, descripcion, verificado}` normalizado; sin admin.permisos.asignar queda {}
  _admPermisosGrupos = (rP.ok && rP.datos)
    ? (typeof adminNormalizarPermisos === 'function'
        ? adminNormalizarPermisos(rP.datos) : rP.datos)
    : {};
  _admRolRefrescarChipSi503(rP);                    // el chip no puede quedar verde
  _admRolPuedeEditarPermisos = rP.ok && Object.keys(_admPermisosGrupos).some(function (g) {
    return (_admPermisosGrupos[g] || []).length > 0;   // con grupos vacíos no hay qué tildar
  });
  renderVistaRolesAdmin();
}

function renderVistaRolesAdmin() {
  var body = adminBody('admin-roles');
  if (!body) return;
  // El render reescribe el body entero, y con él el formulario: el rol que
  // estaba en edición ya no está en pantalla.
  _admRolEditando = null;
  body.innerHTML =
    '<div class="admin-toolbar">' +
      adminBoton('+ Nuevo rol', "abrirFormNuevoRolAdmin()", 'admin-btn-primario', 'admin.roles.crear', 'adminRolNuevo') +
      adminBoton('Recargar', "cargarVistaRolesAdmin()", '') +
    '</div>' +
    '<div id="admin-rol-form"></div>' +
    '<div id="admin-roles-tabla"></div>';
  var cont = document.getElementById('admin-roles-tabla');
  if (!cont) return;
  var filas = _admListaRoles.map(function (r) {
    return [
      { html: '<b>' + escapeHTML(r.id) + '</b>' },
      r.nombre || '',
      r.descripcion || '—',
      String((r.permisos || []).length),
      String(r.cantidad_usuarios || 0),
      { html: adminBotonAccion(r.id === 'superadmin' ? 'Ver' : 'Editar permisos',
                               'editar-rol', r.id, '', 'admin.roles.ver') }
    ];
  });
  cont.innerHTML = adminTabla(
    ['Rol', 'Nombre', 'Descripción', 'Permisos', 'Usuarios', ''], filas);
  adminEngancharAcciones('admin-roles-tabla', function (accion, dato) {
    if (accion === 'editar-rol') abrirEditorRolAdmin(dato);
  });
  adminReaplicarPermisos();
}

function abrirFormNuevoRolAdmin() {
  var cont = document.getElementById('admin-rol-form');
  if (!cont) return;
  _admRolEditando = null;
  cont.innerHTML =
    '<div class="admin-panel"><h4>Nuevo rol</h4>' +
      '<div class="admin-campo"><label>Identificador (sin espacios)</label>' +
        '<input type="text" id="admin-rol-id" placeholder="deposito" data-tooltip="adminRolId"></div>' +
      '<div class="admin-campo"><label>Nombre</label>' +
        '<input type="text" id="admin-rol-nombre" placeholder="Depósito" data-tooltip="adminRolNombre"></div>' +
      '<div class="admin-campo"><label>Descripción</label>' +
        '<input type="text" id="admin-rol-descripcion" data-tooltip="adminRolDescripcion"></div>' +
      '<div class="admin-toolbar" style="margin-top:12px">' +
        adminBotonAccion('Crear', 'crear', null, 'admin-btn-primario', null, 'adminRolCrear') +
        adminBotonAccion('Cancelar', 'cancelar', null, '') +
      '</div></div>';
  adminEngancharAcciones('admin-rol-form', function (accion) {
    if (accion === 'crear') crearRolAdmin();
    else if (accion === 'cancelar') cerrarEditorRolAdmin();
  });
}

async function crearRolAdmin() {
  if (_admRolGuardando) return;                  // un doble click no manda dos altas
  var id = ((document.getElementById('admin-rol-id') || {}).value || '').trim().toLowerCase();
  var nombre = ((document.getElementById('admin-rol-nombre') || {}).value || '').trim();
  var descripcion = ((document.getElementById('admin-rol-descripcion') || {}).value || '').trim();
  if (!id || !nombre) { toastError('El identificador y el nombre son obligatorios'); return; }
  _admRolGuardando = true;
  try {
    var alta = { id: id, nombre: nombre, descripcion: descripcion };
    // Alta: el rol nace sin permisos, así que `permisos: []` es el valor
    // correcto (y el backend también defaultea a []). Igual se manda solo con el
    // catálogo pintado, así la regla "sin catálogo no se manda `permisos`" vale
    // para los tres cuerpos que arma esta vista.
    if (_admRolPuedeEditarPermisos) alta.permisos = [];
    var r = await adminFetch('/api/admin/roles', { method: 'POST', body: alta });
    if (!r.ok) { toastError(r.error); _admRolRefrescarChipSi503(r); return; }
    toastSuccess('Rol creado: ' + id + '. Ahora tildale permisos.');
    await cargarVistaRolesAdmin();
    abrirEditorRolAdmin(id);
  } finally {
    _admRolGuardando = false;
  }
}

function abrirEditorRolAdmin(rolId) {
  var cont = document.getElementById('admin-rol-form');
  if (!cont) return;
  var rol = _admListaRoles.filter(function (r) { return r.id === rolId; })[0];
  if (!rol) { toastError('El rol ya no existe'); return; }
  _admRolEditando = rolId;
  var permisosActuales = rol.permisos || [];
  var esSuperadmin = rolId === 'superadmin';
  // Dos motivos para no ofrecer Guardar: el backend rechaza editar `superadmin`
  // (D5) y sin catálogo de permisos el PUT no puede mandar `permisos` porque los
  // borraría. En los dos casos el editor queda en solo lectura (chips + Cerrar).
  var puedeGuardar = !esSuperadmin && _admRolPuedeEditarPermisos;
  var avisos = '';
  if (esSuperadmin) {
    avisos = '<div class="admin-aviso">El rol <b>superadmin</b> no se puede editar desde el panel ' +
      '(el backend también lo rechaza): es el que garantiza que siempre haya un administrador.</div>';
  }
  var cuerpoPermisos;
  if (puedeGuardar) {
    // Grupos plegables (con el estado recordado por grupo en el navegador): el
    // armado vive en `adminGrupoPlegable` (admin/index.js) para que el editor de
    // roles y el de usuarios se comporten igual.
    cuerpoPermisos = Object.keys(_admPermisosGrupos).sort().map(function (grupo) {
      return adminGrupoPlegable(grupo, _admPermisosGrupos[grupo], permisosActuales,
                                'adminRolPermisos', 'adminRolPermisos');
    }).join('');
  } else if (esSuperadmin) {
    cuerpoPermisos = _admRolChipsPermisos(permisosActuales);   // el motivo ya está arriba
  } else {
    // Sin catálogo el motivo y los permisos actuales van DENTRO del campo, que es
    // donde estaría el editor (mismo patrón que `_htmlEditorSoloLectura` de
    // usuarios.js): un campo vacío se leería como "este rol no tiene permisos".
    cuerpoPermisos = '<div class="admin-aviso">Sin permiso <b>admin.permisos.asignar</b>: no se ' +
      'pueden editar los permisos del rol. Se conservan los actuales: ' +
      _admRolChipsPermisos(permisosActuales) + '</div>';
  }
  cont.innerHTML =
    '<div class="admin-panel"><h4>' + (puedeGuardar ? 'Permisos del rol ' : 'Rol ') +
      escapeHTML(rolId) + '</h4>' + avisos +
      '<div class="admin-campo"><label>Nombre</label><input type="text" id="admin-rol-nombre"' +
        ' data-tooltip="adminRolNombre"' +
        (puedeGuardar ? '' : ' disabled') + ' value="' + escapeHTML(rol.nombre || '') + '"></div>' +
      '<div class="admin-campo"><label>Descripción</label><input type="text" id="admin-rol-descripcion"' +
        ' data-tooltip="adminRolDescripcion"' +
        (puedeGuardar ? '' : ' disabled') + ' value="' + escapeHTML(rol.descripcion || '') + '"></div>' +
      '<div class="admin-campo"><label>' +
        (puedeGuardar ? 'Permisos (' + permisosActuales.length + ' tildados)'
                      : 'Permisos actuales (' + permisosActuales.length + ')') +
        '</label>' +
        (puedeGuardar
          ? '<div class="admin-toolbar" style="margin:0 0 8px">' +
              adminBotonAccion('Colapsar / Expandir todo', 'plegar-todos', null, '', null, 'adminGrupoPlegarTodos') +
            '</div>'
          : '') +
        cuerpoPermisos + '</div>' +
      '<div class="admin-toolbar" style="margin-top:12px">' +
        (puedeGuardar ? adminBotonAccion('Guardar', 'guardar', null, 'admin-btn-primario', null, 'adminRolGuardar') : '') +
        adminBotonAccion('Cerrar', 'cancelar', null, '') +
      '</div></div>';
  adminEngancharAcciones('admin-rol-form', function (accion, dato) {
    if (accion === 'guardar') guardarRolAdmin();
    else if (accion === 'cancelar') cerrarEditorRolAdmin();
    else if (accion === 'tildar-grupo') tildarGrupoRolAdmin(dato);
    else if (accion === 'plegar-todos') adminPlegarTodosGrupos();
  });
  adminEngancharPlegado('admin-rol-form');
  adminReaplicarPermisos();
  if (typeof cont.scrollIntoView === 'function') cont.scrollIntoView({ block: 'nearest' });
}

function tildarGrupoRolAdmin(grupo) {
  if (!_admRolPuedeEditarPermisos) return;      // sin checkboxes no hay nada que tildar
  var permisos = (_admPermisosGrupos[grupo] || []).map(function (p) {
    return (p && p.valor !== undefined) ? p.valor : p;
  });
  var casillas = Array.prototype.filter.call(
    document.querySelectorAll('[data-admin-multi="adminRolPermisos"]'),
    function (c) { return permisos.indexOf(c.value) >= 0; });
  var tildarTodos = casillas.some(function (c) { return !c.checked; });
  casillas.forEach(function (c) { c.checked = tildarTodos; });
}

function cerrarEditorRolAdmin() {
  var cont = document.getElementById('admin-rol-form');
  if (cont) cont.innerHTML = '';
  _admRolEditando = null;
}

async function guardarRolAdmin() {
  if (!_admRolEditando || _admRolGuardando) return;
  // Segunda barrera (el botón Guardar no se pinta en estos dos casos): ningún
  // camino puede mandar un PUT que borre los permisos del rol ni uno que el
  // backend va a rechazar por ser superadmin.
  if (_admRolEditando === 'superadmin') return;
  var inputNombre = document.getElementById('admin-rol-nombre');
  var inputDescripcion = document.getElementById('admin-rol-descripcion');
  if (!inputNombre || !inputDescripcion) return;   // el formulario ya no está en pantalla
  _admRolGuardando = true;
  try {
    var cuerpo = {
      nombre: (inputNombre.value || '').trim(),
      descripcion: (inputDescripcion.value || '').trim()
    };
    // Solo si el catálogo se pintó: omitir `permisos` los preserva (ver cabecera).
    if (_admRolPuedeEditarPermisos) cuerpo.permisos = adminLeerMulti('adminRolPermisos');
    var r = await adminFetch('/api/admin/roles/' + encodeURIComponent(_admRolEditando),
                             { method: 'PUT', body: cuerpo });
    if (!r.ok) { toastError(r.error); _admRolRefrescarChipSi503(r); return; }
    var detalle = ('permisos' in cuerpo)
      ? ' (' + cuerpo.permisos.length + ' permisos)'
      : ' (sin tocar los permisos)';
    toastSuccess('Rol ' + _admRolEditando + ' actualizado' + detalle);
    cerrarEditorRolAdmin();
    await cargarVistaRolesAdmin();
  } finally {
    _admRolGuardando = false;
  }
}

window.cargarVistaRolesAdmin = cargarVistaRolesAdmin;
window.abrirEditorRolAdmin = abrirEditorRolAdmin;
window.abrirFormNuevoRolAdmin = abrirFormNuevoRolAdmin;
window.cerrarEditorRolAdmin = cerrarEditorRolAdmin;
window.guardarRolAdmin = guardarRolAdmin;
window.crearRolAdmin = crearRolAdmin;
window.tildarGrupoRolAdmin = tildarGrupoRolAdmin;

console.log('✅ admin/roles.js cargado');
