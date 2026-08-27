// ============================================================
// REPORTE: CONSOLIDADO VENTAS POR PAÍS - VERSIÓN CORREGIDA
// ============================================================

let anosDisponibles = [];
let anioSeleccionado = null;

// ============================================================
// FORMATEAR NÚMERO (punto como separador de miles, coma como decimal)
// ============================================================

function formatearNumero(valor) {
    if (valor === undefined || valor === null || isNaN(valor)) return '0,00';
    const partes = valor.toFixed(2).split('.');
    const entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return entero + ',' + partes[1];
}

// ============================================================
// CARGAR AÑOS DISPONIBLES
// ============================================================

export async function cargarAnosVentas() {
    console.log('📅 Cargando años disponibles...');
    
    try {
        const base = window.baseActiva || 'plataforma_rd';
        const sociedad = window.sociedadActiva || 'sidesys';
        
        const response = await fetch(`/api/reportes/anos_ventas?base=${base}&sociedad=${sociedad}`);
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        
        if (!data.success) {
            console.warn('⚠️ Error cargando años:', data.error);
            anosDisponibles = [2027, 2026, 2025];
            anioSeleccionado = anosDisponibles[0];
            actualizarSelectorAnios();
            return;
        }
        
        anosDisponibles = data.anos || [2027, 2026, 2025];
        anioSeleccionado = data.anio_default || anosDisponibles[0];
        
        console.log(`✅ Años disponibles: ${anosDisponibles.join(', ')}`);
        console.log(`✅ Año seleccionado: ${anioSeleccionado}`);
        
        actualizarSelectorAnios();
        
    } catch (e) {
        console.error('❌ Error cargando años:', e);
        anosDisponibles = [2027, 2026, 2025];
        anioSeleccionado = anosDisponibles[0];
        actualizarSelectorAnios();
    }
}

// ============================================================
// ACTUALIZAR SELECTOR DE AÑOS (CREA SI NO EXISTE)
// ============================================================

function actualizarSelectorAnios() {
    let container = document.getElementById('reporte-consolidado-pais');
    if (!container) {
        const moduleContent = document.getElementById('module-content');
        if (!moduleContent) {
            console.error('❌ No se encontró #module-content');
            return;
        }
        container = document.createElement('div');
        container.id = 'reporte-consolidado-pais';
        container.className = 'reporte-container';
        container.style.display = 'block';
        moduleContent.appendChild(container);
        console.log('✅ Contenedor #reporte-consolidado-pais creado');
    }
    
    let selector = document.getElementById('selectorAnioVentas');
    if (!selector) {
        const selectorHtml = `
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;background:#f8fafc;padding:12px 16px;border-radius:8px;border:1px solid #e2e8f0;">
                <label for="selectorAnioVentas" style="font-weight:600;color:#475569;">📅 Año:</label>
                <select id="selectorAnioVentas" style="padding:6px 12px;border:1px solid #cbd5e1;border-radius:6px;font-size:14px;background:white;">
                    <option value="">Cargando...</option>
                </select>
                <button id="btnActualizarConsolidado" style="padding:6px 16px;background:#2563eb;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                    🔄 Actualizar
                </button>
                <span id="total-registros-consolidado" style="font-size:13px;color:#64748b;margin-left:auto;"></span>
            </div>
            <div id="resultados-consolidado-pais" style="padding:4px 0;"></div>
        `;
        container.innerHTML = selectorHtml + container.innerHTML;
        selector = document.getElementById('selectorAnioVentas');
        console.log('✅ Selector de años creado');
        
        const btnActualizar = document.getElementById('btnActualizarConsolidado');
        if (btnActualizar) {
            btnActualizar.addEventListener('click', function() {
                cargarConsolidadoPais();
            });
        }
    }
    
    selector.innerHTML = '';
    anosDisponibles.forEach(anio => {
        const option = document.createElement('option');
        option.value = anio;
        option.textContent = anio;
        if (anio === anioSeleccionado) {
            option.selected = true;
        }
        selector.appendChild(option);
    });
    
    selector.onchange = function() {
        cargarConsolidadoPais();
    };
}

// ============================================================
// CARGAR REPORTE CONSOLIDADO POR PAÍS
// ============================================================

export async function cargarConsolidadoPais() {
    console.log('📊 Cargando reporte de Consolidado Ventas por País...');
    
    let container = document.getElementById('reporte-consolidado-pais');
    if (!container) {
        const moduleContent = document.getElementById('module-content');
        if (moduleContent) {
            container = document.createElement('div');
            container.id = 'reporte-consolidado-pais';
            container.className = 'reporte-container';
            container.style.display = 'block';
            moduleContent.appendChild(container);
            console.log('✅ Contenedor creado desde cargarConsolidadoPais');
        } else {
            console.error('❌ No se encontró #module-content');
            return;
        }
    }
    
    let selector = document.getElementById('selectorAnioVentas');
    if (!selector) {
        actualizarSelectorAnios();
        selector = document.getElementById('selectorAnioVentas');
        if (!selector) {
            console.error('❌ No se pudo crear el selector de años');
            return;
        }
    }
    
    anioSeleccionado = parseInt(selector.value) || 2026;
    console.log(`📅 Año seleccionado: ${anioSeleccionado}`);
    
    const resultadosDiv = document.getElementById('resultados-consolidado-pais');
    if (resultadosDiv) {
        resultadosDiv.innerHTML = `
            <div style="text-align:center;padding:30px;color:#94a3b8;">
                <div style="display:inline-block;width:30px;height:30px;border:3px solid #e2e8f0;border-top-color:#2563eb;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
                <div style="margin-top:10px;">⏳ Cargando datos para ${anioSeleccionado}...</div>
            </div>
            <style>
                @keyframes spin { to { transform: rotate(360deg); } }
            </style>
        `;
    }
    
    try {
        const base = window.baseActiva || 'plataforma_rd';
        const sociedad = window.sociedadActiva || 'sidesys';
        
        const url = `/api/reportes/consolidado_ventas_pais?base=${base}&sociedad=${sociedad}&anio=${anioSeleccionado}`;
        console.log(`📡 Fetching: ${url}`);
        
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        
        if (!data.success || data.error) {
            const errorHtml = `
                <div style="color:#dc2626;padding:20px;text-align:center;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;">
                    ❌ ${data.error || 'Error al cargar datos'}
                </div>
            `;
            if (resultadosDiv) {
                resultadosDiv.innerHTML = errorHtml;
            }
            return;
        }
        
        console.log(`✅ ${data.data?.length || 0} registros obtenidos para ${anioSeleccionado}`);
        
        const tablaHtml = generarResumenes(data);
        if (resultadosDiv) {
            resultadosDiv.innerHTML = tablaHtml;
        }
        
        const totalRegistros = document.getElementById('total-registros-consolidado');
        if (totalRegistros) {
            totalRegistros.textContent = `${data.data?.length || 0} registros`;
        }
        
    } catch (e) {
        console.error('❌ Error cargando consolidado por país:', e);
        const errorHtml = `
            <div style="color:#dc2626;padding:20px;text-align:center;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;">
                ❌ Error: ${e.message}
            </div>
        `;
        if (resultadosDiv) {
            resultadosDiv.innerHTML = errorHtml;
        }
    }
}

// ============================================================
// GENERAR RESÚMENES
// ============================================================

function generarResumenes(data) {
    const datos = data.data || [];
    const totales = data.totales || {};
    const resumenCliente = data.resumen_cliente || [];
    const resumenCentro = data.resumen_centro || [];
    const resumenSubdiario = data.resumen_subdiario || [];
    
    if (datos.length === 0) {
        return `
            <div style="text-align:center;padding:40px;color:#94a3b8;border:1px dashed #cbd5e1;border-radius:8px;">
                📭 No hay datos de ventas para el año ${totales.anio || anioSeleccionado || 'seleccionado'}
            </div>
        `;
    }
    
    const totalGeneral = totales.total_dl || 0;
    const totalLocal = totales.total_local || 0;
    const totalRegistros = totales.total_registros || datos.length;
    const anioActual = totales.anio || anioSeleccionado || 2026;
    
    let html = `
        <!-- TARJETAS DE TOTALES -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px;">
            <div style="background:#f0f4ff;padding:14px 18px;border-radius:8px;border:1px solid #93c5fd;">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Total USD</div>
                <div style="font-size:22px;font-weight:700;color:#1e293b;">${formatearNumero(totalGeneral)}</div>
            </div>
            <div style="background:#f0fdf4;padding:14px 18px;border-radius:8px;border:1px solid #86efac;">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Total Local</div>
                <div style="font-size:22px;font-weight:700;color:#1e293b;">${formatearNumero(totalLocal)}</div>
            </div>
            <div style="background:#fef3f2;padding:14px 18px;border-radius:8px;border:1px solid #fecdc9;">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Total Registros</div>
                <div style="font-size:22px;font-weight:700;color:#1e293b;">${totalRegistros.toLocaleString()}</div>
            </div>
            <div style="background:#fefce8;padding:14px 18px;border-radius:8px;border:1px solid #fde68a;">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Año</div>
                <div style="font-size:22px;font-weight:700;color:#1e293b;">${anioActual}</div>
            </div>
        </div>
        
        <!-- TABS -->
        <div style="display:flex;gap:4px;margin-bottom:12px;border-bottom:2px solid #e2e8f0;padding-bottom:0;flex-wrap:wrap;">
            <button class="tab-resumen active" data-tab="cliente" style="padding:8px 16px;border:none;background:#2563eb;color:white;border-radius:6px 6px 0 0;font-weight:600;cursor:pointer;font-size:13px;">👤 Por Cliente</button>
            <button class="tab-resumen" data-tab="centro" style="padding:8px 16px;border:none;background:transparent;color:#64748b;border-radius:6px 6px 0 0;font-weight:500;cursor:pointer;font-size:13px;">📂 Por Centro Costo</button>
            <button class="tab-resumen" data-tab="subdiario" style="padding:8px 16px;border:none;background:transparent;color:#64748b;border-radius:6px 6px 0 0;font-weight:500;cursor:pointer;font-size:13px;">📋 Por Subdiario</button>
        </div>
    `;
    
    html += `<div id="tab-cliente" class="tab-content" style="display:block;">`;
    html += generarTablaResumen(resumenCliente, 'Cliente', 'Total_DL', 'Transacciones', totalGeneral);
    html += `</div>`;
    
    html += `<div id="tab-centro" class="tab-content" style="display:none;">`;
    html += generarTablaResumen(resumenCentro, 'Centro_Costo', 'Total_DL', 'Transacciones', totalGeneral);
    html += `</div>`;
    
    html += `<div id="tab-subdiario" class="tab-content" style="display:none;">`;
    html += generarTablaResumen(resumenSubdiario, 'Subdiario', 'Total_DL', 'Transacciones', totalGeneral);
    html += `</div>`;
    
    // Script para tabs
    html += `
        <script>
            document.querySelectorAll('.tab-resumen').forEach(btn => {
                btn.addEventListener('click', function() {
                    document.querySelectorAll('.tab-resumen').forEach(b => {
                        b.classList.remove('active');
                        b.style.background = 'transparent';
                        b.style.color = '#64748b';
                        b.style.fontWeight = '500';
                    });
                    this.classList.add('active');
                    this.style.background = '#2563eb';
                    this.style.color = 'white';
                    this.style.fontWeight = '600';
                    
                    document.querySelectorAll('.tab-content').forEach(t => {
                        t.style.display = 'none';
                    });
                    
                    const tabId = this.dataset.tab;
                    const content = document.getElementById('tab-' + tabId);
                    if (content) {
                        content.style.display = 'block';
                    }
                });
            });
        </script>
    `;
    
    return html;
}

// ============================================================
// GENERAR TABLA DE RESUMEN
// ============================================================

function generarTablaResumen(datos, columnaNombre, columnaValor, columnaRegistros, totalGeneral) {
    if (!datos || datos.length === 0) {
        return `
            <div style="text-align:center;padding:20px;color:#94a3b8;">
                No hay datos para mostrar
            </div>
        `;
    }
    
    // Tomar valor absoluto para el total general (porque los signos ya están aplicados)
    const totalAbs = Math.abs(totalGeneral);
    
    let html = `
        <div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:8px;max-height:400px;overflow-y:auto;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead style="position:sticky;top:0;background:#f8fafc;border-bottom:2px solid #e2e8f0;z-index:1;">
                    <tr>
                        <th style="padding:8px 12px;text-align:left;font-weight:600;color:#475569;">${columnaNombre}</th>
                        <th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569;">Total USD</th>
                        ${columnaRegistros ? `<th style="padding:8px 12px;text-align:right;font-weight:600;color:#475569;">Registros</th>` : ''}
                        <th style="padding:8px 12px;text-align:center;font-weight:600;color:#475569;">% Participación</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    datos.forEach((row, i) => {
        const nombre = row[columnaNombre] || 'Sin nombre';
        const valor = parseFloat(row[columnaValor] || 0);
        const valorAbs = Math.abs(valor);
        const registros = columnaRegistros ? parseInt(row[columnaRegistros] || 0) : 0;
        const porcentaje = totalAbs > 0 ? (valorAbs / totalAbs * 100) : 0;
        const bg = i % 2 === 0 ? '#fafafa' : 'transparent';
        
        html += `
            <tr style="border-bottom:1px solid #f1f5f9;background:${bg};">
                <td style="padding:8px 12px;font-weight:500;">${nombre}</td>
                <td style="padding:8px 12px;text-align:right;font-variant-numeric:tabular-nums;font-weight:600;color:${valor < 0 ? '#dc2626' : '#16a34a'};">${formatearNumero(valor)}</td>
                ${columnaRegistros ? `<td style="padding:8px 12px;text-align:right;">${registros}</td>` : ''}
                <td style="padding:8px 12px;text-align:center;">
                    <div style="display:flex;align-items:center;gap:6px;justify-content:center;">
                        <span style="font-weight:600;">${porcentaje.toFixed(1)}%</span>
                        <div style="flex:1;max-width:80px;height:5px;background:#e2e8f0;border-radius:4px;overflow:hidden;">
                            <div style="height:100%;width:${Math.min(porcentaje, 100)}%;background:#2563eb;border-radius:4px;"></div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    return html;
}

// ============================================================
// INICIALIZAR REPORTE
// ============================================================

export function inicializarConsolidadoPais() {
    console.log('🚀 Inicializando Consolidado por País...');
    
    const container = document.getElementById('reporte-consolidado-pais');
    if (!container) {
        const moduleContent = document.getElementById('module-content');
        if (moduleContent) {
            const newContainer = document.createElement('div');
            newContainer.id = 'reporte-consolidado-pais';
            newContainer.className = 'reporte-container';
            newContainer.style.display = 'block';
            moduleContent.appendChild(newContainer);
            console.log('✅ Contenedor creado desde inicializarConsolidadoPais');
        }
    }
    
    cargarAnosVentas().then(() => {
        cargarConsolidadoPais();
    });
}

// ============================================================
// EXPONER FUNCIONES GLOBALES
// ============================================================

window.cargarConsolidadoPais = cargarConsolidadoPais;
window.cargarAnosVentas = cargarAnosVentas;
window.inicializarConsolidadoPais = inicializarConsolidadoPais;

console.log('✅ consolidado_pais.js cargado correctamente (versión corregida)');