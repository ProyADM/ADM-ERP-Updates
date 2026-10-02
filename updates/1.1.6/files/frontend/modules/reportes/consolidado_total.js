// ============================================================
// REPORTE: CONSOLIDADO VENTAS GLOBAL - VERSIÓN CON VENTAS MANUALES Y MARCADO NARANJA
// MEJORA: Conversión de sigla a nombre completo para que el marcado funcione
// MEJORA: Muestra siglas en la tabla en lugar de nombres completos
// 24/09/2026: Argentina se despliega POR SOCIEDAD (Sidesys / Advansur).
// ============================================================

let datosGlobales = null;
let anioSeleccionadoGlobal = null;
let anosDisponiblesGlobal = [];
let datosOriginalesGlobal = [];
let inicializadoGlobal = false;
let cargandoAnosGlobal = false;
let ventasManualesData = {};
// Bases sobre las que se calculó el último consolidado (lo informa el backend).
// Un usuario con bases acotadas ve un consolidado PARCIAL: hay que decirlo en
// pantalla, porque si no el número se lee como el total de la empresa.
let basesConsolidadas = { incluidas: [], fallidas: [] };
// La tabla calculada en el ultimo render: la comparten la pantalla y el Excel.
let tablaGlobalCalculada = { columnas: [], filas: [], formatos: [], anchos: [], filasNegrita: [], filasRelleno: {} };

// Grupos (paises con desglose por sociedad) que el usuario dejo ABIERTOS.
// Cerrado por defecto (brief 24/09/2026): el pivote SIEMPRE tiene a los hijos,
// lo unico que cambia es que estan ocultos en pantalla.
let gruposAbiertosGlobal = new Set();

// Aviso de alcance del consolidado: qué bases entraron y cuáles fallaron.
function avisoAlcanceConsolidado() {
    const incluidas = (basesConsolidadas && basesConsolidadas.incluidas) || [];
    const fallidas = (basesConsolidadas && basesConsolidadas.fallidas) || [];
    if (!incluidas.length && !fallidas.length) return '';
    let html = '';
    if (fallidas.length) {
        html += '<div style="background:#fef2f2;border:1px solid #fecaca;color:#991b1b;' +
            'padding:10px 14px;border-radius:8px;margin-bottom:14px;font-size:12px;">' +
            '⚠️ No se pudieron consultar ' + fallidas.length + ' base(s): <b>' +
            fallidas.join(', ') + '</b>. El consolidado está incompleto.</div>';
    }
    if (incluidas.length) {
        html += '<div style="background:#f8fafc;border:1px solid #e2e8f0;color:#475569;' +
            'padding:8px 14px;border-radius:8px;margin-bottom:14px;font-size:12px;">' +
            'Consolidado sobre ' + incluidas.length + ' base(s): ' +
            '<b>' + incluidas.join(', ') + '</b>' +
            (incluidas.length < 11 ? ' — parcial, según las bases habilitadas.' : '.') +
            '</div>';
    }
    return html;
}

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
    // Los importes del informe son ENTEROS (el pivote los redondea): la pantalla
    // muestra el MISMO entero que el Excel, sin decimales.
    if (valor === undefined || valor === null || isNaN(valor)) return '0';
    return String(Math.round(Number(valor))).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

// ============================================================
// SANITIZAR HTML
// ============================================================

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
                    ❌ ${escapeHTML(data.error || 'Error al cargar datos')}
                </div>
            `;
            return;
        }

        ventasManualesData = data.ventas_manuales || {};
        console.log('📦 Ventas manuales recibidas:', ventasManualesData);

        // Alcance real del consolidado (bases habilitadas del usuario + caídas).
        basesConsolidadas = {
            incluidas: data.bases_incluidas || [],
            fallidas: data.bases_fallidas || []
        };

        if (data.data && data.data.length > 0) {
            console.log('🔍 Primer registro:', data.data[0]);
            console.log('🔍 Campos disponibles:', Object.keys(data.data[0]));
        }

        datosOriginalesGlobal = data.data || [];
        datosGlobales = procesarDatosGlobales(datosOriginalesGlobal);
        // Un consolidado nuevo arranca con TODOS los grupos cerrados.
        gruposAbiertosGlobal = new Set();
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
// 24/09/2026: además de agrupar por `Pais`, arma el desglose POR SOCIEDAD del
// país (`row.Sociedad` / `row.SociedadLabel`, que manda el backend para
// Argentina). La forma de cada sociedad es la MISMA que la del país
// (`meses`, `totalDL`, `totalTransacciones`). Un país sin `Sociedad` queda con
// `sociedades` vacío = comportamiento de hoy (una sola fila).

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

    // Crea (o devuelve) el acumulador con la MISMA forma para el país y para
    // cada sociedad: así el pivote recorre los dos con el mismo código.
    const nuevoAcumulador = (nombre) => ({
        pais: nombre,
        meses: {},
        totalDL: 0,
        totalTransacciones: 0,
    });

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
            paises[key] = nuevoAcumulador(pais);
            paises[key].sociedades = {};
        }

        // El país acumula TODO (es el padre: la suma de sus sociedades).
        if (!paises[key].meses[mesKey]) {
            paises[key].meses[mesKey] = { dl: 0, transacciones: 0 };
        }
        paises[key].meses[mesKey].dl += importeDL;
        paises[key].meses[mesKey].transacciones += transacciones;

        paises[key].totalDL += importeDL;
        paises[key].totalTransacciones += transacciones;

        // Y la sociedad de la fila acumula lo suyo, por separado. Los países sin
        // desglose (Uruguay y compañía) no entran acá: `sociedades` queda vacío.
        const sociedadKey = String(row.Sociedad || '').trim().toLowerCase();
        if (sociedadKey) {
            if (!paises[key].sociedades[sociedadKey]) {
                const acumulador = nuevoAcumulador(pais);
                acumulador.sociedad = sociedadKey;
                acumulador.sociedadLabel = row.SociedadLabel || sociedadKey;
                paises[key].sociedades[sociedadKey] = acumulador;
            }
            const hijo = paises[key].sociedades[sociedadKey];
            if (!hijo.meses[mesKey]) {
                hijo.meses[mesKey] = { dl: 0, transacciones: 0 };
            }
            hijo.meses[mesKey].dl += importeDL;
            hijo.meses[mesKey].transacciones += transacciones;
            hijo.totalDL += importeDL;
            hijo.totalTransacciones += transacciones;
        }

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

    // Una sociedad sin ninguna venta en el año no tiene fila en `datos`, así que
    // no aparece (declarado en el brief: si se quisiera verla en cero haría
    // falta que el backend mande el catálogo).
    const conMeses = (acumulador) => {
        const mesesData = {};
        mesesOrdenados.forEach(m => {
            mesesData[m] = acumulador.meses[m] || { dl: 0, transacciones: 0 };
        });
        return { ...acumulador, meses: mesesData, mesesOrdenados: mesesOrdenados };
    };

    const resultado = Object.values(paises).map(p => {
        const paisProcesado = conMeses(p);
        const sociedades = {};
        Object.keys(p.sociedades || {}).forEach(clave => {
            sociedades[clave] = conMeses(p.sociedades[clave]);
        });
        paisProcesado.sociedades = sociedades;
        return paisProcesado;
    });

    resultado.sort((a, b) => b.totalDL - a.totalDL);
    return resultado;
}

// ============================================================
// ETIQUETA DE MES Y ESTILO DE FILA (los usan la pantalla y el Excel)
// ============================================================

// Etiqueta corta del mes tal como se ve en el encabezado de la tabla.
function etiquetaMesGlobal(mesKey) {
    const nombresMesesCortos = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const [anio, mes] = mesKey.split('-').map(Number);
    return `${nombresMesesCortos[mes] || mes} ${String(anio).slice(-2)}`;
}

// Porcentaje como lo pinta la pantalla (un decimal). El valor que viaja al
// Excel es la FRACCION (`0.5`), que es lo que espera el formato `0.0%`.
function porcentajePantallaGlobal(fraccion) {
    const valor = (typeof fraccion === 'number' && isFinite(fraccion)) ? fraccion : 0;
    return (valor * 100).toFixed(1) + '%';
}

// Fondo de la celda de un mes: el mismo naranja del marcado de pantalla.
function fondoVentaManualGlobal() {
    return 'FDE68A';
}

// ============================================================
// PIVOTE UNICO: LA TABLA QUE SE VE *Y* LA QUE SE EXPORTA
// ============================================================
// El Excel de Ventas Globales baja IGUAL a la pantalla. Para que eso no se
// rompa con el tiempo, la agregacion vive en UN SOLO lugar: `construirTablaGlobal`
// calcula columnas, filas, la fila de TOTAL, la marca de ventas manuales y los
// formatos/números; `generarVistaGlobal` los usa para el HTML y
// `exportarGlobalExcel` manda EXACTAMENTE ese resultado al backend.
// `tablaGlobalCalculada` es esa unica fuente de verdad (la llena el render).

// Formatos de Excel (parametros opcionales del endpoint): texto y fecha como
// texto, importes con separador de miles SIN decimales (el pivote los redondea
// a entero), porcentaje como fraccion con un decimal. El valor viaja SIEMPRE
// como numero.
const FORMATO_IMPORTE_GLOBAL = '#,##0';
const FORMATO_PORCENTAJE_GLOBAL = '0.0%';

function construirTablaGlobal(datos, ventasManuales) {
    if (!datos || datos.length === 0) {
        return { columnas: [], filas: [], formatos: [], anchos: [], filasNegrita: [],
                 filasRelleno: {}, filasPais: [], filasHijas: [], agrupaciones: [] };
    }

    // Los meses que muestra la tabla salen del primer pais (todos comparten
    // `mesesOrdenados`): son exactamente los del encabezado.
    const todosMeses = datos[0].mesesOrdenados || [];

    const columnas = ['País'];
    todosMeses.forEach(m => columnas.push(etiquetaMesGlobal(m)));
    if (todosMeses.length === 0) columnas.push('(sin datos mensuales)');
    columnas.push('Total USD');
    columnas.push('% Part.');

    // El ancho de columnas razonable que pide el brief, alineado con `columnas`.
    const anchos = [14];
    todosMeses.forEach(() => anchos.push(13));
    if (todosMeses.length === 0) anchos.push(18);
    anchos.push(14);
    anchos.push(10);

    // Misma alineacion que `columnas`; '' = celda como hoy.
    const formatos = [''];
    todosMeses.forEach(() => formatos.push(FORMATO_IMPORTE_GLOBAL));
    if (todosMeses.length === 0) formatos.push('');
    formatos.push(FORMATO_IMPORTE_GLOBAL);
    formatos.push(FORMATO_PORCENTAJE_GLOBAL);

    // Clave de una venta manual: `pais|sociedad|anio|mes` (la manda el backend).
    // `sociedad` vacio = las filas sin desglose (el resto de los paises).
    const tieneVentaManual = (pais, sociedad, anio, mes) => {
        const key = `${pais}|${sociedad || ''}|${anio}|${mes}`;
        return !!(ventasManuales && ventasManuales[key] && ventasManuales[key] > 0);
    };

    // ---- REDONDEO: UNA sola vez, aca -------------------------------------
    // El usuario pidio montos SIN decimales y que "lo que se ve, sume": cada
    // importe se redondea a entero al armar la tabla y TODOS los totales salen
    // de esos enteros (el Total USD de cada fila = suma de sus meses enteros; el
    // total de cada mes = suma de las celdas enteras; el % Part. = esos totales).
    // Redondear el total por separado daria un total que no coincide con la suma
    // de lo que el usuario ve (3 celdas de 0,5 -> la fila tiene que decir 3, no 1).
    const aEntero = (valor) => {
        const numero = Number(valor);
        return isFinite(numero) ? Math.round(numero) : 0;
    };

    const filas = [];
    const filasRelleno = {};
    const totalesPorMes = todosMeses.map(() => 0);
    const totalesPorFila = [];
    const filasPais = [];
    const filasHijas = [];
    const agrupaciones = [];

    // Media fila de datos: recorre los meses, redondea cada celda, suma el Total
    // USD de los MISMOS enteros y devuelve las columnas a marcar en naranja.
    const armarCeldasDeMes = (acumulador, marcarManual) => {
        const celdas = [];
        const rellenos = [];
        let totalFila = 0;
        todosMeses.forEach((m, idxMes) => {
            const [anio, mes] = m.split('-').map(Number);
            const valor = aEntero((acumulador.meses[m] || {}).dl || 0);
            celdas.push(valor);
            totalFila += valor;
            totalesPorMes[idxMes] += valor;
            if (marcarManual(anio, mes)) {
                rellenos.push({ columna: idxMes + 1, color: fondoVentaManualGlobal() });
            }
        });
        return { celdas: celdas, rellenos: rellenos, totalFila: totalFila };
    };

    datos.forEach((p, idxPais) => {
        const siglaMostrar = PAIS_A_SIGLA[p.pais] || p.pais;
        const clavesSociedades = Object.keys(p.sociedades || {});

        // ---- Caso sin meses: padre e hijos con '-' y el total redondeado ----
        // La MISMA regla del brief: el padre es la SUMA DE LOS HIJOS
        // REDONDEADOS (no el redondeo del agregado crudo). Sin columnas de mes
        // no hay celdas que sumar, asi que se suman los totales ya redondeados
        // de las sociedades; un pais sin desglose cae en `aEntero(p.totalDL)`,
        // que es su unico dato (igual que hoy).
        if (todosMeses.length === 0) {
            const hijosSinMeses = clavesSociedades.map(clave => ({
                label: p.sociedades[clave].sociedadLabel || clave,
                total: aEntero(p.sociedades[clave].totalDL),
            }));
            const totalPadre = hijosSinMeses.length
                ? hijosSinMeses.reduce((acc, h) => acc + h.total, 0)
                : aEntero(p.totalDL);
            filasPais.push(filas.length);
            totalesPorFila.push(totalPadre);
            filas.push([siglaMostrar, '-', totalPadre, 0]);
            const desdeHijos = filas.length;
            hijosSinMeses.forEach(hijo => {
                filasHijas.push(filas.length);
                totalesPorFila.push(hijo.total);
                filas.push([hijo.label, '-', hijo.total, 0]);
            });
            if (hijosSinMeses.length) {
                agrupaciones.push({ padre: idxPais, desde: desdeHijos,
                                    hasta: filas.length - 1, colapsado: true });
            }
            return;
        }

        // ---- Filas hijas: SIDESYS / ADVANSUR (redondeadas primero) ----------
        // El padre es la SUMA de estos hijos redondeados: nunca el redondeo del
        // agregado crudo (que puede dar otro numero).
        const hijos = clavesSociedades.map(clave => {
            const hijo = p.sociedades[clave];
            const partes = armarCeldasDeMes(
                hijo, (anio, mes) => tieneVentaManual(p.pais, clave, anio, mes));
            return {
                label: hijo.sociedadLabel || clave,
                total: partes.totalFila,
                celdas: partes.celdas,
                rellenos: partes.rellenos,
            };
        });

        // El padre: mes a mes la suma de los hijos redondeados. Solo cuando NO
        // hay desglose (un pais de una sola fila) el valor sale del acumulador
        // del pais, que es el comportamiento de hoy.
        const celdasPadre = [];
        let totalPadre = 0;
        const rellenosPadre = [];
        todosMeses.forEach((m, idxMes) => {
            const [anio, mes] = m.split('-').map(Number);
            const valor = hijos.length
                ? hijos.reduce((acc, h) => acc + h.celdas[idxMes], 0)
                : aEntero((p.meses[m] || {}).dl || 0);
            celdasPadre.push(valor);
            totalPadre += valor;
            // `totalesPorMes` es el total de la COLUMNA y tiene que contar a las
            // ventas de Argentina UNA sola vez: cuando hay desglose ya las
            // sumaron las filas de sociedad (abajo), asi que el padre NO vuelve a
            // aportar. Un pais sin desglose si aporta (es su unica fila).
            if (!hijos.length) totalesPorMes[idxMes] += valor;
            // La celda del padre es la SUMA: se marca si el pais tiene manual
            // (paises sin desglose) o si CUALQUIERA de sus sociedades tiene
            // manual ese mes (una celda naranja que no mentiria).
            const manual = tieneVentaManual(p.pais, '', anio, mes)
                || clavesSociedades.some(clave => tieneVentaManual(p.pais, clave, anio, mes));
            if (manual) {
                rellenosPadre.push({ columna: idxMes + 1, color: fondoVentaManualGlobal() });
            }
        });

        const idxPadre = filas.length;
        filasPais.push(idxPadre);
        totalesPorFila.push(totalPadre);
        if (rellenosPadre.length) filasRelleno[idxPadre] = rellenosPadre;
        filas.push([siglaMostrar].concat(celdasPadre, [totalPadre, 0]));

        // ---- Filas hijas, justo DESPUES del padre (misma posicion de hoy) ---
        const desdeHijos = filas.length;
        hijos.forEach(hijo => {
            const idxHijo = filas.length;
            filasHijas.push(idxHijo);
            totalesPorFila.push(hijo.total);
            if (hijo.rellenos.length) filasRelleno[idxHijo] = hijo.rellenos;
            filas.push([hijo.label].concat(hijo.celdas, [hijo.total, 0]));
        });
        if (hijos.length) {
            // El grupo del Excel: las filas de sociedad, colapsadas. `padre` es
            // el indice del pais dentro de `filasPais` (lo usa la pantalla).
            agrupaciones.push({ padre: idxPais, desde: desdeHijos,
                                hasta: filas.length - 1, colapsado: true });
        }
    });

    // El gran total: la suma de los MISMOS enteros (sumar las filas o los meses
    // da igual: los dos son la suma de las celdas redondeadas). Las filas hijas
    // estan DENTRO del total del padre, asi que el TOTAL GENERAL sigue saliendo
    // de las filas de pais (`filasPais`): sumar `totalesPorFila` completo
    // contaria dos veces a las sociedades.
    const totalGeneral = filasPais.reduce((acc, i) => acc + totalesPorFila[i], 0);

    // % Part. de cada pais y de cada sociedad, sobre el gran total.
    filas.forEach((fila, idx) => {
        fila[fila.length - 1] = totalGeneral > 0 ? (totalesPorFila[idx] / totalGeneral) : 0;
    });

    // La fila de TOTAL, en la misma posicion que en pantalla (ultima de datos).
    const filaTotal = ['TOTAL GENERAL'];
    if (todosMeses.length === 0) {
        filaTotal.push('-');
    } else {
        todosMeses.forEach((_m, idxMes) => filaTotal.push(totalesPorMes[idxMes]));
    }
    filaTotal.push(totalGeneral);
    filaTotal.push(totalGeneral > 0 ? 1 : 0);
    filas.push(filaTotal);

    return {
        columnas: columnas,
        filas: filas,
        formatos: formatos,
        anchos: anchos,
        // Indice (0-based) de la fila de TOTAL: la unica en negrita en el Excel.
        filasNegrita: [filas.length - 1],
        filasRelleno: filasRelleno,
        // Indices de las filas de PAIS (el padre, o la fila unica de un pais sin
        // desglose): son las que cuentan para la tarjeta del total y el Top 5.
        filasPais: filasPais,
        // Indices de las filas de SOCIEDAD (hijas).
        filasHijas: filasHijas,
        // Grupos del agrupamiento nativo de Excel: las filas hijas de cada pais
        // que se despliega, colapsadas. Es el campo `agrupaciones` del endpoint.
        agrupaciones: agrupaciones,
        hayVentasManuales: Object.keys(ventasManuales || {}).length > 0
    };
}

// ============================================================
// GENERAR VISTA GLOBAL (CON MARCADO NARANJA Y SIGLAS)
// ============================================================

// Abre/cierra el desglose por sociedad de un pais y vuelve a pintar la tabla.
// El patron es el de `pendiente_cobro.js`: estado de grupos abiertos + re-render
// del contenedor (asi el HTML no se parchea a mano).
window.toggleGrupoGlobal = function (indicePais) {
    const clave = String(indicePais);
    if (gruposAbiertosGlobal.has(clave)) {
        gruposAbiertosGlobal.delete(clave);
    } else {
        gruposAbiertosGlobal.add(clave);
    }
    const contenedor = document.getElementById('resultados-consolidado-global');
    if (!contenedor) return;
    contenedor.innerHTML = generarVistaGlobal(datosGlobales, ventasManualesData);
};

function generarVistaGlobal(datos, ventasManuales) {
    // El render deja fijados los insumos con los que se dibujo la tabla. No es
    // decorativo: `toggleGrupoGlobal` re-renderiza el contenedor llamando a esta
    // funcion con los globales, asi que si no se actualizaran aca, abrir un grupo
    // despues de un render hecho por otro camino (o con otros datos) volveria a
    // pintar la tabla vieja —o el cartel de "no hay datos"—.
    datosGlobales = datos;
    ventasManualesData = ventasManuales;
    // Unica fuente de verdad: el pivote que ve el usuario es el MISMO objeto que
    // despues exporta `exportarGlobalExcel` (nada de recalcular por separado).
    tablaGlobalCalculada = construirTablaGlobal(datos, ventasManuales);

    if (!datos || datos.length === 0) {
        return `
            <div style="text-align:center;padding:40px;color:#94a3b8;border:1px dashed #cbd5e1;border-radius:8px;">
                📭 No hay datos de ventas globales para el año ${anioSeleccionadoGlobal}
            </div>
        `;
    }

    const totalTransaccionesGeneral = datos.reduce((acc, p) => acc + p.totalTransacciones, 0);
    const totalPaises = datos.length;

    const todosMeses = datos.length > 0 ? datos[0].mesesOrdenados || [] : [];

    // Los IMPORTES de la pantalla salen del PIVOTE (los mismos enteros que van
    // al Excel): la tarjeta del total y el Top 5 no pueden mostrar un numero
    // distinto del que suma la tabla. `totalDLGeneral` es el gran total del
    // pivote (suma de los meses redondeados), no el crudo de `datos`.
    const filasPivote = tablaGlobalCalculada.filas;
    const columnaTotalUsd = tablaGlobalCalculada.columnas.length - 2;
    const filaTotalPivote = filasPivote[filasPivote.length - 1] || [];
    const totalDLGeneral = filaTotalPivote[columnaTotalUsd] || 0;

    // Las filas de PAIS del pivote: para un pais con desglose es el padre (no
    // las sociedades), asi el Top 5 y la tabla no cuentan dos veces. Ademas la
    // numeracion de las filas queda alineada con el pivote.
    const filasPais = tablaGlobalCalculada.filasPais || [];
    const indicesHijos = new Set(tablaGlobalCalculada.filasHijas || []);
    // El Top 5 se arma con las filas de PAIS del pivote: `indice` es la fila
    // real en `filasPivote` (no la posicion dentro de `datos`, que con el
    // desglose ya no coinciden).
    const top5 = filasPais.slice(0, 5);

    // El estilo de las filas y la marca de ventas manuales salen del pivote: aca
    // se mapea 1 a 1 con `todosMeses`, que es la CLAVE cruda del mes ('2026-02')
    // — la misma contra la que se compara al pintar la celda. Usar la ETIQUETA
    // del encabezado ('Feb 26') hacia que la marca de ventas manuales no se
    // dibujara NUNCA en pantalla (el Excel si la marcaba).
    const estiloFilaGlobal = (indice) => {
        const rellenos = tablaGlobalCalculada.filasRelleno[indice] || [];
        return rellenos.map(r => ({
            mes: todosMeses[r.columna - 1],
            color: '#' + r.color
        }));
    };

    const hayVentasManuales = !!tablaGlobalCalculada.hayVentasManuales;

    // El nombre que se muestra en la fila: las de pais llevan el globo; las de
    // sociedad van con SANGRIA y sin globo (son parte del pais).
    const nombreDeFila = (indice) => {
        const signos = filasPivote[indice] || [];
        const etiqueta = escapeHTML(String(signos[0] === undefined ? '' : signos[0]));
        if (indicesHijos.has(indice)) {
            return '<span style="display:inline-block;padding-left:22px;color:#475569;">'
                + etiqueta + '</span>';
        }
        return '🌐 ' + etiqueta;
    };

    let html = `
        ${avisoAlcanceConsolidado()}
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
                ${top5.map((indiceFila, i) => {
                    const filaPais = filasPivote[indiceFila] || [];
                    const totalPais = filaPais[columnaTotalUsd] || 0;
                    const porcentaje = totalDLGeneral > 0 ? (totalPais / totalDLGeneral * 100) : 0;
                    const colores = ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe'];
                    // Mostrar sigla en el gráfico
                    const nombrePais = String(filaPais[0] === undefined ? '' : filaPais[0]);
                    return `
                        <div style="display:flex;align-items:center;gap:12px;">
                            <span style="font-size:13px;font-weight:500;min-width:80px;color:#475569;">${escapeHTML(nombrePais)}</span>
                            <div style="flex:1;height:24px;background:#f1f5f9;border-radius:6px;overflow:hidden;position:relative;">
                                <div style="height:100%;width:${Math.min(porcentaje, 100)}%;background:${colores[i % colores.length]};border-radius:6px;transition:width 0.6s ease;display:flex;align-items:center;justify-content:flex-end;padding-right:6px;font-size:11px;color:white;font-weight:600;">
                                    ${porcentaje > 8 ? porcentaje.toFixed(1) + '%' : ''}
                                </div>
                            </div>
                            <span style="font-size:13px;font-weight:600;color:#1e293b;min-width:90px;text-align:right;">${formatearNumero(totalPais)}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>

        <!-- TABLA DETALLADA -->
        <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead style="background:#f8fafc;border-bottom:2px solid #e2e8f0;">
                        <tr>
                            <th style="padding:10px 14px;text-align:left;font-weight:600;color:#475569;min-width:120px;background:#f8fafc;">País</th>
                            ${todosMeses.length > 0 ? todosMeses.map(m => {
                                const label = etiquetaMesGlobal(m);
                                return `<th style="padding:10px 8px;text-align:right;font-weight:600;color:#475569;min-width:65px;background:#f8fafc;font-size:11px;">${label}</th>`;
                            }).join('') : `<th style="padding:10px 8px;text-align:center;font-weight:400;color:#94a3b8;background:#f8fafc;">(sin datos mensuales)</th>`}
                            <th style="padding:10px 14px;text-align:right;font-weight:600;color:#475569;min-width:90px;background:#fef3c7;">Total USD</th>
                            <th style="padding:10px 14px;text-align:right;font-weight:600;color:#475569;min-width:80px;background:#e8f0fe;">% Part.</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    // ---- Filas de la tabla: las del PIVOTE, en su orden --------------------
    // Se recorren las filas de PAIS (`filasPais`) y, cuando el grupo esta
    // ABIERTO, las filas de SOCIEDAD que le siguen. El pivote SIEMPRE tiene a
    // los hijos (asi el Excel nunca se separa de la pantalla): lo unico que
    // cambia es que estan ocultos. El caso sin meses usa este MISMO recorrido
    // (con la unica columna "(sin datos mensuales)"), asi que el triangulo, las
    // filas hijas y la sangria se comportan igual en los dos casos.
    const siguientes = agrupacionPorDesde(tablaGlobalCalculada.agrupaciones);
    const sinMeses = todosMeses.length === 0;

    // HTML de una fila del pivote (padre o hija). `atributos` es lo que
    // distingue al padre (clic, cursor, fondo): la hija va fija.
    const filaHtml = (indice, esHija, atributos) => {
        const filaPivote = filasPivote[indice] || [];
        const porcentaje = filaPivote[filaPivote.length - 1] || 0;
        const mesesManuales = estiloFilaGlobal(indice);
        const color = esHija ? '#475569' : '#334155';
        const pesoTotal = esHija ? '400' : '700';
        const pesoPorc = esHija ? '400' : '600';
        let celdas = '';
        if (sinMeses) {
            celdas = '<td style="padding:8px 8px;text-align:center;color:#94a3b8;">-</td>';
        } else {
            todosMeses.forEach((m, idxMes) => {
                const valor = filaPivote[idxMes + 1] || 0;
                const manual = mesesManuales.find(x => x.mes === m);
                // 🔴 CAMBIO: Color naranja con borde izquierdo, sin lápiz
                const estilo = manual ? `background-color:${manual.color}; font-weight:600; border-left:3px solid #f59e0b;` : '';
                celdas += `<td style="padding:8px 8px;text-align:right;font-variant-numeric:tabular-nums;color:${color};${estilo}">${valor !== 0 ? formatearNumero(valor) : '-'}</td>`;
            });
        }
        return `
                <tr${atributos}>
                    <td style="padding:8px 14px${esHija ? ' 8px 36px' : ''};font-weight:${esHija ? '500' : '700'};color:${esHija ? '#475569' : '#1e293b'};">${nombreDeFila(indice)}</td>
                    ${celdas}
                    <td style="padding:8px 14px;text-align:right;font-weight:${pesoTotal};color:${esHija ? '#475569' : '#1e293b'};background:#fef3c7;">${formatearNumero(filaPivote[columnaTotalUsd])}</td>
                    <td style="padding:8px 14px;text-align:right;font-weight:${pesoPorc};color:#2563eb;background:#e8f0fe;">${porcentajePantallaGlobal(porcentaje)}</td>
                </tr>
        `;
    };

    let idxVisible = 0;
    filasPais.forEach(indice => {
        const grupo = siguientes[indice];
        const abierto = !!grupo && gruposAbiertosGlobal.has(String(grupo.padre));
        const bg = idxVisible % 2 === 0 ? '#fafafa' : 'transparent';
        idxVisible++;
        // El triangulo del desplegable: ▸ cerrado (por defecto), ▾ abierto.
        const triangulo = grupo
            ? `<span style="display:inline-block;width:18px;color:#64748b;">${abierto ? '▾' : '▸'}</span>`
            : '<span style="display:inline-block;width:18px;color:transparent;"></span>';
        const clic = grupo ? ` data-onclick="toggleGrupoGlobal(${grupo.padre})"` : '';
        const titulo = grupo ? ' title="Clic para ver el desglose por sociedad"' : '';
        const cursor = grupo ? 'cursor:pointer;' : '';
        const atributosPadre = `${clic}${titulo} style="${cursor}border-bottom:1px solid #f1f5f9;background:${bg};"`;

        let cuerpoPadre = filaHtml(indice, false, atributosPadre);
        // El triangulo va DENTRO de la primera celda, antes del globo.
        cuerpoPadre = cuerpoPadre.replace('">🌐 ', `">${triangulo}🌐 `);
        html += cuerpoPadre;

        // Las filas de sociedad del grupo, solo cuando esta abierto. En el
        // pivote (y en el Excel) estan SIEMPRE.
        if (!abierto) return;
        for (let k = grupo.desde; k <= grupo.hasta; k++) {
            html += filaHtml(k, true, ' style="border-bottom:1px solid #f1f5f9;background:#fbfcfe;"');
        }
    });

    // Fila de totales: los mismos numeros que la ultima fila del pivote.
    html += `
            <tr style="font-weight:bold;background:#f0f4ff;border-top:2px solid #e2e8f0;">
                <td style="padding:10px 14px;font-size:14px;color:#1e293b;">TOTAL GENERAL</td>
    `;

    if (sinMeses) {
        html += '<td style="padding:10px 8px;text-align:center;color:#94a3b8;">-</td>';
    } else {
        todosMeses.forEach((_m, idxMes) => {
            const totalMes = filaTotalPivote[idxMes + 1] || 0;
            html += `<td style="padding:10px 8px;text-align:right;font-size:14px;color:#1e293b;">${formatearNumero(totalMes)}</td>`;
        });
    }

    html += `
                <td style="padding:10px 14px;text-align:right;font-size:16px;color:#2563eb;background:#fef3c7;">${formatearNumero(totalDLGeneral)}</td>
                <td style="padding:10px 14px;text-align:right;font-size:14px;color:#2563eb;background:#e8f0fe;">${porcentajePantallaGlobal(filaTotalPivote[filaTotalPivote.length - 1])}</td>
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


    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    return html;
}

// Indice (dentro de `filasPais`) -> grupo que empieza en esa fila de pais. Sirve
// para saber si una fila de pais tiene desglose y donde terminan sus hijos.
function agrupacionPorDesde(agrupaciones) {
    const porDesde = {};
    (agrupaciones || []).forEach(g => { porDesde[g.padre] = g; });
    return porDesde;
}

// ============================================================
// ============================================================
// EXPORTAR XLSX GLOBAL (el mismo pivote que se ve en pantalla)
// ============================================================

function filasRellenoPlanasGlobal(tabla) {
    // {indiceFila: [{columna, color}]} -> lista plana que entiende el endpoint.
    const planas = [];
    Object.keys(tabla.filasRelleno || {}).forEach(fila => {
        (tabla.filasRelleno[fila] || []).forEach(r => {
            planas.push({ fila: parseInt(fila, 10), columna: r.columna, color: r.color });
        });
    });
    return planas;
}

// Opciones de presentacion del .xlsx: las comparten la DESCARGA y el ENVIO por
// correo, para que el adjunto sea el mismo archivo (nada de dos listas que se
// separan con el primer cambio).
function opcionesExcelGlobal(tabla) {
    return {
        formatos: tabla.formatos,
        anchos: tabla.anchos,
        filas_negrita: tabla.filasNegrita,
        congelar_encabezado: true,
        rellenos: filasRellenoPlanasGlobal(tabla),
        // El Excel del usuario va SIN lineas de cuadricula. Los otros reportes
        // no mandan este campo y conservan la cuadricula (y sus decimales).
        sin_cuadricula: true,
        // El desglose por sociedad baja AGRUPADO y COLAPSADO (agrupamiento
        // nativo de Excel). Sin grupos el endpoint se comporta como hoy.
        agrupaciones: tabla.agrupaciones
    };
}

// El nombre del archivo adjunto/descargado: el mismo en las dos acciones.
// `Ventas Consolidadas al dd-mm-aaaa.xlsx` con la fecha LOCAL del momento en que
// se exporta/envia (las barras no se pueden usar en un nombre de archivo). La
// fecha se calcula AL LLAMAR, nunca al dibujar la pantalla.
function archivoExcelGlobal() {
    const hoy = (typeof window.fechaHoyConGuiones === 'function')
        ? window.fechaHoyConGuiones()
        : (() => {
            const d = new Date();
            const dosDigitos = (n) => (n < 10 ? '0' : '') + n;
            return dosDigitos(d.getDate()) + '-' + dosDigitos(d.getMonth() + 1) + '-' + d.getFullYear();
        })();
    return `Ventas Consolidadas al ${hoy}.xlsx`;
}

function exportarGlobalExcel() {
    const tabla = tablaGlobalCalculada;
    if (!tabla || !tabla.filas || tabla.filas.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para exportar', 'Reportes');
        return;
    }

    if (typeof window.descargarXlsx !== 'function') {
        if (typeof toastError === 'function') toastError('Exportación no disponible', 'Reportes');
        return;
    }
    window.descargarXlsx(archivoExcelGlobal(), 'Ventas Globales', tabla.columnas, tabla.filas,
                         opcionesExcelGlobal(tabla));

    if (typeof toastSuccess === 'function') toastSuccess('✅ Reporte exportado a Excel', 'Reportes');
}

// ============================================================
// ENVIAR POR CORREO (envio directo por Outlook; solo Ventas Globales por ahora)
// ============================================================
// Brief 23/09/2026 y brief 24/09/2026 (envio directo, `Send()`): el boton va
// SOLO en Ventas Globales, pero el mecanismo es reusable
// (`window.pedirCorreoYEnviar`): los demas informes solo tienen que llamarlo con
// SU tabla y SU asunto por defecto.
//
// El payload es `tablaGlobalCalculada`, el MISMO pivote de la descarga: no se
// recalcula nada (si se recalculara, el adjunto podria no coincidir con lo que
// el usuario ve en pantalla).
function enviarGlobalPorCorreo() {
    const tabla = tablaGlobalCalculada;
    if (!tabla || !tabla.filas || tabla.filas.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para enviar', 'Reportes');
        return;
    }
    if (typeof window.pedirCorreoYEnviar !== 'function') {
        if (typeof toastError === 'function') toastError('El envío por correo no está disponible', 'Reportes');
        return;
    }
    // El asunto por defecto se arma ADENTRO del dialogo, con la fecha del dia.
    window.pedirCorreoYEnviar(archivoExcelGlobal(), 'Ventas Globales', tabla.columnas, tabla.filas,
                              opcionesExcelGlobal(tabla),
                              window.ASUNTO_VENTAS_GLOBALES || 'Ventas Consolidadas al ');
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
            <button id="btnExportarGlobalExcel" style="padding:6px 16px;background:#16a34a;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                📥 Exportar Excel
            </button>
            <button id="btnEnviarGlobalCorreo" style="padding:6px 16px;background:#0ea5e9;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                ✉️ Enviar por correo
            </button>
            <button id="btn-cargar-venta-manual" data-onclick="abrirModalVentaManual()" data-perm="reportes.crear" style="padding:6px 16px;background:#8b5cf6;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                ✏️ Cargar VM
            </button>
            <button id="btn-admin-ventas-manuales" data-onclick="abrirAdminVentasManuales()" style="padding:6px 16px;background:#64748b;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                📋 Admin VM
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
    document.getElementById('btnExportarGlobalExcel').onclick = exportarGlobalExcel;
    document.getElementById('btnEnviarGlobalCorreo').onclick = enviarGlobalPorCorreo;

    inicializadoGlobal = true;
    await cargarConsolidadoTotal();
}

// ============================================================
// EXPONER FUNCIONES GLOBALES
// ============================================================

// `construirTablaGlobal` y `etiquetaMesGlobal` son puras: se exponen para que el
// probe de Node (sin navegador) las ejercite sobre el archivo real.
window.construirTablaGlobal = construirTablaGlobal;
window.etiquetaMesGlobal = etiquetaMesGlobal;
window.filasRellenoPlanasGlobal = filasRellenoPlanasGlobal;
window.cargarConsolidadoTotal = cargarConsolidadoTotal;
window.inicializarConsolidadoTotal = inicializarConsolidadoTotal;
window.exportarGlobalExcel = exportarGlobalExcel;
window.enviarGlobalPorCorreo = enviarGlobalPorCorreo;
// Permite fijar el anio del informe sin navegador (lo usa el probe de Node).
window.setAnioGlobal = function (anio) { anioSeleccionadoGlobal = anio; };
window.opcionesExcelGlobal = opcionesExcelGlobal;
window.archivoExcelGlobal = archivoExcelGlobal;

console.log('✅ consolidado_total.js cargado (con siglas y marcado naranja)');
