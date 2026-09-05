// ============================================================
// VENTAS MANUALES - MODAL, ADMINISTRACIÓN E IMPORTACIÓN (CON SIGLAS)
// ============================================================

// Funciones auxiliares (sanitización, formateo)
function escapeHTML(str) {
    if (!str) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(str).replace(/[&<>"']/g, m => map[m]);
}

function formatearNumero(valor) {
    const num = parseFloat(valor);
    if (isNaN(num)) return '0,00';
    const partes = num.toFixed(2).split('.');
    const entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return entero + ',' + partes[1];
}

// Mapeo de base a país (para el modal) - nombres completos para el backend
const BASE_A_PAIS_COMPLETO = {
    'plataforma_rd': 'República Dominicana',
    'plataforma_ar': 'Argentina',
    'plataforma_mx': 'México',
    'plataforma_gt': 'Guatemala',
    'plataforma_hn': 'Honduras',
    'plataforma_cr': 'Costa Rica',
    'plataforma_pe': 'Perú',
    'plataforma_py': 'Paraguay',
    'plataforma_co': 'Colombia',
    'plataforma_uy': 'Uruguay',
    'plataforma_ec': 'Ecuador'
};

// Mapeo inverso (nombre completo -> base)
const PAIS_A_BASE = {
    'República Dominicana': 'plataforma_rd',
    'Argentina': 'plataforma',
    'México': 'plataforma_mx',
    'Guatemala': 'plataforma_gt',
    'Honduras': 'plataforma_hn',
    'Costa Rica': 'plataforma_cr',
    'Perú': 'plataforma_pe',
    'Paraguay': 'plataforma_py',
    'Colombia': 'plataforma_co',
    'Uruguay': 'plataforma_uy',
    'Ecuador': 'plataforma_ec'
};

// ============================================================
// ABRIR / CERRAR MODAL DE CARGA
// ============================================================

export function abrirModalVentaManual() {
    const modal = document.getElementById('modal-venta-manual');
    if (modal) {
        modal.style.display = 'flex';
        cargarSelectoresVentaManual();
    } else {
        console.warn('⚠️ No se encontró el modal #modal-venta-manual');
        if (typeof toastWarning === 'function') toastWarning('El modal de ventas manuales no está disponible', 'Error');
    }
}

export function cerrarModalVentaManual() {
    const modal = document.getElementById('modal-venta-manual');
    if (modal) {
        modal.style.display = 'none';
        const form = document.getElementById('vm-form');
        if (form) form.reset();
        const usdInput = document.getElementById('vm-importe-usd');
        const psInput = document.getElementById('vm-importe-ps');
        if (usdInput) usdInput.value = '';
        if (psInput) psInput.value = '';
    }
}

// ============================================================
// CARGAR SELECTORES DEL MODAL (con siglas)
// ============================================================

function cargarSelectoresVentaManual() {
    // Años
    const selectAnio = document.getElementById('vm-anio');
    if (selectAnio) {
        const añoActual = new Date().getFullYear();
        selectAnio.innerHTML = '';
        for (let i = añoActual + 1; i >= 2020; i--) {
            const option = document.createElement('option');
            option.value = i;
            option.textContent = i;
            if (i === añoActual) option.selected = true;
            selectAnio.appendChild(option);
        }
    }

    // Meses
    const selectMes = document.getElementById('vm-mes');
    if (selectMes) {
        const meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
        selectMes.innerHTML = '';
        meses.forEach((nombre, idx) => {
            const option = document.createElement('option');
            option.value = idx + 1;
            option.textContent = nombre;
            if (idx + 1 === new Date().getMonth() + 1) option.selected = true;
            selectMes.appendChild(option);
        });
    }

    // Bases y país/sociedad
    const selectBase = document.getElementById('vm-base');
    const selectPais = document.getElementById('vm-pais');
    const paisLabel = document.getElementById('vm-pais-label');
    const paisWrapper = document.getElementById('vm-pais-wrapper');

    if (selectBase && window.BASES_DISPONIBLES_FRONT) {
        const bases = window.BASES_DISPONIBLES_FRONT || {};
        selectBase.innerHTML = '';
        const sortedKeys = Object.keys(bases).sort();
        sortedKeys.forEach(codigo => {
            const info = bases[codigo];
            const option = document.createElement('option');
            option.value = codigo;
            // Mostrar SIGLA en el selector de base (no el nombre completo)
            const sigla = window.siglaBase(codigo) || info.label || codigo;
            option.textContent = sigla;
            if (codigo === window.baseActiva) option.selected = true;
            selectBase.appendChild(option);
        });

        selectBase.onchange = function() {
            const baseCodigo = this.value;
            const baseInfo = bases[baseCodigo];
            if (!baseInfo) return;
            const esArgentina = baseCodigo === 'plataforma';

            if (esArgentina) {
                paisLabel.textContent = 'Sociedad *';
                selectPais.disabled = false;
                selectPais.innerHTML = '';
                const sociedades = baseInfo.sociedades || {};
                const keys = Object.keys(sociedades);
                if (keys.length > 0) {
                    keys.forEach(socKey => {
                        const option = document.createElement('option');
                        option.value = socKey;
                        option.textContent = sociedades[socKey].label || socKey;
                        if (socKey === 'sidesys') option.selected = true;
                        selectPais.appendChild(option);
                    });
                } else {
                    const option = document.createElement('option');
                    option.value = 'sidesys';
                    option.textContent = 'Sidesys (default)';
                    selectPais.appendChild(option);
                }
                // Para Argentina, el país es siempre "Argentina"
                selectPais.dataset.paisFijo = 'Argentina';
                paisWrapper.style.display = 'block';
            } else {
                paisLabel.textContent = 'País *';
                const nombrePais = BASE_A_PAIS_COMPLETO[baseCodigo] || baseInfo.label || baseCodigo;
                // Mostramos la SIGLA en el select (pero el valor sigue siendo el nombre completo)
                const sigla = window.siglaBase(baseCodigo) || nombrePais;
                selectPais.disabled = true;
                selectPais.innerHTML = `<option value="${nombrePais}">${sigla}</option>`;
                selectPais.dataset.paisFijo = nombrePais;
                paisWrapper.style.display = 'block';
            }
        };
        // Disparar el cambio inicial
        selectBase.onchange();
    }
}

// ============================================================
// GUARDAR VENTA MANUAL (el payload debe enviar nombre completo, no sigla)
// ============================================================

export function guardarVentaManual() {
    const selectBase = document.getElementById('vm-base');
    const selectPais = document.getElementById('vm-pais');

    // Obtener valores
    let pais = selectPais?.value || selectPais?.dataset?.paisFijo || null;
    const esArgentina = selectBase?.value === 'plataforma';
    let sociedad = null;
    if (esArgentina) {
        sociedad = selectPais?.value || null;
        pais = 'Argentina';
    }

    let base = PAIS_A_BASE[pais];
    if (!base) {
        base = selectBase?.value;
        console.warn(`⚠️ País "${pais}" no encontrado en PAIS_A_BASE, usando base "${base}"`);
    }

    const anio = parseInt(document.getElementById('vm-anio')?.value);
    const mes = parseInt(document.getElementById('vm-mes')?.value);
    const centroCosto = document.getElementById('vm-centro-costo')?.value || null;
    const importe_usd = parseFloat(document.getElementById('vm-importe-usd')?.value) || 0;
    const importe_ps = parseFloat(document.getElementById('vm-importe-ps')?.value) || 0;
    const fechaRegistro = document.getElementById('vm-fecha')?.value;
    const comentario = document.getElementById('vm-comentario')?.value || '';

    if (!base || !anio || !mes || !pais || (!importe_usd && !importe_ps) || !fechaRegistro) {
        if (typeof toastWarning === 'function') toastWarning('Completa todos los campos obligatorios (al menos un importe)', 'Error');
        return;
    }
    if (importe_usd <= 0 && importe_ps <= 0) {
        if (typeof toastWarning === 'function') toastWarning('Debe ingresar al menos un importe (USD o PS)', 'Error');
        return;
    }

    const btnGuardar = document.querySelector('#modal-venta-manual button[onclick="guardarVentaManual()"]');
    if (btnGuardar) {
        btnGuardar.disabled = true;
        btnGuardar.textContent = '⏳ Guardando...';
    }

    console.log('📤 Enviando venta manual:', { base, sociedad, anio, mes, pais, importe_usd, importe_ps, fechaRegistro, centroCosto, comentario });

    const payload = {
        base: base,
        sociedad: sociedad,
        anio: anio,
        mes: mes,
        pais: pais,  // nombre completo
        centro_costo: centroCosto,
        importe_usd: importe_usd,
        importe_ps: importe_ps,
        fecha_registro: fechaRegistro,
        comentario: comentario
    };

    fetch('/api/reportes/ventas_manuales', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    })
    .then(data => {
        if (data.success) {
            if (typeof toastSuccess === 'function') toastSuccess('Venta manual cargada correctamente', 'Éxito');
            cerrarModalVentaManual();
            if (typeof window.recargarReporteActual === 'function') window.recargarReporteActual();
        } else {
            if (typeof toastError === 'function') toastError(data.error || 'Error al guardar la venta manual', 'Error');
        }
    })
    .catch(e => {
        console.error('❌ Error guardando venta manual:', e);
        if (typeof toastError === 'function') toastError(e.message || 'Error al guardar', 'Error');
    })
    .finally(() => {
        if (btnGuardar) {
            btnGuardar.disabled = false;
            btnGuardar.textContent = 'Guardar';
        }
    });
}

// ============================================================
// IMPORTACIÓN DE VENTAS MANUALES DESDE EXCEL/CSV
// ============================================================

export function importarVentasManuales() {
    const fileInput = document.getElementById('vm-import-file');
    if (fileInput) fileInput.click();
}

export function procesarImportacionVentas() {
    const fileInput = document.getElementById('vm-import-file');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        if (typeof toastWarning === 'function') toastWarning('Selecciona un archivo primero', 'Error');
        return;
    }

    const archivo = fileInput.files[0];
    const formData = new FormData();
    formData.append('archivo', archivo);

    const btnImportar = document.getElementById('btn-importar-ventas');
    if (btnImportar) {
        btnImportar.disabled = true;
        btnImportar.textContent = '⏳ Importando...';
    }

    fetch('/api/reportes/ventas_manuales/importar', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            if (typeof toastSuccess === 'function') toastSuccess(data.message, 'Importación exitosa');
            if (data.errores && data.errores.length > 0) {
                console.warn('Errores en algunas filas:', data.errores);
                if (typeof toastWarning === 'function') toastWarning('Algunas filas no se importaron: ' + data.errores.join('; '), 'Advertencia');
            }
            cerrarModalVentaManual();
            if (typeof window.recargarReporteActual === 'function') window.recargarReporteActual();
        } else {
            if (typeof toastError === 'function') toastError(data.error || 'Error al importar', 'Error');
        }
    })
    .catch(e => {
        if (typeof toastError === 'function') toastError(e.message, 'Error');
    })
    .finally(() => {
        if (btnImportar) {
            btnImportar.disabled = false;
            btnImportar.textContent = '📤 Importar';
        }
        fileInput.value = '';
    });
}

export function descargarPlantillaVentasManuales() {
    const columnas = ['base', 'anio', 'mes', 'pais', 'fecha_registro', 'sociedad', 'centro_costo', 'importe_usd', 'importe_ps', 'comentario'];
    const ejemplo = ['plataforma_rd', '2026', '8', 'República Dominicana', '2026-08-15', '', '410101', '1500.00', '95000.00', 'Venta manual de ejemplo'];
    const ejemplo2 = ['plataforma_py', '2026', '7', 'Paraguay', '2026-07-20', '', '410102', '2500.00', '0.00', 'Venta Paraguay'];
    let csvContent = columnas.join(',') + '\n';
    csvContent += ejemplo.join(',') + '\n';
    csvContent += ejemplo2.join(',') + '\n';
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'plantilla_ventas_manuales.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    if (typeof toastSuccess === 'function') toastSuccess('Plantilla descargada', 'Éxito');
}

// ============================================================
// ADMINISTRACIÓN DE VENTAS MANUALES
// ============================================================

export function abrirAdminVentasManuales() {
    const modal = document.getElementById('modal-admin-ventas-manuales');
    if (modal) {
        modal.style.display = 'flex';
        cargarListaVentasManuales();
    } else {
        if (typeof toastWarning === 'function') toastWarning('El modal de administración no está disponible', 'Error');
    }
}

export function cerrarAdminVentasManuales() {
    const modal = document.getElementById('modal-admin-ventas-manuales');
    if (modal) modal.style.display = 'none';
}

function cargarListaVentasManuales() {
    const tbody = document.getElementById('lista-ventas-manuales-body');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;">Cargando...</td></tr>';

    // No enviamos filtro de base para que devuelva todas
    const anio = document.getElementById('admin-filtro-anio')?.value || '';
    const mes = document.getElementById('admin-filtro-mes')?.value || '';
    let url = '/api/reportes/ventas_manuales?';
    if (anio) url += `anio=${anio}&`;
    if (mes) url += `mes=${mes}&`;

    fetch(url)
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const ventas = data.data || [];
            if (ventas.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#94a3b8;">No hay ventas manuales cargadas</td></tr>';
                return;
            }
            let html = '';
            ventas.forEach(v => {
                const fechaReg = v.fecha_registro ? v.fecha_registro.split('T')[0] : '';
                const importe_usd = parseFloat(v.importe_usd) || 0;
                const importe_ps = parseFloat(v.importe_ps) || 0;
                html += `
                    <tr>
                        <td>${escapeHTML(v.base)}</td>
                        <td>${escapeHTML(v.sociedad || '')}</td>
                        <td>${v.anio}</td>
                        <td>${v.mes}</td>
                        <td>${escapeHTML(v.pais)}</td>
                        <td style="text-align:right;">${formatearNumero(importe_usd)}</td>
                        <td style="text-align:right;">${formatearNumero(importe_ps)}</td>
                        <td>${fechaReg}</td>
                        <td>
                            <button onclick="window.eliminarVentaManual(${v.id})" style="background:#dc2626;color:white;border:none;border-radius:4px;padding:2px 8px;cursor:pointer;">🗑</button>
                        </td>
                    </tr>
                `;
            });
            tbody.innerHTML = html;
        } else {
            tbody.innerHTML = `<tr><td colspan="9" style="color:#dc2626;">Error: ${data.error}</td></tr>`;
        }
    })
    .catch(e => {
        tbody.innerHTML = `<tr><td colspan="9" style="color:#dc2626;">Error al cargar: ${e.message}</td></tr>`;
    });
}

export function eliminarVentaManual(id) {
    if (!confirm('¿Estás seguro de eliminar esta venta manual?')) return;
    fetch(`/api/reportes/ventas_manuales/${id}`, { method: 'DELETE' })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            if (typeof toastSuccess === 'function') toastSuccess('Venta manual eliminada', 'Éxito');
            cargarListaVentasManuales();
            if (typeof window.recargarReporteActual === 'function') window.recargarReporteActual();
        } else {
            if (typeof toastError === 'function') toastError(data.error || 'Error al eliminar', 'Error');
        }
    })
    .catch(e => {
        if (typeof toastError === 'function') toastError(e.message, 'Error');
    });
}