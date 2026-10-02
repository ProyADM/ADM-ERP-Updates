// ============================================================
// ADMIN - CLIENTE HTTP DEL PANEL
// ============================================================
// Único lugar del panel que habla con /api/admin/*. Traduce los códigos de
// error del backend (spec §6.5) y NUNCA lanza: siempre devuelve
// {ok, codigo, datos, error}.

var ADMIN_MENSAJES_HTTP = {
  401: 'Tu sesión venció. Volvé a iniciar sesión.',
  403: 'No tenés permiso para esta acción.',
  404: 'El registro ya no existe (puede haberlo borrado otra PC).',
  503: 'El almacén central no está disponible. No se guardó nada.'
};

async function adminFetch(ruta, opciones) {
  opciones = opciones || {};
  var cfg = {
    method: opciones.method || 'GET',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin'
  };
  if (opciones.body !== undefined) {
    // JSON.stringify lanza con estructuras circulares: el contrato de esta
    // función es NUNCA rechazar, así que se atrapa acá.
    try {
      cfg.body = JSON.stringify(opciones.body);
    } catch (e) {
      return { ok: false, codigo: 0, datos: {},
               error: 'Los datos de la operación no se pudieron preparar.' };
    }
  }
  var respuesta;
  try {
    respuesta = await fetch(ruta, cfg);
  } catch (e) {
    return { ok: false, codigo: 0, datos: {},
             error: 'No se pudo conectar con el servidor. Revisá la conexión.' };
  }
  var datos = {};
  try { datos = (await respuesta.json()) || {}; } catch (e) { datos = {}; }
  if (respuesta.ok) return { ok: true, codigo: respuesta.status, datos: datos };
  var error = datos.error || ADMIN_MENSAJES_HTTP[respuesta.status] ||
              ('Error ' + respuesta.status);
  if (respuesta.status === 401 && typeof mostrarLoginUI === 'function') {
    // La UI de login no puede romper el contrato de "nunca lanza".
    try { mostrarLoginUI(); } catch (e) { /* sin sesión igual se informa el 401 */ }
  }
  return { ok: false, codigo: respuesta.status, datos: datos, error: error };
}

window.adminFetch = adminFetch;
