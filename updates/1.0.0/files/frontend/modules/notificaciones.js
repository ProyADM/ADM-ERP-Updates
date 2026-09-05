// frontend/modules/notificaciones.js
// ============================================================
// NOTIFICACIONES GLOBALES - Badge con cambios en tiempo real
// ============================================================

let ultimaConsulta = null;
let notifInterval = null;
let notificacionesData = [];
let badgeElement = null;
let countElement = null;
let dropdownElement = null;
let dropdownVisible = false;

export function iniciarNotificaciones() {
    console.log('🔔 Iniciando sistema de notificaciones...');

    badgeElement = document.getElementById('notificacion-badge');
    if (!badgeElement) {
        console.warn('⚠️ No se encontró #notificacion-badge en el DOM');
        return;
    }

    countElement = document.getElementById('notif-count');
    dropdownElement = document.getElementById('notif-dropdown');

    // Crear dropdown si no existe
    if (!dropdownElement) {
        dropdownElement = document.createElement('div');
        dropdownElement.id = 'notif-dropdown';
        dropdownElement.style.cssText = `
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            min-width: 300px;
            max-width: 500px;
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.15);
            padding: 12px 16px;
            z-index: 1000;
            margin-top: 8px;
            max-height: 400px;
            overflow-y: auto;
        `;
        badgeElement.style.position = 'relative';
        badgeElement.appendChild(dropdownElement);

        // Cerrar dropdown al hacer clic fuera
        document.addEventListener('click', (e) => {
            if (!badgeElement.contains(e.target)) {
                cerrarDropdown();
            }
        });
    }

    // Evento click en el badge
    badgeElement.addEventListener('click', (e) => {
        e.stopPropagation();
        if (dropdownVisible) {
            cerrarDropdown();
        } else {
            abrirDropdown();
        }
    });

    // Solicitar permiso para notificaciones del navegador
    if (Notification.permission === 'default') {
        Notification.requestPermission();
    }

    // Primera consulta
    actualizarNotificaciones();

    // Polling cada 30 segundos
    if (notifInterval) clearInterval(notifInterval);
    notifInterval = setInterval(actualizarNotificaciones, 30000);

    // También actualizar cuando el usuario vuelve a la pestaña
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            actualizarNotificaciones();
        }
    });
}

async function actualizarNotificaciones() {
    try {
        const desde = ultimaConsulta || new Date(Date.now() - 86400000).toISOString();
        const url = `/api/notificaciones/resumen?desde=${encodeURIComponent(desde)}`;
        const response = await fetch(url);
        const data = await response.json();

        if (!data.success) {
            console.warn('⚠️ Error al obtener notificaciones:', data.error);
            return;
        }

        // Guardar los datos para el detalle
        notificacionesData = data.detalle || [];
        const total = data.total || 0;

        // Actualizar badge
        if (countElement) {
            if (total > 0) {
                countElement.textContent = total > 99 ? '99+' : total;
                countElement.style.display = 'inline';
                // Si la pestaña no está activa, mostrar notificación del navegador
                if (document.hidden && Notification.permission === 'granted' && total > 0) {
                    const mensaje = `📢 ${total} cambios nuevos en el sistema.`;
                    new Notification('📢 SIDESYS', {
                        body: mensaje,
                        icon: '/favicon.ico'
                    });
                }
            } else {
                countElement.style.display = 'none';
            }
        }

        // Actualizar dropdown si está abierto
        if (dropdownVisible) {
            renderDropdown();
        }

        // Actualizar timestamp de última consulta
        ultimaConsulta = data.desde || new Date().toISOString();

    } catch (e) {
        console.warn('❌ Error en polling de notificaciones:', e);
    }
}

function abrirDropdown() {
    dropdownVisible = true;
    if (dropdownElement) {
        dropdownElement.style.display = 'block';
        renderDropdown();
    }
}

function cerrarDropdown() {
    dropdownVisible = false;
    if (dropdownElement) {
        dropdownElement.style.display = 'none';
    }
}

function renderDropdown() {
    if (!dropdownElement) return;

    if (!notificacionesData || notificacionesData.length === 0) {
        dropdownElement.innerHTML = `
            <div style="padding:8px 0;color:#94a3b8;text-align:center;font-size:13px;">
                ✅ No hay cambios nuevos
            </div>
        `;
        return;
    }

    let html = `
        <div style="font-weight:600;font-size:14px;padding-bottom:8px;border-bottom:1px solid #e2e8f0;margin-bottom:8px;">
            📊 Resumen de cambios
        </div>
    `;

    notificacionesData.forEach(item => {
        const total = item.total || 0;
        if (total === 0) return;
        html += `
            <div style="padding:6px 0;border-bottom:1px solid #f1f5f9;font-size:13px;">
                <div style="display:flex;justify-content:space-between;align-items:center;font-weight:600;">
                    <span>${item.sigla || item.base}</span>
                    <span style="background:#2563eb;color:#fff;border-radius:12px;padding:0 10px;font-size:11px;">${total}</span>
                </div>
                <div style="display:flex;gap:12px;font-size:12px;color:#64748b;margin-top:2px;">
                    ${item.stock > 0 ? `<span>📦 ${item.stock}</span>` : ''}
                    ${item.ventas > 0 ? `<span>💰 ${item.ventas}</span>` : ''}
                    ${item.contratos > 0 ? `<span>📋 ${item.contratos}</span>` : ''}
                </div>
            </div>
        `;
    });

    html += `
        <div style="padding-top:8px;margin-top:8px;border-top:1px solid #e2e8f0;font-size:12px;color:#94a3b8;text-align:center;">
            🔄 Actualizado automáticamente
        </div>
    `;

    dropdownElement.innerHTML = html;
}

// Iniciar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciarNotificaciones);
} else {
    iniciarNotificaciones();
}