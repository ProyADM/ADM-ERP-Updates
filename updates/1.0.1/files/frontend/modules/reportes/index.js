// ============================================================
// REPORTES - PUNTO DE ENTRADA
// ============================================================

import { cargarPendienteCobro } from './pendiente_cobro.js';
import { cargarConsolidadoTotal } from './consolidado_total.js';

// 🔴 Exportar funciones globalmente
window.cargarPendienteCobro = cargarPendienteCobro;
window.cargarConsolidadoTotal = cargarConsolidadoTotal;

console.log('✅ Reportes - Módulo cargado correctamente');