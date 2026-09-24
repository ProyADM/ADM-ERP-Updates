// ============================================================
// REPORTE: CONTRATOS (PENDIENTE DE FACTURAR)
// ============================================================

let datosReporte = [];
let filtroAnio = '';
let filtroMes = '';
let monedaActual = 'PS';

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
//   columnas     los encabezados tal como se ven: Contrato, Cliente, Concepto,
//                una por mes/anio y Total.
//   filas        una fila por `CONTRATO|CLIENTE|CENTRO_COSTO` (las tres primeras
//                celdas son el TEXTO CRUDO, sin escapar: el .xlsx lo escribe tal
//                cual y la pantalla lo escapa al dibujar) + la fila
//                `TOTAL GENERAL` al final. Cada fila trae los meses y el Total.
//                El ORDEN de las filas se calcula sobre el texto ESCAPADO (el
//                mismo criterio que HEAD: ver el `sort` mas abajo).
//   columnasMes  los meses en orden: `{anio, mes, clave: 'AAAA-MM', etiqueta}`.
//   anios        los anios presentes, ordenados (son los grupos del .xlsx).
//   filaTotal    indice 0-based de `TOTAL GENERAL` dentro de `filas`.
//   registros    cuantas filas crudas pasaron los filtros (0 = no hay nada que
//                mostrar para esa moneda/filtros).
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

    const filas = [];
    let totalGeneral = 0;
    keys.forEach(key => {
        const grupo = grupos[key];
        let totalFila = 0;
        const valores = columnasMes.map(cm => {
            const valor = grupo.valores[cm.clave] || 0;
            totalFila += valor;
            return valor;
        });
        totalGeneral += totalFila;
        filas.push([grupo.CONTRATO, grupo.CLIENTE, grupo.CENTRO_COSTO, ...valores, totalFila]);
    });

    if (filas.length > 0) {
        const totalesColumna = columnasMes.map((cm, columna) =>
            filas.reduce((acc, fila) => acc + fila[3 + columna], 0));
        filas.push(['TOTAL GENERAL', '', '', ...totalesColumna, totalGeneral]);
    }

    return {
        columnas: ['Contrato', 'Cliente', 'Concepto', ...columnasMes.map(cm => cm.etiqueta), 'Total'],
        filas: filas,
        columnasMes: columnasMes,
        anios: anios,
        filaTotal: filas.length - 1,
        registros: datosFiltrados.length
    };
}

// Los anchos y el formato de los importes del .xlsx: los de la pantalla (los
// min-width de las tres primeras columnas, los meses y el Total; el anio, que
// solo existe en el archivo, es la columna angosta del rotulo). El formato es el
// de la pantalla (separador de miles y dos decimales): `#,##0.00`.
const ANCHO_COLUMNA_CONTRATO = 16;
const ANCHO_COLUMNA_CLIENTE = 20;
const ANCHO_COLUMNA_CONCEPTO = 20;
const ANCHO_COLUMNA_MES = 11;
const ANCHO_COLUMNA_TOTAL = 12;
const ANCHO_COLUMNA_ANIO = 6;
const FORMATO_IMPORTE_PENDIENTES = '#,##0.00';

// Las COLUMNAS que van al .xlsx y la posicion de cada valor de una fila del
// pivote dentro de ellas. Con MAS DE UN anio, delante de los meses de cada anio
// va una columna angosta con el anio (solo el rotulo del encabezado: en las
// filas de datos queda vacia) y los meses de ese anio se agrupan (colapsados).
// Con UN solo anio no hay columna de anio ni grupos: las columnas salen como en
// la pantalla.
//   `indices[i]` = que celda de la fila del pivote va en esa columna; -1 = vacia.
function layoutColumnasExcel(pivote) {
    const variosAnios = pivote.anios.length > 1;
    const columnas = ['Contrato', 'Cliente', 'Concepto'];
    const formatos = ['', '', ''];
    const anchos = [ANCHO_COLUMNA_CONTRATO, ANCHO_COLUMNA_CLIENTE, ANCHO_COLUMNA_CONCEPTO];
    const indices = [0, 1, 2];
    const grupos = [];

    pivote.anios.forEach(anio => {
        if (variosAnios) {
            columnas.push(String(anio));
            formatos.push('');
            anchos.push(ANCHO_COLUMNA_ANIO);
            indices.push(-1);
        }
        const desde = columnas.length;
        pivote.columnasMes.forEach((cm, posicion) => {
            if (cm.anio !== anio) return;
            columnas.push(cm.etiqueta);
            formatos.push(FORMATO_IMPORTE_PENDIENTES);
            anchos.push(ANCHO_COLUMNA_MES);
            indices.push(3 + posicion);
        });
        if (variosAnios) {
            grupos.push({ desde: desde, hasta: columnas.length - 1, colapsado: true });
        }
    });

    columnas.push('Total');
    formatos.push(FORMATO_IMPORTE_PENDIENTES);
    anchos.push(ANCHO_COLUMNA_TOTAL);
    indices.push(3 + pivote.columnasMes.length);

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

    let html = `
        <div style="overflow-x:auto;">
            <table class="table table-striped" style="font-size:12px; border-collapse:collapse; width:100%;">
                <thead style="background:#f1f5f9;">
                    <tr>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:110px; text-align:left; background:#f8fafc;">Contrato</th>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:140px; text-align:left; background:#f8fafc;">Cliente</th>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:140px; text-align:left; background:#f8fafc;">Concepto</th>
    `;
    pivote.columnasMes.forEach(cm => {
        html += `<th style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; min-width:75px; background:#f8fafc;">${escapeHTML(cm.etiqueta)}</th>`;
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
        pivote.columnasMes.forEach((cm, columna) => {
            html += `<td style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-variant-numeric:tabular-nums;">${formatearNumero(fila[3 + columna])}</td>`;
        });
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-weight:bold; background:#fef3c7;">${formatearNumero(fila[fila.length - 1])}</td>`;
        html += `</tr>`;
    });

    html += `<tfoot style="background:#f1f5f9;">`;
    html += `<tr style="font-weight:bold; background:#f0f4ff;">`;
    html += `<td colspan="3" style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; background:#e8f0fe;">TOTAL GENERAL</td>`;
    pivote.columnasMes.forEach((cm, columna) => {
        html += `<td style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; background:#e8f0fe;">${formatearNumero(filaTotal[3 + columna])}</td>`;
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
    // La columna del anio solo lleva el rotulo del encabezado: en las filas de
    // datos va vacia (si no, los meses quedarian corridos una columna).
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