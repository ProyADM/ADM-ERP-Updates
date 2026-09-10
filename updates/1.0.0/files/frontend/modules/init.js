// frontend/modules/init.js
// ============================================================
// INICIALIZACIÓN DE LA APLICACIÓN (extraído de index.html, C9b)
// ============================================================
// Antes este código era un <script type="module"> inline en index.html.
// Con la política CSP fuerte (script-src 'self') el JS inline está prohibido,
// así que vive en este archivo. NO agregar <script> inline a index.html.

import { cargarDashboard } from '/frontend/modules/dashboard.js';

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
      const nameEl = document.getElementById('user-indicator-name');
      const roleEl = document.getElementById('user-indicator-role');
      if (nameEl) nameEl.textContent = userData.nombre || userData.username || 'Usuario';
      if (roleEl) {
        if (userData.es_superadmin || userData.rol === 'superadmin') {
          roleEl.textContent = 'SuperAdmin';
          roleEl.style.display = 'inline';
          roleEl.style.background = '#dc2626';
        } else if (userData.rol) {
          roleEl.textContent = userData.rol.charAt(0).toUpperCase() + userData.rol.slice(1);
          roleEl.style.display = 'inline';
        }
      }
      if (typeof window.aplicarPermisosUI === 'function') {
        window.aplicarPermisosUI(userData);
      }
    }

    // 2. Inicializar base
    await inicializarBase('plataforma_rd', 'sidesys');
    toastSuccess('Base: República Dominicana', 'Base inicializada');

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

    // 6. Inicializar Tooltips globales
    setTimeout(() => {
      try {
        if (!window._tooltipsInicializados) {
          import('/frontend/modules/shared/tooltip-component.js').then(module => {
            if (module.initTooltips) {
              module.initTooltips();
              window._tooltipsInicializados = true;
              console.log('✅ Tooltips globales inicializados desde init.js');
            }
            if (module.injectTooltipStyles) {
              module.injectTooltipStyles();
            }
          }).catch(e => {
            console.warn('⚠️ Error cargando tooltips:', e.message);
          });
        } else {
          console.log('ℹ️ Tooltips ya inicializados, omitiendo desde init.js');
        }
      } catch (e) {
        console.warn('⚠️ Error inicializando tooltips:', e.message);
      }
    }, 1200);

    toastSuccess('Aplicación lista', '✅ SIDESYS ERP');

    window.addEventListener('baseChanged', function (e) {
      console.log('📌 Evento baseChanged recibido:', e.detail);
      if (typeof validarBaseGT === 'function') {
        setTimeout(() => validarBaseGT(), 200);
      }
    });

    // ✅ Escuchar evento de usuario cargado (re-aplica permisos si cambia)
    window.addEventListener('userLoaded', function (e) {
      const user = e.detail.user;
      const nameEl = document.getElementById('user-indicator-name');
      const roleEl = document.getElementById('user-indicator-role');
      if (nameEl) nameEl.textContent = user.nombre || user.username || 'Usuario';
      if (roleEl) {
        if (user.es_superadmin || user.rol === 'superadmin') {
          roleEl.textContent = 'SuperAdmin';
          roleEl.style.display = 'inline';
          roleEl.style.background = '#dc2626';
        } else if (user.rol) {
          roleEl.textContent = user.rol.charAt(0).toUpperCase() + user.rol.slice(1);
          roleEl.style.display = 'inline';
        }
      }
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
