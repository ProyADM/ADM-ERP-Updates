// ============================================================
// ADMIN - VISTA ESTADO DEL ALMACÉN (spec §5.3)
// ============================================================
// Celdas de `adminTabla`: las de datos van PELADAS (adminTabla las escapa) y las
// de markup van como `{html: '...'}` con los datos ya pasados por escapeHTML()
// acá. Nunca al revés: el default de adminTabla es escapar. En particular, en la
// tabla de conflictos el nombre, la fecha y los bytes son DATOS (van crudos,
// con escapeHTML quedarían doble escapados en pantalla) y la celda del botón
// "Ver" es MARKUP (`{html}`, porque `adminBotonAccion` ya escapa lo suyo).
//
// El orden de la lista de conflictos lo decide el SERVIDOR ordenando por NOMBRE
// de archivo (descendente), no por `mtime`: la columna Fecha es informativa y no
// tiene por qué coincidir con el orden de las filas.
//
// El "Importar respaldo" es por RUTA DEL DISCO DEL SERVIDOR: el navegador manda
// el texto de la ruta y el backend la abre con `os.path.exists` + `importar` en
// el disco de la máquina donde corre el ERP (no en el de quien mira el panel).
// Esa ruta sale de "Exportar respaldo", que deja el archivo en `data/` y
// devuelve la ruta absoluta en `datos.archivo`.

var _admEstadoConflictos = [];
// `''` = la consulta de conflictos se pudo hacer (y `_admEstadoConflictos` es la
// verdad); con texto = NO se pudo preguntar al almacén. Es la diferencia entre
// "no hay conflictos" (respuesta ok y vacía) y "no sé": sin este estado, un 403,
// un 500 o una caída de red mostraban la lista vacía y la vista afirmaba que la
// última sincronización no descartó nada — una mentira en la pantalla que existe
// justamente para exponer los cambios descartados.
var _admEstadoConflictosError = '';

async function cargarVistaEstadoAdmin() {
  adminAviso('admin-estado', 'Consultando el almacén…');
  var rE = await adminFetch('/api/admin/config/estado');
  if (!rE.ok) {
    // Un 503 (también el de un GET) no puede dejar el chip verde mintiendo
    // sobre el almacén. Chequeo local a propósito: los scripts del panel
    // comparten un solo scope global y no se agrega un helper nuevo.
    if (rE.codigo === 503) refrescarChipAdmin();
    adminAviso('admin-estado', rE.error, 'error');
    return;
  }
  var estado = rE.datos || {};
  var rC = await adminFetch('/api/admin/config/conflictos');
  if (rC.codigo === 503) refrescarChipAdmin();
  if (rC.ok) {
    _admEstadoConflictos = (rC.datos && rC.datos.archivos) || [];
    _admEstadoConflictosError = '';
  } else {
    _admEstadoConflictos = [];
    _admEstadoConflictosError = rC.error || ('Error ' + rC.codigo);
  }
  renderVistaEstadoAdmin(estado);
  pintarChipAdmin(estado.modo, estado);
}

function _admEstadoDato(etiqueta, valor) {
  return '<div class="admin-dato"><b>' + escapeHTML(etiqueta) + '</b><span>' +
         escapeHTML(valor === null || valor === undefined || valor === '' ? '—' : valor) +
         '</span></div>';
}

function renderVistaEstadoAdmin(estado) {
  var body = adminBody('admin-estado');
  if (!body) return;
  var htmlConflictos;
  if (_admEstadoConflictosError) {
    // Ni "no hay" ni "hay": no se pudo preguntar. El aviso neutro lleva el
    // error, y la frase afirmativa NO se emite nunca en este caso.
    htmlConflictos = '<div class="admin-aviso admin-aviso-error">No se pudieron consultar los ' +
                     'conflictos del almacén: ' + escapeHTML(_admEstadoConflictosError) + '</div>';
  } else if (!_admEstadoConflictos.length) {
    htmlConflictos = '<div class="admin-aviso">No hay conflictos: la última sincronización no ' +
                     'descartó ningún cambio.</div>';
  } else {
    htmlConflictos = '<div id="admin-conflictos-tabla"></div>';
  }
  body.innerHTML =
    '<div class="admin-panel"><h4>Almacén</h4>' +
      _admEstadoDato('Modo', ADMIN_CHIP_TEXTO[estado.modo] || estado.modo) +
      _admEstadoDato('Ruta', estado.ruta) +
      _admEstadoDato('Sello', estado.sello) +
      _admEstadoDato('Último escritor', estado.escritor) +
      _admEstadoDato('Última escritura', estado.ultima_escritura) +
      _admEstadoDato('Última lectura', estado.ultima_lectura) +
      (estado.mensaje ? '<div class="admin-aviso">' + escapeHTML(estado.mensaje) + '</div>' : '') +
      '<div class="admin-toolbar" style="margin-top:12px">' +
        adminBoton('Traer cambios ahora', 'recargarAlmacenAdmin()', '', 'admin.acceso') +
        adminBoton('Exportar respaldo', 'exportarConfigAdmin()', '', 'admin.backup') +
      '</div></div>' +
    '<div class="admin-panel"><h4>Conflictos pendientes (' +
      (_admEstadoConflictosError ? '—' : _admEstadoConflictos.length) + ')</h4>' +
      htmlConflictos + '</div>' +
    '<div class="admin-panel"><h4>Importar respaldo</h4>' +
      '<div class="admin-aviso">El respaldo se lee del disco de la PC donde corre el ERP (no del ' +
        'navegador): pegá la ruta que devolvió «Exportar respaldo», por ejemplo ' +
        '<code>data\\config_export_20260912_190000.json</code>.</div>' +
      '<div class="admin-campo"><label>Ruta del respaldo</label>' +
        '<input type="text" id="admin-importar-ruta" placeholder="data\\config_export_....json"></div>' +
      '<div class="admin-toolbar">' +
        adminBoton('Importar', 'importarConfigAdmin()', 'admin-btn-peligro', 'admin.restaurar') +
      '</div></div>';
  if (_admEstadoConflictos.length) {
    // Orden y contenido tal como los manda el servidor (por nombre de archivo):
    // la vista no reordena ni asume que `fecha` va en orden.
    document.getElementById('admin-conflictos-tabla').innerHTML = adminTabla(
      ['Archivo', 'Fecha', 'Bytes', ''],
      _admEstadoConflictos.map(function (c) {
        return [c.nombre,
                (c.fecha || '').replace('T', ' ').slice(0, 19),
                String(c.bytes),
                { html: adminBotonAccion('Ver', 'ver-conflicto', c.nombre, '', 'admin.acceso') }];
      }));
    adminEngancharAcciones('admin-conflictos-tabla', function (accion, dato) {
      if (accion === 'ver-conflicto') verConflictoAdmin(dato);
    });
  }
  adminReaplicarPermisos();
}

async function recargarAlmacenAdmin() {
  var r = await adminFetch('/api/admin/config/recargar', { method: 'POST' });
  if (!r.ok) {
    toastError(r.error);
    if (r.codigo === 503) refrescarChipAdmin();
    return;
  }
  var estado = (r.datos && r.datos.estado) || {};
  pintarChipAdmin(estado.modo, estado);
  toastSuccess(r.datos && r.datos.recargado
    ? 'Se trajeron los cambios del almacén'
    : 'No había cambios nuevos que traer');
  renderVistaEstadoAdmin(estado);
}

async function exportarConfigAdmin() {
  var r = await adminFetch('/api/admin/config/exportar', { method: 'POST' });
  if (!r.ok) {
    toastError(r.error);
    if (r.codigo === 503) refrescarChipAdmin();
    return;
  }
  var archivo = (r.datos && r.datos.archivo) || '';
  var copiada = false;
  if (archivo && navigator.clipboard) {
    try { await navigator.clipboard.writeText(archivo); copiada = true; } catch (e) { /* opcional */ }
  }
  // El aviso dice la verdad: si no se pudo copiar (o el navegador no expone
  // `navigator.clipboard`), no se anuncia una copia que no ocurrió.
  toastSuccess('Respaldo escrito en: ' + archivo +
               (copiada ? ' (ruta copiada al portapapeles)' : ''));
}

async function importarConfigAdmin() {
  var ruta = ((document.getElementById('admin-importar-ruta') || {}).value || '').trim();
  if (!ruta) { toastError('Pegá la ruta del respaldo'); return; }
  if (!confirm('¿Importar ' + ruta + '? Reemplaza los usuarios y los roles del almacén.')) return;
  var r = await adminFetch('/api/admin/config/importar', { method: 'POST', body: { archivo: ruta } });
  if (!r.ok) {
    toastError(r.error);
    if (r.codigo === 503) refrescarChipAdmin();
    return;
  }
  toastSuccess('Importado: ' + (r.datos.usuarios || 0) + ' usuarios y ' +
               (r.datos.roles || 0) + ' roles');
  await cargarVistaEstadoAdmin();
}

async function verConflictoAdmin(nombre) {
  var r = await adminFetch('/api/admin/config/conflictos/' + encodeURIComponent(nombre));
  if (!r.ok) {
    toastError(r.error);
    if (r.codigo === 503) refrescarChipAdmin();
    return;
  }
  var detalle = document.getElementById('admin-conflicto-detalle');
  if (!detalle) {
    detalle = document.createElement('pre');
    detalle.id = 'admin-conflicto-detalle';
    detalle.className = 'admin-panel';
    var body = adminBody('admin-estado');
    if (body) body.appendChild(detalle);
  }
  // `textContent` (no innerHTML): el contenido del conflicto es un dato del
  // almacén y se muestra tal cual, sin interpretarlo como HTML.
  detalle.textContent = nombre + '\n\n' + JSON.stringify(r.datos.contenido, null, 2);
}

window.cargarVistaEstadoAdmin = cargarVistaEstadoAdmin;
window.recargarAlmacenAdmin = recargarAlmacenAdmin;
window.exportarConfigAdmin = exportarConfigAdmin;
window.importarConfigAdmin = importarConfigAdmin;
window.verConflictoAdmin = verConflictoAdmin;

console.log('✅ admin/estado.js cargado');
