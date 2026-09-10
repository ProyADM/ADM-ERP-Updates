// ============================================================
// CXP - PUNTO DE ENTRADA (INDEX) - CORREGIDO
// ============================================================

import { mostrarMsg, validarBaseGT, cargarCondicionesPago } from './ui.js';
import { 
    handleFiles, 
    toBase64, 
    parsearFacturas, 
    cargarTodo, 
    limpiarRendicion, 
    debugPDF 
} from './main.js';
import { renderFacturas } from './render.js';
import { 
    agregarRenglon, 
    eliminarRenglon, 
    sincronizarBruto, 
    getRenglones 
} from './renglones.js';
import { eliminarFactura, validarIntegridad } from './eliminar.js';
import { 
    actualizarCotizacion, 
    recalcFact, 
    cuentaAutoDesdeDesc, 
    setupAC 
} from './utils.js';
import { aplicarEventualGlobal, toggleEventualFact } from './eventuales.js';
import { 
    crearBotonSelector, 
    inicializarCXP, 
    configurarEventListenersCXP 
} from './init.js';
import { initTooltips, injectTooltipStyles } from '../shared/tooltip-component.js';

window.condiciones = window.condiciones || [];
window.cuentasList = window.cuentasList || [];
window.facturasData = window.facturasData || [];
window.currentFiles = window.currentFiles || [];

// Exportar funciones globales
window.mostrarMsg = mostrarMsg;
window.validarBaseGT = validarBaseGT;
window.cargarCondicionesPago = cargarCondicionesPago;
window.handleFiles = handleFiles;
window.toBase64 = toBase64;
window.parsearFacturas = parsearFacturas;
window.renderFacturas = renderFacturas;
window.agregarRenglon = agregarRenglon;
window.eliminarRenglon = eliminarRenglon;
window.sincronizarBruto = sincronizarBruto;
window.getRenglones = getRenglones;
window.eliminarFactura = eliminarFactura;
window.validarIntegridad = validarIntegridad;
window.cargarTodo = cargarTodo;
window.limpiarRendicion = limpiarRendicion;
window.debugPDF = debugPDF;
window.actualizarCotizacion = actualizarCotizacion;
window.recalcFact = recalcFact;
window.cuentaAutoDesdeDesc = cuentaAutoDesdeDesc;
window.setupAC = setupAC;
window.aplicarEventualGlobal = aplicarEventualGlobal;
window.toggleEventualFact = toggleEventualFact;
window.crearBotonSelector = crearBotonSelector;
window.inicializarCXP = inicializarCXP;
window.configurarEventListenersCXP = configurarEventListenersCXP;

window.initTooltips = initTooltips;
window.injectTooltipStyles = injectTooltipStyles;

console.log('✅ CXP - Módulo cargado correctamente (XSS sanitizado)');

setTimeout(() => {
    try {
        injectTooltipStyles();
        initTooltips();
        console.log('✅ Tooltips globales inicializados desde CXP index');
    } catch (e) {
        console.warn('⚠️ Error inicializando tooltips desde index:', e);
    }
}, 1000);