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

// El nombre del informe con las siglas del pais de la BASE ACTIVA y la fecha
// (brief 05/10/2026): "RD - Ventas al 04-10-2026".
//
// Lo usan los CUATRO informes de Reportes para el archivo exportado y para el
// asunto y el adjunto del correo, asi los cuatro dicen lo mismo y no hay cuatro
// armados que se puedan separar. `tipo` es lo que va despues de las siglas
// ('Ventas', 'Pendiente de cobro', 'Pendiente de facturar') y `fecha` viene como
// `dd-mm-aaaa` (los modulos ya la tienen con `fechaHoyConGuiones`).
//
// OJO: la fecha va con GUIONES y no con barras como en el ejemplo del usuario
// ("RD - Ventas al 04/10/2026"): la barra es un separador de carpeta en Windows y
// ademas Excel no la acepta en un nombre de archivo. El formato es el mismo que ya
// usaban los informes, asi que el cambio es solo agregar las siglas y el tipo.
window.nombreInformeConSiglas = function(tipo, fecha) {
    // Las SIGLAS van SIEMPRE: es lo que pide el brief ("RD - Ventas al 04/10/2026")
    // y no puede depender de que `window.baseActiva` este cargada en ese instante.
    // OJO (medido el 05/10/2026): `baseActiva` arranca en `null` (la setea `app.js`
    // al inicializar), y con la primera version de esta funcion el nombre salia SIN
    // siglas justo por eso. Ahora, si `baseActiva` no esta, se usa la BASE POR
    // DEFECTO (el mismo `plataforma_rd` del backend) y, si el mapeo no la conociera,
    // la convencion de nombres (`plataforma_gt` -> GT).
    const base = window.baseActiva
        || window.BASE_DEFAULT
        || 'plataforma_rd';
    let siglas = '';
    if (typeof window.siglaBase === 'function') siglas = window.siglaBase(base) || '';
    if (!siglas) {
        const codigo = String(base).replace(/^plataforma_?/, '');
        siglas = codigo ? codigo.toUpperCase() : '';
    }
    const partes = [];
    if (siglas) partes.push(siglas + ' -');
    if (tipo) partes.push(tipo);
    partes.push('al ' + (fecha || ''));
    return partes.join(' ').replace(/\s+/g, ' ').trim();
};

// El PREFIJO del nombre, sin la fecha: es lo que el dialogo del correo usa como
// asunto por defecto (`app.js` le pega la fecha como `dd/mm/aaaa`). Sale de
// `nombreInformeConSiglas` para que el asunto y el archivo digan lo mismo.
window.prefijoInformeConSiglas = function(tipo) {
    return window.nombreInformeConSiglas(tipo, '').replace(/\s*al\s*$/, ' al ');
};

console.log('✅ paises.js cargado (global) - con mapeos corregidos para AR y UY');