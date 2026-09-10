// frontend/modules/reportes/index.js
// ============================================================
// REPORTES - PUNTO DE ENTRADA (index.js)
// ============================================================

import * as contratos from './contratos.js';
import * as ventasManuales from './ventas_manuales.js';
import { cargarPendienteCobro } from './pendiente_cobro.js';
import { cargarConsolidadoPais } from './consolidado_pais.js';
import { cargarConsolidadoTotal } from './consolidado_total.js';

// Variable para guardar el último reporte activo
let ultimoReporteActivo = 'contratos'; // valor por defecto

// Función para guardar el reporte activo
function guardarReporteActivo(tipo) {
    ultimoReporteActivo = tipo;
    try {
        localStorage.setItem('ultimoReporteActivo', tipo);
    } catch (e) {
        // silencioso
    }
}

// Función para obtener el último reporte activo
function obtenerUltimoReporteActivo() {
    try {
        const guardado = localStorage.getItem('ultimoReporteActivo');
        if (guardado) {
            ultimoReporteActivo = guardado;
        }
    } catch (e) {
        // silencioso
    }
    return ultimoReporteActivo;
}

// Mapeo de tipo de reporte a nombre para mostrar en el título
const NOMBRES_REPORTES = {
    'contratos': '📄 Pendiente de Facturar',
    'pendiente-cobro': '💰 Pendiente de Cobro',
    'consolidado-pais': '🌍 Ventas por País',
    'consolidado-total': '🌐 Ventas Globales'
};

function actualizarTituloReporte(tipo) {
    const titulo = document.getElementById('seccion-activa');
    if (titulo) {
        const nombre = NOMBRES_REPORTES[tipo] || tipo;
        titulo.textContent = nombre;
        titulo.style.display = 'block';
    }
}

// Inicializar al cargar el módulo
obtenerUltimoReporteActivo();

// ============================================================
// FUNCIÓN PARA CAMBIAR ENTRE REPORTES (desde el drawer)
// ============================================================

export function cambiarReporte(tipo) {
    console.log(`📊 Cambiando a reporte: ${tipo}`);

    // Guardar el reporte activo
    guardarReporteActivo(tipo);

    // Ocultar todos los contenedores de reportes
    document.querySelectorAll('.reporte-container').forEach(el => {
        el.style.display = 'none';
        el.classList.remove('active');
    });

    // Resaltar el tab del drawer
    document.querySelectorAll('.drawer-tab').forEach(tab => tab.classList.remove('active'));
    const tab = document.querySelector(`.drawer-tab[data-tab="reportes-${tipo}"]`);
    if (tab) tab.classList.add('active');

    const container = document.getElementById(`reporte-${tipo}`);
    if (container) {
        container.style.display = 'block';
        container.classList.add('active');

        // 🔴 ACTUALIZAR EL TÍTULO DE LA SECCIÓN
        actualizarTituloReporte(tipo);

        // Cargar el contenido específico
        cargarContenidoReporte(tipo);
    }
}

// Función para cargar el contenido de un reporte (sin cambiar la UI)
function cargarContenidoReporte(tipo) {
    switch (tipo) {
        case 'pendiente-cobro':
            if (typeof cargarPendienteCobro === 'function') cargarPendienteCobro();
            break;
        case 'consolidado-pais':
            import('./consolidado_pais.js')
                .then(module => {
                    if (module.inicializarConsolidadoPais) module.inicializarConsolidadoPais();
                    else if (module.cargarConsolidadoPais) module.cargarConsolidadoPais();
                })
                .catch(e => console.error('❌ Error cargando consolidado_pais:', e));
            break;
        case 'consolidado-total':
            import('./consolidado_total.js')
                .then(module => {
                    if (module.inicializarConsolidadoTotal) module.inicializarConsolidadoTotal();
                    else if (module.cargarConsolidadoTotal) module.cargarConsolidadoTotal();
                })
                .catch(e => console.error('❌ Error cargando consolidado_total:', e));
            break;
        case 'contratos':
        default:
            contratos.cargarAnos();
            break;
    }
}

// ============================================================
// FUNCIÓN PARA CARGAR EL REPORTE POR DEFECTO (desde templates.js)
// ============================================================

export function cargarReporte() {
    console.log('📊 cargarReporte() ejecutado');
    document.querySelectorAll('.modulo-content').forEach(el => el.style.display = 'none');
    const moduloReportes = document.getElementById('modulo-reportes');
    if (moduloReportes) {
        moduloReportes.style.display = 'block';
    } else {
        console.error('❌ No se encontró #modulo-reportes');
        return;
    }
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.style.display = 'none';
    const seccionActiva = document.getElementById('seccion-activa');
    if (seccionActiva) seccionActiva.style.display = 'none';
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));

    // Usar el último reporte activo en lugar de siempre 'contratos'
    const ultimo = obtenerUltimoReporteActivo();
    cambiarReporte(ultimo);
}

// ============================================================
// RECARGAR REPORTE ACTUAL (después de una venta manual)
// ============================================================

export function recargarReporteActual() {
    const reporteActual = document.querySelector('.reporte-container.active');
    if (reporteActual) {
        const id = reporteActual.id;
        // Extraer el tipo del id (ej. "reporte-consolidado-total" -> "consolidado-total")
        const tipo = id.replace('reporte-', '');
        cargarContenidoReporte(tipo);
        // Actualizar título por si acaso
        actualizarTituloReporte(tipo);
    }
}

// ============================================================
// EXPONER FUNCIONES GLOBALES (para el HTML)
// ============================================================

window.cambiarReporte = cambiarReporte;
window.cargarReporte = cargarReporte;
window.recargarReporteActual = recargarReporteActual;
window.obtenerUltimoReporteActivo = obtenerUltimoReporteActivo;
window.guardarReporteActivo = guardarReporteActivo;

// Funciones de contratos
window.ejecutarReporte = contratos.ejecutarReporte;
window.exportarExcel = contratos.exportarExcel;
window.cambiarMoneda = contratos.cambiarMoneda;
window.cargarAnos = contratos.cargarAnos;

// Funciones de ventas manuales
window.abrirModalVentaManual = ventasManuales.abrirModalVentaManual;
window.cerrarModalVentaManual = ventasManuales.cerrarModalVentaManual;
window.guardarVentaManual = ventasManuales.guardarVentaManual;
window.importarVentasManuales = ventasManuales.importarVentasManuales;
window.procesarImportacionVentas = ventasManuales.procesarImportacionVentas;
window.abrirAdminVentasManuales = ventasManuales.abrirAdminVentasManuales;
window.cerrarAdminVentasManuales = ventasManuales.cerrarAdminVentasManuales;
window.eliminarVentaManual = ventasManuales.eliminarVentaManual;
window.descargarPlantillaVentasManuales = ventasManuales.descargarPlantillaVentasManuales;

// Funciones de pendiente de cobro (ya están expuestas en su módulo)
import { cargarPendienteCobro as pendienteCobro } from './pendiente_cobro.js';
window.cargarPendienteCobro = pendienteCobro;

// ============================================================
// LISTENER PARA CAMBIO DE BASE (recarga solo si es necesario)
// ============================================================

// Reportes que dependen de la base activa (se recargan al cambiar de base)
const REPORTES_DEPENDIENTES_DE_BASE = [
    'pendiente-cobro',  // Pendiente de Cobro (base activa)
    'consolidado-pais', // Ventas por País (base activa)
    'contratos'         // Pendiente de Facturar (base activa)
];

// Reportes GLOBALES que NO dependen de la base activa
const REPORTES_GLOBALES = [
    'consolidado-total' // Ventas Globales (muestra todos los países)
];

// Escuchar en `window`: app.js despacha el CustomEvent 'baseChanged' con
// window.dispatchEvent() y SIN bubbles, así que un listener en `document`
// nunca se disparaba → la recarga selectiva por base no funcionaba.
window.addEventListener('baseChanged', function(e) {
    console.log('🔄 Base cambiada a:', e.detail.base);
    
    // Obtener el reporte actual
    const reporteActual = document.querySelector('.reporte-container.active');
    if (!reporteActual) return;
    
    const id = reporteActual.id;
    const tipo = id.replace('reporte-', '');
    
    // Verificar si el reporte actual depende de la base
    if (REPORTES_DEPENDIENTES_DE_BASE.includes(tipo)) {
        console.log(`🔄 Recargando reporte "${tipo}" por cambio de base...`);
        cargarContenidoReporte(tipo);
    } else if (REPORTES_GLOBALES.includes(tipo)) {
        console.log(`ℹ️ Reporte global "${tipo}" no requiere recarga por cambio de base.`);
    } else {
        // Por si hay algún otro reporte, asumimos que no se recarga
        console.log(`ℹ️ Reporte "${tipo}" no requiere recarga por cambio de base.`);
    }
});

console.log('✅ Reportes - Punto de entrada cargado (con persistencia de último reporte, recarga selectiva por base y actualización de título)');