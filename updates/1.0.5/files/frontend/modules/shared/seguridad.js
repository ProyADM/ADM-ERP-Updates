// frontend/seguridad.js
// ============================================================
// HELPERS COMUNES DE SEGURIDAD DEL FRONTEND (C9)
// ============================================================
// Cargado ANTES que el resto de los scripts. Define la ÚNICA copia de
// escapeHTML del proyecto (antes había ~19 definiciones duplicadas que se
// pisaban según el orden de carga).
//
// Regla C9: NINGÚN dato dinámico (servidor, BD, input, errores, URL) se
// interpola en innerHTML sin pasar por escapeHTML().
// ============================================================

(function () {
    'use strict';

    var MAPA_HTML = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };

    /**
     * Escapa texto para insertarlo en HTML de forma segura (& < > " ').
     * Devuelve '' para null/undefined y convierte cualquier valor a string.
     */
    var escapeHTML = function (str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/[&<>"']/g, function (m) { return MAPA_HTML[m]; });
    };

    window.escapeHTML = escapeHTML;
    window.ADMSeg = { escapeHTML: escapeHTML };
})();
