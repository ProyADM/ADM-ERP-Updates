// ============================================================
// REPORTE: CONTRATOS (PENDIENTE DE FACTURAR)
// ============================================================

let datosReporte = [];
let filtroAnio = '';
let filtroMes = '';
let monedaActual = 'PS';

// Funciones auxiliares (sanitización, formateo)
function escapeHTML(str) {
    if (!str) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(str).replace(/[&<>"']/g, m => map[m]);
}

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

    let datosFiltrados = datos.filter(d => d.MONEDA === moneda);
    if (filtroAnio && filtroAnio !== '') {
        datosFiltrados = datosFiltrados.filter(d => d.ANIO === parseInt(filtroAnio));
    }
    if (filtroMes && filtroMes !== '') {
        datosFiltrados = datosFiltrados.filter(d => d.MES === parseInt(filtroMes));
    }
    if (datosFiltrados.length === 0) {
        const nombreMoneda = moneda === 'PS' ? 'PESOS' : 'DÓLARES';
        let mensaje = `No hay datos para ${escapeHTML(nombreMoneda)}`;
        if (filtroAnio) mensaje += ` en ${escapeHTML(filtroAnio)}`;
        if (filtroMes) mensaje += ` - mes ${escapeHTML(filtroMes)}`;
        container.innerHTML = `<div style="text-align:center; padding:40px; color:#94a3b8;">${escapeHTML(mensaje)}</div>`;
        return;
    }

    const anios = [...new Set(datosFiltrados.map(d => d.ANIO))].sort();
    const meses = [...new Set(datosFiltrados.map(d => d.MES))].sort((a, b) => a - b);
    const nombresMeses = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

    const grupos = {};
    datosFiltrados.forEach(row => {
        const contrato = escapeHTML(row.CONTRATO || 'Sin Contrato');
        const cliente = escapeHTML(row.CLIENTE || 'Sin Cliente');
        const centro = escapeHTML(row.CENTRO_COSTO || 'Sin Concepto');
        const key = `${contrato}|${cliente}|${centro}`;
        if (!grupos[key]) {
            grupos[key] = { CONTRATO: contrato, CLIENTE: cliente, CENTRO_COSTO: centro, valores: {} };
        }
        const colKey = `${row.ANIO || 0}-${String(row.MES || 0).padStart(2, '0')}`;
        const importe = parseFloat(row.IMPORTE) || 0;
        grupos[key].valores[colKey] = (grupos[key].valores[colKey] || 0) + importe;
    });

    const keys = Object.keys(grupos);
    if (keys.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding:40px; color:#94a3b8;">No hay datos para mostrar</div>';
        return;
    }

    let html = `
        <div style="overflow-x:auto; max-height:500px; overflow-y:auto;">
            <table class="table table-striped" style="font-size:12px; border-collapse:collapse; width:100%;">
                <thead style="position:sticky; top:0; z-index:10; background:#f1f5f9;">
                    <tr>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:110px; text-align:left; background:#f8fafc;">Contrato</th>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:140px; text-align:left; background:#f8fafc;">Cliente</th>
                        <th style="padding:8px 10px; border:1px solid #e2e8f0; min-width:140px; text-align:left; background:#f8fafc;">Concepto</th>
    `;
    const columnas = [];
    anios.forEach(anio => {
        meses.forEach(mes => {
            const colKey = `${anio}-${String(mes).padStart(2, '0')}`;
            columnas.push(colKey);
            const mesName = `${escapeHTML(nombresMeses[mes] || mes)} ${anio}`;
            html += `<th style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; min-width:75px; background:#f8fafc;">${mesName}</th>`;
        });
    });
    html += `<th style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; min-width:80px; background:#fef3c7;">Total</th>`;
    html += `</tr></thead><tbody>`;

    let totalGeneral = 0;
    const keysOrdenadas = keys.sort((a, b) => {
        const gA = grupos[a], gB = grupos[b];
        if (gA.CLIENTE !== gB.CLIENTE) return gA.CLIENTE.localeCompare(gB.CLIENTE);
        return gA.CONTRATO.localeCompare(gB.CONTRATO);
    });

    keysOrdenadas.forEach(key => {
        const grupo = grupos[key];
        let totalFila = 0;
        html += `<tr>`;
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;">${grupo.CONTRATO}</td>`;
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;">${grupo.CLIENTE}</td>`;
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0;">${grupo.CENTRO_COSTO}</td>`;
        columnas.forEach(colKey => {
            const valor = grupo.valores[colKey] || 0;
            totalFila += valor;
            html += `<td style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-variant-numeric:tabular-nums;">${formatearNumero(valor)}</td>`;
        });
        totalGeneral += totalFila;
        html += `<td style="padding:6px 8px; border:1px solid #e2e8f0; text-align:right; font-weight:bold; background:#fef3c7;">${formatearNumero(totalFila)}</td>`;
        html += `</tr>`;
    });

    html += `<tfoot style="position:sticky; bottom:0; z-index:10; background:#f1f5f9;">`;
    html += `<tr style="font-weight:bold; background:#f0f4ff;">`;
    html += `<td colspan="3" style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; background:#e8f0fe;">TOTAL GENERAL</td>`;
    columnas.forEach(colKey => {
        let totalCol = 0;
        keysOrdenadas.forEach(key => {
            totalCol += grupos[key].valores[colKey] || 0;
        });
        html += `<td style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:13px; background:#e8f0fe;">${formatearNumero(totalCol)}</td>`;
    });
    html += `<td style="padding:8px 10px; border:1px solid #e2e8f0; text-align:right; font-size:15px; background:#fef3c7; color:#92400e;">${formatearNumero(totalGeneral)}</td>`;
    html += `</tr></tfoot>`;
    html += `</tbody></table></div>`;

    container.innerHTML = html;
}

function mostrarLoading(activo) {
    const loading = document.getElementById('loading-reporte');
    if (loading) loading.style.display = activo ? 'block' : 'none';
}

// ============================================================
// EXPORTAR A CSV
// ============================================================

export function exportarExcel() {
    if (datosReporte.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('⚠️ No hay datos para exportar', 'Reportes');
        return;
    }
    let datosExportar = datosReporte.filter(d => d.MONEDA === monedaActual);
    if (filtroAnio && filtroAnio !== '') {
        datosExportar = datosExportar.filter(d => d.ANIO === parseInt(filtroAnio));
    }
    if (filtroMes && filtroMes !== '') {
        datosExportar = datosExportar.filter(d => d.MES === parseInt(filtroMes));
    }
    if (datosExportar.length === 0) {
        if (typeof toastWarning === 'function') toastWarning(`⚠️ No hay datos para exportar con los filtros actuales`, 'Reportes');
        return;
    }

    const columnas = ['CONTRATO', 'CLIENTE', 'CENTRO_COSTO', 'MONEDA', 'ANIO', 'MES', 'IMPORTE'];
    let csv = columnas.join(',') + '\n';
    datosExportar.forEach(row => {
        csv += columnas.map(col => {
            let valor = row[col] || '';
            if (typeof valor === 'string') {
                valor = sanitizarCSV(valor);
                if (valor.includes(',') || valor.includes('"')) {
                    valor = `"${valor.replace(/"/g, '""')}"`;
                }
            } else if (typeof valor === 'number') {
                valor = valor.toString().replace('.', ',');
            }
            return valor;
        }).join(',') + '\n';
    });

    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `reporte_pendientes_${monedaActual}_${filtroAnio || 'todos'}_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    if (typeof toastSuccess === 'function') toastSuccess('✅ Reporte exportado', 'Reportes');
}

// ============================================================
// EXPONER FUNCIONES QUE USA EL HTML (se exportan en index.js)
// ============================================================

// (Las funciones que necesitan ser globales se asignarán en index.js)