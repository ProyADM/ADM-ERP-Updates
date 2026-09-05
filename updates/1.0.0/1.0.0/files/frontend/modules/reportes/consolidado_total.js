// ============================================================
// REPORTE: CONSOLIDADO VENTAS GLOBAL - VERSIÓN CON VENTAS MANUALES Y MARCADO NARANJA
// MEJORA: Conversión de sigla a nombre completo para que el marcado funcione
// MEJORA: Muestra siglas en la tabla en lugar de nombres completos
// ============================================================

let datosGlobales = null;
let anioSeleccionadoGlobal = null;
let anosDisponiblesGlobal = [];
let datosOriginalesGlobal = [];
let inicializadoGlobal = false;
let cargandoAnosGlobal = false;
let ventasManualesData = {};

// Mapeo de sigla a nombre completo de país
const SIGLA_A_PAIS = {
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

// Mapeo inverso: nombre completo a sigla (para mostrar siglas en la tabla)
const PAIS_A_SIGLA = {
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

function escapeHTML(str) {
    if (!str) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(str).replace(/[&<>"']/g, function(m) { return map[m]; });
}

// ============================================================
// CARGAR AÑOS DISPONIBLES (UNA SOLA VEZ)
// ============================================================

async function cargarAnosDisponiblesGlobal() {
    if (anosDisponiblesGlobal.length > 0) return;
    if (cargandoAnosGlobal) {
        for (let i = 0; i < 10; i++) {
            await new Promise(r => setTimeout(r, 500));
            if (anosDisponiblesGlobal.length > 0) return;
        }
        console.warn('⚠️ Timeout esperando años globales, usando valores por defecto');
        anosDisponiblesGlobal = [2026, 2025, 2024];
        anioSeleccionadoGlobal = 2026;
        return;
    }

    cargandoAnosGlobal = true;
    try {
        const base = window.baseActiva || 'plataforma_rd';
        const sociedad = window.sociedadActiva || 'sidesys';
        const response = await fetch(`/api/reportes/anos_ventas?base=${base}&sociedad=${sociedad}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (data.success && data.anos) {
            anosDisponiblesGlobal = data.anos.sort((a, b) => b - a);
            anioSeleccionadoGlobal = data.anio_default || 2026;
        } else {
            anosDisponiblesGlobal = [2026, 2025, 2024];
            anioSeleccionadoGlobal = 2026;
        }
    } catch (e) {
        console.warn('⚠️ Error cargando años globales:', e);
        anosDisponiblesGlobal = [2026, 2025, 2024];
        anioSeleccionadoGlobal = 2026;
    } finally {
        cargandoAnosGlobal = false;
    }
}

// ============================================================
// CARGAR REPORTE CONSOLIDADO TOTAL (SOLO DATOS)
// ============================================================

export async function cargarConsolidadoTotal() {
    console.log('📊 Cargando datos de Consolidado Total de Ventas...');

    const selector = document.getElementById('selectorAnioGlobal');
    if (!selector) {
        console.error('❌ Selector global no encontrado. Ejecutar inicializarConsolidadoTotal() primero.');
        const container = document.getElementById('reporte-consolidado-total');
        if (container) {
            container.innerHTML = `
                <div style="color:#dc2626;padding:20px;text-align:center;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;">
                    ❌ Error: El selector no está inicializado. Recarga la página o ejecuta inicializarConsolidadoTotal().
                </div>
            `;
        }
        return;
    }

    let anio = parseInt(selector.value);
    if (isNaN(anio) || !anosDisponiblesGlobal.includes(anio)) {
        anio = anioSeleccionadoGlobal || 2026;
        selector.value = anio;
    }
    if (anio !== anioSeleccionadoGlobal) {
        anioSeleccionadoGlobal = anio;
    }

    const resultadosDiv = document.getElementById('resultados-consolidado-global');
    if (!resultadosDiv) return;

    resultadosDiv.innerHTML = `
        <div style="text-align:center;padding:30px;color:#94a3b8;">
            <div class="spinner" style="display:inline-block;width:30px;height:30px;border:3px solid #e2e8f0;border-top-color:#2563eb;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
            <div style="margin-top:10px;">⏳ Cargando datos para ${anioSeleccionadoGlobal}...</div>
        </div>
    `;

    try {
        const base = window.baseActiva || 'plataforma_rd';
        const sociedad = window.sociedadActiva || 'sidesys';
        const url = `/api/reportes/consolidado_ventas_global?base=${base}&sociedad=${sociedad}&anio=${anioSeleccionadoGlobal}`;
        console.log(`📡 Fetching: ${url}`);

        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (!data.success || data.error) {
            resultadosDiv.innerHTML = `
                <div style="color:#dc2626;padding:20px;text-align:center;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;">
                    ❌ ${data.error || 'Error al cargar datos'}
                </div>
            `;
            return;
        }

        ventasManualesData = data.ventas_manuales || {};
        console.log('📦 Ventas manuales recibidas:', ventasManualesData);

        if (data.data && data.data.length > 0) {
            console.log('🔍 Primer registro:', data.data[0]);
            console.log('🔍 Campos disponibles:', Object.keys(data.data[0]));
        }

        datosOriginalesGlobal = data.data || [];
        datosGlobales = procesarDatosGlobales(datosOriginalesGlobal);
        console.log(`✅ ${datosOriginalesGlobal.length} registros obtenidos para ${anioSeleccionadoGlobal}`);

        const html = generarVistaGlobal(datosGlobales, ventasManualesData);
        resultadosDiv.innerHTML = html;

        const totalRegistros = document.getElementById('total-registros-global');
        if (totalRegistros) {
            totalRegistros.textContent = `${datosOriginalesGlobal.length} registros`;
        }

    } catch (e) {
        console.error('❌ Error cargando consolidado global:', e);
        resultadosDiv.innerHTML = `
            <div style="color:#dc2626;padding:20px;text-align:center;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;">
                ❌ Error: ${escapeHTML(e.message)}
            </div>
        `;
    }
}

// ============================================================
// PROCESAR DATOS GLOBALES (agrupar por país y mes) - CON CONVERSIÓN DE SIGLA A NOMBRE COMPLETO
// ============================================================

function procesarDatosGlobales(datos) {
    if (!datos || datos.length === 0) return [];

    const primeraFila = datos[0];
    const posiblesUSD = ['Importe_DL', 'Total', 'Importe', 'Monto', 'Total_USD', 'USD'];
    const posiblesTrans = ['Transacciones', 'Cantidad', 'Numero', 'Count'];

    let campoUSD = posiblesUSD.find(c => c in primeraFila) || 'Importe_DL';
    let campoTrans = posiblesTrans.find(c => c in primeraFila) || 'Transacciones';

    console.log(`🔍 Usando campos: USD=${campoUSD}, Trans=${campoTrans}`);

    const paises = {};
    const mesesSet = new Set();

    datos.forEach(row => {
        // Primero intentar obtener el nombre completo del país
        let pais = row.Pais || row.Base || row.Sigla || 'Sin País';
        // Si es una sigla (2 letras), convertir a nombre completo
        if (pais.length === 2 && SIGLA_A_PAIS[pais]) {
            pais = SIGLA_A_PAIS[pais];
        }
        // Si viene 'AR' y no está en el mapeo (por si acaso), dejar como está
        const anio = parseInt(row.Anio) || parseInt(row.Año) || 0;
        const mes = parseInt(row.Mes) || 0;
        const importeDL = parseFloat(row[campoUSD]) || 0;
        const transacciones = parseInt(row[campoTrans]) || 0;

        const key = pais;
        const mesKey = `${anio}-${String(mes).padStart(2, '0')}`;

        if (!paises[key]) {
            paises[key] = {
                pais: pais,
                meses: {},
                totalDL: 0,
                totalTransacciones: 0,
            };
        }

        if (!paises[key].meses[mesKey]) {
            paises[key].meses[mesKey] = { dl: 0, transacciones: 0 };
        }
        paises[key].meses[mesKey].dl += importeDL;
        paises[key].meses[mesKey].transacciones += transacciones;

        paises[key].totalDL += importeDL;
        paises[key].totalTransacciones += transacciones;

        if (anio > 0 && mes > 0) {
            mesesSet.add(mesKey);
        }
    });

    const mesesOrdenados = Array.from(mesesSet).sort((a, b) => {
        const [aAnio, aMes] = a.split('-').map(Number);
        const [bAnio, bMes] = b.split('-').map(Number);
        if (aAnio !== bAnio) return aAnio - bAnio;
        return aMes - bMes;
    });

    const resultado = Object.values(paises).map(p => {
        const mesesData = {};
        mesesOrdenados.forEach(m => {
            mesesData[m] = p.meses[m] || { dl: 0, transacciones: 0 };
        });
        return {
            ...p,
            meses: mesesData,
            mesesOrdenados: mesesOrdenados
        };
    });

    resultado.sort((a, b) => b.totalDL - a.totalDL);
    return resultado;
}

// ============================================================
// GENERAR VISTA GLOBAL (CON MARCADO NARANJA Y SIGLAS)
// ============================================================

function generarVistaGlobal(datos, ventasManuales) {
    if (!datos || datos.length === 0) {
        return `
            <div style="text-align:center;padding:40px;color:#94a3b8;border:1px dashed #cbd5e1;border-radius:8px;">
                📭 No hay datos de ventas globales para el año ${anioSeleccionadoGlobal}
            </div>
        `;
    }

    const totalDLGeneral = datos.reduce((acc, p) => acc + p.totalDL, 0);
    const totalTransaccionesGeneral = datos.reduce((acc, p) => acc + p.totalTransacciones, 0);
    const totalPaises = datos.length;

    const nombresMesesCortos = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const todosMeses = datos.length > 0 ? datos[0].mesesOrdenados || [] : [];
    const top5 = datos.slice(0, 5);

    const tieneVentaManual = (pais, anio, mes) => {
        const key = `${pais}|${anio}|${mes}`;
        return ventasManuales && ventasManuales[key] && ventasManuales[key] > 0;
    };

    const hayVentasManuales = Object.keys(ventasManuales).length > 0;

    let html = `
        <!-- TARJETAS DE TOTALES -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px;">
            <div style="background:#f0f4ff;padding:14px 18px;border-radius:10px;border:1px solid #93c5fd;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Total Ventas (USD)</div>
                <div style="font-size:24px;font-weight:700;color:#1e293b;">${formatearNumero(totalDLGeneral)}</div>
            </div>
            <div style="background:#fef3f2;padding:14px 18px;border-radius:10px;border:1px solid #fecdc9;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Total Transacciones</div>
                <div style="font-size:24px;font-weight:700;color:#1e293b;">${totalTransaccionesGeneral.toLocaleString()}</div>
            </div>
            <div style="background:#fefce8;padding:14px 18px;border-radius:10px;border:1px solid #fde68a;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
                <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Total Países</div>
                <div style="font-size:24px;font-weight:700;color:#1e293b;">${totalPaises}</div>
            </div>
        </div>

        <!-- GRÁFICO DE BARRAS (TOP 5) -->
        <div style="background:white;border-radius:10px;padding:16px 20px;margin-bottom:20px;border:1px solid #e2e8f0;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
            <div style="font-size:14px;font-weight:600;color:#1e293b;margin-bottom:12px;">📊 Top 5 países en ventas (USD)</div>
            <div style="display:flex;flex-direction:column;gap:8px;">
                ${top5.map((p, i) => {
                    const porcentaje = totalDLGeneral > 0 ? (p.totalDL / totalDLGeneral * 100) : 0;
                    const colores = ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe'];
                    // Mostrar sigla en el gráfico
                    const siglaMostrar = PAIS_A_SIGLA[p.pais] || p.pais;
                    return `
                        <div style="display:flex;align-items:center;gap:12px;">
                            <span style="font-size:13px;font-weight:500;min-width:80px;color:#475569;">${escapeHTML(siglaMostrar)}</span>
                            <div style="flex:1;height:24px;background:#f1f5f9;border-radius:6px;overflow:hidden;position:relative;">
                                <div style="height:100%;width:${Math.min(porcentaje, 100)}%;background:${colores[i % colores.length]};border-radius:6px;transition:width 0.6s ease;display:flex;align-items:center;justify-content:flex-end;padding-right:6px;font-size:11px;color:white;font-weight:600;">
                                    ${porcentaje > 8 ? porcentaje.toFixed(1) + '%' : ''}
                                </div>
                            </div>
                            <span style="font-size:13px;font-weight:600;color:#1e293b;min-width:90px;text-align:right;">${formatearNumero(p.totalDL)}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>

        <!-- TABLA DETALLADA -->
        <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
            <div style="overflow-x:auto;max-height:500px;overflow-y:auto;">
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead style="position:sticky;top:0;background:#f8fafc;border-bottom:2px solid #e2e8f0;z-index:2;">
                        <tr>
                            <th style="padding:10px 14px;text-align:left;font-weight:600;color:#475569;min-width:120px;background:#f8fafc;">País</th>
                            ${todosMeses.length > 0 ? todosMeses.map(m => {
                                const [anio, mes] = m.split('-').map(Number);
                                const label = `${nombresMesesCortos[mes] || mes} ${String(anio).slice(-2)}`;
                                return `<th style="padding:10px 8px;text-align:right;font-weight:600;color:#475569;min-width:65px;background:#f8fafc;font-size:11px;">${label}</th>`;
                            }).join('') : `<th style="padding:10px 8px;text-align:center;font-weight:400;color:#94a3b8;background:#f8fafc;">(sin datos mensuales)</th>`}
                            <th style="padding:10px 14px;text-align:right;font-weight:600;color:#475569;min-width:90px;background:#fef3c7;">Total USD</th>
                            <th style="padding:10px 14px;text-align:right;font-weight:600;color:#475569;min-width:80px;background:#e8f0fe;">% Part.</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    if (todosMeses.length === 0) {
        datos.forEach((p, idx) => {
            const bg = idx % 2 === 0 ? '#fafafa' : 'transparent';
            const porcentaje = totalDLGeneral > 0 ? (p.totalDL / totalDLGeneral * 100) : 0;
            const siglaMostrar = PAIS_A_SIGLA[p.pais] || p.pais;
            html += `
                <tr style="border-bottom:1px solid #f1f5f9;background:${bg};">
                    <td style="padding:8px 14px;font-weight:500;color:#1e293b;">🌐 ${escapeHTML(siglaMostrar)}</td>
                    <td style="padding:8px 8px;text-align:center;color:#94a3b8;">-</td>
                    <td style="padding:8px 14px;text-align:right;font-weight:700;color:#1e293b;background:#fef3c7;">${formatearNumero(p.totalDL)}</td>
                    <td style="padding:8px 14px;text-align:right;font-weight:600;color:#2563eb;background:#e8f0fe;">${porcentaje.toFixed(1)}%</td>
                </tr>
            `;
        });
        html += `
            <tr style="font-weight:bold;background:#f0f4ff;border-top:2px solid #e2e8f0;">
                <td style="padding:10px 14px;font-size:14px;color:#1e293b;">TOTAL GENERAL</td>
                <td style="padding:10px 8px;text-align:center;color:#94a3b8;">-</td>
                <td style="padding:10px 14px;text-align:right;font-size:16px;color:#2563eb;background:#fef3c7;">${formatearNumero(totalDLGeneral)}</td>
                <td style="padding:10px 14px;text-align:right;font-size:14px;color:#2563eb;background:#e8f0fe;">100%</td>
            </tr>
        `;
        if (hayVentasManuales) {
            html += `
                <tr style="background:#f0f9ff;border-top:1px solid #93c5fd;">
                    <td colspan="4" style="padding:6px 14px;font-size:12px;color:#1e40af;">
                        🟠 Las celdas con fondo naranja indican que tienen ventas manuales cargadas.
                    </td>
                </tr>
            `;
        }
    } else {
        datos.forEach((p, idx) => {
            const bg = idx % 2 === 0 ? '#fafafa' : 'transparent';
            const porcentaje = totalDLGeneral > 0 ? (p.totalDL / totalDLGeneral * 100) : 0;
            const siglaMostrar = PAIS_A_SIGLA[p.pais] || p.pais;

            html += `
                <tr style="border-bottom:1px solid #f1f5f9;background:${bg};">
                    <td style="padding:8px 14px;font-weight:500;color:#1e293b;">🌐 ${escapeHTML(siglaMostrar)}</td>
            `;

            todosMeses.forEach(m => {
                const [anio, mes] = m.split('-').map(Number);
                const mesData = p.meses[m] || { dl: 0 };
                const valor = mesData.dl || 0;
                const tieneManual = tieneVentaManual(p.pais, anio, mes);
                // 🔴 CAMBIO: Color naranja con borde izquierdo, sin lápiz
                const style = tieneManual ? 'background-color:#fde68a; font-weight:600; border-left:3px solid #f59e0b;' : '';
                html += `<td style="padding:8px 8px;text-align:right;font-variant-numeric:tabular-nums;color:#334155;${style}">${valor !== 0 ? formatearNumero(valor) : '-'}</td>`;
            });

            html += `
                    <td style="padding:8px 14px;text-align:right;font-weight:700;color:#1e293b;background:#fef3c7;">${formatearNumero(p.totalDL)}</td>
                    <td style="padding:8px 14px;text-align:right;font-weight:600;color:#2563eb;background:#e8f0fe;">${porcentaje.toFixed(1)}%</td>
                </tr>
            `;
        });

        // Fila de totales por mes
        html += `
            <tr style="font-weight:bold;background:#f0f4ff;border-top:2px solid #e2e8f0;">
                <td style="padding:10px 14px;font-size:14px;color:#1e293b;">TOTAL GENERAL</td>
        `;

        todosMeses.forEach(m => {
            const [anio, mes] = m.split('-').map(Number);
            let totalMes = 0;
            datos.forEach(p => {
                totalMes += (p.meses[m] || { dl: 0 }).dl || 0;
            });
            html += `<td style="padding:10px 8px;text-align:right;font-size:14px;color:#1e293b;">${formatearNumero(totalMes)}</td>`;
        });

        html += `
                <td style="padding:10px 14px;text-align:right;font-size:16px;color:#2563eb;background:#fef3c7;">${formatearNumero(totalDLGeneral)}</td>
                <td style="padding:10px 14px;text-align:right;font-size:14px;color:#2563eb;background:#e8f0fe;">100%</td>
            </tr>
        `;

        if (hayVentasManuales) {
            html += `
                <tr style="background:#f0f9ff;border-top:1px solid #93c5fd;">
                    <td colspan="${todosMeses.length + 3}" style="padding:6px 14px;font-size:12px;color:#1e40af;">
                        🟠 Las celdas con fondo naranja indican que tienen ventas manuales cargadas.
                    </td>
                </tr>
            `;
        }
    }

    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    return html;
}

// ============================================================
// EXPORTAR CSV GLOBAL
// ============================================================

function exportarGlobalCSV() {
    if (!datosOriginalesGlobal || datosOriginalesGlobal.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para exportar', 'Reportes');
        return;
    }

    const columnas = ['País', 'Año', 'Mes', 'Importe USD', 'Transacciones'];
    let csv = columnas.join(',') + '\n';

    datosOriginalesGlobal.forEach(row => {
        let pais = row.Pais || row.Base || row.Sigla || 'Sin País';
        if (pais.length === 2 && SIGLA_A_PAIS[pais]) {
            pais = SIGLA_A_PAIS[pais];
        }
        const anio = row.Anio || row.Año || '';
        const mes = row.Mes || '';
        const importeDL = row.Importe_DL || row.Total || row.Importe || 0;
        const transacciones = row.Transacciones || row.Cantidad || 0;
        csv += `"${pais}",${anio},${mes},${importeDL},${transacciones}\n`;
    });

    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `consolidado_global_${anioSeleccionadoGlobal}_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    if (typeof toastSuccess === 'function') toastSuccess('✅ Reporte exportado a CSV', 'Reportes');
}

// ============================================================
// INICIALIZAR REPORTE GLOBAL
// ============================================================

export async function inicializarConsolidadoTotal() {
    console.log('🚀 Inicializando Consolidado Total de Ventas...');

    const selector = document.getElementById('selectorAnioGlobal');
    if (!selector) {
        inicializadoGlobal = false;
        console.log('🔄 Selector global no encontrado, reinicializando...');
    }

    if (inicializadoGlobal) {
        console.log('ℹ️ Reporte global ya inicializado, recargando datos...');
        await cargarConsolidadoTotal();
        return;
    }

    const container = document.getElementById('reporte-consolidado-total');
    if (!container) {
        console.error('❌ No se encontró #reporte-consolidado-total');
        return;
    }

    if (document.getElementById('selectorAnioGlobal') && !inicializadoGlobal) {
        inicializadoGlobal = true;
        await cargarConsolidadoTotal();
        return;
    }

    await cargarAnosDisponiblesGlobal();

    container.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;background:#f8fafc;padding:12px 16px;border-radius:8px;border:1px solid #e2e8f0;">
            <label for="selectorAnioGlobal" style="font-weight:600;color:#475569;">📅 Año:</label>
            <select id="selectorAnioGlobal" style="padding:6px 12px;border:1px solid #cbd5e1;border-radius:6px;font-size:14px;background:white;min-width:100px;">
                ${anosDisponiblesGlobal.map(a => `<option value="${a}" ${a === anioSeleccionadoGlobal ? 'selected' : ''}>${a}</option>`).join('')}
            </select>
            <button id="btnActualizarGlobal" style="padding:6px 16px;background:#2563eb;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                🔄 Actualizar
            </button>
            <button id="btnExportarGlobalCSV" style="padding:6px 16px;background:#16a34a;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                📥 Exportar CSV
            </button>
            <span id="total-registros-global" style="font-size:13px;color:#64748b;margin-left:auto;"></span>
        </div>
        <div id="resultados-consolidado-global" style="padding:4px 0;">
            <div style="text-align:center;padding:30px;color:#94a3b8;">
                <div class="spinner" style="display:inline-block;width:30px;height:30px;border:3px solid #e2e8f0;border-top-color:#2563eb;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
                <div style="margin-top:10px;">⏳ Cargando datos globales...</div>
                <style>
                    @keyframes spin { to { transform: rotate(360deg); } }
                </style>
            </div>
        </div>
    `;

    document.getElementById('selectorAnioGlobal').onchange = function() {
        anioSeleccionadoGlobal = parseInt(this.value);
        cargarConsolidadoTotal();
    };
    document.getElementById('btnActualizarGlobal').onclick = cargarConsolidadoTotal;
    document.getElementById('btnExportarGlobalCSV').onclick = exportarGlobalCSV;

    inicializadoGlobal = true;
    await cargarConsolidadoTotal();
}

// ============================================================
// EXPONER FUNCIONES GLOBALES
// ============================================================

window.cargarConsolidadoTotal = cargarConsolidadoTotal;
window.inicializarConsolidadoTotal = inicializarConsolidadoTotal;
window.exportarGlobalCSV = exportarGlobalCSV;

console.log('✅ consolidado_total.js cargado (con siglas y marcado naranja)');