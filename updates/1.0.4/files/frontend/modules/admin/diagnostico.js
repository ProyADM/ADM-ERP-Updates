// ============================================================
// ADMIN - VISTA DIAGNÓSTICO (16/09/2026)
// ============================================================
// Responde "¿por qué no anda / no actualiza?". Tres bloques, en orden de
// utilidad:
//   1. Estado actual  → chequeos en vivo (SQL por base, canal de updates,
//                       almacén de usuarios, permisos de escritura, disco).
//   2. Errores recientes → lo que la app registró en logs/app.log, agrupado.
//   3. Accesos rechazados → resumen (la vista completa vive en su pestaña).
//
// Todo lo que entra a `innerHTML` sale por escapeHTML: los mensajes de error y
// los detalles técnicos son datos del servidor y del log, no texto propio.

var _admDiag = null;
var _admDiagFiltro = '';
var _admDiagHoras = 24;
var _admDiagApp = null;   // resultado de comprobar la app viva

// Comprueba la APP VIVA (no solo la base): pide un endpoint que necesita SQL de
// verdad. Hace falta porque varios endpoints degradan en silencio —el dashboard
// devuelve 200 con datos vacíos cuando el SQL no responde— así que "la app
// responde" no alcanza como señal.
async function _admDiagProbarAppViva() {
  try {
    var r = await fetch('/api/stock', { credentials: 'same-origin', cache: 'no-store' });
    if (!r.ok) return { ok: false, motivo: 'la app respondió ' + r.status };
    var datos = await r.json();
    if (!Array.isArray(datos)) return { ok: false, motivo: 'respuesta inesperada del servidor' };
    if (!datos.length) {
      return { ok: false, vacio: true,
               motivo: 'la consulta volvió vacía: puede ser la base sin responder o sin stock cargado' };
    }
    return { ok: true, filas: datos.length };
  } catch (e) {
    return { ok: false, motivo: 'no se pudo consultar la app: ' + (e && e.message ? e.message : e) };
  }
}

function _admDiagChip(estado, texto) {
  // estado: 'ok' | 'warn' | 'err' | 'gris'
  return '<span class="admin-chip admin-chip-' + estado + '" style="margin:0">' +
         escapeHTML(texto) + '</span>';
}

function _admDiagChipDe(ok, textoOk, textoFalla) {
  if (ok === true) return _admDiagChip('ok', textoOk);
  if (ok === false) return _admDiagChip('err', textoFalla);
  return _admDiagChip('gris', 'sin dato');
}

// Fila "Aplicación": la prueba contra la app viva (ver `_admDiagProbarAppViva`).
function _admDiagBloqueApp() {
  var app = _admDiagApp;
  if (!app) return '';
  var txt = app.ok ? ('responde y devuelve datos (' + app.filas + ' filas)') : app.motivo;
  return '<div class="admin-dato"><b>Aplicación</b><span>' +
         _admDiagChipDe(app.ok, txt, txt) + '</span></div>';
}

// Fila "Versión": qué versión corre ESTA PC y si está al día. Antes la versión no
// se veía en ningún lado de la interfaz (solo se usaba internamente para decidir
// si había actualización), así que no había forma de saber qué tenía cada PC.
function _admDiagBloqueVersion(canal) {
  canal = canal || {};
  var instalada = canal.version_instalada;
  if (!instalada) return '';
  var hayNovedad = !!canal.hay_novedad;
  var remota = canal.version_remota;
  var texto, chip;
  if (!canal.ok) {
    texto = 'v' + instalada + ' · sin poder consultar el canal';
    chip = 'warn';
  } else if (hayNovedad) {
    texto = 'v' + instalada + ' · hay ' + (remota ? 'v' + remota : 'una versión nueva');
    chip = 'warn';
  } else {
    texto = 'v' + instalada + ' · al día';
    chip = 'ok';
  }
  return '<div class="admin-dato"><b>Versión</b><span>' +
         _admDiagChip(chip, texto) + '</span></div>';
}

async function cargarVistaDiagnosticoAdmin() {
  adminAviso('admin-diagnostico', 'Comprobando el sistema… (puede tardar unos segundos)');
  var r = await adminFetch('/api/admin/diagnostico');
  if (!r.ok) {
    if (r.codigo === 503) refrescarChipAdmin();
    adminAviso('admin-diagnostico', r.error, 'error');
    return;
  }
  _admDiag = r.datos || {};
  _admDiagApp = await _admDiagProbarAppViva();
  renderVistaDiagnosticoAdmin();
}

function renderVistaDiagnosticoAdmin() {
  var body = adminBody('admin-diagnostico');
  if (!body) return;
  // Al abrir la pestaña, lo ya visto deja de contar como "nuevo": la insignia
  // del menú lateral se limpia sola.
  _admDiagMarcarVisto();
  pintarBadgeDiagnosticoAdmin(0);
  var d = _admDiag || {};
  var sql = d.sql || {};
  var bases = sql.bases || [];
  var canal = d.canal || {};
  var alm = d.almacen || {};
  var permisos = d.permisos || [];
  var disco = d.disco || [];

  // --- bloque 1: estado actual ---
  var filas = bases.map(function (b) {
    var detalle = b.ok
      ? (b.ms + ' ms')
      : ((b.causa || 'falla') + (b.detalle ? ' · ' + b.detalle : ''));
    return [
      b.etiqueta || b.base,
      b.servidor || '—',
      { html: _admDiagChipDe(b.ok, 'OK', 'sin respuesta') },
      detalle
    ];
  });

  var canalTexto = canal.ok
    ? (canal.hay_novedad ? ('actualización ' + (canal.version_remota || '') + ' disponible') : 'al día')
    : 'no se pudo consultar';
  var canalDetalle = canal.ok
    ? (canal.canal || '')
    : (canal.motivo || 'sin Internet o canal inaccesible');

  var almModo = alm.modo || 'desconocido';
  var almChip = (almModo === 'central') ? 'ok' : (almModo === 'degradado' ? 'err' : 'warn');

  var bloque1 =
    '<div class="admin-panel"><h4>Estado actual</h4>' +
      '<div class="admin-toolbar" style="margin-bottom:10px">' +
        adminBotonAccion('Volver a comprobar', 'diag-refrescar', null, 'admin-btn-primario', null, 'adminDiagRefrescar') +
        '<span class="admin-grupo-cuenta">Generado: ' + escapeHTML(d.generado || '—') +
          (d.cacheado ? ' (en caché)' : '') + '</span>' +
      '</div>' +
      (bases.length
        ? adminTabla(['Base', 'Servidor', 'Respuesta', 'Detalle'], filas)
        : '<div class="admin-aviso">Tu usuario no tiene bases habilitadas para comprobar.</div>') +
      '<div class="admin-grupo">' +
        _admDiagBloqueApp() +
        _admDiagBloqueVersion(canal) +
        '<div class="admin-dato"><b>Actualizaciones</b>' +
          '<span>' + _admDiagChip(canal.ok ? (canal.hay_novedad ? 'warn' : 'ok') : 'err', canalTexto) +
          ' <span class="admin-check-pie">' + escapeHTML(canalDetalle) + '</span></span></div>' +
        '<div class="admin-dato"><b>Almacén de usuarios</b>' +
          '<span>' + _admDiagChip(almChip, almModo) +
          ' <span class="admin-check-pie">' + escapeHTML(alm.ruta || '') +
          (alm.sello ? ' · sello ' + escapeHTML(String(alm.sello).slice(0, 8)) : '') + '</span></span></div>' +
        (alm.mensaje ? '<div class="admin-aviso" style="margin-top:8px">' + escapeHTML(alm.mensaje) + '</div>' : '') +
        permisos.map(function (p) {
          var pistas = (p.causas || []).map(function (c) { return '· ' + c; }).join('<br>');
          return '<div class="admin-dato"><b>Escritura: ' + escapeHTML(p.etiqueta) + '</b>' +
            '<span>' + _admDiagChipDe(p.ok, 'se puede escribir', 'NO se puede escribir') +
            '<br><span class="admin-check-pie">' + escapeHTML(p.ruta || '') + ' — ' + escapeHTML(p.motivo || '') + '</span>' +
            (pistas ? '<br><span class="admin-check-pie">' + pistas + '</span>' : '') +
            (p.residuo ? '<br><span class="admin-check-pie">Quedó un archivo de prueba que no se pudo borrar.</span>' : '') +
            '</span></div>';
        }).join('') +
        disco.map(function (x) {
          var txt = x.error ? ('error: ' + x.error)
                            : (x.libre_mb + ' MB libres de ' + x.total_mb + ' MB (' + x.libre_pct + '%)');
          var chip = x.error ? 'err' : (x.libre_pct !== null && x.libre_pct < 10 ? 'warn' : 'ok');
          return '<div class="admin-dato"><b>Disco: ' + escapeHTML(x.etiqueta) + '</b>' +
            '<span>' + _admDiagChip(chip, txt) + '</span></div>';
        }).join('') +
      '</div>' +
    '</div>';

  // --- bloque 2: errores recientes ---
  var errores = d.errores || [];
  var t = _admDiagFiltro.trim().toLowerCase();
  var visibles = errores.filter(function (e) {
    if (!t) return true;
    return ((e.categoria || '') + ' ' + (e.mensaje || '') + ' ' + (e.logger || ''))
      .toLowerCase().indexOf(t) >= 0;
  });

  var bloque2 =
    '<div class="admin-panel"><h4>Errores recientes del sistema (' + errores.length + ')</h4>' +
      '<div class="admin-toolbar">' +
        '<input type="text" id="admin-diag-buscar" data-tooltip="adminDiagBuscar" ' +
          'placeholder="Filtrar por tipo de error o mensaje…" value="' + escapeHTML(_admDiagFiltro) + '">' +
        adminBotonAccion('Recargar', 'diag-errores', null, '', null, 'adminDiagRecargar') +
        '<span class="admin-grupo-cuenta">últimas ' + _admDiagHoras + ' h · ' +
          escapeHTML(String((d.log || {}).lineas_leidas || 0)) + ' líneas leídas</span>' +
      '</div>' +
      (visibles.length ? adminTabla(
        ['Veces', 'Última', 'Nivel', 'Qué', 'Mensaje', ''],
        visibles.map(function (e) {
          return [
            String(e.veces || 0),
            (e.ultima || '').replace('T', ' '),
            e.nivel || '',
            e.categoria || '',
            (e.mensaje || '').split('\n')[0],
            { html: adminBotonAccion('Detalle', 'diag-ver', e.categoria + ' ||| ' + (e.mensaje || ''), '', null, 'adminDiagDetalle') }
          ];
        }))
        : '<div class="admin-aviso">No hay errores ni advertencias en el período. ' +
          'Si algo no anda y acá no aparece nada, usá "Volver a comprobar".</div>') +
    '</div>';

  // --- bloque 3: accesos rechazados (resumen) ---
  var bloque3 =
    '<div class="admin-panel"><h4>Accesos rechazados</h4>' +
      '<div class="admin-aviso">Los intentos de ingreso rechazados (usuario no dado de alta, ' +
      'desactivado o bloqueado) tienen su propia pestaña, con el alta en un clic: ' +
      '<b>🚫 Accesos rechazados</b>.</div>' +
    '</div>';

  body.innerHTML = bloque1 + bloque2 + bloque3;

  // Delega los botones del bloque 1 y 2 (el detalle tiene su propio contenedor).
  adminEngancharAcciones('admin-diagnostico', function (accion, dato) {
    if (accion === 'diag-refrescar') recargarDiagnosticoAdmin();
    else if (accion === 'diag-errores') recargarErroresDiagnosticoAdmin();
    else if (accion === 'diag-ver') verDetalleDiagnosticoAdmin(dato);
  });

  var buscar = document.getElementById('admin-diag-buscar');
  if (buscar) {
    buscar.addEventListener('input', function () {
      _admDiagFiltro = this.value;
      renderVistaDiagnosticoAdmin();
      var el = document.getElementById('admin-diag-buscar');
      if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }
    });
  }
  adminReaplicarPermisos();
}

async function recargarDiagnosticoAdmin() {
  var r = await adminFetch('/api/admin/diagnostico');
  if (!r.ok) { toastError(r.error); return; }
  _admDiag = r.datos || {};
  renderVistaDiagnosticoAdmin();
  toastSuccess('Chequeos actualizados');
}

async function recargarErroresDiagnosticoAdmin() {
  var r = await adminFetch('/api/admin/diagnostico/errores?horas=' + _admDiagHoras);
  if (!r.ok) { toastError(r.error); return; }
  _admDiag = _admDiag || {};
  _admDiag.errores = (r.datos && r.datos.errores) || [];
  renderVistaDiagnosticoAdmin();
  toastSuccess('Errores recargados');
}

// Muestra el detalle técnico del grupo elegido (el mismo texto que se copia).
function verDetalleDiagnosticoAdmin(dato) {
  if (!dato) return;
  var partes = String(dato).split(' ||| ');
  var categoria = partes[0] || '';
  var mensaje = partes.slice(1).join(' ||| ');
  var errores = (_admDiag || {}).errores || [];
  var grupo = null;
  for (var i = 0; i < errores.length; i++) {
    if ((errores[i].categoria || '') === categoria &&
        (errores[i].mensaje || '') === mensaje) { grupo = errores[i]; break; }
  }
  var detalle = (grupo && grupo.detalle) ? grupo.detalle : mensaje;
  var cont = document.getElementById('admin-diag-detalle');
  if (!cont) {
    cont = document.createElement('div');
    cont.id = 'admin-diag-detalle';
    cont.className = 'admin-panel';
    var body = adminBody('admin-diagnostico');
    if (body) body.appendChild(cont);
  }
  cont.innerHTML =
    '<h4>Detalle técnico: ' + escapeHTML(categoria) + '</h4>' +
    '<div class="admin-toolbar">' +
      adminBotonAccion('Copiar detalle', 'diag-copiar', detalle, '', null, 'adminDiagCopiar') +
      adminBotonAccion('Cerrar', 'diag-cerrar', null, '') +
    '</div>' +
    '<pre style="white-space:pre-wrap; word-break:break-word; font-size:11.5px; ' +
      'background:var(--surface-2); border:1px solid var(--border); border-radius:var(--radius-sm); ' +
      'padding:10px; max-height:320px; overflow:auto">' + escapeHTML(detalle) + '</pre>';
  adminEngancharAcciones('admin-diag-detalle', function (accion, dato) {
    if (accion === 'diag-copiar') copiarDetalleDiagnosticoAdmin(dato);
    else if (accion === 'diag-cerrar') cerrarDetalleDiagnosticoAdmin();
  });
}

function copiarDetalleDiagnosticoAdmin(texto) {
  var listo = function () { toastSuccess('Detalle copiado al portapapeles'); };
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(texto).then(listo, function () { _admDiagSeleccionar(texto); });
      return;
    }
  } catch (e) { /* sigue el plan B */ }
  _admDiagSeleccionar(texto);
}

// Plan B (sin permisos de portapapeles): se selecciona el texto para copiar a mano.
function _admDiagSeleccionar(texto) {
  var cont = document.getElementById('admin-diag-detalle');
  if (cont) {
    var pre = cont.querySelector('pre');
    if (pre && window.getSelection) {
      var rango = document.createRange();
      rango.selectNodeContents(pre);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(rango);
      toastInfo('Texto seleccionado: copialo con Ctrl+C');
      return;
    }
  }
  toastWarning('No se pudo copiar automáticamente');
}

function cerrarDetalleDiagnosticoAdmin() {
  var cont = document.getElementById('admin-diag-detalle');
  if (cont) cont.remove();
}

// ============================================================
// INSIGNIA DE ALERTAS EN EL MENÚ LATERAL
// ============================================================
// Cuenta PROBLEMAS NUEVOS (grupos de error del log) desde la última vez que esta
// PC abrió la pestaña, así el contador se limpia solo al entrar a mirar. No
// sondea el SQL: consulta un endpoint que solo lee el log.
//
// Visibilidad: la fila del menú lleva `data-perm="admin.diagnostico"`, así que
// `aplicarPermisosUI` la oculta —y con ella la insignia— a quien no tenga el
// permiso. Hoy ese permiso lo tienen el superadmin y el administrador.

var _admDiagBadgeTimer = null;
var _ADM_DIAG_VISTO = 'sidesys_diag_visto';

function _admDiagLeerVisto() {
  try { return window.localStorage.getItem(_ADM_DIAG_VISTO) || null; } catch (e) { return null; }
}

function _admDiagMarcarVisto() {
  try {
    var ahora = new Date();
    var p = function (n) { return (n < 10 ? '0' : '') + n; };
    // Formato 'YYYY-MM-DDTHH:MM:SS' (hora local): el backend lo parsea igual.
    window.localStorage.setItem(_ADM_DIAG_VISTO,
      ahora.getFullYear() + '-' + p(ahora.getMonth() + 1) + '-' + p(ahora.getDate()) +
      'T' + p(ahora.getHours()) + ':' + p(ahora.getMinutes()) + ':' + p(ahora.getSeconds()));
  } catch (e) { /* preferencia de UI: si no se puede guardar, no pasa nada */ }
}

// Pinta (o limpia) la insignia en la fila del menú lateral.
// El badge va DENTRO del span del texto (no como hermano del `.drawer-tab`):
// ese contenedor es `display:flex` con `space-between`, así que un hijo extra
// se llevaría el texto a los extremos — el mismo motivo por el que el ícono ⓘ
// de ayuda necesita el texto envuelto.
function pintarBadgeDiagnosticoAdmin(cantidad) {
  var tab = document.querySelector('.drawer-tab[data-tab="admin-diagnostico"]');
  if (!tab) return;
  var previo = tab.querySelector('.badge-alerta');
  if (previo) previo.remove();
  if (!cantidad || cantidad <= 0) return;
  var b = document.createElement('span');
  b.className = 'badge-alerta';
  b.textContent = cantidad > 99 ? '99+' : String(cantidad);
  b.title = cantidad + ' problema(s) nuevo(s) en el sistema';
  var destino = tab.querySelector('.drawer-tab-texto') || tab;
  destino.appendChild(b);
}

async function refrescarBadgeDiagnosticoAdmin() {
  // Sin sesión (pantalla de login) no se consulta nada.
  try { if (typeof obtenerUsuarioActual !== 'function' || !obtenerUsuarioActual()) return; }
  catch (e) { return; }
  var desde = _admDiagLeerVisto();
  var url = '/api/admin/diagnostico/alerta' + (desde ? ('?desde=' + encodeURIComponent(desde)) : '');
  var r = await adminFetch(url);
  if (!r.ok) {
    // 403 = este usuario no tiene la pestaña: no corresponde insignia.
    if (r.codigo === 403) pintarBadgeDiagnosticoAdmin(0);
    return;
  }
  pintarBadgeDiagnosticoAdmin((r.datos || {}).nuevos || 0);
}

function iniciarBadgeDiagnosticoAdmin() {
  refrescarBadgeDiagnosticoAdmin();
  if (_admDiagBadgeTimer) clearInterval(_admDiagBadgeTimer);
  // Cada 5 minutos, igual que el chequeo de notificaciones de la app.
  _admDiagBadgeTimer = setInterval(refrescarBadgeDiagnosticoAdmin, 300000);
}

window.iniciarBadgeDiagnosticoAdmin = iniciarBadgeDiagnosticoAdmin;
window.refrescarBadgeDiagnosticoAdmin = refrescarBadgeDiagnosticoAdmin;
window.pintarBadgeDiagnosticoAdmin = pintarBadgeDiagnosticoAdmin;

window.cargarVistaDiagnosticoAdmin = cargarVistaDiagnosticoAdmin;
window.renderVistaDiagnosticoAdmin = renderVistaDiagnosticoAdmin;
window.recargarDiagnosticoAdmin = recargarDiagnosticoAdmin;
window.recargarErroresDiagnosticoAdmin = recargarErroresDiagnosticoAdmin;
window.verDetalleDiagnosticoAdmin = verDetalleDiagnosticoAdmin;
window.copiarDetalleDiagnosticoAdmin = copiarDetalleDiagnosticoAdmin;
window.cerrarDetalleDiagnosticoAdmin = cerrarDetalleDiagnosticoAdmin;

console.log('✅ admin/diagnostico.js cargado');
