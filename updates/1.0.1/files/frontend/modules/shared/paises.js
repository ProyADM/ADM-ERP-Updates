// frontend/modules/shared/paises.js
// ============================================================
// MAPEOS DE PAÍSES (nombre completo ↔ sigla) - VERSIÓN GLOBAL
// ============================================================

window.SIGLA_A_PAIS = {
    'AR': 'Argentina',
    'UY': 'Uruguay',
    'RD': 'República Dominicana',
    'HN': 'Honduras',
    'GT': 'Guatemala',
    'CO': 'Colombia',
    'PE': 'Perú',
    'PY': 'Paraguay',
    'EC': 'Ecuador',
    'MX': 'México',
    'CR': 'Costa Rica'
};

window.PAIS_A_SIGLA = {
    'Argentina': 'AR',
    'Uruguay': 'UY',
    'República Dominicana': 'RD',
    'Honduras': 'HN',
    'Guatemala': 'GT',
    'Colombia': 'CO',
    'Perú': 'PE',
    'Paraguay': 'PY',
    'Ecuador': 'EC',
    'México': 'MX',
    'Costa Rica': 'CR'
};

// 🔴 CORREGIDO: Mapeo de código de base a sigla (incluye plataforma y plataforma_ur)
window.BASE_A_SIGLA = {
    'plataforma_rd': 'RD',
    'plataforma_ar': 'AR',    // fallback
    'plataforma': 'AR',       // Argentina (base correcta)
    'plataforma_mx': 'MX',
    'plataforma_gt': 'GT',
    'plataforma_hn': 'HN',
    'plataforma_cr': 'CR',
    'plataforma_pe': 'PE',
    'plataforma_py': 'PY',
    'plataforma_co': 'CO',
    'plataforma_uy': 'UY',    // fallback
    'plataforma_ur': 'UY',    // Uruguay (base correcta)
    'plataforma_ec': 'EC'
};

window.SIGLA_A_BASE = {
    'RD': 'plataforma_rd',
    'AR': 'plataforma',
    'MX': 'plataforma_mx',
    'GT': 'plataforma_gt',
    'HN': 'plataforma_hn',
    'CR': 'plataforma_cr',
    'PE': 'plataforma_pe',
    'PY': 'plataforma_py',
    'CO': 'plataforma_co',
    'UY': 'plataforma_ur',
    'EC': 'plataforma_ec'
};

window.siglaPais = function(nombreCompleto) {
    if (!nombreCompleto) return nombreCompleto;
    return window.PAIS_A_SIGLA[nombreCompleto] || nombreCompleto;
};

window.paisPorSigla = function(sigla) {
    if (!sigla) return sigla;
    return window.SIGLA_A_PAIS[sigla] || sigla;
};

window.siglaBase = function(codigoBase) {
    if (!codigoBase) return codigoBase;
    return window.BASE_A_SIGLA[codigoBase] || codigoBase;
};

console.log('✅ paises.js cargado (global) - con mapeos corregidos para AR y UY');