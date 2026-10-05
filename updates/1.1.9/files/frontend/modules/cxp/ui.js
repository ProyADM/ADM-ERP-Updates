// ============================================================
// UI - MENSAJES, PROGRESO Y VALIDACIONES (CORREGIDO)
// ============================================================

// ============================================================
// FUNCIÓN DE SANITIZACIÓN
// ============================================================

function sanitizarValor(val) {
    if (val === undefined || val === null) return '';
    return escapeHTML(String(val));
}

// ============================================================
// AVISOS (TOAST, ARRIBA A LA DERECHA)
// ============================================================
// Antes los mensajes iban a `#cxpBanner`: una linea ARRIBA del dropzone que ademas
// tenia las clases cambiadas (`banner ok`/`banner err` contra `.banner.success`/
// `.banner.error` del CSS), asi que salia sin color y se borraba a los 8 segundos.
// Medido el 03/10/2026: el operador no la veia ("no hizo nada").
//
// Ahora son avisos apilables. LA FIRMA DE `mostrarMsg(msg, ok)` NO CAMBIA (la llaman
// muchos lugares): solo cambia por dentro. `mostrarErrores` es para listas (los
// errores de "Cargar todas", que antes se unian con " | " en una sola linea).
const ID_AVISOS = 'cxpAvisos';
const MS_AUTO = 10000;
const ESTILOS = {
    ok: {borde: '#1a7a52', fondo: '#d4f0e4', titulo: '#145c3e'},
    warn: {borde: '#9a6200', fondo: '#fef3d8', titulo: '#7a4d00'},
    err: {borde: '#b91c1c', fondo: '#fee2e2', titulo: '#8f1616'},
};

function contenedorAvisos() {
    let contenedor = document.getElementById(ID_AVISOS);
    if (!contenedor) {
        contenedor = document.createElement('div');
        contenedor.id = ID_AVISOS;
        contenedor.style.cssText = `
            position: fixed; top: 16px; right: 16px; z-index: 10000;
            display: flex; flex-direction: column; gap: 8px;
            max-width: min(460px, 90vw);
        `;
        document.body.appendChild(contenedor);
    }
    return contenedor;
}

export function mostrarAviso(titulo, lineas = [], tipo = 'ok') {
    // Todo se arma con textContent: los mensajes pueden traer texto del PDF.
    const estilo = ESTILOS[tipo] || ESTILOS.ok;
    const aviso = document.createElement('div');
    aviso.className = 'cxp-aviso cxp-aviso-' + tipo;
    aviso.style.cssText = `
        background: ${estilo.fondo}; border-left: 4px solid ${estilo.borde};
        border-radius: 8px; padding: 10px 12px; box-shadow: 0 6px 18px rgba(15,23,42,.18);
        font-size: 13px; color: #1e293b; display: flex; gap: 10px; align-items: flex-start;
    `;
    const cuerpo = document.createElement('div');
    cuerpo.style.cssText = 'flex:1; min-width:0;';
    if (titulo) {
        const h = document.createElement('div');
        h.textContent = titulo;
        h.style.cssText = `font-weight:600; color:${estilo.titulo}; margin-bottom:${lineas.length ? '4px' : '0'};`;
        cuerpo.appendChild(h);
    }
    for (const linea of lineas) {
        const p = document.createElement('div');
        p.textContent = linea;
        p.style.cssText = 'margin-top:2px; word-break:break-word;';
        cuerpo.appendChild(p);
    }
    aviso.appendChild(cuerpo);
    const cerrar = document.createElement('button');
    cerrar.type = 'button';
    cerrar.textContent = '✕';
    cerrar.setAttribute('aria-label', 'Cerrar aviso');
    cerrar.style.cssText = `
        border:none; background:transparent; cursor:pointer; font-size:14px;
        line-height:1; color:${estilo.titulo}; padding:2px 4px;
    `;
    cerrar.addEventListener('click', () => aviso.remove());
    aviso.appendChild(cerrar);

    contenedorAvisos().appendChild(aviso);
    // Los ERRORES no se cierran solos: hay que corregirlos. Los informativos si.
    if (tipo !== 'err') setTimeout(() => aviso.remove(), MS_AUTO);
    return aviso;
}

export function mostrarMsg(msg, ok) {
    return mostrarAviso('', [msg], ok ? 'ok' : 'err');
}

export function mostrarErrores(titulo, errores) {
    return mostrarAviso(titulo, errores, 'err');
}

export function mostrarProgreso(mensaje, porcentaje = null) {
    const container = document.getElementById('cxpProgreso');
    if (!container) {
        const dropZone = document.getElementById('dropZone');
        if (dropZone) {
            const prog = document.createElement('div');
            prog.id = 'cxpProgreso';
            prog.style.cssText = `
                margin-top: 12px;
                padding: 10px 14px;
                background: #f0f4ff;
                border-radius: 8px;
                border: 1px solid #93c5fd;
                display: none;
                font-size: 13px;
                color: #1e293b;
            `;
            prog.innerHTML = `
                <div style="display:flex;align-items:center;gap:10px;">
                    <span class="spinner-small" id="cxpSpinner"></span>
                    <span id="cxpProgresoTexto"></span>
                </div>
                <div id="cxpBarraProgreso" style="margin-top:8px;height:4px;background:#e2e8f0;border-radius:4px;overflow:hidden;display:none;">
                    <div id="cxpBarraProgresoFill" style="height:100%;width:0%;background:#2563eb;border-radius:4px;transition:width 0.3s;"></div>
                </div>
            `;
            dropZone.parentNode.insertBefore(prog, dropZone.nextSibling);
        }
    }
    
    const el = document.getElementById('cxpProgreso');
    if (!el) return;
    
    el.style.display = 'block';
    const texto = document.getElementById('cxpProgresoTexto');
    if (texto) {
        // ✅ CORREGIDO: Usar textContent en lugar de innerHTML
        texto.textContent = sanitizarValor(mensaje);
    }
    
    const barra = document.getElementById('cxpBarraProgreso');
    const fill = document.getElementById('cxpBarraProgresoFill');
    
    if (porcentaje !== null && porcentaje >= 0 && porcentaje <= 100) {
        barra.style.display = 'block';
        fill.style.width = porcentaje + '%';
    } else {
        barra.style.display = 'none';
    }
}

export function ocultarProgreso() {
    const el = document.getElementById('cxpProgreso');
    if (el) el.style.display = 'none';
}

/**
 * La base activa tiene el modulo de CxP habilitado?
 *
 * La marca la manda el BACKEND por base (`cxp_habilitado` en `/api/bases`): el frontend
 * no tiene la constante de pais. Es la UNICA lectura de la marca: la usan la compuerta de
 * la pantalla (`validarBaseCxP`) y las guardas de las acciones (`main.js`).
 */
export function baseCxPHabilitada() {
    const base = window.baseActiva || 'plataforma_rd';
    return window.BASES_DISPONIBLES_FRONT?.[base]?.cxp_habilitado === true;
}

export function validarBaseCxP() {
    const modulo = document.getElementById('cxp-facturas');
    if (!modulo) return false;

    let msg = document.getElementById('cxp-gt-only');
    const habilitada = baseCxPHabilitada();
    // Solo para la etiqueta del cartel ("Base actual: ..."): la marca de habilitacion la
    // lee `baseCxPHabilitada`.
    const base = window.baseActiva || 'plataforma_rd';

    // El bloqueo es UNA clase en el modulo: el CSS esconde todo lo que no sea el cartel
    // (`#cxp-facturas.cxp-bloqueado > *:not(#cxp-gt-only)`, con `!important`) para ganarle
    // a los `style.display = 'block'` que el propio flujo escribe al extraer y al cargar.
    // Antes se escondian las tarjetas una por una con `display:none` y `parsearFacturas`
    // las volvia a mostrar: medido el 03/10/2026, en RD se veian la configuracion del lote
    // y el boton "Cargar todas las facturas" con el cartel puesto.
    modulo.classList.toggle('cxp-bloqueado', !habilitada);

    if (!habilitada) {
        const baseLabel = window.BASES_DISPONIBLES_FRONT?.[base]?.label || base;
        if (!msg) {
            msg = document.createElement('div');
            msg.id = 'cxp-gt-only';
            msg.style.cssText = 'padding:40px 20px; text-align:center; background:#fef3f2; border-radius:8px; border:1px solid #fecdc9; margin:20px 0;';
            // ✅ CORREGIDO: HTML fijo; el unico dato variable (la base) va por textContent.
            msg.innerHTML = `
                <div style="font-size:48px; margin-bottom:12px;">⚠️</div>
                <h3 style="color:#b42318; margin:0 0 8px 0;">Cargador de Facturas exclusivo para Guatemala</h3>
                <p style="color:#64748b; margin:0;">Seleccioná la base <strong>"Guatemala"</strong> para utilizar esta funcionalidad.</p>
                <p style="color:#64748b; font-size:12px; margin-top:8px;">Base actual: <strong id="cxp-gt-base"></strong></p>
            `;
            modulo.prepend(msg);
        }
        // La base activa se reescribe SIEMPRE: el cartel se crea una sola vez, asi que un
        // texto puesto solo al crearlo queda congelado con el pais de ese momento (medido
        // en pantalla el 03/10/2026: RD -> GT -> PY seguia diciendo "Republica
        // Dominicana"). `textContent` no interpreta HTML: el nombre de la base no puede
        // inyectar nada.
        const etiqueta = document.getElementById('cxp-gt-base');
        if (etiqueta) etiqueta.textContent = baseLabel;
        msg.style.display = 'block';
        return false;
    }

    // El camino habilitado NO toca el `display` de ninguna tarjeta: `#rendicionConfig` y
    // `#btnCargarTodo` tienen que seguir escondidos hasta que haya comprobantes extraidos
    // (antes esta funcion los mostraba con solo validar la base).
    if (msg) msg.style.display = 'none';
    return true;
}

export async function cargarCondicionesPago() {
    const sel = document.getElementById("rendCondPago");
    if (!sel) return;
    
    try {
        const API = window.API || '/api';
        window.condiciones = await fetch(`${API}/condiciones_pago`).then(r => r.json());
        sel.innerHTML = '';
        window.condiciones.forEach(c => {
            const o = document.createElement('option');
            // ✅ CORREGIDO: Usar textContent en lugar de innerHTML
            o.value = c.id;
            o.textContent = `${c.id} · ${c.nombre}`;
            sel.appendChild(o);
        });
        if (sel.querySelector('option[value="00"]')) sel.value = '00';
        setTimeout(() => validarBaseCxP(), 300);
    } catch (e) {
        console.warn('Error cargando condiciones de pago:', e);
    }
}