// ============================================================
// REPORTE: CONTRATOS (PENDIENTE DE FACTURAR)
// ============================================================

let datosReporte = [];
let filtroAnio = '';
let filtroMes = '';
let monedaActual = 'PS';

// Los anios que el usuario ABRIO en la tabla (los meses de ese anio a la vista).
// Arranca vacio: con "Anios: Todos" la tabla se ve con una columna por anio y
// todo CERRADO, como el .xlsx (los grupos de columnas bajan colapsados). Es
// estado de MODULO, no del DOM: `toggleAnioContratos` lo cambia y vuelve a
// pintar la tabla entera (mismo patron que `gruposAbiertosGlobal` de
// `consolidado_total.js`). Se guarda el anio como String porque las claves de un
// `Set` y el `data-onclick` del HTML son texto.
const aniosAbiertosContratos = new Set();

// Los CLIENTES que el usuario ABRIO en la tabla (los contratos de ese cliente a
// la vista). Misma idea que `aniosAbiertosContratos`, pero en las FILAS: la fila
// del cliente es el `summary` del grupo y los contratos van plegados debajo
// (Punto 5 del 05/10/2026: `Cliente` -> `Contrato`). Arranca vacio: la tabla se ve
// con los clientes SOLO (sus contratos plegados).
const clientesAbiertosContratos = new Set();

// Funciones auxiliares (sanitización, formateo)
function sanitizarCSV(str) {
    if (!str) return '';
    return String(str).replace(/[=+\-@\t\r\n]/g, ' ');
}

function formatearNumero(valor) {
    const num = parseFloat(valor);
    if (isNaN(num)) return '0,00';
    const partes = num.toFixed(2).split('.');
    const entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return entero + ',' + partes[1];
}

// ============================================================
// CARGA DE AÑOS
// ============================================================

export function cargarAnos() {
    console.log('📅 Cargando años...');
    const select = document.getElementById('filtro-anio');
    if (!select) {
        console.error('❌ No se encontró #filtro-anio');
        return;
    }

    select.innerHTML = '<option value="">Cargando...</option>';
    select.disabled = true;

    const base = window.baseActiva || 'plataforma_rd';
    const sociedad = window.sociedadActiva || '';
    console.log('📌 Base para años:', base, 'Sociedad:', sociedad);

    fetch(`/api/reportes/anos?base=${base}&sociedad=${sociedad}`)
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        })
        .then(data => {
            select.disabled = false;
            if (data.success && data.anos && data.anos.length > 0) {
                const anosOrdenados = data.anos.sort((a, b) => b - a);
                const anosLimitados = anosOrdenados.slice(0, 10);
                select.innerHTML = '<option value="">Todos</option>';
                anosLimitados.forEach(anio => {
                    const option = document.createElement('option');
                    option.value = anio;
                    option.textContent = anio;
                    select.appendChild(option);
                });
                const añoActual = new Date().getFullYear();
                select.value = anosLimitados.includes(añoActual) ? añoActual : anosLimitados[0] || '';
                filtroAnio = select.value;
                console.log('✅ Años cargados, seleccionado:', filtroAnio);
                setTimeout(() => ejecutarReporte(), 300);
            } else {
                select.innerHTML = '<option value="">Sin datos</option>';
                if (typeof toastWarning === 'function') toastWarning('No se encontraron años disponibles', 'Reportes');
            }
        })
        .catch(error => {
            console.error('❌ Error cargando años:', error);
            select.disabled = false;
            select.innerHTML = '<option value="">Error al cargar</option>';
            if (typeof toastError === 'function') toastError('Error al cargar años: ' + escapeHTML(error.message), 'Reportes');
        });
}

// ============================================================
// EJECUTAR REPORTE
// ============================================================

export function ejecutarReporte() {
    console.log('🔍 ejecutarReporte() llamado');
    const selectAnio = document.getElementById('filtro-anio');
    const selectMes = document.getElementById('filtro-mes');
    const anio = selectAnio?.value || '';
    const mes = selectMes?.value || '';
    filtroAnio = anio;
    filtroMes = mes;

    mostrarLoading(true);

    const base = window.baseActiva || 'plataforma_rd';
    const sociedad = window.sociedadActiva || null;
    console.log('📌 Base para reporte:', base, 'Sociedad:', sociedad);

    const payload = { anio: anio || null, mes: mes || null, base, sociedad };
    console.log('📤 Payload:', payload);

    fetch('/api/reportes/contratos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    })
    .then(data => {
        mostrarLoading(false);
        if (data.success) {
            datosReporte = data.data || [];
            // Cada corrida del reporte arranca con TODO CERRADO (el defecto del
            // brief): los anios y los clientes abiertos de la corrida anterior no
            // se arrastran (los clientes se guardan por INDICE, asi que una
            // corrida nueva con otro orden abriria el cliente equivocado).
            aniosAbiertosContratos.clear();
            clientesAbiertosContratos.clear();
            console.log('📊 datosReporte.length:', datosReporte.length);
            if (datosReporte.length > 0) {
                const monedas = [...new Set(datosReporte.map(d => d.MONEDA))];
                console.log('🔍 MONEDAS ENCONTRADAS:', monedas);
            }
            actualizarBotonesMoneda();
            renderizarResumenPorMoneda(datosReporte);
            const datosFiltrados = filtrarDatosPorAnioMes(datosReporte);
            renderizarResumenAnualCompleto(datosFiltrados);
            renderizarTablaDinamica(datosReporte, monedaActual);
            if (data.total_registros > 0) {
                if (typeof toastSuccess === 'function') toastSuccess(`✅ ${data.total_registros} registros encontrados`, 'Reportes');
            } else {
                if (typeof toastWarning === 'function') toastWarning('⚠️ No se encontraron registros para los filtros seleccionados', 'Reportes');
            }
        } else {
            console.error('❌ data.success es false:', data.error);
            if (typeof toastError === 'function') toastError('❌ Error: ' + escapeHTML(data.error || 'Error desconocido'), 'Reportes');
            renderizarTablaDinamica([], 'PS');
            renderizarResumenPorMoneda([]);
            renderizarResumenAnualCompleto([]);
        }
    })
    .catch(error => {
        console.error('❌ Error en fetch:', error);
        mostrarLoading(false);
        if (typeof toastError === 'function') toastError('❌ Error al cargar el reporte: ' + escapeHTML(error.message), 'Reportes');
        renderizarTablaDinamica([], 'PS');
        renderizarResumenPorMoneda([]);
        renderizarResumenAnualCompleto([]);
    });
}

// ============================================================
// FILTROS Y RENDERIZADO
// ============================================================

function filtrarDatosPorAnioMes(datos) {
    if (!datos || datos.length === 0) return [];
    let filtrados = datos;
    if (filtroAnio && filtroAnio !== '') {
        filtrados = filtrados.filter(d => d.ANIO === parseInt(filtroAnio));
    }
    if (filtroMes && filtroMes !== '') {
        filtrados = filtrados.filter(d => d.MES === parseInt(filtroMes));
    }
    return filtrados;
}

function actualizarBotonesMoneda() {
    document.querySelectorAll('.btn-moneda').forEach(btn => {
        btn.classList.remove('active');
        btn.style.background = 'white';
        btn.style.color = btn.dataset.moneda === 'PS' ? '#2563eb' : '#16a34a';
        btn.style.borderColor = btn.dataset.moneda === 'PS' ? '#2563eb' : '#16a34a';
        btn.style.boxShadow = 'none';
        if (btn.dataset.moneda === monedaActual) {
            btn.classList.add('active');
            btn.style.background = btn.dataset.moneda === 'PS' ? '#2563eb' : '#16a34a';
            btn.style.color = 'white';
            btn.style.borderColor = btn.dataset.moneda === 'PS' ? '#2563eb' : '#16a34a';
            btn.style.boxShadow = `0 2px 8px ${btn.dataset.moneda === 'PS' ? 'rgba(37,99,235,0.4)' : 'rgba(22,163,74,0.4)'}`;
        }
    });
}

// Cambia la moneda activa y REPINTA la tabla. El estado de los anios abiertos
// (`aniosAbiertosContratos`) no se toca: el usuario que abrio un anio lo sigue
// viendo abierto al cambiar de moneda.
export function cambiarMoneda(moneda) {
    monedaActual = moneda;
    actualizarBotonesMoneda();
    renderizarTablaDinamica(datosReporte, moneda);
}

function renderizarResumenPorMoneda(datos) {
    const container = document.getElementById('resumen-moneda');
    if (!container) return;
    if (!datos || datos.length === 0) {
        container.innerHTML = '<p style="color:#94a3b8;">No hay datos disponibles</p>';
        return;
    }
    const datosPS = datos.filter(d => d.MONEDA === 'PS' || d.MONEDA === 'PESOS');
    const datosDL = datos.filter(d => d.MONEDA === 'DL' || d.MONEDA === 'DOLARES' || d.MONEDA === 'USD');
    const totalPS = datosPS.reduce((sum, d) => sum + (parseFloat(d.IMPORTE) || 0), 0);
    const totalDL = datosDL.reduce((sum, d) => sum + (parseFloat(d.IMPORTE) || 0), 0);
    container.innerHTML = `
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:20px;">
            <div style="background:white; border-radius:10px; padding:16px; border-left:4px solid #2563eb; box-shadow:0 2px 4px rgba(0,0,0,0.06);">
                <div style="font-size:12px; color:#64748b; font-weight:600; text-transform:uppercase; letter-spacing:0.04em;">🇩🇴 PESOS (PS)</div>
                <div style="font-size:22px; font-weight:700; color:#2563eb; margin-top:4px;">$${formatearNumero(totalPS)}</div>
                <div style="font-size:12px; color:#94a3b8; margin-top:2px;">${datosPS.length} registros</div>
            </div>
            <div style="background:white; border-radius:10px; padding:16px; border-left:4px solid #16a34a; box-shadow:0 2px 4px rgba(0,0,0,0.06);">
                <div style="font-size:12px; color:#64748b; font-weight:600; text-transform:uppercase; letter-spacing:0.04em;">💵 DÓLARES (DL)</div>
                <div style="font-size:22px; font-weight:700; color:#16a34a; margin-top:4px;">$${formatearNumero(totalDL)}</div>
                <div style="font-size:12px; color:#94a3b8; margin-top:2px;">${datosDL.length} registros</div>
            </div>
        </div>
    `;
}

// El resumen es por ANIO (revision del usuario, 05/10/2026: "Resumen por Año/Mes,
// ocupa espacio. Quizas lo achicaria solo a Resumen por Año"): UNA fila por anio con
// los dos totales, en vez de una por mes. La suma es la misma de antes (los importes
// de cada moneda); lo unico que cambia es la agrupacion, y con eso el bloque pasa de
// ~8 filas a 2-3 y la tabla de detalle sube en la pantalla.
function renderizarResumenAnualCompleto(datos) {
    const container = document.getElementById('resumen-anual');
    if (!container) return;
    container.innerHTML = '';
    if (!datos || datos.length === 0) {
        container.innerHTML = '<p style="color:#94a3b8;">No hay datos para resumen</p>';
        return;
    }
    const datosPS = datos.filter(d => d.MONEDA === 'PS' || d.MONEDA === 'PESOS');
    const datosDL = datos.filter(d => d.MONEDA === 'DL' || d.MONEDA === 'DOLARES' || d.MONEDA === 'USD');

    const porAnio = {};
    const acumular = (row, campo) => {
        const anio = row.ANIO;
        if (!porAnio[anio]) porAnio[anio] = { ANIO: anio, PS_IMPORTE: 0, DL_IMPORTE: 0 };
        porAnio[anio][campo] += parseFloat(row.IMPORTE) || 0;
    };
    datosPS.forEach(row => acumular(row, 'PS_IMPORTE'));
    datosDL.forEach(row => acumular(row, 'DL_IMPORTE'));

    const resumen = Object.keys(porAnio).map(clave => porAnio[clave])
        .sort((a, b) => a.ANIO - b.ANIO);

    if (resumen.length === 0) {
        container.innerHTML = '<p style="color:#94a3b8;">No hay datos para resumen</p>';
        return;
    }

    let totalPSGeneral = 0, totalDLGeneral = 0;
    let html = `
        <table style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead>
                <tr>
                    <th style="background:#f1f5f9; padding:8px 12px; text-align:left; font-weight:600; border-bottom:2px solid #e2e8f0;">Año</th>
                    <th style="background:#f1f5f9; padding:8px 12px; text-align:right; font-weight:600; border-bottom:2px solid #e2e8f0; color:#2563eb;">Total PS</th>
                    <th style="background:#f1f5f9; padding:8px 12px; text-align:right; font-weight:600; border-bottom:2px solid #e2e8f0; color:#16a34a;">Total DL</th>
                </tr>
            </thead>
            <tbody>
    `;
    resumen.forEach(row => {
        totalPSGeneral += row.PS_IMPORTE;
        totalDLGeneral += row.DL_IMPORTE;
        html += `
            <tr>
                <td style="padding:6px 12px; border-bottom:1px solid #f1f5f9;">${row.ANIO}</td>
                <td style="padding:6px 12px; border-bottom:1px solid #f1f5f9; text-align:right; color:#2563eb;">$${formatearNumero(row.PS_IMPORTE)}</td>
                <td style="padding:6px 12px; border-bottom:1px solid #f1f5f9; text-align:right; color:#16a34a;">$${formatearNumero(row.DL_IMPORTE)}</td>
            </tr>
        `;
    });
    html += `
        <tfoot>
            <tr style="font-weight:bold; background:#f8fafc;">
                <td style="padding:8px 12px; text-align:right; border-top:2px solid #e2e8f0;">TOTALES</td>
                <td style="padding:8px 12px; text-align:right; border-top:2px solid #e2e8f0; color:#2563eb; font-size:15px;">$${formatearNumero(totalPSGeneral)}</td>
                <td style="padding:8px 12px; text-align:right; border-top:2px solid #e2e8f0; color:#16a34a; font-size:15px;">$${formatearNumero(totalDLGeneral)}</td>
            </tr>
        </tfoot>
    `;
    html += `</tbody>`;
    container.innerHTML = html;
}

// ============================================================
// EL PIVOTE (una sola fuente: la pantalla y el .xlsx)
// ============================================================
// `construirPivoteContratos` es el UNICO armado del pivote de Pendiente de
// Facturar: lo usan `renderizarTablaDinamica` (la pantalla) y `exportarExcel`
// (el archivo). Si cada uno armara su tabla, la pantalla y el Excel se
// separarian con el primer cambio: es la misma regla que se aplico en Ventas
// Globales (`construirTablaGlobal`).
//
// Punto 5 de la lista del 05/10/2026 (el usuario): el pivote pasa de PLANO
// (una fila por `contrato|cliente|concepto`) a DOS NIVELES (`Cliente` ->
// `Contrato`), con el nombre del cliente en su fila de resumen y los contratos
// AGRUPADOS debajo (plegados), y con la columna `Total` AL FINAL de las columnas
// de valor. Las decisiones del usuario estan escritas en el codigo, no aca.
//
// Aplica los filtros de la pantalla (moneda activa + `filtroAnio` + `filtroMes`)
// y devuelve:
//   columnas      los encabezados CON TODAS las columnas de mes, incluidas las que
//                 dan cero y se ocultan: es la lista de la PRESENTACION del
//                 encabezado (`Cliente, Contrato, Concepto`, `Total` cuando hay mas
//                 de un anio, y cada anio con sus meses), y de ella sale `indiceTotal`
//                 (la ULTIMA columna). OJO: el encabezado y la FILA no tienen el
//                 mismo orden (`Total` va 4o en el encabezado y ultimo en la fila),
//                 asi que `columnas` NO sirve para leer una celda por posicion; lo
//                 que se VE es `columnasMesVisibles`.
//   filas         las filas de CONTRATO (las tres primeras celdas son el TEXTO
//                 CRUDO, sin escapar: el .xlsx lo escribe tal cual y la pantalla
//                 lo escapa al dibujar) + la fila `TOTAL GENERAL` al final. Las
//                 filas de CLIENTE (el nivel de arriba) NO estan aca: viven en
//                 `filasCliente` (ver abajo), porque su posicion en la grilla la
//                 decide el que dibuja (la pantalla intercala los dos niveles, el
//                 .xlsx usa `filas_ocultas` para plegar los contratos).
//                 La celda del CLIENTE va VACIA en las filas de contrato: el nombre
//                 vive SOLO en la fila del cliente (punto 1 de la revision en
//                 pantalla, 05/10/2026: `[contrato, '', concepto, ...]`).
//                 Cada fila trae, en este orden: las tres celdas de texto, la
//                 celda de cada anio (el TOTAL de ese anio), los meses en el
//                 orden de `columnasMes` y el Total de la fila (la suma de TODOS
//                 sus meses, de todos los anios).
//                 El ORDEN de las filas se calcula sobre el texto ESCAPADO (el
//                 mismo criterio que HEAD: ver el `sort` mas abajo).
//   filasCliente  una entrada por CLIENTE, en el orden de `filas`, con
//                 `{cliente, fila: {textos + valores}}`: la fila RESUMEN del
//                 cliente (su nombre en la 2a celda -`Cliente`- y la 1a vacia, el
//                 total de todos sus contratos, mes por mes). Es el nivel de arriba
//                 de la tabla.
//   clienteDeFila el nombre del cliente de cada fila de contrato (mismo indice
//                 que `filas`), para saber que filas van plegadas bajo que
//                 cliente. La fila `TOTAL GENERAL` trae el nombre de su cliente
//                 sintetico porque no se pliega nunca.
//   columnasMes   TODAS las columnas de mes, en orden: el producto `anios x meses`
//                 (`{anio, mes, clave: 'AAAA-MM', etiqueta}`). Incluye las que dan
//                 cero: es de aca de donde sale la celda de cada fila.
//   columnasMesVisibles  las MISMAS columnas menos las que dan cero, cada una con su
//                 `posicion` dentro de `columnasMes`: es la lista que dibujan la
//                 pantalla y el .xlsx (una sola regla para los dos).
//   mesesOcultos  las etiquetas de las columnas que NO se muestran (las de total
//                 cero): es lo que el .xlsx manda en `meses_visibles`.
//   columnasAnio  un `{anio, etiqueta}` por anio cuando hay MAS DE UNO (es el
//                 rotulo de la columna del anio); vacio con un solo anio (esa
//                 tabla no lleva columna de anio: sale por mes, como hoy).
//   anios         los anios presentes, ordenados (son los grupos del .xlsx).
//   indiceTotal   indice de la columna `Total` (la ULTIMA) dentro de una fila.
//   filaTotal     indice 0-based de `TOTAL GENERAL` dentro de `filas`.
//   registros     cuantas filas crudas pasaron los filtros (0 = no hay nada que
//                 mostrar para esa moneda/filtros).
function construirPivoteContratos(datos, moneda) {
    let datosFiltrados = (datos || []).filter(d => d.MONEDA === moneda);
    if (filtroAnio && filtroAnio !== '') {
        datosFiltrados = datosFiltrados.filter(d => d.ANIO === parseInt(filtroAnio));
    }
    if (filtroMes && filtroMes !== '') {
        datosFiltrados = datosFiltrados.filter(d => d.MES === parseInt(filtroMes));
    }

    const anios = [...new Set(datosFiltrados.map(d => d.ANIO))].sort();
    const meses = [...new Set(datosFiltrados.map(d => d.MES))].sort((a, b) => a - b);
    const nombresMeses = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

    // Las columnas son el producto `anios x meses` (los meses que aparecen en
    // CUALQUIER anio).
    const columnasMes = [];
    anios.forEach(anio => {
        meses.forEach(mes => {
            columnasMes.push({
                anio: anio,
                mes: mes,
                clave: `${anio}-${String(mes).padStart(2, '0')}`,
                etiqueta: `${nombresMeses[mes] || mes} ${anio}`
            });
        });
    });

    // El agrupamiento de DOS NIVELES: cliente -> contrato. Cada contrato guarda
    // sus importes por mes; el cliente, la suma de los suyos. Los dos acumulan
    // sobre las MISMAS celdas de mes (nada de recalcular por otro camino).
    const porCliente = {};
    datosFiltrados.forEach(row => {
        const contrato = row.CONTRATO || 'Sin Contrato';
        const cliente = row.CLIENTE || 'Sin Cliente';
        const centro = row.CENTRO_COSTO || 'Sin Concepto';
        if (!porCliente[cliente]) porCliente[cliente] = { valores: {}, contratos: {} };
        const grupo = porCliente[cliente];
        const claveContrato = `${contrato}|${centro}`;
        if (!grupo.contratos[claveContrato]) {
            grupo.contratos[claveContrato] = { CONTRATO: contrato, CENTRO_COSTO: centro, valores: {} };
        }
        const colKey = `${row.ANIO || 0}-${String(row.MES || 0).padStart(2, '0')}`;
        const importe = parseFloat(row.IMPORTE) || 0;
        grupo.contratos[claveContrato].valores[colKey] =
            (grupo.contratos[claveContrato].valores[colKey] || 0) + importe;
        grupo.valores[colKey] = (grupo.valores[colKey] || 0) + importe;
    });

    // El ORDEN de los clientes es el de HEAD: se compara el texto YA ESCAPADO (que
    // es lo que el pivote guardaba antes de unificar pantalla y Excel). El pivote
    // sigue GUARDANDO el crudo (el .xlsx lo escribe tal cual y la pantalla lo
    // escapa al dibujar: escapar aca haria salir `&amp;` en el Excel), asi que se
    // escapa SOLO para comparar.
    // Por que: escapar cambia el orden relativo de dos textos que empiezan con
    // `<` y con `>` (`"<Sin cliente>"` vs `">Mayorista del Sur"`: el crudo da -1 y
    // el escapado +1), asi que comparando el crudo las filas salian en OTRO orden
    // que ayer. Medido en la ronda de fix del 24/09/2026: la pantalla vuelve a ser
    // byte a byte la de HEAD en los 48 fixtures del auxiliar 339, y el 341 mide
    // este par de textos. Ahora el orden es CLIENTE y despues CONTRATO (el
    // desempate de los contratos de un mismo cliente).
    const clientes = Object.keys(porCliente).sort((a, b) =>
        escapeHTML(a).localeCompare(escapeHTML(b)));

    // La celda del ANIO lleva el TOTAL de ese anio (la suma de sus meses) y va
    // DELANTE de los meses, una por anio. Con UN solo anio no hay celda de anio:
    // la tabla sale por mes. El total del anio sale de las MISMAS celdas de mes
    // que van a la tabla (`valoresMes`): nada de recalcular por otro camino, asi
    // la pantalla y el .xlsx no se pueden separar.
    const variosAnios = anios.length > 1;
    const columnasAnio = variosAnios
        ? anios.map(anio => ({ anio: anio, etiqueta: String(anio) }))
        : [];
    const totalesPorAnio = anios.map(() => 0);

    // Las celdas de VALOR de una fila, en el orden del pivote: las celdas de anio,
    // los meses y el Total AL FINAL (decision del usuario del 05/10/2026: el Total
    // va al final de todas las columnas de valor, no despues de `Concepto`).
    //
    // `sumarAlInforme` dice si esas celdas de anio entran en el TOTAL GENERAL del
    // informe. Lo llevan SOLO las filas de CONTRATO: la fila de resumen del CLIENTE
    // es la suma de sus contratos, asi que sumarla TAMBIEN contaria dos veces cada
    // importe. Ese fue el defecto medido en la primera corrida del probe 311 con el
    // pivote de dos niveles (05/10/2026): el Total de cada anio salia al DOBLE
    // exacto (2025: 4.669,48 en vez de 2.334,74; 2026: 5.015,50 en vez de 2.507,75).
    // Los MESES nunca se acumulan (salen de `valoresMes` y el pie del .xlsx los
    // recalcula de la grilla): por eso el defecto tocaba solo las celdas de anio.
    const valoresDe = (valores, sumarAlInforme) => {
        const valoresMes = columnasMes.map(cm => valores[cm.clave] || 0);
        const valoresAnio = variosAnios
            ? anios.map((anio, indiceAnio) => {
                const totalAnio = valoresMes.reduce((suma, valor, posicion) =>
                    (columnasMes[posicion].anio === anio ? suma + valor : suma), 0);
                if (sumarAlInforme) totalesPorAnio[indiceAnio] += totalAnio;
                return totalAnio;
            })
            : [];
        const totalFila = valoresMes.reduce((suma, valor) => suma + valor, 0);
        return { valoresMes: valoresMes, valoresAnio: valoresAnio, totalFila: totalFila };
    };

    const filas = [];
    const filasCliente = [];
    const clienteDeFila = [];
    let totalGeneral = 0;
    clientes.forEach(cliente => {
        const grupo = porCliente[cliente];
        // `false`: la fila del cliente NO suma al informe (sus contratos ya suman).
        const suyos = valoresDe(grupo.valores, false);
        // La fila del CLIENTE (el nivel de arriba): el nombre en la columna `Cliente`
        // (la 1a: es la columna A del informe, en la pantalla y en el .xlsx) y las de
        // `Contrato` y `Concepto` vacias. La posicion en la grilla la decide el que
        // dibuja. Revision del usuario en pantalla (05/10/2026): el nombre del cliente
        // va en SU columna (antes iba debajo del encabezado `Contrato`) y no se repite
        // en las filas de contrato (ver el `push` de abajo).
        filasCliente.push({
            cliente: cliente,
            fila: [cliente, '', '', ...suyos.valoresAnio, ...suyos.valoresMes, suyos.totalFila]
        });
        Object.keys(grupo.contratos)
            .sort((a, b) => {
                const cA = grupo.contratos[a], cB = grupo.contratos[b];
                const contratoA = escapeHTML(cA.CONTRATO), contratoB = escapeHTML(cB.CONTRATO);
                if (contratoA !== contratoB) return contratoA.localeCompare(contratoB);
                return escapeHTML(cA.CENTRO_COSTO).localeCompare(escapeHTML(cB.CENTRO_COSTO));
            })
            .forEach(clave => {
                const contrato = grupo.contratos[clave];
                // `true`: las celdas de anio de cada CONTRATO son las que arman el
                // total por anio del informe (una sola vez cada importe).
                const delContrato = valoresDe(contrato.valores, true);
                totalGeneral += delContrato.totalFila;
                // `clienteDeFila` guarda el cliente de cada fila (es lo que dice bajo
                // que grupo va plegada), pero la CELDA del cliente va VACIA: el nombre
                // ya esta en la fila del cliente, arriba, y no se repite. El CONTRATO
                // va en la 2a celda (es la columna B: `Cliente` -> `Contrato` ->
                // `Concepto`, el orden que pidio el usuario el 05/10/2026, igual en la
                // pantalla y en el .xlsx).
                clienteDeFila.push(cliente);
                filas.push(['', contrato.CONTRATO, contrato.CENTRO_COSTO,
                            ...delContrato.valoresAnio, ...delContrato.valoresMes,
                            delContrato.totalFila]);
            });
    });

    // El TOTAL de cada columna de mes: la suma de la columna sobre las filas de
    // CONTRATO. Se calcula ANTES de agregar el pie: el TOTAL GENERAL no es un dato y,
    // sumandolo tambien, todos los totales de columna salian al doble.
    const totalesColumna = filas.length > 0
        ? columnasMes.map((cm, columna) =>
            filas.reduce((acc, fila) => acc + fila[3 + columnasAnio.length + columna], 0))
        : columnasMes.map(() => 0);
    const totalesMes = {};
    columnasMes.forEach((cm, columna) => { totalesMes[cm.clave] = totalesColumna[columna]; });

    // Las columnas de MES que se muestran (`columnasMesVisibles`) y las que se
    // OCULTAN (`mesesOcultos`). Es UNA sola lista y UNA sola regla, y la usan la
    // pantalla y el .xlsx: hasta el 05/10/2026 la regla estaba escrita dos veces y no
    // daba lo mismo (el .xlsx ocultaba las columnas de total cero y la pantalla las
    // dibujaba igual, con `0,00`).
    // Con "Anios: Todos" las columnas son el producto `anios x meses` (los meses de
    // CUALQUIER anio), asi que un mes con datos en 2026 deja su columna VACIA en 2025:
    // esas son las columnas en cero que el usuario veia de mas (punto 3 de la revision
    // en pantalla). `posicion` es el indice dentro de `columnasMes`, que es de donde
    // sale la celda de la fila del pivote (`3 + columnasAnio.length + posicion`).
    const columnasMesVisibles = columnasMes
        .map((cm, posicion) => ({ anio: cm.anio, mes: cm.mes, clave: cm.clave,
                                  etiqueta: cm.etiqueta, posicion: posicion }))
        .filter(cv => totalesMes[cv.clave] !== 0);
    const mesesOcultos = columnasMes.filter(cm => totalesMes[cm.clave] === 0)
        .map(cm => cm.etiqueta);

    if (filas.length > 0) {
        // La fila TOTAL GENERAL lleva, en la celda de cada anio, el total de TODO
        // el informe en ese anio. Con UN anio NO lleva celda de anio: `totalesPorAnio`
        // queda con un elemento (nunca se llena, porque `valoresAnio` es `[]`), y si
        // se esparciera igual la fila tendria una celda de mas que las de datos y los
        // totales de mes saldrian corridos una columna (y se perderia el ultimo).
        filas.push(['TOTAL GENERAL', '', '',
                    ...(variosAnios ? totalesPorAnio : []), ...totalesColumna, totalGeneral]);
        clienteDeFila.push('TOTAL GENERAL');
    }

    // `columnas` es el encabezado tal como se ve: las TRES de texto (Cliente,
    // Contrato, Concepto: el orden que pidio el usuario el 05/10/2026, igual en la
    // pantalla y en el .xlsx), la celda de cada anio DELANTE de los meses de ese anio
    // (en la PANTALLA: la celda del anio es el boton que abre los meses) y el Total
    // SIEMPRE AL FINAL de las columnas de valor. Con UN solo anio no hay celda de
    // anio: los meses de corrido y el Total, tambien al final (decision del usuario
    // del 05/10/2026: "al final de todo"). Esto es la PRESENTACION: la celda del
    // Total en `filas` sigue siendo la ULTIMA de la fila y `indiceTotal` dice en que
    // columna cayo. OJO: este `columnas` NO es el del .xlsx (ese lo arma
    // `columnasHojaMoneda`, con el anio DESPUES de sus meses y el `Total general` al
    // final).
    const columnas = ['Cliente', 'Contrato', 'Concepto'];
    if (variosAnios) columnas.push('Total');
    anios.forEach(anio => {
        if (variosAnios) columnas.push(String(anio));
        columnasMes.forEach(cm => {
            if (cm.anio === anio) columnas.push(cm.etiqueta);
        });
    });
    if (!variosAnios) columnas.push('Total');

    return {
        columnas: columnas,
        filas: filas,
        filasCliente: filasCliente,
        clienteDeFila: clienteDeFila,
        columnasAnio: columnasAnio,
        columnasMes: columnasMes,
        columnasMesVisibles: columnasMesVisibles,
        mesesOcultos: mesesOcultos,
        // El ANO ACTIVO: el que el usuario tiene elegido en pantalla (`filtroAnio`)
        // o, si no hay ninguno (o esta vacio), el primero con datos. Es el unico
        // que sale ABIERTO en el .xlsx; los demas van con sus meses plegados.
        anioActivo: (filtroAnio ? parseInt(filtroAnio, 10) : null)
            || (anios.length > 0 ? anios[0] : null),
        anios: anios,
        totalesMes: totalesMes,
        // La columna `Total` es la ULTIMA de la fila: su indice es el del final.
        indiceTotal: columnas.length - 1,
        filaTotal: filas.length - 1,
        registros: datosFiltrados.length
    };
}

// Los anchos y el formato de los importes del .xlsx: los de la pantalla (los
// min-width de las tres primeras columnas, los meses y el Total; el anio, que
// solo existe con mas de un anio, lleva el total de ese anio y por eso NO es la
// columna angosta del rotulo: mide lo mismo que el Total). El formato es el de la
// pantalla (separador de miles y dos decimales): `#,##0.00`.
const ANCHO_COLUMNA_CONTRATO = 16;
const ANCHO_COLUMNA_CLIENTE = 20;
const ANCHO_COLUMNA_CONCEPTO = 20;
const ANCHO_COLUMNA_MES = 11;
const ANCHO_COLUMNA_TOTAL = 12;

// Las COLUMNAS que van al .xlsx y la posicion de cada valor de una fila del
// pivote dentro de ellas. El orden es el que pidio el usuario en la SEGUNDA
// revision del .xlsx (05/10/2026, mirando el archivo exportado):
//   1. las TRES de texto, con `Cliente` ANTES de `Contrato` ("en el excel cliente
//      debe ser columna A y contrato columna B", igual que la pantalla);
//   2. los meses de cada anio y, a su DERECHA, la columna de ese anio
//      (`Total 2026`), que suma esos meses ("quiero la columna [del anio] al final
//      del ultimo mes de cada anio"): es la columna RESUMEN del grupo (la unica que
//      se ve con el grupo colapsado) y por eso el `+/-` queda ahi
//      (`resumen_columnas: 'derecha'`). Los meses del anio que NO es el activo van
//      AGRUPADOS y plegados;
//   3. la ULTIMA columna del libro: `Total general`, que suma las columnas de anio
//      ("la columna total al lado de concepto no va ... deberia ir al final").
//   `indices[i]` = que celda de la fila del pivote va en esa columna; -1 = vacia.
//   El pivote trae, por fila: 3 textos + las celdas de anio + los meses + Total,
//   asi que la celda de anio `k` es la `3 + k` y el mes `m` la
//   `3 + pivote.columnasAnio.length + m`.
// Brief 05/10/2026 (primera revision, el usuario mirando el .xlsx exportado):
//   - "dos solapas DL y PS asi se baja todo junto": UN archivo con UNA hoja por
//     moneda (antes bajaba solo la moneda que estaba en pantalla);
//   - "los meses que el total da cero que no los muestre": esos meses NO se escriben
//     como columna (el layout se arma con `columnasMesVisibles`), y la lista de sus
//     rotulos viaja igual al motor en `meses_visibles` (que oculta la columna si el
//     rotulo esta: el motor es generico). El total del anio sale de la celda del
//     pivote, que SI incluye esos meses (valen cero);
//   - "el excel el ultimo año no esta agrupado": los anos que NO son el activo
//     llevan sus meses AGRUPADOS y plegados, con el `+/-` del ano;
//   - "la columna año sume toda la fila y el total general sume con formula
//     cada columna": la columna del ano, el `Total general` y el pie llevan
//     FORMULA (con el valor, que es lo que se ve si el archivo se abre sin Excel).
// El molde es su libro `RD - Pendiente de Facturar.xlsx` (hojas `Pend Facturar
// DL` / `PS`, medidas con el dumper el 05/10/2026): panel congelado en C6,
// numeros SIN decimales (`#,##0`) y sin autofiltro. Se cambio el formato de
// `#,##0.00` al de la referencia, y con el la constante que lo usaba.
const FORMATO_IMPORTE_PENDIENTES = '#,##0';

// El ancho de la ULTIMA columna (el `Total general`) y el de la columna de cada
// anio (`Total 2026`).
const ANCHO_COLUMNA_TOTAL_CONTRATO = 14;

function letraColumna(indice) {
    // 0-based -> A, B, ... Z, AA...
    let letra = '';
    let numero = indice + 1;
    while (numero > 0) {
        const resto = (numero - 1) % 26;
        letra = String.fromCharCode(65 + resto) + letra;
        numero = Math.floor((numero - 1) / 26);
    }
    return letra;
}

// El rotulo de la columna de un anio (`Total <anio>`) y su lectura: la usan las
// FORMULAS (la columna del anio suma los meses que tiene a la IZQUIERDA; el `Total
// general` suma las celdas de anio de su fila).
function rotuloColumnaAnio(anio) {
    return 'Total ' + anio;
}

function anioDeColumna(etiqueta) {
    const coincidencia = /^Total (\d{4})$/.exec(etiqueta);
    return coincidencia ? parseInt(coincidencia[1], 10) : null;
}

// Los encabezados de la fila 1 y el FORMATO de numero de cada columna: la lista
// de columnas que ve el usuario y las HERRAMIENTAS (formulas, anchos, indices)
// que necesita `armarHojaMoneda`. Sale del mismo pivote que la pantalla.
function columnasHojaMoneda(pivote, columnasVisibles) {
    const columnas = ['Cliente', 'Contrato', 'Concepto'];
    const formatos = ['', '', ''];
    const anchos = [ANCHO_COLUMNA_CLIENTE, ANCHO_COLUMNA_CONTRATO, ANCHO_COLUMNA_CONCEPTO];
    const indices = [0, 1, 2];
    const grupos = [];

    // La columna de UN anio: sus meses VISIBLES y, a la derecha, la del anio (que
    // los suma). `indiceAnio` es la posicion del anio dentro de `pivote.anios`, de
    // donde sale la celda de la fila del pivote (`3 + indiceAnio`). Devuelve `false`
    // si ese anio no tiene ningun mes visible: todas sus columnas dan cero, asi que
    // no se escribe nada (es la misma regla que oculta los meses en cero).
    const agregarAnio = (anio, indiceAnio, activo) => {
        const meses = columnasVisibles.filter(cv => cv.anio === anio);
        if (meses.length === 0) return false;
        const desde = columnas.length;
        meses.forEach(cv => {
            // Los meses del anio ACTIVO van con el numero pelado (es el rotulo del
            // libro de referencia del usuario); los de los otros anios, con el mes y
            // el anio, porque si no DOS anios tendrian columnas con el MISMO rotulo y
            // Excel REPARA el archivo al abrirlo (la tabla nativa exige rotulos
            // unicos: ver `_nombres_de_columnas_de_tabla` en `routes.py`).
            columnas.push(activo ? String(pivote.columnasMes[cv.posicion].mes)
                                 : pivote.columnasMes[cv.posicion].etiqueta);
            formatos.push(FORMATO_IMPORTE_PENDIENTES);
            anchos.push(ANCHO_COLUMNA_MES);
            indices.push(3 + pivote.columnasAnio.length + cv.posicion);
        });
        // El grupo cubre SOLO los meses: la columna del anio queda afuera (es la del
        // `+/-` y la que se lee con el grupo cerrado).
        if (!activo) {
            grupos.push({ desde: desde, hasta: columnas.length - 1, colapsado: true });
        }
        columnas.push(rotuloColumnaAnio(anio));
        formatos.push(FORMATO_IMPORTE_PENDIENTES);
        anchos.push(ANCHO_COLUMNA_TOTAL);
        // La columna del AÑO lleva la celda del total de ese año en el pivote (el
        // indice `3 + k`), NO la del primer mes: con `delActivo[0].posicion` (que es
        // siempre 0 dentro del array filtrado) el año y su primer mes leian la
        // MISMA celda y la fila salia corrida (medido: `1234.5` repetido en el mes
        // 2025-02). El arreglo lo cazo el probe 311 con el volcado de indices.
        indices.push(3 + indiceAnio);
        return true;
    };

    // El AÑO ACTIVO primero (es el unico que arranca ABIERTO: sus meses no van
    // agrupados) y despues los demas, cada uno con sus meses plegados.
    const aniosDelPivote = pivote.columnasAnio.map(ca => ca.anio);
    agregarAnio(pivote.anioActivo, aniosDelPivote.indexOf(pivote.anioActivo), true);
    pivote.anios.forEach((anio, indiceAnio) => {
        if (anio === pivote.anioActivo) return;
        agregarAnio(anio, indiceAnio, false);
    });

    // La ULTIMA columna del libro: el `Total general` (en las filas de datos, la
    // celda del Total del pivote, que es la ULTIMA de la fila).
    columnas.push('Total general');
    formatos.push(FORMATO_IMPORTE_PENDIENTES);
    anchos.push(ANCHO_COLUMNA_TOTAL_CONTRATO);
    indices.push(pivote.indiceTotal);

    return { columnas, formatos, anchos, indices, grupos };
}

// La hoja de UN SOLO anio: sin columna de anio y sin grupos (sale como la
// pantalla, que es el comportamiento de siempre en ese caso). Las columnas son las
// 3 de texto (`Cliente` primero, como en la pantalla y en el .xlsx multi-anio) +
// los meses VISIBLES de ese ano + el `Total general`, AL FINAL (decision del
// usuario del 05/10/2026).
function columnasHojaMonedaUnAnio(pivote, columnasVisibles) {
    const columnas = ['Cliente', 'Contrato', 'Concepto'];
    const formatos = ['', '', ''];
    const anchos = [ANCHO_COLUMNA_CLIENTE, ANCHO_COLUMNA_CONTRATO, ANCHO_COLUMNA_CONCEPTO];
    const indices = [0, 1, 2];
    columnasVisibles.forEach(cv => {
        columnas.push(pivote.columnasMes[cv.posicion].etiqueta);
        formatos.push(FORMATO_IMPORTE_PENDIENTES);
        anchos.push(ANCHO_COLUMNA_MES);
        indices.push(3 + cv.posicion);
    });
    // El Total del pivote es la ULTIMA celda de la fila y su columna va AL FINAL,
    // con el rotulo `Total general` (decision del usuario del 05/10/2026).
    columnas.push('Total general');
    formatos.push(FORMATO_IMPORTE_PENDIENTES);
    anchos.push(ANCHO_COLUMNA_TOTAL_CONTRATO);
    indices.push(pivote.indiceTotal);
    return { columnas, formatos, anchos, indices, grupos: [] };
}

// Una hoja del .xlsx para UNA moneda: las filas, los meses que hay que OCULTAR,
// las agrupaciones de columnas (un grupo por ano) y las FORMULAS.
function armarHojaMoneda(pivote, moneda) {
    // Las columnas que se VEN y las que se OCULTAN salen las dos del PIVOTE
    // (`columnasMesVisibles` / `mesesOcultos`): es la MISMA lista que dibuja la
    // pantalla, asi que la pantalla y el .xlsx no se pueden separar. Un mes se oculta
    // cuando su total (la suma de TODA la columna) da cero.
    const columnasVisibles = pivote.columnasMesVisibles
        .map(cv => ({ anio: cv.anio, posicion: cv.posicion }));
    const ocultas = pivote.mesesOcultos;

    const variosAnios = pivote.anios.length > 1;
    const layout = variosAnios
        ? columnasHojaMoneda(pivote, columnasVisibles)
        : columnasHojaMonedaUnAnio(pivote, columnasVisibles);

    // El agrupamiento por CLIENTE en el .xlsx: la fila del cliente queda VISIBLE
    // (es el `summary` del esquema: ahi queda el `+/-`) y los contratos de ese
    // cliente van PLEGADOS debajo (`filas_ocultas`, el mismo mecanismo con el que
    // el pivote de Cobro pliega los comprobantes). El orden de la grilla es
    // Cliente -> Contrato, el que pidio el usuario: la fila del cliente va UNA vez,
    // delante del PRIMER contrato de ese cliente (no una por contrato: el defecto
    // medido en la corrida del 05/10/2026 fue un `9` de filas donde van `8`, con
    // la fila del cliente repetida entre sus propios contratos).
    const celdasDe = (fila) => layout.indices.map(posicion =>
        (posicion < 0 || fila[posicion] === undefined) ? '' : fila[posicion]);
    const filas = [];
    const filasOcultas = [];
    const filasNegrita = [];
    // Las filas de CLIENTE de la GRILLA: son los SUBTOTALES. El pie del .xlsx suma
    // SOLO estas y no el rango entero de la columna, porque las filas de contrato
    // repiten los mismos importes que su cliente ya suma: sumar la columna completa
    // daba el DOBLE (defecto real medido el 05/10/2026: la columna `8` daba 1.915.542
    // donde la pantalla mostraba 957.771, y el `Total general` 81.981.782 donde va
    // 40.990.891).
    const filasClienteGrilla = [];
    // El orden de la grilla es el del pivote, con la fila del CLIENTE intercalada
    // delante del PRIMER contrato de cada cliente: por eso las FORMULAS se arman sobre
    // la GRILLA (con `i`), y no sobre las filas del pivote. Antes se armaban recorriendo
    // el pivote: como la grilla tiene una fila de mas por cliente, a partir de la primera
    // fila de cliente cada fila recibia la formula de la fila siguiente del pivote
    // (defecto real medido el 05/10/2026: la columna `Total` del pie llevaba
    // `=SUM(E2:E7)`, la del AÑO).
    const clienteDe = (indice) => pivote.clienteDeFila[indice];
    pivote.filas.forEach((fila, indice) => {
        if (indice === pivote.filaTotal) {
            filas.push(celdasDe(fila));
            return;
        }
        // La fila del CLIENTE: solo delante del PRIMER contrato de ese cliente.
        const cliente = clienteDe(indice);
        if (indice === 0 || clienteDe(indice - 1) !== cliente) {
            const grupo = pivote.filasCliente.filter(fc => fc.cliente === cliente)[0];
            if (grupo) {
                filasNegrita.push(filas.length);
                filasClienteGrilla.push(filas.length);
                filas.push(celdasDe(grupo.fila));
            }
        }
        filasOcultas.push(filas.length);
        filas.push(celdasDe(fila));
    });
    if (filas.length > 0) {
        // El TOTAL GENERAL va en negrita; las filas de CLIENTE, tambien.
        filasNegrita.push(filas.length - 1);
        filasNegrita.sort((a, b) => a - b);
    }

    // Las formulas se calculan sobre la GRILLA del .xlsx (A1, B2...): la fila 1
    // es el encabezado, asi que la fila de datos `i` es la de Excel `i + 2`.
    //   - la columna del AÑO (`Total 2026`) suma los meses que tiene a la IZQUIERDA
    //     (el grupo de meses esta entre las tres de texto y la columna del anio);
    //   - la ULTIMA columna (`Total general`) suma SOLO las celdas de AÑO de su fila
    //     (decision del usuario del 05/10/2026: "el total al final seria la sumatoria
    //     de todas las columnas de año"): sumar los meses daria el mismo numero pero
    //     contaria dos veces lo que ya esta en las celdas de anio. Con UN solo anio no
    //     hay celdas de anio y el Total suma los meses de esa fila (la unica vez que
    //     la tabla sale por mes);
    //   - el TOTAL GENERAL (la ultima fila) suma, columna por columna, **solo las filas
    //     de CLIENTE** (los subtotales) y SOLO en las columnas de VALOR: los textos
    //     (Cliente, Contrato, Concepto) no llevan formula (el volcado del 05/10/2026
    //     mostraba `=SUM(B2:B4)` sobre `Cliente` y sobre `Concepto`: un numero donde va
    //     un texto).
    const columnaTotalGeneral = layout.columnas.length - 1;
    const columnasDeAnio = layout.columnas
        .map((etiquetaDeColumna, columna) => ({ anio: anioDeColumna(etiquetaDeColumna),
                                                columna: columna }))
        .filter(ca => ca.anio !== null);
    const formulas = filas.map((_fila, i) => layout.columnas.map((etiqueta, c) => {
        const excel = i + 2;
        // El TOTAL GENERAL: cada columna de valor suma las filas de CLIENTE de arriba
        // (los subtotales), una por una: el rango completo contaria dos veces los
        // importes, porque cada contrato ya esta sumado en la fila de su cliente.
        if (i === filas.length - 1) {
            if (c < 3 || filasClienteGrilla.length === 0) return null;
            return '=SUM(' + filasClienteGrilla.map(
                indice => letraColumna(c) + (indice + 2)).join(',') + ')';
        }
        // La columna del año: suma sus meses, que son los que tiene a la IZQUIERDA.
        const anioDeLaColumna = anioDeColumna(etiqueta);
        if (anioDeLaColumna !== null) {
            const meses = columnasVisibles.filter(cv => cv.anio === anioDeLaColumna);
            if (meses.length > 0) {
                return '=SUM(' + letraColumna(c - meses.length) + excel + ':'
                    + letraColumna(c - 1) + excel + ')';
            }
        }
        if (c === columnaTotalGeneral) {
            // Las celdas de AÑO de ESTA fila: las columnas de la grilla cuyo rotulo es
            // `Total <anio>`. Como los meses de cada anio estan en el medio, se
            // referencian una por una: no hay un rango que las junte sin agarrar
            // tambien los meses.
            if (columnasDeAnio.length > 0) {
                const celdasDeAnio = columnasDeAnio.map(
                    ca => letraColumna(ca.columna) + excel);
                return celdasDeAnio.length ? '=SUM(' + celdasDeAnio.join(',') + ')' : null;
            }
            // Un solo anio: no hay celdas de anio y el Total suma los meses, que son
            // los que van ANTES del `Total general` (hasta la columna anterior; llegar
            // a la ultima columna de la grilla incluia la celda del propio Total:
            // referencia circular).
            if (columnasVisibles.length === 0) return null;
            return '=SUM(' + letraColumna(3) + excel + ':'
                + letraColumna(columnaTotalGeneral - 1) + excel + ')';
        }
        return null;
    }));

    return {
        hoja: moneda,
        // Sin `sin_cuadricula`: este informe sigue con lineas de cuadricula, como hoy.
        columnas: layout.columnas,
        filas: filas,
        formatos: layout.formatos,
        anchos: layout.anchos,
        // Las filas de CLIENTE y el TOTAL GENERAL van en negrita; los contratos de
        // cada cliente, plegados debajo de su fila (Punto 5 del 05/10/2026).
        filas_negrita: filasNegrita,
        filas_ocultas: filasOcultas,
        formulas: formulas,
        meses_visibles: ocultas,
        agrupaciones_columnas: layout.grupos,
        // El `+/-` de cada grupo queda en la columna de la DERECHA del grupo: es la
        // del anio (`Total 2026`), que va DESPUES de sus meses (decision del usuario
        // del 05/10/2026). El motor lo escribe con `summaryRight = True`.
        resumen_columnas: 'derecha',
        congelar_encabezado: true,
        // Brief 05/10/2026: "todo tiene que tener formato tabla" (el estilo azul
        // del catalogo de Excel). El motor lo aplica a cada hoja del libro.
        tabla: true
    };
}

function renderizarTablaDinamica(datos, moneda) {
    const container = document.getElementById('tabla-dinamica');
    if (!container) {
        console.error('❌ No se encontró #tabla-dinamica');
        return;
    }
    if (!datos || datos.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding:40px; color:#94a3b8;">No hay datos disponibles</div>';
        return;
    }

    // El pivote lo arma `construirPivoteContratos` (UNA sola fuente: la usa
    // tambien `exportarExcel`). Aca solo se dibuja.
    const pivote = construirPivoteContratos(datos, moneda);

    if (pivote.registros === 0) {
        const nombreMoneda = moneda === 'PS' ? 'PESOS' : 'DÓLARES';
        let mensaje = `No hay datos para ${escapeHTML(nombreMoneda)}`;
        if (filtroAnio) mensaje += ` en ${escapeHTML(filtroAnio)}`;
        if (filtroMes) mensaje += ` - mes ${escapeHTML(filtroMes)}`;
        container.innerHTML = `<div style="text-align:center; padding:40px; color:#94a3b8;">${escapeHTML(mensaje)}</div>`;
        return;
    }

    if (pivote.filas.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding:40px; color:#94a3b8;">No hay datos para mostrar</div>';
        return;
    }

    // Con MAS DE UN anio la tabla lleva la celda del anio (con su total) delante
    // de los meses de ese anio; los meses de un anio CERRADO no se dibujan (con el
    // grupo cerrado se lee la celda del anio). Con UN anio no hay columna de anio ni
    // encabezado de dos niveles (el brief: esa tabla sale por mes, como hoy); abajo se
    // arma la lista local para que el dibujo sea UN solo camino.
    const columnasAnio = pivote.columnasAnio;
    const variosAnios = columnasAnio.length > 0;
    // `columnasDibujadas` = lo que se DIBUJA: con un anio, una sola entrada con
    // `visible: false` (esa tabla no lleva celda de anio: sale por mes, como hoy).
    const columnasDibujadas = variosAnios
        ? columnasAnio.map(ca => ({ anio: ca.anio, etiqueta: ca.etiqueta, visible: true }))
        : pivote.anios.map(anio => ({ anio: anio, etiqueta: String(anio), visible: false }));

    // La tabla va PELADA adentro de `#tabla-dinamica`: el contenedor con scroll es
    // `.tabla-container` (su `overflow: auto` + `max-height`, en `reportes.css`), que
    // es el que deja el encabezado fijo y la barra horizontal AL PIE DE LA CAJA.
    // Puntos 2 y 4 de la revision en pantalla (05/10/2026): con un `div` con
    // `overflow-x:auto` en el medio, ESE div pasaba a ser el contenedor de scroll; el
    // encabezado `sticky` quedaba pegado a el (y como su alto es el de la tabla, no
    // scrollea hacia abajo: el encabezado se iba con el scroll de la pagina) y la
    // barra horizontal viajaba al final de todas las filas.
    let html = `
            <table class="table table-striped" style="font-size:12px; border-collapse:collapse; width:100%;">
                <thead style="background:#f1f5f9;">
    `;
    html += `
                    <tr>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:140px; text-align:left; background:#f8fafc;">Cliente</th>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:110px; text-align:left; background:#f8fafc;">Contrato</th>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:140px; text-align:left; background:#f8fafc;">Concepto</th>
    `;
    // Las TRES primeras columnas son `Cliente | Contrato | Concepto` (el orden que
    // pidio el usuario el 05/10/2026: el nombre del cliente en la columna A, el
    // contrato en la B), igual que el `.xlsx` (`columnasHojaMoneda`).
    // UNA SOLA FILA de encabezado: la celda del anio (clickeable, con su triangulo) y,
    // a continuacion, los meses de ESE anio SOLO si el anio esta abierto.
    // Antes habia una fila de grupos arriba con `colspan = 1 + meses` mientras los
    // meses se ocultaban con `display:none`: el navegador sacaba esas celdas del
    // layout, la celda del anio se comia las columnas de al lado y el anio salia
    // repetido (una vez en la fila de grupos y otra en la de meses). Medido con la
    // captura del usuario del 24/09/2026.
    columnasDibujadas.forEach(cd => {
        const abierto = variosAnios && aniosAbiertosContratos.has(String(cd.anio));
        const mostrarMeses = !variosAnios || abierto;
        // La celda del anio NO se oculta nunca: es la que se lee con el anio cerrado
        // (el triangulo y su total). Con un solo anio no se dibuja (`visible:false`).
        if (cd.visible) {
            const triangulo = `<span style="display:inline-block; width:14px;">${abierto ? '▾' : '▸'}</span>`;
            html += `<th data-anio="${cd.anio}" data-onclick="toggleAnioContratos(${cd.anio})" title="Clic para ver los meses de ${escapeHTML(cd.etiqueta)}" style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; min-width:80px; background:#e2e8f0; font-weight:700; cursor:pointer;">${triangulo}${escapeHTML(cd.etiqueta)}</th>`;
        }
        if (!mostrarMeses) return;
        // Solo los meses con total distinto de cero (`columnasMesVisibles`: la MISMA
        // lista que exporta el .xlsx). Con "Anios: Todos" las columnas del pivote son
        // el producto `anios x meses`, asi que un mes con datos en 2026 deja su
        // columna vacia en 2025: esas columnas en `0,00` son el punto 3 de la revision
        // en pantalla (el .xlsx ya las ocultaba y la pantalla las dibujaba igual).
        pivote.columnasMesVisibles.forEach(cv => {
            if (cv.anio !== cd.anio) return;
            html += `<th data-mes="${cv.clave}" style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; min-width:75px; background:#f8fafc;">${escapeHTML(cv.etiqueta)}</th>`;
        });
    });
    html += `<th style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; min-width:80px; background:#fef3c7;">Total</th>`;
    html += `</tr></thead><tbody>`;

    // Referencias al pivote (Punto 5 del 05/10/2026). En el pivote una fila es
    // `[3 textos] + [una celda por anio] + [una por mes] + [Total AL FINAL]`:
    //   `indiceTotal` es la ULTIMA celda (la columna Total);
    //   `3 + indiceAnio` es la celda del anio `indiceAnio`;
    //   `3 + columnasAnio.length + posicion` es el mes `posicion`.
    const celdaDeAnio = (fila, indiceAnio) => formatearNumero(fila[3 + indiceAnio]);
    const celdaDeMes = (fila, posicion) =>
        formatearNumero(fila[3 + columnasAnio.length + posicion]);
    const celdaTotal = (fila) => formatearNumero(fila[pivote.indiceTotal]);
    const filaTotal = pivote.filas[pivote.filaTotal];

    // El agrupamiento de FILAS: la fila del CLIENTE (el `summary`, con su nombre y su
    // total) y, debajo, los CONTRATOS de ese cliente, plegados. Las columnas son
    // `Cliente | Contrato | Concepto`: el nombre va en la PRIMERA (con el triangulo del
    // toggle) y deja las otras dos vacias, y no se repite en las filas de contrato
    // (revision del usuario, 05/10/2026).
    pivote.filasCliente.forEach((grupo, indiceCliente) => {
        const abierto = clientesAbiertosContratos.has(indiceCliente);
        const triangulo = `<span style="display:inline-block; width:14px;">${abierto ? '▾' : '▸'}</span>`;
        html += `<tr style="font-weight:bold; background:#eef2ff;">`;
        html += `<td data-cliente="${escapeHTML(grupo.cliente)}" data-abierto="${abierto ? 'si' : 'no'}" data-onclick="toggleClienteContratos(${indiceCliente})" title="Clic para ver los contratos de ${escapeHTML(grupo.cliente)}" style="padding:6px 8px; border:1px solid #e2e8f0; cursor:pointer;">${triangulo}${escapeHTML(grupo.cliente)}</td>`;
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;"></td>`;
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;"></td>`;
        columnasDibujadas.forEach((cd, indiceAnio) => {
            const mostrarMeses = !variosAnios || (variosAnios && aniosAbiertosContratos.has(String(cd.anio)));
            if (cd.visible) {
                html += `<td data-anio="${cd.anio}" style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-weight:bold; background:#e8ecfb;">${celdaDeAnio(grupo.fila, indiceAnio)}</td>`;
            }
            if (!mostrarMeses) return;
            pivote.columnasMesVisibles.forEach(cv => {
                if (cv.anio !== cd.anio) return;
                html += `<td data-mes="${cv.clave}" style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-weight:bold; background:#eef2ff; font-variant-numeric:tabular-nums;">${celdaDeMes(grupo.fila, cv.posicion)}</td>`;
            });
        });
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-weight:bold; background:#fde68a;">${celdaTotal(grupo.fila)}</td>`;
        html += `</tr>`;
        // Los CONTRATOS del cliente: solo cuando el grupo esta abierto.
        if (!abierto) return;
        pivote.filas.forEach((fila, indice) => {
            if (indice === pivote.filaTotal) return;
            if (pivote.clienteDeFila[indice] !== grupo.cliente) return;
            html += `<tr data-contrato="${escapeHTML(fila[1])}">`;
            // El nombre del cliente NO se repite: la fila del grupo ya lo dice en la
            // columna `Cliente` (revision del usuario, 05/10/2026).
            html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;"></td>`;
            html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;">${escapeHTML(fila[1])}</td>`;
            html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;">${escapeHTML(fila[2])}</td>`;
            // La celda del anio lleva el total de ESE anio y va delante de sus meses.
            // Los meses se dibujan SOLO si el anio esta abierto (no se ocultan con
            // `display:none`: eso desalineaba la tabla) y SOLO los que dan distinto de
            // cero. Cada celda lleva su dato (`data-anio` / `data-mes`) para que los
            // probes la lean por dato y no por POSICION (que cambia segun que anios
            // esten abiertos).
            columnasDibujadas.forEach((cd, indiceAnio) => {
                const mostrarMeses = !variosAnios || (variosAnios && aniosAbiertosContratos.has(String(cd.anio)));
                if (cd.visible) {
                    html += `<td data-anio="${cd.anio}" style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-weight:bold; background:#f1f5f9;">${celdaDeAnio(fila, indiceAnio)}</td>`;
                }
                if (!mostrarMeses) return;
                pivote.columnasMesVisibles.forEach(cv => {
                    if (cv.anio !== cd.anio) return;
                    html += `<td data-mes="${cv.clave}" style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-variant-numeric:tabular-nums;">${celdaDeMes(fila, cv.posicion)}</td>`;
                });
            });
            html += `<td style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-weight:bold; background:#fef3c7;">${celdaTotal(fila)}</td>`;
            html += `</tr>`;
        });
    });

    html += `<tfoot style="background:#f1f5f9;">`;
    html += `<tr style="font-weight:bold; background:#f0f4ff;">`;
    html += `<td colspan="3" style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; background:#e8f0fe;">TOTAL GENERAL</td>`;
    columnasDibujadas.forEach((cd, indiceAnio) => {
        const abierto = variosAnios && aniosAbiertosContratos.has(String(cd.anio));
        const mostrarMeses = !variosAnios || abierto;
        if (cd.visible) {
            html += `<td data-anio="${cd.anio}" style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; font-weight:bold; background:#e8f0fe;">${celdaDeAnio(filaTotal, indiceAnio)}</td>`;
        }
        if (!mostrarMeses) return;
        pivote.columnasMesVisibles.forEach(cv => {
            if (cv.anio !== cd.anio) return;
            html += `<td data-mes="${cv.clave}" style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; background:#e8f0fe;">${celdaDeMes(filaTotal, cv.posicion)}</td>`;
        });
    });
    html += `<td style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:15px; background:#fef3c7; color:#92400e;">${celdaTotal(filaTotal)}</td>`;
    html += `</tr></tfoot>`;
    html += `</tbody></table>`;

    container.innerHTML = html;
}

function mostrarLoading(activo) {
    const loading = document.getElementById('loading-reporte');
    if (loading) loading.style.display = activo ? 'block' : 'none';
}

// Abre/cierra los meses de UN anio de la tabla y la vuelve a pintar. Es el
// patron de `toggleGrupoGlobal` (`consolidado_total.js`): estado de modulo +
// re-render del contenedor, asi el HTML no se parchea a mano. El `data-onclick`
// del encabezado y los probes la llaman por su nombre, y `index.js` la expone en
// `window` como el resto de las funciones del informe.
function toggleAnioContratos(anio) {
    const clave = String(anio);
    if (aniosAbiertosContratos.has(clave)) {
        aniosAbiertosContratos.delete(clave);
    } else {
        aniosAbiertosContratos.add(clave);
    }
    renderizarTablaDinamica(datosReporte, monedaActual);
}

export { toggleAnioContratos };

// Abre/cierra los CONTRATOS de UN cliente de la tabla y la vuelve a pintar. Mismo
// patron que `toggleAnioContratos` (estado de modulo + re-render), pero en las
// FILAS: la clave es el INDICE del cliente dentro del pivote (`pivote.filasCliente`),
// no su nombre, porque el nombre puede traer comillas y el `data-onclick` viaja
// dentro del HTML. El `data-onclick` de la fila y los probes la llaman por su
// nombre, y `index.js` la expone en `window` como el resto.
function toggleClienteContratos(indiceCliente) {
    if (clientesAbiertosContratos.has(indiceCliente)) {
        clientesAbiertosContratos.delete(indiceCliente);
    } else {
        clientesAbiertosContratos.add(indiceCliente);
    }
    renderizarTablaDinamica(datosReporte, monedaActual);
}

export { toggleClienteContratos };

// ============================================================
// EXPORTAR A EXCEL (.xlsx vía backend)
// ============================================================
// Brief 24/09/2026 ("columnas por anio"): el .xlsx baja el MISMO pivote de la
// pantalla con los meses de cada anio agrupados con el agrupamiento nativo de
// Excel (colapsado; el anio se lee en su columna angosta) y la fila TOTAL
// GENERAL. Punto 5 y SEGUNDA revision del 05/10/2026: las filas van agrupadas por
// CLIENTE (con los contratos PLEGADOS debajo), las columnas son `Cliente | Contrato |
// Concepto`, los meses de cada anio con la columna de ESE anio (`Total 2026`) a la
// DERECHA, y la ULTIMA columna del libro es el `Total general`; el anio, el Total
// general y el pie llevan FORMULA. La lista plana de siempre
// (CONTRATO/CLIENTE/.../IMPORTE) no se exporta. Con UN solo anio no hay columna
// de anio ni grupos de columnas (sale por mes).

export function exportarExcel() {
    const armado = armarExcelContratos();
    if (!armado) return;

    if (typeof window.descargarXlsx === 'function') {
        // UN archivo con UNA hoja por moneda (brief 05/10/2026): el cuerpo va con
        // `hojas: [...]` y el motor arma las dos solapas de una.
        window.descargarXlsx(armado.archivo, armado.hoja, [], [],
                             { hojas: armado.hojas });
    } else {
        if (typeof toastError === 'function') toastError('Exportación no disponible', 'Reportes');
        return;
    }
    if (typeof toastSuccess === 'function') toastSuccess('✅ Reporte exportado', 'Reportes');
}

// El ARMADO del Excel de Pendiente de Facturar, en UNA sola funcion: lo usan la
// descarga (`exportarExcel`) y el envio por correo (`enviarContratosPorCorreo`).
// Si cada accion armara su tabla, el adjunto del correo y el archivo que baja la
// descarga se separarian con el primer cambio (mismo contrato que Ventas
// Globales). Devuelve `{archivo, columnas, filas, opciones}` o `null` si no hay
// nada que exportar (y avisa por toast).
function armarExcelContratos() {
    if (datosReporte.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para exportar', 'Reportes');
        return null;
    }

    // El corte de "no hay datos" se hace con la moneda que el usuario tiene en
    // PANTALLA: es lo que esta mirando cuando aprieta el boton.
    const pivotePantalla = construirPivoteContratos(datosReporte, monedaActual);
    if (pivotePantalla.registros === 0) {
        if (typeof toastWarning === 'function') toastWarning(`⚠️ No hay datos para exportar con los filtros actuales`, 'Reportes');
        return null;
    }

    // UNA HOJA POR MONEDA, con las monedas que traen los datos (no una lista
    // fija): asi una base con otras siglas no deja filas afuera.
    const hojas = [];
    monedasDeLosDatos().forEach(moneda => {
        const pivote = construirPivoteContratos(datosReporte, moneda);
        if (pivote.registros === 0) return;
        hojas.push(armarHojaMoneda(pivote, moneda));
    });
    if (hojas.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para exportar con los filtros actuales', 'Reportes');
        return null;
    }

    // Brief 05/10/2026: "RD - Pendiente de facturar al 04-10-2026" (las siglas del
    // pais de la base activa), el MISMO nombre para el archivo exportado y para el
    // adjunto y el asunto del correo. La fecha es la LOCAL (helper de `app.js`),
    // nunca `toISOString()`, y el nombre NO lleva la moneda: el archivo trae las
    // dos hojas.
    const archivo = window.nombreInformeConSiglas('Pendiente de facturar',
                                                  window.fechaHoyConGuiones()) + '.xlsx';
    return { archivo: archivo, hoja: hojas[0].hoja, hojas: hojas };
}

// Las monedas que aparecen en los datos, en el orden en que se exportan las hojas.
function monedasDeLosDatos() {
    const vistas = [];
    datosReporte.forEach(fila => {
        const moneda = fila.MONEDA;
        if (moneda && vistas.indexOf(moneda) < 0) vistas.push(moneda);
    });
    return vistas;
}

// ============================================================
// ENVIAR POR CORREO (Outlook de esta PC; el adjunto es el MISMO .xlsx)
// ============================================================
// El dialogo del correo, el armado del adjunto y el envio viven en `app.js`
// (`window.pedirCorreoYEnviar`): aca solo se le pasa SU tabla, la misma que baja
// la descarga (`armarExcelContratos`), y el prefijo del asunto del informe.
// Brief 05/10/2026: "RD - Pendiente de facturar al 04/10/2026" (las siglas del
// pais de la base activa), el MISMO nombre para el asunto y para el archivo.
//
// OJO (defecto real medido el 05/10/2026): el prefijo se armaba al CARGAR el modulo
// (`window.ASUNTO_PENDIENTES_FACTURAR = ...`), y en ese momento `window.baseActiva`
// todavia es `null` (la setea `app.js` al inicializar), asi que se quedaba con las
// siglas de la base POR DEFECTO: con la base PE activa el asunto del correo decia
// "RD - ...". Ahora se arma ADENTRO de la funcion, en el momento de mandar.
function enviarContratosPorCorreo() {
    const armado = armarExcelContratos();
    if (!armado) return;
    if (typeof window.pedirCorreoYEnviar !== 'function') {
        if (typeof toastError === 'function') toastError('El envío por correo no está disponible', 'Reportes');
        return;
    }
    // El asunto por defecto se arma ADENTRO del dialogo, con la fecha del dia.
    const asunto = window.prefijoInformeConSiglas('Pendiente de facturar')
        || 'Pendiente de facturar al ';
    window.pedirCorreoYEnviar(armado.archivo, armado.hoja, [], [],
                              { hojas: armado.hojas }, asunto);
}

export { armarExcelContratos, enviarContratosPorCorreo };

// ============================================================
// EXPONER FUNCIONES QUE USA EL HTML (se exportan en index.js)
// ============================================================

// (Las funciones que necesitan ser globales se asignarán en index.js)