// ============================================================
// TOOLTIP COMPONENT - Ayuda contextual (hover + clic)
// ============================================================
// Cómo funciona: a cada elemento con `data-tooltip="clave"` se le agrega un
// ícono ⓘ. Pasar el mouse por encima (o pasar por el elemento) muestra la
// ayuda; hacer clic en el ícono la deja FIJA (para leerla con calma), y se
// cierra con la ✕, con Esc o haciendo clic afuera.
//
// `initTooltips()` es idempotente: se puede llamar las veces que haga falta y
// solo agrega el ícono a los elementos nuevos. Antes corría una sola vez (con
// un flag global) y todo lo que se pintaba después —el panel de administración,
// por ejemplo— quedaba sin ayuda.

import { TOOLTIPS } from './tooltips.js';

let tooltipActivo = null;
let tooltipFijo = false;          // true = lo abrió un clic y no se oculta al salir el mouse
let iconoConFoco = null;          // ícono que abrió el tooltip fijo (para el hover)
let tooltipsInicializados = false;

export function initTooltips() {
    const elementos = document.querySelectorAll('[data-tooltip]:not([data-tooltip-listo])');

    if (!tooltipsInicializados) {
        console.log('💡 Inicializando sistema de tooltips (hover + clic)...');
        tooltipsInicializados = true;
    }
    if (!elementos.length) return 0;

    let agregados = 0;
    elementos.forEach(el => {
        // Marca de idempotencia: el ícono se agrega UNA sola vez por elemento.
        el.dataset.tooltipListo = '1';
        const key = el.dataset.tooltip;
        const config = TOOLTIPS[key];

        if (!config) {
            console.warn(`⚠️ Tooltip no encontrado para: ${key}`);
            return;
        }

        // El ⓘ está DESACTIVADO en todo el software: el texto de ayuda ya aparece
        // al pasar el mouse por el destino (y con Tab si es focusable), así que el
        // ícono repetía al lado lo mismo que se ve. Si algún día hace falta en un
        // destino puntual, se enciende con `data-tooltip-con-icono="1"`.
        const esControl = el.dataset.tooltipConIcono !== '1';

        // Mostrar/ocultar al pasar el mouse por el elemento o por el ícono.
        el.addEventListener('mouseenter', () => mostrarTooltip(key, el, false));
        el.addEventListener('mouseleave', () => { if (!tooltipFijo) ocultarTooltip(); });
        // Teclado: hay destinos que son SÓLO un ícono (el indicador de usuario),
        // así que la info tiene que poder leerse con Tab. El destino tiene que ser
        // focusable (`tabindex="0"`); `focusin/focusout` burbujean, a diferencia
        // de `focus/blur`.
        el.addEventListener('focusin', () => mostrarTooltip(key, el, false));
        el.addEventListener('focusout', () => { if (!tooltipFijo) ocultarTooltip(); });

        if (esControl) { agregados++; return; }

        const ayudaIcon = document.createElement('span');
        ayudaIcon.className = 'ayuda-icono';
        ayudaIcon.textContent = 'ⓘ';
        ayudaIcon.title = 'Pasá el mouse para ver la ayuda (clic para fijarla)';
        ayudaIcon.dataset.tooltipIcono = key;

        ayudaIcon.addEventListener('mouseenter', () => mostrarTooltip(key, el, false));
        ayudaIcon.addEventListener('mouseleave', () => { if (!tooltipFijo) ocultarTooltip(); });

        ayudaIcon.addEventListener('click', function (e) {
            e.stopPropagation();
            e.preventDefault();
            // Repetir el clic sobre el mismo ícono la cierra.
            if (tooltipActivo && tooltipActivo._targetKey === key) {
                tooltipFijo = false;
                iconoConFoco = null;
                ocultarTooltip();
                return;
            }
            mostrarTooltip(key, el, true);
        });

        // ⚠️ DÓNDE va el ícono: la regla la dicta el LAYOUT del destino, no el
        // gusto. Verificado midiendo el layout real con Chrome:
        //   · Dentro de un BOTÓN (pestañas del menú, navegación superior, barra
        //     de base): va ADENTRO. Son `display:flex`, así que un hermano se
        //     convierte en otro ítem flex y BAJA DE LÍNEA — bug real: el ⓘ
        //     aparecía debajo del título en todo el menú. Adentro queda al lado
        //     del texto (el de las pestañas ya está envuelto en
        //     `.drawer-tab-texto` / `.tab-texto`, así que el ícono no toca el
        //     submenú) y el clic sigue siendo del botón, que es lo que el usuario
        //     espera al tocar su ayuda.
        //   · Fuera de un botón (chip de usuario, campana, títulos de sección,
        //     etiquetas de campo): va DESPUÉS, como hermano. Son bloques y
        //     insertarlo adentro ensuciaría su contenido.
        const adentro = el.matches('button');
        if (adentro) {
          el.appendChild(ayudaIcon);
        } else {
          el.insertAdjacentElement('afterend', ayudaIcon);
          // DEFENSIVO: si el contenedor es una fila flex (`.drawer-tab`,
          // `.module-tab`), un hermano se convierte en otro ítem flex y el ícono
          // BAJA DE LÍNEA. Pasa cuando el navegador tiene cacheado un
          // `index.html` viejo —sin el `<span class="drawer-tab-texto">`— y sí
          // descarga el JS nuevo: mezcla de versiones. En vez de depender de la
          // caché, se reubica el ícono adentro y se envuelve el texto si falta.
          if (el.matches('.drawer-tab, .module-tab')) {
            if (!el.querySelector('.drawer-tab-texto, .tab-texto')) {
              const texto = document.createElement('span');
              texto.className = el.matches('.drawer-tab') ? 'drawer-tab-texto' : 'tab-texto';
              while (el.firstChild) texto.appendChild(el.firstChild);
              el.appendChild(texto);
            }
            el.appendChild(ayudaIcon);
          }
        }
        agregados++;
    });

    if (agregados) console.log(`💡 Tooltips: ${agregados} elemento(s) con ayuda`);
    return agregados;
}

// Escapa texto que viene de DATOS (sesión del usuario, servidor). Se usa sólo
// para los campos dinámicos del catálogo: los estáticos son texto del código y
// se interpolan tal cual, como siempre.
function _escaparHTML(valor) {
    return String(valor).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
}

// Un campo del catálogo puede ser texto (estático) o una FUNCIÓN que devuelve el
// texto ahora (dinámico). Lo dinámico se escapa siempre: `innerHTML` con datos
// del servidor sería XSS.
function _campo(valor) {
    if (typeof valor !== 'function') return valor;
    try {
        // UNA sola evaluación: se arma el texto y se escapa ESE texto (evaluarla
        // dos veces podía escapar un valor distinto del que se muestra y duplicar
        // efectos secundarios).
        const texto = valor();
        return _escaparHTML(texto == null ? '' : texto);
    } catch (e) {
        return '';
    }
}

function mostrarTooltip(key, targetElement, fijo) {
    const config = TOOLTIPS[key];
    if (!config) return;

    // Ya está abierto el mismo: solo actualizar si el clic lo fija.
    if (tooltipActivo && tooltipActivo._targetKey === key) {
        tooltipFijo = tooltipFijo || !!fijo;
        if (fijo) iconoConFoco = targetElement;
        return;
    }

    ocultarTooltip();
    tooltipFijo = !!fijo;
    iconoConFoco = fijo ? targetElement : null;

    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip-contextual';
    tooltip._targetKey = key;
    tooltip.style.cssText = `
        position: fixed;
        z-index: 10000;
        max-width: 420px;
        min-width: 250px;
        background: #1e293b;
        color: #f1f5f9;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        font-size: 13px;
        line-height: 1.6;
        font-family: system-ui, -apple-system, sans-serif;
        border: 1px solid #334155;
        animation: tooltipFadeIn 0.25s ease;
        pointer-events: auto;
    `;

    // El contenido sale del catálogo `TOOLTIPS`: los campos de texto son texto del
    // código (sin datos de usuario ni del servidor), así que `innerHTML` no expone
    // XSS. Los campos que son FUNCIÓN traen datos dinámicos y pasan por `_campo()`,
    // que los escapa antes de interpolar.
    tooltip.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:6px;">
            <div style="font-weight:600;color:#60a5fa;font-size:15px;">
                ${_campo(config.titulo)}
            </div>
            <button data-onclick="this.closest('.tooltip-contextual').remove()" 
                    style="background:transparent;border:none;color:#94a3b8;cursor:pointer;font-size:18px;padding:0 4px;line-height:1;">
                ✕
            </button>
        </div>
        <div style="color:#e2e8f0;margin-bottom:8px;">
            ${_campo(config.descripcion)}
        </div>
        ${config.accion ? `
            <div style="font-size:12px;color:#94a3b8;border-top:1px solid #334155;padding-top:8px;margin-top:4px;">
                💡 ${_campo(config.accion)}
            </div>
        ` : ''}
        <div style="font-size:10px;color:#64748b;margin-top:8px;text-align:right;">
            ⏎ ${key}
        </div>
    `;
    
    document.body.appendChild(tooltip);
    
    // Posicionar
    const rect = targetElement.getBoundingClientRect();
    const tooltipWidth = Math.min(420, window.innerWidth - 40);
    
    let left = rect.left + rect.width / 2 - tooltipWidth / 2;
    let top = rect.top - 220 - 12;
    
    if (top < 10) {
        top = rect.bottom + 12;
    }
    
    if (left < 10) left = 10;
    if (left + tooltipWidth > window.innerWidth - 10) {
        left = window.innerWidth - tooltipWidth - 10;
    }
    
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
    tooltip.style.maxWidth = tooltipWidth + 'px';
    
    tooltipActivo = tooltip;
    
    // Cerrar al hacer clic fuera (solo si quedó fijo; si no, ya lo cierra el mouseleave)
    setTimeout(() => {
        document.addEventListener('click', cerrarTooltipClickFuera);
    }, 100);
}

function cerrarTooltipClickFuera(e) {
    if (!tooltipActivo) return;
    const tocoElIcono = e.target.closest && e.target.closest('.ayuda-icono');
    if (tooltipActivo.contains(e.target) || tocoElIcono) return;
    if (!tooltipFijo) {
        document.removeEventListener('click', cerrarTooltipClickFuera);
        return;
    }
    // Fijo: un clic afuera lo cierra y desengancha el ícono.
    if (iconoConFoco) iconoConFoco = null;
    tooltipFijo = false;
    ocultarTooltip();
}

function ocultarTooltip() {
    if (tooltipActivo) {
        tooltipActivo.remove();
        tooltipActivo = null;
        tooltipFijo = false;
        iconoConFoco = null;
        document.removeEventListener('click', cerrarTooltipClickFuera);
    }
}

// Esc cierra la ayuda (el tooltip es una capa que puede tapar contenido).
if (!window.__tooltipEscEnganchado) {
    window.__tooltipEscEnganchado = true;
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && tooltipActivo) ocultarTooltip();
    });
}

export function injectTooltipStyles() {
    if (document.getElementById('tooltip-styles')) return;
    
    const styles = document.createElement('style');
    styles.id = 'tooltip-styles';
    styles.textContent = `
        @keyframes tooltipFadeIn {
            from { opacity: 0; transform: translateY(-8px) scale(0.98); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        
        .tooltip-contextual {
            animation: tooltipFadeIn 0.2s ease;
        }
        
        .ayuda-icono {
            display: inline-block;
            margin-left: 6px;
            font-size: 14px;
            color: #94a3b8;
            cursor: pointer;
            transition: all 0.2s;
            pointer-events: all;
            padding: 2px 4px;
            border-radius: 4px;
        }
        
        .ayuda-icono:hover {
            color: #2563eb !important;
            background: #e8f0fe !important;
        }
        
        [data-tooltip] {
            position: relative;
        }
    `;
    document.head.appendChild(styles);
    console.log('✅ Estilos de tooltips inyectados');
}