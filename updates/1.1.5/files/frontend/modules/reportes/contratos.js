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
            // brief): los anios abiertos de la corrida anterior no se arrastran.
            aniosAbiertosContratos.clear();
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

    const gruposPS = {};
    datosPS.forEach(row => {
        const key = `${row.ANIO}-${String(row.MES).padStart(2, '0')}`;
        if (!gruposPS[key]) gruposPS[key] = { ANIO: row.ANIO, MES: row.MES, IMPORTE: 0 };
        gruposPS[key].IMPORTE += parseFloat(row.IMPORTE) || 0;
    });
    const gruposDL = {};
    datosDL.forEach(row => {
        const key = `${row.ANIO}-${String(row.MES).padStart(2, '0')}`;
        if (!gruposDL[key]) gruposDL[key] = { ANIO: row.ANIO, MES: row.MES, IMPORTE: 0 };
        gruposDL[key].IMPORTE += parseFloat(row.IMPORTE) || 0;
    });

    const allKeys = new Set([...Object.keys(gruposPS), ...Object.keys(gruposDL)]);
    const resumen = Array.from(allKeys).map(key => {
        const [anio, mes] = key.split('-');
        const ps = gruposPS[key] || { IMPORTE: 0 };
        const dl = gruposDL[key] || { IMPORTE: 0 };
        return { ANIO: parseInt(anio), MES: parseInt(mes), PS_IMPORTE: ps.IMPORTE, DL_IMPORTE: dl.IMPORTE };
    }).sort((a, b) => a.ANIO - b.ANIO || a.MES - b.MES);

    if (resumen.length === 0) {
        container.innerHTML = '<p style="color:#94a3b8;">No hay datos para resumen</p>';
        return;
    }

    const nombresMeses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    let totalPSGeneral = 0, totalDLGeneral = 0;
    let html = `
        <table style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead>
                <tr>
                    <th style="background:#f1f5f9; padding:8px 12px; text-align:left; font-weight:600; border-bottom:2px solid #e2e8f0;">Año</th>
                    <th style="background:#f1f5f9; padding:8px 12px; text-align:left; font-weight:600; border-bottom:2px solid #e2e8f0;">Mes</th>
                    <th style="background:#f1f5f9; padding:8px 12px; text-align:right; font-weight:600; border-bottom:2px solid #e2e8f0; color:#2563eb;">Total PS</th>
                    <th style="background:#f1f5f9; padding:8px 12px; text-align:right; font-weight:600; border-bottom:2px solid #e2e8f0; color:#16a34a;">Total DL</th>
                </tr>
            </thead>
            <tbody>
    `;
    resumen.forEach(row => {
        totalPSGeneral += row.PS_IMPORTE;
        totalDLGeneral += row.DL_IMPORTE;
        const mesNombre = escapeHTML(nombresMeses[row.MES] || row.MES);
        html += `
            <tr>
                <td style="padding:6px 12px; border-bottom:1px solid #f1f5f9;">${row.ANIO}</td>
                <td style="padding:6px 12px; border-bottom:1px solid #f1f5f9;">${mesNombre}</td>
                <td style="padding:6px 12px; border-bottom:1px solid #f1f5f9; text-align:right; color:#2563eb;">$${formatearNumero(row.PS_IMPORTE)}</td>
                <td style="padding:6px 12px; border-bottom:1px solid #f1f5f9; text-align:right; color:#16a34a;">$${formatearNumero(row.DL_IMPORTE)}</td>
            </tr>
        `;
    });
    html += `
        <tfoot>
            <tr style="font-weight:bold; background:#f8fafc;">
                <td colspan="2" style="padding:8px 12px; text-align:right; border-top:2px solid #e2e8f0;">TOTALES</td>
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
// Aplica los filtros de la pantalla (moneda activa + `filtroAnio` + `filtroMes`)
// y devuelve:
//   columnas      los encabezados tal como se ven: Contrato, Cliente, Concepto,
//                 una por mes/anio y Total (la tabla de la pantalla y, con UN
//                 anio, tambien el .xlsx). Con MAS DE UN anio, la pantalla y el
//                 .xlsx intercalan la celda del anio: ver `columnasAnio`.
//   filas         una fila por `CONTRATO|CLIENTE|CENTRO_COSTO` (las tres primeras
//                 celdas son el TEXTO CRUDO, sin escapar: el .xlsx lo escribe tal
//                 cual y la pantalla lo escapa al dibujar) + la fila
//                 `TOTAL GENERAL` al final. Cada fila trae, en este orden: las
//                 tres celdas de texto, la celda de cada anio (el TOTAL de ese
//                 anio), los meses en el orden de `columnasMes` y el Total de la
//                 fila (la suma de TODOS sus meses, de todos los anios).
//                 El ORDEN de las filas se calcula sobre el texto ESCAPADO (el
//                 mismo criterio que HEAD: ver el `sort` mas abajo).
//   columnasAnio  un `{anio, etiqueta}` por anio cuando hay MAS DE UNO (es el
//                 rotulo de la columna del anio); vacio con un solo anio (esa
//                 tabla no lleva columna de anio: sale por mes, como hoy).
//   columnasMes   los meses en orden: `{anio, mes, clave: 'AAAA-MM', etiqueta}`.
//   anios         los anios presentes, ordenados (son los grupos del .xlsx).
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
    // CUALQUIER anio): es la forma que tiene la pantalla de hoy.
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

    const grupos = {};
    datosFiltrados.forEach(row => {
        const contrato = row.CONTRATO || 'Sin Contrato';
        const cliente = row.CLIENTE || 'Sin Cliente';
        const centro = row.CENTRO_COSTO || 'Sin Concepto';
        const key = `${contrato}|${cliente}|${centro}`;
        if (!grupos[key]) {
            grupos[key] = { CONTRATO: contrato, CLIENTE: cliente, CENTRO_COSTO: centro, valores: {} };
        }
        const colKey = `${row.ANIO || 0}-${String(row.MES || 0).padStart(2, '0')}`;
        const importe = parseFloat(row.IMPORTE) || 0;
        grupos[key].valores[colKey] = (grupos[key].valores[colKey] || 0) + importe;
    });

    // El ORDEN de las filas es el de HEAD: se compara el texto YA ESCAPADO (que
    // es lo que el pivote guardaba antes de unificar pantalla y Excel). El pivote
    // sigue GUARDANDO el crudo (el .xlsx lo escribe tal cual y la pantalla lo
    // escapa al dibujar: escapar aca haria salir `&amp;` en el Excel), asi que se
    // escapa SOLO para comparar.
    // Por que: escapar cambia el orden relativo de dos textos que empiezan con
    // `<` y con `>` (`"<Sin cliente>"` vs `">Mayorista del Sur"`: el crudo da -1 y
    // el escapado +1), asi que comparando el crudo las filas salian en OTRO orden
    // que ayer. Medido en la ronda de fix del 24/09/2026: la pantalla vuelve a ser
    // byte a byte la de HEAD en los 48 fixtures del auxiliar 339, y el 341 mide
    // este par de textos.
    const keys = Object.keys(grupos).sort((a, b) => {
        const gA = grupos[a], gB = grupos[b];
        const clienteA = escapeHTML(gA.CLIENTE), clienteB = escapeHTML(gB.CLIENTE);
        if (clienteA !== clienteB) return clienteA.localeCompare(clienteB);
        return escapeHTML(gA.CONTRATO).localeCompare(escapeHTML(gB.CONTRATO));
    });

    // La celda del ANIO lleva el TOTAL de ese anio (la suma de sus meses) y va
    // DELANTE de los meses, una por anio. Con UN solo anio no hay celda de anio:
    // la tabla sale por mes, como hoy. El total del anio sale de las MISMAS
    // celdas de mes que van a la tabla (`valoresMes`): nada de recalcular por
    // otro camino, asi la pantalla y el .xlsx no se pueden separar.
    const variosAnios = anios.length > 1;
    const columnasAnio = variosAnios
        ? anios.map(anio => ({ anio: anio, etiqueta: String(anio) }))
        : [];
    const totalesPorAnio = anios.map(() => 0);

    const filas = [];
    let totalGeneral = 0;
    keys.forEach(key => {
        const grupo = grupos[key];
        const valoresMes = columnasMes.map(cm => grupo.valores[cm.clave] || 0);
        const valoresAnio = variosAnios
            ? anios.map((anio, indiceAnio) => {
                const posiciones = columnasMes
                    .map((cm, posicion) => (cm.anio === anio ? posicion : -1))
                    .filter(posicion => posicion >= 0);
                const totalAnio = posiciones.reduce((suma, posicion) => suma + valoresMes[posicion], 0);
                totalesPorAnio[indiceAnio] += totalAnio;
                return totalAnio;
            })
            : [];
        // El Total de la derecha NO cambia de significado: la suma de todos los
        // meses de la fila, de todos los anios.
        const totalFila = valoresMes.reduce((suma, valor) => suma + valor, 0);
        totalGeneral += totalFila;
        filas.push([grupo.CONTRATO, grupo.CLIENTE, grupo.CENTRO_COSTO,
                    ...valoresAnio, ...valoresMes, totalFila]);
    });

    if (filas.length > 0) {
        const totalesColumna = columnasMes.map((cm, columna) =>
            filas.reduce((acc, fila) => acc + fila[3 + columnasAnio.length + columna], 0));
        // La fila TOTAL GENERAL lleva, en la celda de cada anio, el total de TODO
        // el informe en ese anio. Con UN anio NO lleva celda de anio: `totalesPorAnio`
        // queda con un elemento (nunca se llena, porque `valoresAnio` es `[]`), y si
        // se esparciera igual la fila tendria una celda de mas que las de datos y los
        // totales de mes saldrian corridos una columna (y se perderia el ultimo).
        filas.push(['TOTAL GENERAL', '', '',
                    ...(variosAnios ? totalesPorAnio : []), ...totalesColumna, totalGeneral]);
    }

    // `columnas` es el encabezado tal como se ve: con mas de un anio, la celda de
    // cada anio va DELANTE de los meses de ese anio (el encabezado de dos niveles
    // de la pantalla y, abajo, los meses). Con un anio, los meses de corrido.
    const columnas = ['Contrato', 'Cliente', 'Concepto'];
    anios.forEach(anio => {
        if (variosAnios) columnas.push(String(anio));
        columnasMes.forEach(cm => {
            if (cm.anio === anio) columnas.push(cm.etiqueta);
        });
    });
    columnas.push('Total');

    return {
        columnas: columnas,
        filas: filas,
        columnasAnio: columnasAnio,
        columnasMes: columnasMes,
        anios: anios,
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
const ANCHO_COLUMNA_ANIO = 12;
const FORMATO_IMPORTE_PENDIENTES = '#,##0.00';

// Las COLUMNAS que van al .xlsx y la posicion de cada valor de una fila del
// pivote dentro de ellas. Con MAS DE UN anio, delante de los meses de cada anio
// va la columna del anio (el rotulo en el encabezado y, en las filas de datos, el
// TOTAL de ese anio: es la columna RESUMEN del grupo, `summaryRight=false`, la
// unica que se ve con el grupo colapsado) y los meses de ese anio se agrupan
// (colapsados). Con UN solo anio no hay columna de anio ni grupos: las columnas
// salen como en la pantalla.
//   `indices[i]` = que celda de la fila del pivote va en esa columna; -1 = vacia.
//   El pivote trae, por fila: 3 textos + las celdas de anio + los meses + Total,
//   asi que la celda de anio `k` es la `3 + k` y el mes `m` la
//   `3 + pivote.columnasAnio.length + m`.
function layoutColumnasExcel(pivote) {
    const variosAnios = pivote.anios.length > 1;
    const columnas = ['Contrato', 'Cliente', 'Concepto'];
    const formatos = ['', '', ''];
    const anchos = [ANCHO_COLUMNA_CONTRATO, ANCHO_COLUMNA_CLIENTE, ANCHO_COLUMNA_CONCEPTO];
    const indices = [0, 1, 2];
    const grupos = [];

    pivote.anios.forEach((anio, indiceAnio) => {
        if (variosAnios) {
            columnas.push(String(anio));
            // La celda del anio lleva el total del anio: mismo formato de numero
            // que los meses (no es un rotulo vacio).
            formatos.push(FORMATO_IMPORTE_PENDIENTES);
            anchos.push(ANCHO_COLUMNA_ANIO);
            indices.push(3 + indiceAnio);
        }
        const desde = columnas.length;
        pivote.columnasMes.forEach((cm, posicion) => {
            if (cm.anio !== anio) return;
            columnas.push(cm.etiqueta);
            formatos.push(FORMATO_IMPORTE_PENDIENTES);
            anchos.push(ANCHO_COLUMNA_MES);
            indices.push(3 + pivote.columnasAnio.length + posicion);
        });
        if (variosAnios) {
            // El grupo cubre SOLO los meses: la columna del anio queda afuera (es
            // la del `+/-` y la que se lee con el grupo cerrado).
            grupos.push({ desde: desde, hasta: columnas.length - 1, colapsado: true });
        }
    });

    columnas.push('Total');
    formatos.push(FORMATO_IMPORTE_PENDIENTES);
    anchos.push(ANCHO_COLUMNA_TOTAL);
    indices.push(3 + pivote.columnasAnio.length + pivote.columnasMes.length);

    return { columnas: columnas, formatos: formatos, anchos: anchos, indices: indices, grupos: grupos };
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
    // de los meses de ese anio. Los meses de un anio CERRADO se dibujan con
    // `display:none` (la columna existe, con su dato, y no se ve): asi el
    // encabezado de dos niveles y los probes ven el `colspan` siempre igual.
    // Con UN anio no hay columna de anio ni encabezado de dos niveles (el brief:
    // esa tabla sale por mes, como hoy); abajo se arma la lista local para que el
    // dibujo sea UN solo camino.
    const columnasAnio = pivote.columnasAnio;
    const variosAnios = columnasAnio.length > 0;
    // `columnasDibujadas` = lo que se DIBUJA: con un anio, una sola entrada con
    // `visible: false` (esa tabla no lleva celda de anio: sale por mes, como hoy).
    const columnasDibujadas = variosAnios
        ? columnasAnio.map(ca => ({ anio: ca.anio, etiqueta: ca.etiqueta, visible: true }))
        : pivote.anios.map(anio => ({ anio: anio, etiqueta: String(anio), visible: false }));

    let html = `
        <div style="overflow-x:auto;">
            <table class="table table-striped" style="font-size:12px; border-collapse:collapse; width:100%;">
                <thead style="background:#f1f5f9;">
    `;
    if (variosAnios) {
        html += `
                    <tr>
                        <th colspan="3" style="padding:8px 10px; border:1px solid #e2e8f0; background:#f8fafc;"></th>
        `;
        columnasAnio.forEach(ca => {
            const abierto = aniosAbiertosContratos.has(String(ca.anio));
            const mesesDelAnio = pivote.columnasMes.filter(cm => cm.anio === ca.anio).length;
            const triangulo = `<span style="display:inline-block; width:14px;">${abierto ? '▾' : '▸'}</span>`;
            html += `<th colspan="${1 + mesesDelAnio}" data-anio="${ca.anio}" data-onclick="toggleAnioContratos(${ca.anio})" title="Clic para ver los meses de ${escapeHTML(ca.etiqueta)}" style="padding:6px 10px; border:1px solid #e2e8f0; text-align:center; font-weight:700; background:#e2e8f0; cursor:pointer;">${triangulo}${escapeHTML(ca.etiqueta)}</th>`;
        });
        html += `<th style="padding:6px 10px; border:1px solid #e2e8f0; background:#fef3c7;"></th>`;
        html += `</tr>`;
    }
    html += `
                    <tr>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:110px; text-align:left; background:#f8fafc;">Contrato</th>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:140px; text-align:left; background:#f8fafc;">Cliente</th>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:140px; text-align:left; background:#f8fafc;">Concepto</th>
    `;
    // Los meses se dibujan agrupados por anio y la celda del anio va UNA sola vez,
    // delante de los meses de ese anio (el `colspan` de arriba es 1 + sus meses).
    columnasDibujadas.forEach(cd => {
        // La celda del anio NO se oculta nunca: es la que se lee con el anio
        // cerrado (el `+/-` y su total). Lo que se oculta son sus MESES.
        const oculto = variosAnios && !aniosAbiertosContratos.has(String(cd.anio));
        if (cd.visible) {
            html += `<th style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; min-width:80px; background:#f1f5f9;">${escapeHTML(cd.etiqueta)}</th>`;
        }
        pivote.columnasMes.forEach((cm, posicion) => {
            if (cm.anio !== cd.anio) return;
            html += `<th style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; min-width:75px; background:#f8fafc;${oculto ? ' display:none;' : ''}">${escapeHTML(cm.etiqueta)}</th>`;
        });
    });
    html += `<th style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; min-width:80px; background:#fef3c7;">Total</th>`;
    html += `</tr></thead><tbody>`;

    const filaTotal = pivote.filas[pivote.filaTotal];
    pivote.filas.forEach((fila, indice) => {
        if (indice === pivote.filaTotal) return;   // el TOTAL va en el tfoot
        html += `<tr>`;
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;">${escapeHTML(fila[0])}</td>`;
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;">${escapeHTML(fila[1])}</td>`;
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;">${escapeHTML(fila[2])}</td>`;
        // La celda del anio lleva el total de ESE anio y va delante de sus meses
        // (una sola vez por anio; el texto sale de la misma celda del pivote que
        // baja al .xlsx). Las de los meses de un anio cerrado salen ocultas.
        columnasDibujadas.forEach((cd, indiceAnio) => {
            const oculto = variosAnios && !aniosAbiertosContratos.has(String(cd.anio));
            if (cd.visible) {
                html += `<td style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-weight:bold; background:#f1f5f9;">${formatearNumero(fila[3 + indiceAnio])}</td>`;
            }
            pivote.columnasMes.forEach((cm, posicion) => {
                if (cm.anio !== cd.anio) return;
                html += `<td style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-variant-numeric:tabular-nums;${oculto ? ' display:none;' : ''}">${formatearNumero(fila[3 + columnasAnio.length + posicion])}</td>`;
            });
        });
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-weight:bold; background:#fef3c7;">${formatearNumero(fila[fila.length - 1])}</td>`;
        html += `</tr>`;
    });

    html += `<tfoot style="background:#f1f5f9;">`;
    html += `<tr style="font-weight:bold; background:#f0f4ff;">`;
    html += `<td colspan="3" style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; background:#e8f0fe;">TOTAL GENERAL</td>`;
    columnasDibujadas.forEach((cd, indiceAnio) => {
        const oculto = variosAnios && !aniosAbiertosContratos.has(String(cd.anio));
        if (cd.visible) {
            html += `<td style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; font-weight:bold; background:#e8f0fe;">${formatearNumero(filaTotal[3 + indiceAnio])}</td>`;
        }
        pivote.columnasMes.forEach((cm, posicion) => {
            if (cm.anio !== cd.anio) return;
            html += `<td style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; background:#e8f0fe;${oculto ? ' display:none;' : ''}">${formatearNumero(filaTotal[3 + columnasAnio.length + posicion])}</td>`;
        });
    });
    html += `<td style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:15px; background:#fef3c7; color:#92400e;">${formatearNumero(filaTotal[filaTotal.length - 1])}</td>`;
    html += `</tr></tfoot>`;
    html += `</tbody></table></div>`;

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

// ============================================================
// EXPORTAR A EXCEL (.xlsx vía backend)
// ============================================================
// Brief 24/09/2026 ("columnas por anio"): el .xlsx baja el MISMO pivote de la
// pantalla (una fila por contrato+cliente+concepto, una columna por mes/anio, la
// columna Total y la fila TOTAL GENERAL), con los meses de cada anio agrupados
// con el agrupamiento nativo de Excel (colapsado; el anio se lee en su columna
// angosta). La lista plana de siempre (CONTRATO/CLIENTE/.../IMPORTE) deja de
// exportarse: es lo declarado en el brief. Con UN solo anio no hay columna de
// anio ni grupos (sale como la pantalla).

export function exportarExcel() {
    if (datosReporte.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para exportar', 'Reportes');
        return;
    }

    const pivote = construirPivoteContratos(datosReporte, monedaActual);
    if (pivote.registros === 0) {
        if (typeof toastWarning === 'function') toastWarning(`⚠️ No hay datos para exportar con los filtros actuales`, 'Reportes');
        return;
    }

    const layout = layoutColumnasExcel(pivote);
    // Cada columna del .xlsx lleva la celda del pivote que le toca segun
    // `layout.indices` (incluida la del anio, con el total de ese anio).
    const filas = pivote.filas.map(fila =>
        layout.indices.map(posicion => (posicion < 0 ? '' : fila[posicion])));

    const opciones = {
        formatos: layout.formatos,
        anchos: layout.anchos,
        filas_negrita: [pivote.filaTotal],
        congelar_encabezado: true
    };
    if (layout.grupos.length > 0) {
        opciones.agrupaciones_columnas = layout.grupos;
    }
    // Sin `sin_cuadricula`: este informe sigue con lineas de cuadricula, como hoy.

    // Fecha LOCAL (helper de `app.js`), nunca `toISOString()`: el nombre no puede
    // adelantarse un dia despues de las 21:00 en Argentina.
    const archivo = `reporte_pendientes_${monedaActual}_${filtroAnio || 'todos'}_${window.fechaHoyConGuiones()}.xlsx`;
    if (typeof window.descargarXlsx === 'function') {
        window.descargarXlsx(archivo, 'Pendientes', layout.columnas, filas, opciones);
    } else {
        if (typeof toastError === 'function') toastError('Exportación no disponible', 'Reportes');
        return;
    }
    if (typeof toastSuccess === 'function') toastSuccess('✅ Reporte exportado', 'Reportes');
}

// ============================================================
// EXPONER FUNCIONES QUE USA EL HTML (se exportan en index.js)
// ============================================================

// (Las funciones que necesitan ser globales se asignarán en index.js)