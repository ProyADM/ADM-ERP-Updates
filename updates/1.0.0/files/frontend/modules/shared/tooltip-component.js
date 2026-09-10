// ============================================================
// TOOLTIP COMPONENT - Versión mejorada (click para mostrar)
// ============================================================

import { TOOLTIPS } from './tooltips.js';

let tooltipActivo = null;
let tooltipsInicializados = false;

export function initTooltips() {
    if (tooltipsInicializados) {
        console.log('ℹ️ Tooltips ya inicializados');
        return;
    }
    
    console.log('💡 Inicializando sistema de tooltips (modo click)...');
    
    const elementos = document.querySelectorAll('[data-tooltip]');
    console.log(`📊 Encontrados ${elementos.length} elementos con tooltip`);
    
    elementos.forEach(el => {
        const key = el.dataset.tooltip;
        const config = TOOLTIPS[key];
        
        if (!config) {
            console.warn(`⚠️ Tooltip no encontrado para: ${key}`);
            return;
        }
        
        // 🔴 CAMBIO: Solo mostrar tooltip con CLICK en el ícono de ayuda
        // Crear ícono de ayuda
        const ayudaIcon = document.createElement('span');
        ayudaIcon.className = 'ayuda-icono';
        ayudaIcon.textContent = 'ⓘ';
        ayudaIcon.style.cssText = `
            display: inline-block;
            margin-left: 6px;
            font-size: 14px;
            color: #94a3b8;
            cursor: pointer;
            transition: all 0.2s;
            pointer-events: all;
            padding: 2px 4px;
            border-radius: 4px;
        `;
        ayudaIcon.title = 'Hacé clic para ver ayuda';
        
        ayudaIcon.addEventListener('mouseenter', () => {
            ayudaIcon.style.color = '#2563eb';
            ayudaIcon.style.background = '#e8f0fe';
        });
        ayudaIcon.addEventListener('mouseleave', () => {
            ayudaIcon.style.color = '#94a3b8';
            ayudaIcon.style.background = 'transparent';
        });
        
        // 🔴 CLICK en el ícono para mostrar tooltip
        ayudaIcon.addEventListener('click', function(e) {
            e.stopPropagation();
            e.preventDefault();
            toggleTooltip(e, key, el);
        });
        
        // Insertar ícono al final del elemento
        el.appendChild(ayudaIcon);
    });
    
    tooltipsInicializados = true;
    console.log('✅ Tooltips inicializados (modo click)');
}

function toggleTooltip(event, key, targetElement) {
    // Si ya hay un tooltip activo y es del mismo elemento, cerrarlo
    if (tooltipActivo && tooltipActivo._targetKey === key) {
        ocultarTooltip();
        return;
    }
    
    // Cerrar tooltip anterior
    ocultarTooltip();
    
    const config = TOOLTIPS[key];
    if (!config) return;
    
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
    
    tooltip.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:6px;">
            <div style="font-weight:600;color:#60a5fa;font-size:15px;">
                ${config.titulo}
            </div>
            <button data-onclick="this.closest('.tooltip-contextual').remove()" 
                    style="background:transparent;border:none;color:#94a3b8;cursor:pointer;font-size:18px;padding:0 4px;line-height:1;">
                ✕
            </button>
        </div>
        <div style="color:#e2e8f0;margin-bottom:8px;">
            ${config.descripcion}
        </div>
        ${config.accion ? `
            <div style="font-size:12px;color:#94a3b8;border-top:1px solid #334155;padding-top:8px;margin-top:4px;">
                💡 ${config.accion}
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
    
    // Cerrar al hacer clic fuera
    setTimeout(() => {
        document.addEventListener('click', cerrarTooltipClickFuera);
    }, 100);
}

function cerrarTooltipClickFuera(e) {
    if (tooltipActivo && !tooltipActivo.contains(e.target) && !e.target.closest('.ayuda-icono')) {
        ocultarTooltip();
        document.removeEventListener('click', cerrarTooltipClickFuera);
    }
}

function ocultarTooltip() {
    if (tooltipActivo) {
        tooltipActivo.remove();
        tooltipActivo = null;
        document.removeEventListener('click', cerrarTooltipClickFuera);
    }
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