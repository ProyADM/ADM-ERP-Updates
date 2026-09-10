// ============================================================
// REPORTE: CONSOLIDADO VENTAS POR PAÍS - VERSIÓN DEFINITIVA
// (Selector y contenedor de resultados creados automáticamente)
// ============================================================

let anosDisponibles = [];
let anioSeleccionado = null;
let datosCompletos = null;
let grupoActual = 'cliente';
let inicializado = false;
let datosPaisCache = {};
let cargandoAnos = false;

// ============================================================
// FORMATEAR NÚMERO
// ============================================================

function formatearNumero(valor) {
    if (valor === undefined || valor === null || isNaN(valor)) return '0,00';
    const partes = Number(valor).toFixed(2).split('.');
    const entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return entero + ',' + partes[1];
}

// ============================================================
// SANITIZAR HTML
// ============================================================

// ============================================================
// CARGAR AÑOS DISPONIBLES (UNA SOLA VEZ)
// ============================================================

async function cargarAnosVentas() {
    if (anosDisponibles.length > 0) return;
    if (cargandoAnos) {
        for (let i = 0; i < 10; i++) {
            await new Promise(r => setTimeout(r, 500));
            if (anosDisponibles.length > 0) return;
        }
        console.warn('⚠️ Timeout esperando años, usando valores por defecto');
        anosDisponibles = [2026, 2025, 2024];
        anioSeleccionado = 2026;
        return;
    }

    cargandoAnos = true;
    console.log('📅 Cargando años disponibles (una vez)...');

    try {
        const base = window.baseActiva || 'plataforma_rd';
        const sociedad = window.sociedadActiva || 'sidesys';
        const response = await fetch(`/api/reportes/anos_ventas?base=${base}&sociedad=${sociedad}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!data.success) {
            console.warn('⚠️ Error cargando años:', data.error);
            anosDisponibles = [2026, 2025, 2024];
            anioSeleccionado = 2026;
            return;
        }
        anosDisponibles = data.anos || [2026, 2025, 2024];
        anioSeleccionado = data.anio_default || 2026;
        console.log(`✅ Años disponibles: ${anosDisponibles.join(', ')}`);
        console.log(`✅ Año seleccionado: ${anioSeleccionado}`);
    } catch (e) {
        console.error('❌ Error cargando años:', e);
        anosDisponibles = [2026, 2025, 2024];
        anioSeleccionado = 2026;
    } finally {
        cargandoAnos = false;
    }
}

// ============================================================
// CREAR SELECTOR Y CONTENEDOR DE RESULTADOS (si no existen)
// ============================================================

function crearEstructuraSiNoExiste() {
    const container = document.getElementById('reporte-consolidado-pais');
    if (!container) {
        console.error('❌ No se encontró #reporte-consolidado-pais');
        return null;
    }

    // Verificar si ya existe el selector
    let selector = document.getElementById('selectorAnioVentas');
    let resultadosDiv = document.getElementById('resultados-consolidado-pais');

    // Si no existe el selector, crearlo con su contenedor de filtros
    if (!selector) {
        // Eliminar cualquier contenido previo para evitar duplicados (pero conservar el container)
        container.innerHTML = '';

        // Crear div de filtros
        const filtrosDiv = document.createElement('div');
        filtrosDiv.className = 'filtros-consolidado-pais';
        filtrosDiv.style.cssText = 'display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;background:#f8fafc;padding:12px 16px;border-radius:8px;border:1px solid #e2e8f0;';
        filtrosDiv.innerHTML = `
            <label for="selectorAnioVentas" style="font-weight:600;color:#475569;">📅 Año:</label>
            <select id="selectorAnioVentas" style="padding:6px 12px;border:1px solid #cbd5e1;border-radius:6px;font-size:14px;background:white;min-width:100px;"></select>
            <button id="btnActualizarConsolidado" style="padding:6px 16px;background:#2563eb;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                🔄 Actualizar
            </button>
            <span id="total-registros-consolidado" style="font-size:13px;color:#64748b;margin-left:auto;"></span>
        `;
        container.appendChild(filtrosDiv);

        // Crear div de resultados
        resultadosDiv = document.createElement('div');
        resultadosDiv.id = 'resultados-consolidado-pais';
        resultadosDiv.style.padding = '4px 0';
        container.appendChild(resultadosDiv);

        selector = document.getElementById('selectorAnioVentas');
        const btn = document.getElementById('btnActualizarConsolidado');

        // Llenar opciones y asignar eventos
        actualizarSelector(selector);
        if (btn) {
            btn.onclick = function() {
                cargarConsolidadoPais();
            };
        }
        selector.onchange = function() {
            anioSeleccionado = parseInt(this.value);
            cargarConsolidadoPais();
        };
    } else {
        // Si el selector ya existe pero no el div de resultados (por ejemplo, si se perdió), crearlo
        if (!resultadosDiv) {
            resultadosDiv = document.createElement('div');
            resultadosDiv.id = 'resultados-consolidado-pais';
            resultadosDiv.style.padding = '4px 0';
            container.appendChild(resultadosDiv);
        }
        // Actualizar el selector por si los años cambiaron
        actualizarSelector(selector);
    }

    return { selector, resultadosDiv };
}

function actualizarSelector(selector) {
    if (!selector) return;
    // Guardar el valor actual antes de llenar
    const valorActual = selector.value || anioSeleccionado || 2026;
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
    // Forzar el valor seleccionado
    selector.value = anioSeleccionado || 2026;
}

// ============================================================
// CARGAR REPORTE CONSOLIDADO POR PAÍS (SOLO DATOS)
// ============================================================

export async function cargarConsolidadoPais() {
    console.log('📊 Cargando datos de Consolidado Ventas por País...');

    // Asegurar que la estructura (selector + resultados) existe
    const estructura = crearEstructuraSiNoExiste();
    if (!estructura) {
        console.error('❌ No se pudo crear la estructura del reporte');
        return;
    }
    const { selector, resultadosDiv } = estructura;

    // Asegurar que el valor del selector sea correcto
    let anio = parseInt(selector.value);
    if (isNaN(anio) || !anosDisponibles.includes(anio)) {
        anio = anioSeleccionado || 2026;
        selector.value = anio;
    }
    if (anio !== anioSeleccionado) {
        anioSeleccionado = anio;
    }

    resultadosDiv.innerHTML = `
        <div style="text-align:center;padding:30px;color:#94a3b8;">
            <div class="spinner" style="display:inline-block;width:30px;height:30px;border:3px solid #e2e8f0;border-top-color:#2563eb;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
            <div style="margin-top:10px;">⏳ Cargando datos para ${anioSeleccionado}...</div>
            <style>
                @keyframes spin { to { transform: rotate(360deg); } }
            </style>
        </div>
    `;

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
                    ❌ ${escapeHTML(data.error || 'Error al cargar datos')}
                </div>
            `;
            resultadosDiv.innerHTML = errorHtml;
            return;
        }

        if (data.data && data.data.length > 0) {
            console.log('🔍 Primer registro (país):', data.data[0]);
            console.log('🔍 Campos disponibles:', Object.keys(data.data[0]));
        }

        datosCompletos = data;
        datosPaisCache[anioSeleccionado] = data;
        console.log(`✅ ${data.data?.length || 0} registros obtenidos para ${anioSeleccionado}`);

        const tablaHtml = generarVistaCompleta(data);
        resultadosDiv.innerHTML = tablaHtml;

        const totalRegistros = document.getElementById('total-registros-consolidado');
        if (totalRegistros) {
            totalRegistros.textContent = `${data.data?.length || 0} registros`;
        }

        // Activar pestaña Cliente por defecto
        if (typeof window.mostrarTabPais === 'function') {
            window.mostrarTabPais('cliente');
        }

    } catch (e) {
        console.error('❌ Error cargando consolidado por país:', e);
        const errorHtml = `
            <div style="color:#dc2626;padding:20px;text-align:center;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;">
                ❌ Error: ${escapeHTML(e.message)}
            </div>
        `;
        resultadosDiv.innerHTML = errorHtml;
    }
}

// ============================================================
// GENERAR VISTA COMPLETA (RESUMEN + PESTAÑAS + TABLA PIVOT)
// ============================================================

function generarVistaCompleta(data) {
    const datos = data.data || [];
    const totales = data.totales || {};

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
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px;">
            <div style="background:#f0f4ff;padding:14px 18px;border-radius:10px;border:1px solid #93c5fd;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Total USD</div>
                <div style="font-size:24px;font-weight:700;color:#1e293b;">${formatearNumero(totalGeneral)}</div>
            </div>
            <div style="background:#f0fdf4;padding:14px 18px;border-radius:10px;border:1px solid #86efac;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Total Local</div>
                <div style="font-size:24px;font-weight:700;color:#1e293b;">${formatearNumero(totalLocal)}</div>
            </div>
            <div style="background:#fef3f2;padding:14px 18px;border-radius:10px;border:1px solid #fecdc9;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Registros</div>
                <div style="font-size:24px;font-weight:700;color:#1e293b;">${totalRegistros.toLocaleString()}</div>
            </div>
            <div style="background:#fefce8;padding:14px 18px;border-radius:10px;border:1px solid #fde68a;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Año</div>
                <div style="font-size:24px;font-weight:700;color:#1e293b;">${anioActual}</div>
            </div>
        </div>

        <!-- TABS -->
        <div style="display:flex;gap:4px;margin-bottom:12px;border-bottom:2px solid #e2e8f0;flex-wrap:wrap;">
            <button class="tab-pais active" data-tab="cliente" data-onclick="window.mostrarTabPais('cliente')" style="padding:8px 20px;border:none;background:#2563eb;color:white;border-radius:8px 8px 0 0;font-weight:600;cursor:pointer;font-size:13px;transition:all 0.2s;">
                👤 Por Cliente
            </button>
            <button class="tab-pais" data-tab="centro" data-onclick="window.mostrarTabPais('centro')" style="padding:8px 20px;border:none;background:transparent;color:#64748b;border-radius:8px 8px 0 0;font-weight:500;cursor:pointer;font-size:13px;transition:all 0.2s;">
                📂 Por Centro Costo
            </button>
        </div>
    `;

    html += `<div id="tab-pais-cliente" class="tab-pais-content" style="display:block;">`;
    html += generarTablaPivot(datos, 'cliente');
    html += `</div>`;

    html += `<div id="tab-pais-centro" class="tab-pais-content" style="display:none;">`;
    html += generarTablaPivot(datos, 'centro');
    html += `</div>`;

    return html;
}

// ============================================================
// GENERAR TABLA PIVOTANTE (MESES + TOTALES) - ROBUSTA
// ============================================================

function generarTablaPivot(datos, grupo) {
    if (!datos || datos.length === 0) {
        return `<div style="text-align:center;padding:20px;color:#94a3b8;">No hay datos para mostrar</div>`;
    }

    const primeraFila = datos[0];
    const posiblesUSD = ['Importe_DL', 'Total', 'Importe', 'Monto', 'Total_USD', 'USD'];
    const campoUSD = posiblesUSD.find(c => c in primeraFila) || 'Importe_DL';

    const claveGrupo = grupo === 'cliente' ? 'NombreCliente' : 'CentroCosto';
    const nombreColumna = grupo === 'cliente' ? 'Cliente' : 'Centro Costo';

    const grupos = {};
    const mesesSet = new Set();

    datos.forEach(row => {
        const entidad = row[claveGrupo] || 'Sin nombre';
        const anio = parseInt(row.Anio) || parseInt(row.Año) || 0;
        const mes = parseInt(row.Mes) || 0;
        const importe = parseFloat(row[campoUSD]) || 0;

        if (anio === 0 || mes === 0) return;

        const nombreMes = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'][mes] || mes;
        const mesKey = `${nombreMes}-${String(anio).slice(-2)}`;

        if (!grupos[entidad]) {
            grupos[entidad] = { meses: {} };
        }
        if (!grupos[entidad].meses[mesKey]) {
            grupos[entidad].meses[mesKey] = 0;
        }
        grupos[entidad].meses[mesKey] += importe;
        mesesSet.add(mesKey);
    });

    if (mesesSet.size === 0) {
        return `<div style="text-align:center;padding:20px;color:#94a3b8;">No hay datos con fechas válidas</div>`;
    }

    const mesesOrdenados = Array.from(mesesSet).sort((a, b) => {
        const [mesA, anioA] = a.split('-');
        const [mesB, anioB] = b.split('-');
        const mesNumA = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'].indexOf(mesA) + 1;
        const mesNumB = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'].indexOf(mesB) + 1;
        if (anioA !== anioB) return parseInt(anioA) - parseInt(anioB);
        return mesNumA - mesNumB;
    });

    const entidades = Object.keys(grupos).sort((a, b) => a.localeCompare(b));

    let totalGeneral = 0;
    const totalPorMes = {};
    mesesOrdenados.forEach(m => totalPorMes[m] = 0);

    let html = `
        <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead style="background:#f8fafc;border-bottom:2px solid #e2e8f0;">
                        <tr>
                            <th style="padding:10px 14px;text-align:left;font-weight:600;color:#475569;min-width:150px;background:#f8fafc;">${nombreColumna}</th>
    `;

    mesesOrdenados.forEach(m => {
        html += `<th style="padding:10px 8px;text-align:right;font-weight:600;color:#475569;min-width:70px;background:#f8fafc;font-size:11px;">${escapeHTML(m)}</th>`;
    });

    html += `
                            <th style="padding:10px 14px;text-align:right;font-weight:600;color:#475569;min-width:90px;background:#fef3c7;">Total</th>
                            <th style="padding:10px 14px;text-align:right;font-weight:600;color:#475569;min-width:80px;background:#e8f0fe;">% Part.</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    // 🔴 DOS PASADAS para que "% Part." use el TOTAL FINAL como denominador.
    // (Antes se calculaba contra un totalGeneral parcial que crecía dentro del
    // mismo bucle de render → porcentajes incorrectos: no sumaban 100.)
    const filasConTotal = [];
    entidades.forEach(entidad => {
        const fila = grupos[entidad].meses;
        let totalFila = 0;

        mesesOrdenados.forEach(m => {
            totalFila += (fila[m] || 0);
        });

        if (totalFila === 0) return;

        filasConTotal.push({ entidad, fila, totalFila });
        totalGeneral += totalFila;
        mesesOrdenados.forEach(m => {
            totalPorMes[m] += (fila[m] || 0);
        });
    });

    filasConTotal.forEach((item, i) => {
        const { entidad, fila, totalFila } = item;
        const porcentajeFila = totalGeneral > 0 ? (totalFila / totalGeneral * 100) : 0;
        const bg = i % 2 === 0 ? '#fafafa' : 'transparent';

        html += `
            <tr style="border-bottom:1px solid #f1f5f9;background:${bg};">
                <td style="padding:8px 14px;font-weight:500;color:#1e293b;">${escapeHTML(entidad)}</td>
        `;

        mesesOrdenados.forEach(m => {
            const valor = fila[m] || 0;
            html += `<td style="padding:8px 8px;text-align:right;font-variant-numeric:tabular-nums;color:#334155;">${valor !== 0 ? formatearNumero(valor) : '-'}</td>`;
        });

        html += `
                <td style="padding:8px 14px;text-align:right;font-weight:700;color:#1e293b;background:#fef3c7;">${formatearNumero(totalFila)}</td>
                <td style="padding:8px 14px;text-align:right;font-weight:600;color:#2563eb;background:#e8f0fe;">${porcentajeFila.toFixed(2)}%</td>
            </tr>
        `;
    });

    html += `
        <tr style="font-weight:bold;background:#f0f4ff;border-top:2px solid #e2e8f0;">
            <td style="padding:10px 14px;font-size:14px;color:#1e293b;">TOTAL GENERAL</td>
    `;

    mesesOrdenados.forEach(m => {
        html += `<td style="padding:10px 8px;text-align:right;font-size:14px;color:#1e293b;">${formatearNumero(totalPorMes[m])}</td>`;
    });

    html += `
            <td style="padding:10px 14px;text-align:right;font-size:16px;color:#2563eb;background:#fef3c7;">${formatearNumero(totalGeneral)}</td>
            <td style="padding:10px 14px;text-align:right;font-size:14px;color:#2563eb;background:#e8f0fe;">100%</td>
        </tr>
    `;

    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    return html;
}

// ============================================================
// FUNCIÓN PARA CAMBIAR PESTAÑAS (GLOBAL)
// ============================================================

window.mostrarTabPais = function(tab) {
    document.querySelectorAll('.tab-pais-content').forEach(el => {
        el.style.display = 'none';
    });
    const target = document.getElementById('tab-pais-' + tab);
    if (target) {
        target.style.display = 'block';
    }
    document.querySelectorAll('.tab-pais').forEach(btn => {
        btn.classList.remove('active');
        btn.style.background = 'transparent';
        btn.style.color = '#64748b';
        btn.style.fontWeight = '500';
    });
    const activeBtn = document.querySelector(`.tab-pais[data-tab="${tab}"]`);
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.style.background = '#2563eb';
        activeBtn.style.color = 'white';
        activeBtn.style.fontWeight = '600';
    }
};

// ============================================================
// INICIALIZAR REPORTE (LLAMAR DESDE reportes.js)
// ============================================================

export async function inicializarConsolidadoPais() {
    console.log('🚀 Inicializando Consolidado por País...');

    // Cargar años si no están disponibles
    await cargarAnosVentas();

    // Crear la estructura (selector + resultados) si no existe
    const estructura = crearEstructuraSiNoExiste();
    if (!estructura) {
        console.error('❌ No se pudo crear la estructura del reporte');
        return;
    }

    // Asegurar que el valor del selector sea 2026
    const selector = document.getElementById('selectorAnioVentas');
    if (selector) {
        selector.value = anioSeleccionado || 2026;
    }

    // Si ya estaba inicializado, solo recargar datos
    if (inicializado) {
        console.log('ℹ️ Reporte ya inicializado, recargando datos...');
        await cargarConsolidadoPais();
        return;
    }

    inicializado = true;
    await cargarConsolidadoPais();
}

// ============================================================
// EXPONER FUNCIONES GLOBALES
// ============================================================

window.cargarConsolidadoPais = cargarConsolidadoPais;
window.inicializarConsolidadoPais = inicializarConsolidadoPais;

console.log('✅ consolidado_pais.js cargado (estructura automática)');