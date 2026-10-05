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
// El total USD del ULTIMO render: lo deja `generarVistaCompleta` y lo lee la
// tarjeta de la barra (`#tarjeta-total-pais`). Variable de modulo para que el
// numero tenga una sola fuente y la vista siga devolviendo el HTML.
let ultimoTotalUsdPais = 0;
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
            <button id="btnExportarPaisExcel" style="padding:6px 16px;background:#16a34a;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                📥 Exportar Excel
            </button>
            <button id="btnEnviarPaisCorreo" style="padding:6px 16px;background:#0ea5e9;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                ✉️ Enviar por correo
            </button>
            <span style="margin-left:auto;"></span>
            <!-- La tarjeta de Total USD va en la esquina superior derecha de la
                 barra (brief 05/10/2026: igual que Ventas Globales). El contenido
                 lo escribe el render, que es quien tiene el total. -->
            <span id="tarjeta-total-pais"></span>
        `;
        container.appendChild(filtrosDiv);

        // Crear div de resultados
        resultadosDiv = document.createElement('div');
        resultadosDiv.id = 'resultados-consolidado-pais';
        resultadosDiv.style.padding = '4px 0';
        container.appendChild(resultadosDiv);

        selector = document.getElementById('selectorAnioVentas');
        const btn = document.getElementById('btnActualizarConsolidado');
        const btnExportar = document.getElementById('btnExportarPaisExcel');
        const btnCorreo = document.getElementById('btnEnviarPaisCorreo');

        // Llenar opciones y asignar eventos
        actualizarSelector(selector);
        if (btn) {
            btn.onclick = function() {
                cargarConsolidadoPais();
            };
        }
        // Los botones de export y correo llevan SOLO este `onclick` directo, y NO
        // `data-onclick`: con los dos, el clic los disparaba DOS veces (uno en el
        // propio elemento y otro en el delegado de `app.js` a nivel documento) y el
        // Excel se bajaba por DUPLICADO (defecto reportado el 05/10/2026). El
        // comentario anterior decia que hacia falta el `onclick` porque el
        // `appendChild` no pasa por el observador: era falso para estos botones (el
        // `container` ya esta en el documento cuando se asignan), pero como el
        // `onclick` directo funciona y es el que se probo en pantalla, se deja ESE
        // y se saca el `data-onclick` (un solo mecanismo por boton).
        if (btnExportar) {
            btnExportar.onclick = function() {
                exportarPaisExcel();
            };
        }
        if (btnCorreo) {
            btnCorreo.onclick = function() {
                enviarPaisPorCorreo();
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

        const vista = generarVistaCompleta(data);
        resultadosDiv.innerHTML = vista;

        // La tarjeta de Total USD, en la esquina superior derecha de la barra
        // (brief 05/10/2026). El numero sale de la MISMA vista, no se recalcula.
        const tarjetaTotal = document.getElementById('tarjeta-total-pais');
        if (tarjetaTotal) {
            tarjetaTotal.innerHTML = `
                <div style="background:#f0f4ff;padding:8px 16px;border-radius:10px;border:1px solid #93c5fd;box-shadow:0 2px 4px rgba(0,0,0,0.04);text-align:right;">
                    <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;white-space:nowrap;">Total USD</div>
                    <div style="font-size:20px;font-weight:700;color:#1e293b;white-space:nowrap;">${formatearNumero(ultimoTotalUsdPais)}</div>
                </div>`;
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

    // Si alguna base permitida no respondió, el consolidado está incompleto y hay
    // que decirlo: antes la base caída desaparecía en silencio (un `continue` en
    // el servicio) y el usuario comparaba totales sin saber que faltaba un país.
    const fallidas = data.bases_fallidas || [];
    const avisoFallidas = fallidas.length
        ? '<div style="background:#fef2f2;border:1px solid #fecaca;color:#991b1b;' +
          'padding:10px 14px;border-radius:8px;margin-bottom:14px;font-size:12px;">' +
          '⚠️ No se pudieron consultar ' + fallidas.length + ' base(s): <b>' +
          fallidas.join(', ') + '</b>. El consolidado está incompleto.</div>'
        : '';

    if (datos.length === 0) {
        ultimoTotalUsdPais = 0;
        return `
            ${avisoFallidas}
            <div style="text-align:center;padding:40px;color:#94a3b8;border:1px dashed #cbd5e1;border-radius:8px;">
                📭 No hay datos de ventas para el año ${totales.anio || anioSeleccionado || 'seleccionado'}
            </div>
        `;
    }

    // Brief 05/10/2026: la tarjeta de Total USD es la unica que queda (el usuario
    // pidio borrar las otras tres), asi que `total_local`, `total_registros` y el
    // anio ya no se usan en la vista.
    const totalGeneral = totales.total_dl || 0;

    let html = `
        ${avisoFallidas}
        <!-- La tarjeta de Total USD NO va aca: se escribe en el contenedor
             tarjeta-total-pais, de la barra de filtros (esquina superior
             derecha). Brief 05/10/2026. -->

        <!-- TABS (brief 05/10/2026: se suman las dos secciones por CCO) -->
        <div style="display:flex;gap:4px;margin-bottom:12px;border-bottom:2px solid #e2e8f0;flex-wrap:wrap;">
            <button class="tab-pais active" data-tab="cliente" data-onclick="window.mostrarTabPais('cliente')" style="padding:8px 20px;border:none;background:#2563eb;color:white;border-radius:8px 8px 0 0;font-weight:600;cursor:pointer;font-size:13px;transition:all 0.2s;">
                👤 Por Cliente
            </button>
            <button class="tab-pais" data-tab="centro" data-onclick="window.mostrarTabPais('centro')" style="padding:8px 20px;border:none;background:transparent;color:#64748b;border-radius:8px 8px 0 0;font-weight:500;cursor:pointer;font-size:13px;transition:all 0.2s;">
                📂 Por Centro Costo
            </button>
            <button class="tab-pais" data-tab="hw" data-onclick="window.mostrarTabPais('hw')" style="padding:8px 20px;border:none;background:transparent;color:#64748b;border-radius:8px 8px 0 0;font-weight:500;cursor:pointer;font-size:13px;transition:all 0.2s;">
                🖥️ Centro de Costo HW
            </button>
            <button class="tab-pais" data-tab="resto" data-onclick="window.mostrarTabPais('resto')" style="padding:8px 20px;border:none;background:transparent;color:#64748b;border-radius:8px 8px 0 0;font-weight:500;cursor:pointer;font-size:13px;transition:all 0.2s;">
                📦 Resto de Centros de Costo
            </button>
        </div>
    `;

    html += `<div id="tab-pais-cliente" class="tab-pais-content" style="display:block;">`;
    html += generarTablaPivot(datos, 'cliente');
    html += `</div>`;

    html += `<div id="tab-pais-centro" class="tab-pais-content" style="display:none;">`;
    html += generarTablaPivot(datos, 'centro');
    html += `</div>`;

    // Las dos secciones nuevas: el eje es el CENTRO DE COSTO, separado por la
    // regla de negocio (nombre con HARDWARE / SOPORTE HW / LICENCIA HW /
    // ALQUILER HW = Hardware, todo lo demas = Resto).
    html += `<div id="tab-pais-hw" class="tab-pais-content" style="display:none;">`;
    html += generarTablaCentros(datos, true);
    html += `</div>`;

    html += `<div id="tab-pais-resto" class="tab-pais-content" style="display:none;">`;
    html += generarTablaCentros(datos, false);
    html += `</div>`;

    // El total queda en la variable de modulo `ultimoTotalUsdPais` (la vista sigue
    // devolviendo el HTML: es el contrato que usan los probes) y de ahi lo lee la
    // tarjeta de la barra. Una sola fuente del numero.
    ultimoTotalUsdPais = totalGeneral;
    return html;
}

// ============================================================
// CLASIFICACION DE CENTROS DE COSTO (Hardware / Resto)
// ============================================================
// Brief 05/10/2026 (el usuario): "no esta la seccion de centro de costo HW, ni
// tampoco la de el resto de centro de costo que no son HW". La clasificacion ya
// existia para el .xlsx (`_esCentroHardware`); aca se reusa para la PANTALLA, con
// las mismas cuatro marcas por NOMBRE del centro de costo.
function esCentroHardware(centro) {
    return _esCentroHardware(centro);
}

// Las dos secciones nuevas (y el `.xlsx`) comparten esta tabla: el mismo formato
// que la tabla por cliente/centro (meses + Total + % Part.), con la opcion de
// agregar la fila `Total general` al pie (como las hojas `Cons HW` y
// `Cons Resto` del libro de referencia del usuario).
function generarTablaPivotDatos(armado, opciones) {
    const conPorcentaje = !opciones || opciones.conPorcentaje !== false;
    const conTotalGeneral = !!(opciones && opciones.conTotalGeneral);
    const { datos, grupos, meses } = armado;

    if (!datos || datos.length === 0 || meses.length === 0) {
        return `<div style="text-align:center;padding:20px;color:#94a3b8;">No hay datos para mostrar</div>`;
    }

    const entidades = Object.keys(grupos).sort((a, b) => a.localeCompare(b));

    let html = `
        <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead style="background:#f8fafc;border-bottom:2px solid #e2e8f0;">
                        <tr>
                            <th style="padding:10px 14px;text-align:left;font-weight:600;color:#475569;min-width:150px;background:#f8fafc;">${opciones && opciones.titulo ? opciones.titulo : 'Cliente'}</th>
    `;

    meses.forEach(m => {
        html += `<th style="padding:10px 8px;text-align:right;font-weight:600;color:#475569;min-width:70px;background:#f8fafc;font-size:11px;">${escapeHTML(m.etiqueta)}</th>`;
    });

    html += `
                            <th style="padding:10px 14px;text-align:right;font-weight:600;color:#475569;min-width:90px;background:#fef3c7;">Total</th>
                            ${conPorcentaje ? '<th style="padding:10px 14px;text-align:right;font-weight:600;color:#475569;min-width:80px;background:#e8f0fe;">% Part.</th>' : ''}
                        </tr>
                    </thead>
                    <tbody>
    `;

    // Dos pasadas: el "% Part." de cada fila usa el TOTAL FINAL (no un total
    // parcial que crece dentro del mismo bucle).
    const filasConTotal = [];
    let totalGeneral = 0;
    const totalPorMes = {};
    meses.forEach(m => { totalPorMes[m.clave] = 0; });

    entidades.forEach(entidad => {
        const fila = grupos[entidad];
        let totalFila = 0;
        meses.forEach(m => { totalFila += (fila[m.clave] || 0); });
        if (totalFila === 0) return;
        filasConTotal.push({ entidad, fila, totalFila });
        totalGeneral += totalFila;
        meses.forEach(m => { totalPorMes[m.clave] += (fila[m.clave] || 0); });
    });

    filasConTotal.forEach((item, i) => {
        const { entidad, fila, totalFila } = item;
        const porcentajeFila = totalGeneral > 0 ? (totalFila / totalGeneral * 100) : 0;
        const bg = i % 2 === 0 ? '#fafafa' : 'transparent';
        html += `
            <tr style="border-bottom:1px solid #f1f5f9;background:${bg};">
                <td style="padding:8px 14px;font-weight:500;color:#1e293b;">${escapeHTML(entidad)}</td>
        `;
        meses.forEach(m => {
            const valor = fila[m.clave] || 0;
            html += `<td style="padding:8px 8px;text-align:right;font-variant-numeric:tabular-nums;color:#334155;">${valor !== 0 ? formatearNumero(valor) : '-'}</td>`;
        });
        html += `
                <td style="padding:8px 14px;text-align:right;font-weight:700;color:#1e293b;background:#fef3c7;">${formatearNumero(totalFila)}</td>
                ${conPorcentaje ? `<td style="padding:8px 14px;text-align:right;font-weight:600;color:#2563eb;background:#e8f0fe;">${porcentajeFila.toFixed(2)}%</td>` : ''}
            </tr>
        `;
    });

    if (conTotalGeneral || conPorcentaje) {
        html += `
            <tr style="font-weight:bold;background:#f0f4ff;border-top:2px solid #e2e8f0;">
                <td style="padding:10px 14px;font-size:14px;color:#1e293b;">Total general</td>
        `;
        meses.forEach(m => {
            html += `<td style="padding:10px 8px;text-align:right;font-size:14px;color:#1e293b;">${formatearNumero(totalPorMes[m.clave])}</td>`;
        });
        html += `
                <td style="padding:10px 14px;text-align:right;font-size:16px;color:#2563eb;background:#fef3c7;">${formatearNumero(totalGeneral)}</td>
                ${conPorcentaje ? '<td style="padding:10px 14px;text-align:right;font-size:14px;color:#2563eb;background:#e8f0fe;">100%</td>' : ''}
            </tr>
        `;
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
// GENERAR TABLA PIVOTANTE (MESES + TOTALES) - ROBUSTA
// ============================================================

// El pivote por entidad (cliente o centro de costo) de un conjunto de filas.
// Devuelve `{datos, grupos, meses}`: lo comparten las cuatro secciones de la
// pantalla (Cliente, Centro Costo, Hardware y Resto) y lo dibuja
// `generarTablaPivotDatos`. Los meses van con su etiqueta (`Ene-26`) y su clave.
function armarPivotPorEntidad(datos, claveGrupo) {
    const grupos = {};
    const mesesSet = new Set();

    datos.forEach(row => {
        const entidad = row[claveGrupo] || 'Sin nombre';
        const anio = parseInt(row.Anio) || parseInt(row.Año) || 0;
        const mes = parseInt(row.Mes) || 0;
        const importe = parseFloat(row.Importe_DL) || 0;

        if (anio === 0 || mes === 0) return;

        const nombreMes = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'][mes] || mes;
        const mesKey = `${nombreMes}-${String(anio).slice(-2)}`;

        if (!grupos[entidad]) grupos[entidad] = {};
        grupos[entidad][mesKey] = (grupos[entidad][mesKey] || 0) + importe;
        mesesSet.add(mesKey);
    });

    const meses = Array.from(mesesSet).map(clave => {
        const [etiqueta, anio] = clave.split('-');
        return {
            clave: clave,
            etiqueta: clave,
            anio: parseInt(anio, 10),
            mes: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'].indexOf(etiqueta) + 1
        };
    }).sort((a, b) => (a.anio !== b.anio ? a.anio - b.anio : a.mes - b.mes));

    return { datos: datos, grupos: grupos, meses: meses };
}

function generarTablaPivot(datos, grupo) {
    if (!datos || datos.length === 0) {
        return `<div style="text-align:center;padding:20px;color:#94a3b8;">No hay datos para mostrar</div>`;
    }
    const claveGrupo = grupo === 'cliente' ? 'NombreCliente' : 'CentroCosto';
    const nombreColumna = grupo === 'cliente' ? 'Cliente' : 'Centro Costo';
    return generarTablaPivotDatos(armarPivotPorEntidad(datos, claveGrupo),
                                  { titulo: nombreColumna });
}

// La tabla de una de las dos secciones de CENTROS DE COSTO (Hardware o Resto):
// el eje es el centro de costo y lleva `Total general` al pie, como las hojas
// `Cons HW` / `Cons Resto` del libro de referencia.
function generarTablaCentros(datos, soloHardware) {
    const filtrados = (datos || []).filter(
        row => esCentroHardware(row.CentroCosto) === !!soloHardware);
    if (filtrados.length === 0) {
        return `<div style="text-align:center;padding:20px;color:#94a3b8;">No hay centros de costo ${soloHardware ? 'de Hardware' : 'fuera de Hardware'} para el año elegido</div>`;
    }
    return generarTablaPivotDatos(armarPivotPorEntidad(filtrados, 'CentroCosto'),
                                  { titulo: 'Centro Costo', conTotalGeneral: true,
                                    conPorcentaje: false });
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
// EXPORTAR A EXCEL (.xlsx vía backend): TRES hojas
// ============================================================
// El .xlsx baja TRES hojas, con la jerarquia pedida (brief 03/10/2026):
//   1) Resumen por Cliente: CLIENTE y, adentro, CENTRO DE COSTO.
//   2) Hardware: los centros de costo de hardware (HARDWARE, SOPORTE HW,
//      LICENCIA HW, ALQUILER HW) y, adentro, CLIENTE.
//   3) Resto: el resto de los centros de costo y, adentro, CLIENTE.
// Las tres llevan los MESES del anio abierto, la columna Total, el agrupamiento
// NATIVO de Excel (los hijos de cada padre se pliegan y arrancan PLEGADOS), el
// AUTOFILTRO de Excel y el `Total general` al pie.
//
// El agrupado por centro de costo NO sale del ERP: es una REGLA DE NEGOCIO sobre
// el NOMBRE del centro (PENDIENTE_MEJORAS.md punto 5). Se compara en MAYUSCULAS
// y sin acentos ("SOPORTE HÁRDWARE" tambien entra), esta escrito en
// `MARCAS_HARDWARE` y lo que no coincide va a Resto: ningun centro cae en las
// dos hojas.
const MARCAS_HARDWARE = ['HARDWARE', 'SOPORTE HW', 'LICENCIA HW', 'ALQUILER HW'];
const NOMBRES_MESES_PAIS = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul',
                            'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
const FORMATO_IMPORTE_PAIS = '#,##0.00';
const ANCHO_PAIS_NOMBRE_1 = 34;
const ANCHO_PAIS_NOMBRE_2 = 28;
const ANCHO_PAIS_MES = 12;
const ANCHO_PAIS_TOTAL = 14;

// El texto comparable: MAYUSCULAS, sin acentos y con los espacios colapsados.
// Sin esto, "Soporte Hándware" o "SOPORTE  HW" (dos espacios) no entrarian a la
// hoja de hardware y el total de las dos hojas no cuadraria con la 1.
function _normalizarCentro(valor) {
    return String(valor === undefined || valor === null ? '' : valor)
        .toUpperCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
}

function _esCentroHardware(centro) {
    const texto = _normalizarCentro(centro);
    if (!texto) return false;
    return MARCAS_HARDWARE.some(marca => texto.indexOf(_normalizarCentro(marca)) >= 0);
}

// Los meses (1..12) que tienen algun movimiento en ese conjunto de filas,
// ordenados. Se calculan UNA vez y los usan las tres hojas: asi las columnas de
// las hojas 2 y 3 son comparables con las de la 1.
function _mesesPaisExcel(datos) {
    const meses = new Set();
    datos.forEach(row => {
        const mes = parseInt(row.Mes);
        if (mes >= 1 && mes <= 12) meses.add(mes);
    });
    return Array.from(meses).sort((a, b) => a - b);
}

// El armado del libro, en UNA sola funcion: lo usan la descarga
// (`exportarPaisExcel`) y el envio por correo (`enviarPaisPorCorreo`). Devuelve
// `{archivo, hoja, hojas}` o `null` si no hay nada que exportar (y avisa).
function armarLibroPais() {
    const datos = ((datosCompletos || {}).data) || [];
    if (datos.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para exportar', 'Reportes');
        return null;
    }
    const meses = _mesesPaisExcel(datos);
    if (meses.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos con fechas válidas para exportar', 'Reportes');
        return null;
    }
    const etiquetas = meses.map(mes => NOMBRES_MESES_PAIS[mes] || String(mes));
    const hojas = [
        _crearHojaPais('Resumen por Cliente', 'cliente', datos, etiquetas, meses),
        _crearHojaPais('Hardware', 'centro', datos.filter(row => _esCentroHardware(row.CentroCosto)), etiquetas, meses),
        _crearHojaPais('Resto', 'centro', datos.filter(row => !_esCentroHardware(row.CentroCosto)), etiquetas, meses)
    ];
    // Brief 05/10/2026: "RD - Ventas al 04/10/2026" (las siglas del pais de la
    // base activa), el MISMO nombre para el archivo que se exporta y para el
    // adjunto y el asunto del correo. La fecha es la LOCAL (helper de `app.js`),
    // nunca `toISOString()`.
    const archivo = window.nombreInformeConSiglas('Ventas', window.fechaHoyConGuiones())
                    + '.xlsx';
    return { archivo: archivo, hoja: 'Resumen por Cliente', hojas: hojas };
}

// Una hoja: el pivote de dos niveles + las opciones de presentacion del motor.
// `nivel` es el PRIMER nivel de la jerarquia ('cliente' en la hoja 1, 'centro'
// en las hojas 2 y 3); el segundo nivel es el otro.
function _crearHojaPais(nombre, nivel, datos, etiquetas, meses) {
    const primera = (nivel === 'cliente') ? 'cliente' : 'centro';
    const segunda = (primera === 'cliente') ? 'centro' : 'cliente';
    const pivote = _pivoteJerarquicoPais(datos, primera, segunda, etiquetas, meses);
    return {
        hoja: nombre,
        columnas: pivote.columnas,
        filas: pivote.filas,
        formatos: pivote.formatos,
        anchos: pivote.anchos,
        filas_negrita: pivote.filasNegrita,
        // Brief 05/10/2026: "los totales deberian tener sumatoria con formula
        // (tanto mensual como general)". El pivote arma la matriz alineada con las
        // filas y el motor la aplica al final.
        formulas: pivote.formulas,
        congelar_encabezado: true,
        autofiltro: true,
        agrupaciones: pivote.agrupaciones,
        // Brief 05/10/2026: "formato tabla" en las tres hojas de Pais.
        tabla: true
    };
}

// La clave de agrupacion de cada nivel. `NombreCliente` es el nombre del cliente
// (la pantalla agrupa por ahi) y `CentroCosto` el nombre del centro de costo, ya
// rellenado por el servicio ("SIN CENTRO" cuando viene vacio).
function _claveNivelPais(row, nivel) {
    if (nivel === 'cliente') return String(row.NombreCliente || 'SIN NOMBRE');
    return String(row.CentroCosto || 'SIN CENTRO');
}

// El pivote de DOS niveles (padre -> hijo -> meses) de UNA hoja. Los importes
// son `Importe_DL` (el USD del informe, el mismo campo que la tabla de la
// pantalla) redondeados a entero, y cada total es la suma de las celdas que se
// muestran: lo que se ve, suma.
function _pivoteJerarquicoPais(datos, primera, segunda, etiquetas, meses) {
    const sumar = (a, b) => (parseFloat(a) || 0) + (parseFloat(b) || 0);

    const padres = [];
    const porPadre = new Map();
    datos.forEach(row => {
        const clavePadre = _claveNivelPais(row, primera);
        const claveHijo = _claveNivelPais(row, segunda);
        const importe = Math.round(parseFloat(row.Importe_DL) || 0);
        if (!porPadre.has(clavePadre)) {
            const padre = { clave: clavePadre, total: 0, meses: {},
                            hijos: [], porHijo: new Map() };
            porPadre.set(clavePadre, padre);
            padres.push(padre);
        }
        const padre = porPadre.get(clavePadre);
        if (!padre.porHijo.has(claveHijo)) {
            const hijo = { clave: claveHijo, total: 0, meses: {} };
            padre.porHijo.set(claveHijo, hijo);
            padre.hijos.push(hijo);
        }
        const hijo = padre.porHijo.get(claveHijo);
        const mes = parseInt(row.Mes);
        if (!(mes >= 1 && mes <= 12)) return;
        hijo.meses[mes] = sumar(hijo.meses[mes], importe);
        hijo.total = sumar(hijo.total, importe);
        padre.meses[mes] = sumar(padre.meses[mes], importe);
        padre.total = sumar(padre.total, importe);
    });

    const columnas = [primera === 'cliente' ? 'Cliente' : 'Centro Costo',
                      primera === 'cliente' ? 'Centro Costo' : 'Cliente']
        .concat(etiquetas).concat(['Total']);
    const formatos = ['', ''].concat(etiquetas.map(() => FORMATO_IMPORTE_PAIS))
        .concat([FORMATO_IMPORTE_PAIS]);
    const anchos = [ANCHO_PAIS_NOMBRE_1, ANCHO_PAIS_NOMBRE_2]
        .concat(etiquetas.map(() => ANCHO_PAIS_MES)).concat([ANCHO_PAIS_TOTAL]);

    const filas = [];
    const filasNegrita = [];
    const agrupaciones = [];
    const totales = etiquetas.map(() => 0);
    let totalGeneral = 0;

    padres.forEach(padre => {
        // El orden de los hijos es el de la primera aparicion en los datos (el
        // del `ORDER BY` del servicio), igual que la pantalla.
        // Un mes SIN movimiento va VACIO (`null`): en el .xlsx es la celda en
        // blanco, no un `0` (los reportes del proyecto no escriben ceros que no
        // existen). `null` viaja en el JSON como `null` y openpyxl lo escribe
        // como celda vacia.
        const valoresPadre = meses.map(mes => (padre.meses[mes] || null));
        filasNegrita.push(filas.length);
        // Brief 05/10/2026 (el usuario, mirando el .xlsx): "en la columna de centro
        // de costo eliminar lo que dice Total XXX para que no duplique el nombre
        // del cliente" y "si colapso el cliente que no aparezca en cada fila el
        // nombre del cliente". O sea: la fila del PADRE lleva SOLO su nombre (en la
        // primera columna, que es la que se ve con el grupo plegado) y la segunda
        // columna va VACIA (el hijo va en su propia fila). La segunda columna del
        // hijo tampoco repite el nombre del padre (ya esta arriba, en negrita).
        filas.push([padre.clave, ''].concat(valoresPadre).concat([padre.total]));
        // Los totales de abajo salen de LO QUE SE VE (`valoresPadre`), no del
        // crudo: con un importe de 75,5 la celda muestra 76 y el Total general
        // tiene que cerrar con la columna (si no, el usuario ve una columna que
        // no suma al pie).
        meses.forEach((mes, indice) => {
            totales[indice] = sumar(totales[indice], valoresPadre[indice]);
        });
        totalGeneral = sumar(totalGeneral, padre.total);
        const desde = filas.length;
        padre.hijos.forEach(hijo => {
            const valoresHijo = meses.map(mes => (hijo.meses[mes] || null));
            filas.push([padre.clave, hijo.clave].concat(valoresHijo).concat([hijo.total]));
        });
        if (filas.length > desde) {
            agrupaciones.push({ desde: desde, hasta: filas.length - 1, colapsado: true });
        }
    });

    if (filas.length > 0) {
        filasNegrita.push(filas.length);
        filas.push(['TOTAL GENERAL', ''].concat(totales).concat([totalGeneral]));
    }

    // Brief 05/10/2026: "los totales deberian tener sumatoria con formula (tanto
    // mensual como general)". Se arma una matriz ALINEADA con `filas` (mismo alto y
    // ancho; `null` = queda el valor): el motor la aplica al final.
    //   - la columna Total de cada fila: `=SUM` de sus celdas de mes;
    //   - la fila TOTAL GENERAL: `=SUM` de lo que tiene arriba en cada columna (los
    //     meses y el Total);
    //   - la fila del padre: su Total tambien con formula (suma SUS meses, que ya
    //     son la suma de sus hijos).
    const letraColumnaPais = (indice) => {
        let letra = '';
        let numero = indice + 1;
        while (numero > 0) {
            const resto = (numero - 1) % 26;
            letra = String.fromCharCode(65 + resto) + letra;
            numero = Math.floor((numero - 1) / 26);
        }
        return letra;
    };
    const primeraColumnaMes = 3;                  // A y B son los dos textos
    // La ULTIMA columna de MESES, 0-based: los meses son C..? y despues va el
    // Total. Con `etiquetas` de 5 meses las columnas son A..G, asi que la ultima
    // de meses es la F (indice 5): `2 + 5 - 1`. Estaba en `2 + meses.length` (sin
    // el `-1`), o sea UNA de mas, y por eso `formulaDelTotal` y el pie tomaban la
    // columna del Total como si fuera un mes (medido en
    // `_investigacion_gt/_diag_formas.txt`).
    const ultimaColumnaMes = 2 + meses.length - 1;
    const columnaDelTotal = ultimaColumnaMes + 1;
    const formulaDelTotal = (filaExcel) =>
        '=SUM(' + letraColumnaPais(primeraColumnaMes) + filaExcel + ':'
        + letraColumnaPais(ultimaColumnaMes) + filaExcel + ')';
    const formulas = filas.map((_fila, indice) => {
        const filaExcel = indice + 2;             // 1 = encabezado, 2 = primera fila
        const delTotalGeneral = indice === filas.length - 1;
        // OJO: la columna del TOTAL es la ULTIMA (despues de los meses); el
        // parametro se llama `indiceColumna` para no tapar nada.
        return columnas.map((_c, indiceColumna) => {
            if (indiceColumna < primeraColumnaMes) return null;
            if (delTotalGeneral) {
                // El pie: cada columna suma las filas de datos de arriba.
                return '=SUM(' + letraColumnaPais(indiceColumna) + '2:'
                    + letraColumnaPais(indiceColumna) + (filaExcel - 1) + ')';
            }
            if (indiceColumna === columnaDelTotal) return formulaDelTotal(filaExcel);
            return null;
        });
    });

    return {
        columnas: columnas,
        filas: filas,
        formatos: formatos,
        anchos: anchos,
        filasNegrita: filasNegrita,
        agrupaciones: agrupaciones,
        formulas: formulas,
        registros: datos.length
    };
}

function exportarPaisExcel() {
    const libro = armarLibroPais();
    if (!libro) return;

    if (typeof window.descargarXlsx !== 'function') {
        if (typeof toastError === 'function') toastError('Exportación no disponible', 'Reportes');
        return;
    }
    // UN solo .xlsx con las tres hojas. El motor arma UNA hoja por elemento de
    // `hojas` con el MISMO codigo que la hoja unica (el archivo no se puede
    // separar de lo que baja la descarga ni de lo que sale por correo).
    window.descargarXlsx(libro.archivo, libro.hoja, [], [], { hojas: libro.hojas });
    if (typeof toastSuccess === 'function') toastSuccess('✅ Reporte exportado (3 hojas)', 'Reportes');
}

// ============================================================
// ENVIAR POR CORREO (Outlook de esta PC; el adjunto es el MISMO .xlsx)
// ============================================================
// El dialogo del correo, el armado del adjunto y el envio viven en `app.js`
// (`window.pedirCorreoYEnviar`): aca solo se le pasa SU libro, el mismo que baja
// la descarga (`armarLibroPais`), y el prefijo del asunto del informe.
// Brief 05/10/2026: el asunto y el archivo llevan el MISMO nombre con las siglas
// de la base activa ("RD - Ventas al 04/10/2026"). El prefijo sale del ayudante
// compartido y la fecha la pega el dialogo del correo.
//
// OJO (defecto real medido el 05/10/2026): el prefijo se armaba al CARGAR el modulo,
// cuando `window.baseActiva` todavia es `null` (la setea `app.js` al inicializar), y
// quedaba con las siglas de la base POR DEFECTO. Ahora se arma al mandar el correo.
function enviarPaisPorCorreo() {
    const libro = armarLibroPais();
    if (!libro) return;
    if (typeof window.pedirCorreoYEnviar !== 'function') {
        if (typeof toastError === 'function') toastError('El envío por correo no está disponible', 'Reportes');
        return;
    }
    // El asunto por defecto se arma ADENTRO del dialogo, con la fecha del dia.
    const asunto = window.prefijoInformeConSiglas('Ventas') || 'Ventas al ';
    window.pedirCorreoYEnviar(libro.archivo, libro.hoja, [], [], { hojas: libro.hojas },
                              asunto);
}

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
// Los dos botones del informe (el `onclick` directo y el `data-onclick`, que el
// motor de `app.js` resuelve por NOMBRE en `window`).
window.exportarPaisExcel = exportarPaisExcel;
window.enviarPaisPorCorreo = enviarPaisPorCorreo;
window.armarLibroPais = armarLibroPais;

console.log('✅ consolidado_pais.js cargado (estructura automática)');