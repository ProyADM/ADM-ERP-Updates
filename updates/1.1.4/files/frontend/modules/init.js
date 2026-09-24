// frontend/modules/init.js
// ============================================================
// INICIALIZACIÓN DE LA APLICACIÓN (extraído de index.html, C9b)
// ============================================================
// Antes este código era un <script type="module"> inline en index.html.
// Con la política CSP fuerte (script-src 'self') el JS inline está prohibido,
// así que vive en este archivo. NO agregar <script> inline a index.html.

import { cargarDashboard } from '/frontend/modules/dashboard.js';
import { TOOLTIPS } from '/frontend/modules/shared/tooltips.js';

// El indicador de usuario de la barra es SÓLO un ícono: el nombre y el rol se
// leen en su tooltip. Acá se copia ese mismo texto al `aria-label` para que un
// lector de pantalla lo anuncie; la fuente es una sola (la función del catálogo,
// que ya escapa los datos de la sesión).
function _marcarIndicadorUsuario() {
  try {
    const pill = document.querySelector('[data-tooltip="barraUsuario"]');
    if (!pill) return;
    const texto = TOOLTIPS['barraUsuario'].descripcion();
    if (texto) pill.setAttribute('aria-label', texto);
  } catch (e) { /* sin sesión o sin tooltip: no puede romper la UI */ }
}

(async function () {
  try {
    toastInfo('Inicializando aplicación...', 'Cargando');

    // ✅ 0. CARGAR USUARIO ACTUAL (ANTES DE TODO)
    await cargarUsuarioActual();

    // ✅ 1. Mostrar usuario en la interfaz y aplicar permisos de UI (C9c)
    const userData = obtenerUsuarioActual();

    // Sin sesión (acceso remoto sin SSO): mostrar el login y NO seguir
    // inicializando (evita 401 en masa y el error de inicializarBase).
    if (!userData) {
      if (typeof window.mostrarLoginUI === 'function') {
        window.mostrarLoginUI();
      }
      return;
    }

    if (userData) {
      _marcarIndicadorUsuario();
      if (typeof window.aplicarPermisosUI === 'function') {
        window.aplicarPermisosUI(userData);
      }
    }

    // 2. Inicializar base con la que corresponde a ESTE usuario: el backend la
    //    resuelve desde su `base_default` (o su primera base permitida). Antes se
    //    forzaba 'plataforma_rd' y todos arrancaban en RD, tuvieran o no ese país.
    await inicializarBase();
    const _infoBaseInicial = (window.BASES_DISPONIBLES_FRONT || {})[window.baseActiva] || {};
    toastSuccess('Base: ' + (_infoBaseInicial.label || window.baseActiva || 'por defecto'), 'Base inicializada');

    // ✅ 3. CARGAR DASHBOARD (EN LUGAR DE STOCK)
    setTimeout(() => {
      cargarDashboard();
      toastSuccess('Dashboard cargado', '🏠 Inicio');
    }, 200);

    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.style.display = 'none';

    const moduleContent = document.getElementById('module-content');
    if (moduleContent) moduleContent.style.display = 'block';

    // 4. Inicializar drawer (siempre)
    setTimeout(() => {
      if (typeof inicializarDrawer === 'function') {
        inicializarDrawer();
      }
    }, 500);

    // 5. Inicializar CXP (en segundo plano)
    setTimeout(() => {
      try {
        if (typeof window.inicializarCXP === 'function') {
          window.inicializarCXP();
          console.log('✅ CXP inicializado');
        } else {
          console.warn('⚠️ window.inicializarCXP no disponible, reintentando...');
          setTimeout(() => {
            if (typeof window.inicializarCXP === 'function') {
              window.inicializarCXP();
              console.log('✅ CXP inicializado (reintento)');
            } else {
              console.error('❌ CXP no disponible - ejecuta manualmente desde consola');
            }
          }, 1000);
        }
      } catch (e) {
        console.warn('⚠️ Error inicializando CXP:', e.message);
      }
    }, 600);

    // 6. Ayuda contextual (tooltips) de TODA la interfaz.
    // Es el punto de arranque real, así que acá se deja el sistema disponible
    // globalmente (`window.initTooltips`) para que los módulos que se pintan
    // después —el panel de administración, sobre todo— puedan volver a llamarlo
    // y enganchar los íconos ⓘ de lo recién renderizado.
    setTimeout(() => {
      try {
        import('/frontend/modules/shared/tooltip-component.js').then(module => {
          if (module.injectTooltipStyles) module.injectTooltipStyles();
          if (module.initTooltips) {
            window.initTooltips = module.initTooltips;
            module.initTooltips();
            console.log('✅ Tooltips globales inicializados desde init.js');
          }
        }).catch(e => {
          console.warn('⚠️ Error cargando tooltips:', e.message);
        });
      } catch (e) {
        console.warn('⚠️ Error inicializando tooltips:', e.message);
      }
    }, 1200);

    toastSuccess('Aplicación lista', '✅ SIDESYS ERP');

    window.addEventListener('baseChanged', function (e) {
      console.log('📌 Evento baseChanged recibido:', e.detail);
      // `validarBaseCxP` vive en modules/cxp/ui.js y se publica en `window` desde
      // modules/cxp/index.js. Aca decia `validarBaseGT`, que ya no existe: el
      // `typeof` tapaba esa referencia muerta y la revalidacion al cambiar de base
      // (el cartel de "exclusivo para Guatemala" por `cxp_habilitado`) no corria.
      if (typeof window.validarBaseCxP === 'function') {
        setTimeout(() => window.validarBaseCxP(), 200);
      }
    });

    // ✅ Escuchar evento de usuario cargado (re-aplica permisos si cambia)
    window.addEventListener('userLoaded', function (e) {
      const user = e.detail.user;
      // Insignia de alertas del sistema en el menú lateral: solo la consulta
      // quien tiene la pestaña (el endpoint responde 403 al resto).
      if (typeof window.iniciarBadgeDiagnosticoAdmin === 'function') {
        try { window.iniciarBadgeDiagnosticoAdmin(); } catch (err) { /* no puede romper la UI */ }
      }
      _marcarIndicadorUsuario();
      if (typeof window.aplicarPermisosUI === 'function') {
        window.aplicarPermisosUI(user);
      }
      console.log('👤 Usuario actualizado en UI:', user.username);
    });

  } catch (error) {
    toastError('Error al iniciar: ' + error.message, 'Error crítico');
    console.error('Error al iniciar:', error);
  }
})();
