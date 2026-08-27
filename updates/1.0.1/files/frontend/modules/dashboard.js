// frontend/modules/dashboard.js
// ============================================================
// DASHBOARD - 3 COLUMNAS (STOCK + VENTAS + CONTRATOS)
// ============================================================

let dashboardInterval = null;
let datosCompletos = [];

export function cargarDashboard() {
    console.log('🏠 Cargando Dashboard...');
    const container = document.getElementById('module-content');
    if (!container) {
        console.error('❌ No se encontró #module-content');
        return;
    }

    if (document.getElementById('dashboard-container')) {
        console.log('ℹ️ Dashboard ya está cargado');
        fetchActividad();
        return;
    }

    if (typeof cargarTemplate === 'function') {
        cargarTemplate('dashboard');
    } else {
        console.warn('⚠️ cargarTemplate no disponible');
        container.innerHTML = `<div style="text-align:center;padding:40px;color:#94a3b8;">⚠️ Error: Template no disponible</div>`;
        return;
    }

    setTimeout(() => {
        const btnRefresh = document.getElementById('btn-refresh-dashboard');
        if (btnRefresh) btnRefresh.addEventListener('click', fetchActividad);
        fetchActividad();
        if (dashboardInterval) clearInterval(dashboardInterval);
        dashboardInterval = setInterval(fetchActividad, 60000);
    }, 150);
}

async function fetchActividad() {
    console.log('📡 Consultando actividad reciente...');
    const timestampEl = document.getElementById('dashboard-timestamp');

    try {
        const response = await fetch('/api/dashboard/actividad');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (!data.success) throw new Error(data.error || 'Error al cargar datos');

        datosCompletos = data.data;

        if (timestampEl) {
            const fecha = new Date(data.timestamp);
            timestampEl.textContent = `⏱️ Última actualización: ${fecha.toLocaleString()}`;
        }

        renderNewsletter(data.data);

    } catch (e) {
        console.error('❌ Error en fetchActividad:', e);
        document.querySelectorAll('.newsletter-card .card-body').forEach(el => {
            el.innerHTML = `<div style="color:#dc2626;padding:12px;text-align:center;">❌ Error al cargar datos</div>`;
        });
    }
}

function renderNewsletter(data) {
    const stockItems = data.filter(item => item.tipo === 'STOCK');
    const ventasItems = data.filter(item => item.tipo === 'VENTA');
    const contratosItems = data.filter(item => item.tipo === 'CONTRATO');

    renderCard('newsletter-stock', stockItems);
    renderCard('newsletter-ventas', ventasItems);
    renderCard('newsletter-contratos', contratosItems);
}

function renderCard(containerId, items) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!items || items.length === 0) {
        container.innerHTML = `<div class="sin-actividad">No hay actividad reciente</div>`;
        return;
    }

    let html = '';
    items.slice(0, 10).forEach((item, i) => {
        const fecha = formatFecha(item.fecha);
        html += `
            <div class="newsletter-item">
                <span class="desc">${escapeHTML(item.descripcion)}</span>
                <span class="fecha">${fecha}</span>
            </div>
        `;
    });

    container.innerHTML = html;
}

function formatFecha(fechaStr) {
    if (!fechaStr) return '—';
    const d = new Date(fechaStr);
    if (isNaN(d)) return '—';
    const ahora = new Date();
    const diff = Math.floor((ahora - d) / (1000 * 60 * 60 * 24));
    if (diff === 0) return 'Hoy';
    if (diff === 1) return 'Ayer';
    if (diff > 0 && diff < 7) return `Hace ${diff} días`;
    if (diff > 0) return d.toLocaleDateString();
    return `📅 ${d.toLocaleDateString()} (futura)`;
}

function escapeHTML(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, function(m) {
        const map = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'};
        return map[m];
    });
}

window.cargarDashboard = cargarDashboard;