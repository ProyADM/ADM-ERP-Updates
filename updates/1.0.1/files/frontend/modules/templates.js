// ============================================================
// TEMPLATES - VERSIÓN CORREGIDA (CON SANITIZACIÓN)
// ============================================================

// ============================================================
// FUNCIÓN DE SANITIZACIÓN
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
// TEMPLATES
// ============================================================

const TEMPLATES = {
   dashboard: `
    <!-- DASHBOARD - 3 COLUMNAS -->
    <div id="dashboard-container">
        <div class="dashboard-header">
            <h2>🏠 Inicio</h2>
            <div class="dashboard-info">
                <span id="dashboard-timestamp">⏱️ Última actualización: cargando...</span>
                <button id="btn-refresh-dashboard" class="small">🔄 Actualizar</button>
            </div>
        </div>

        <!-- 3 COLUMNAS -->
        <div id="dashboard-newsletter" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;">
            <!-- STOCK -->
            <div class="newsletter-card">
                <div class="card-header" style="background:#f0fdf4;">
                    <span>📦 Stock</span>
                    <button class="btn-ver-todos" onclick="cambiarModulo('stock')">Ver todos</button>
                </div>
                <div class="card-body" id="newsletter-stock">
                    <div class="sin-actividad">Cargando...</div>
                </div>
            </div>

            <!-- VENTAS REGISTRADAS -->
            <div class="newsletter-card">
                <div class="card-header" style="background:#fef3f2;">
                    <span>💰 Ventas registradas</span>
                    <button class="btn-ver-todos" onclick="cambiarModulo('reportes')">Ver todos</button>
                </div>
                <div class="card-body" id="newsletter-ventas">
                    <div class="sin-actividad">Cargando...</div>
                </div>
            </div>

            <!-- CONTRATOS (afecta solo pendiente de facturar) -->
            <div class="newsletter-card">
                <div class="card-header" style="background:#fefce8;">
                    <span>📋 Contratos pendientes</span>
                    <button class="btn-ver-todos" onclick="cambiarModulo('reportes')">Ver todos</button>
                </div>
                <div class="card-body" id="newsletter-contratos">
                    <div class="sin-actividad">Cargando...</div>
                </div>
            </div>
        </div>

        <!-- TIMELINE GENERAL (opcional) -->
        <div id="dashboard-timeline" style="margin-top:24px;display:none;">
            <h3>📋 Actividad reciente</h3>
            <div id="dashboard-activity"></div>
        </div>
    </div>
    `,
    
    stock: `
        <!-- STOCK: Ajuste + -->
        <div class="section" id="ajuste-e">
            <div class="subsection active" id="ae-individual">
                <label>Artículo</label>
                <select id="ae-articulo" onchange="cargarPartidasEntrada()"></select>
                <label>Depósito</label>
                <select id="ae-deposito" onchange="cargarPartidasEntrada()"></select>
                <label id="ae-partida-label" style="display:none">Nombre de partida <span class="hint">(opcional)</span></label>
                <input type="text" id="ae-partida-nombre" style="display:none" placeholder="Ej: SY15 622552025">
                <label>Cantidad</label>
                <input type="number" id="ae-cantidad" min="0.0001" step="any" value="1">
                <label>Fecha <span class="hint">(opcional, default hoy)</span></label>
                <input type="date" id="ae-fecha">
                <label>Comentario <span class="hint">(opcional)</span></label>
                <input type="text" id="ae-comentario" placeholder="Descripción del movimiento">
                <button class="full" onclick="hacerAjusteIndividual('E')">Cargar Ajuste de Entrada</button>
            </div>
            <div class="subsection" id="ae-multiple">
                <table class="grid-editable" id="ae-grid"><thead><tr><th>Artículo</th><th>Depósito</th><th>Cantidad</th><th></th></tr></thead><tbody></tbody></table>
                <div class="grid-actions">
                    <button class="small secondary" onclick="agregarFila('ae')">+ Agregar fila</button>
                    <button class="small" onclick="cargarLote('ae', 'E')">Cargar todo (1 comprobante)</button>
                </div>
                <div class="resultados-tabla" id="ae-resultados"></div>
            </div>
            <div class="subsection" id="ae-excel">
                <p class="hint">Descargá la plantilla, completala con tus artículos y subila acá.</p>
                <button class="small secondary" onclick="descargarPlantilla('ajuste')">Descargar plantilla Excel</button>
                <div class="file-drop" onclick="document.getElementById('ae-file').click()">Click para elegir archivo .xlsx</div>
                <input type="file" id="ae-file" accept=".xlsx" style="display:none" onchange="cargarExcel('ajuste', this, 'ae')">
                <div class="resultados-tabla" id="ae-excel-resultados"></div>
            </div>
        </div>

        <!-- STOCK: Ajuste - -->
        <div class="section" id="ajuste-s">
            <div class="subsection active" id="as-individual">
                <label>Artículo</label>
                <select id="as-articulo" onchange="cargarPartidas()"></select>
                <label>Depósito</label>
                <select id="as-deposito" onchange="cargarPartidas()"></select>
                <label id="as-partida-label" style="display:none">Partida</label>
                <select id="as-partida" style="display:none"></select>
                <label>Cantidad</label>
                <input type="number" id="as-cantidad" min="0.0001" step="any" value="1">
                <label>Fecha <span class="hint">(opcional, default hoy)</span></label>
                <input type="date" id="as-fecha">
                <label>Comentario <span class="hint">(opcional)</span></label>
                <input type="text" id="as-comentario" placeholder="Descripción del movimiento">
                <button class="full" onclick="hacerAjusteIndividual('S')">Cargar Ajuste de Salida</button>
            </div>
            <div class="subsection" id="as-multiple">
                <table class="grid-editable" id="as-grid"><thead><tr><th>Artículo</th><th>Depósito</th><th>Cantidad</th><th id="as-th-partida" style="display:none">Partida</th><th></th></tr></thead><tbody></tbody></table>
                <div class="grid-actions">
                    <button class="small secondary" onclick="agregarFila('as')">+ Agregar fila</button>
                    <button class="small" onclick="cargarLote('as', 'S')">Cargar todo (1 comprobante)</button>
                </div>
                <div class="resultados-tabla" id="as-resultados"></div>
            </div>
            <div class="subsection" id="as-excel">
                <p class="hint">Descargá la plantilla (columna "partida" solo si aplica) y subila acá.</p>
                <button class="small secondary" onclick="descargarPlantilla('ajuste')">Descargar plantilla Excel</button>
                <div class="file-drop" onclick="document.getElementById('as-file').click()">Click para elegir archivo .xlsx</div>
                <input type="file" id="as-file" accept=".xlsx" style="display:none" onchange="cargarExcel('ajuste', this, 'as')">
                <div class="resultados-tabla" id="as-excel-resultados"></div>
            </div>
        </div>

        <!-- STOCK: Transferencia -->
        <div class="section" id="transferencia">
            <div class="subsection active" id="tr-individual">
                <label>Artículo</label>
                <select id="tr-articulo" onchange="cargarPartidasTransferencia()"></select>
                <label>Depósito origen</label>
                <select id="tr-origen" onchange="cargarPartidasTransferencia()"></select>
                <label id="tr-partida-label" style="display:none">Partida</label>
                <select id="tr-partida" style="display:none"></select>
                <label>Depósito destino</label>
                <select id="tr-destino"></select>
                <label>Cantidad</label>
                <input type="number" id="tr-cantidad" min="0.0001" step="any" value="1">
                <label>Fecha <span class="hint">(opcional, default hoy)</span></label>
                <input type="date" id="tr-fecha">
                <label>Comentario <span class="hint">(opcional)</span></label>
                <input type="text" id="tr-comentario" placeholder="Descripción del movimiento">
                <button class="full" onclick="hacerTransferenciaIndividual()">Cargar Transferencia</button>
            </div>
            <div class="subsection" id="tr-multiple">
                <table class="grid-editable" id="trm-grid"><thead><tr><th>Artículo</th><th>Dep. Origen</th><th>Dep. Destino</th><th>Cantidad</th><th id="trm-th-partida" style="display:none">Partida</th><th></th></tr></thead><tbody></tbody></table>
                <div class="grid-actions">
                    <button class="small secondary" onclick="agregarFila('trm')">+ Agregar fila</button>
                    <button class="small" onclick="cargarLoteTransferencia()">Cargar todo</button>
                </div>
                <div class="resultados-tabla" id="trm-resultados"></div>
            </div>
            <div class="subsection" id="tr-excel">
                <p class="hint">Descargá la plantilla (columna "partida" solo si aplica), completala y subila acá.</p>
                <button class="small secondary" onclick="descargarPlantilla('transferencia')">Descargar plantilla Excel</button>
                <div class="file-drop" onclick="document.getElementById('tr-file').click()">Click para elegir archivo .xlsx</div>
                <input type="file" id="tr-file" accept=".xlsx" style="display:none" onchange="cargarExcel('transferencia', this, 'trm')">
                <div class="resultados-tabla" id="trm-excel-resultados"></div>
            </div>
        </div>

        <!-- STOCK: Consultar Stock -->
        <div class="section" id="stock">
            <div class="stock-filters">
                <div>
                    <label>Buscar artículo</label>
                    <input type="text" id="stk-q" placeholder="Nombre del artículo..." onkeydown="if(event.key==='Enter') consultarStock()">
                </div>
                <div>
                    <label>Depósito</label>
                    <select id="stk-deposito"><option value="">Todos</option></select>
                </div>
            </div>
            <button class="small" style="margin-top:14px" onclick="consultarStock()">Buscar</button>
            <div id="stk-seleccion-bar">
                <span id="stk-seleccion-count">0 seleccionados</span>
                <button class="small secondary" onclick="enviarSeleccionAMovimiento('ae')">A Ajuste +</button>
                <button class="small secondary" onclick="enviarSeleccionAMovimiento('as')">A Ajuste -</button>
                <button class="small secondary" onclick="enviarSeleccionAMovimiento('trm')">A Transferencia</button>
            </div>
            <div class="stock-tabla-wrap">
                <table class="grid-editable" id="stk-tabla">
                    <thead>
                        <tr>
                            <th style="width:36px;text-align:center;"><input type="checkbox" id="stk-check-all" onclick="toggleTodosStock(this)"></th>
                            <th>Código</th>
                            <th>Descripción</th>
                            <th>Depósito</th>
                            <th style="text-align:right">Stock</th>
                            <th style="text-align:center">Acciones</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                    <tfoot></tfoot>
                </table>
            </div>
        </div>

        <!-- STOCK: Stock Consolidado -->
        <div class="section" id="stock-consolidado">
            <div id="cons-banner"><span>Hay nuevos movimientos de stock.</span><button onclick="buscarConsolidado(true)">Actualizar</button></div>
            <label>Buscar artículo</label>
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
                <input type="text" id="cons-q" placeholder="Nombre o código..." style="flex:1;min-width:180px" onkeydown="if(event.key==='Enter') buscarConsolidado()">
                <button class="small" onclick="buscarConsolidado()">Buscar</button>
                <label style="display:flex;align-items:center;gap:7px;margin:0;font-size:13px;font-weight:500;cursor:pointer;white-space:nowrap">
                    <input type="checkbox" id="cons-solo-errores" onchange="filtrarSoloErrores()" style="width:15px;height:15px;accent-color:var(--primary)"> Solo inconsistencias
                </label>
            </div>
            <div id="cons-loading" style="display:none;margin-top:16px;color:var(--ink-soft);font-size:13px">Consultando todas las bases…</div>
            <div id="cons-tabla-wrap" style="margin-top:16px"></div>
        </div>

        <!-- STOCK: Artículos -->
        <div class="section" id="articulos">
            <div class="subsection active" id="art-crear">
                <label>Nombre</label>
                <input type="text" id="art-nombre" placeholder="Nombre del artículo">
                <label>Código</label>
                <input type="text" id="art-codigo" placeholder="Ej: 10.8.9">
                <label>Categoría</label>
                <select id="art-categoria" onchange="aplicarDefaultPartidas()"></select>
                <label style="display:flex;align-items:center;gap:8px;text-transform:none;font-weight:500;margin-top:14px">
                    <input type="checkbox" id="art-con-partidas" style="width:auto"> Lleva partidas
                </label>
                <label style="display:flex;align-items:center;gap:8px;text-transform:none;font-weight:500;margin-top:10px">
                    <input type="checkbox" id="art-se-compra" checked style="width:auto" onchange="actualizarCamposOrigen()"> Se compra
                </label>
                <label style="display:flex;align-items:center;gap:8px;text-transform:none;font-weight:500;margin-top:10px">
                    <input type="checkbox" id="art-se-vende" checked style="width:auto" onchange="actualizarCamposOrigen()"> Se vende
                </label>
                <div id="art-origen-wrap">
                    <label>Origen (define cuentas contables)</label>
                    <select id="art-origen"><option value="local">Local</option><option value="exterior">Exterior</option></select>
                </div>
                <button class="full" onclick="crearArticulo()">Crear Artículo</button>
            </div>
            <div class="subsection" id="art-modificar">
                <label>Buscar artículo</label>
                <select id="art-mod-buscar" onchange="cargarArticuloParaModificar()"><option value="">Elegí un artículo...</option></select>
                <div id="art-mod-form" style="display:none">
                    <label>Nombre</label>
                    <input type="text" id="art-mod-nombre">
                    <label>Código</label>
                    <input type="text" id="art-mod-codigo">
                    <label>Categoría</label>
                    <select id="art-mod-categoria"></select>
                    <label style="display:flex;align-items:center;gap:8px;text-transform:none;font-weight:500;margin-top:14px">
                        <input type="checkbox" id="art-mod-con-partidas" style="width:auto"> Lleva partidas
                    </label>
                    <label style="display:flex;align-items:center;gap:8px;text-transform:none;font-weight:500;margin-top:10px">
                        <input type="checkbox" id="art-mod-se-compra" style="width:auto" onchange="actualizarCamposOrigenMod()"> Se compra
                    </label>
                    <label style="display:flex;align-items:center;gap:8px;text-transform:none;font-weight:500;margin-top:10px">
                        <input type="checkbox" id="art-mod-se-vende" style="width:auto" onchange="actualizarCamposOrigenMod()"> Se vende
                    </label>
                    <div id="art-mod-origen-wrap">
                        <label>Origen</label>
                        <select id="art-mod-origen"><option value="local">Local</option><option value="exterior">Exterior</option></select>
                    </div>
                    <button class="full" onclick="guardarModificacionArticulo()">Guardar Cambios</button>
                </div>
            </div>
            <div class="subsection" id="art-excel">
                <div class="grid-actions" style="margin-bottom:18px">
                    <button class="small" id="art-excel-btn-crear" onclick="mostrarExcelModo('crear')">Crear nuevos</button>
                    <button class="small secondary" id="art-excel-btn-modificar" onclick="mostrarExcelModo('modificar')">Modificar existentes</button>
                </div>
                <div class="multibase-selector">
                    <label>Aplicar en (dejar todo destildado = solo la base activa actual)</label>
                    <div id="multibase-checklist"></div>
                </div>
                <div id="art-excel-crear">
                    <p class="hint">Descargá la plantilla, completala y subila acá.</p>
                    <button class="small secondary" onclick="descargarPlantilla('articulos')">Descargar plantilla Excel</button>
                    <div class="file-drop" onclick="document.getElementById('art-file').click()">Click para elegir archivo .xlsx</div>
                    <input type="file" id="art-file" accept=".xlsx" style="display:none" onchange="cargarExcelArticulos(this, 'articulos')">
                    <div class="resultados-tabla" id="art-excel-resultados"></div>
                </div>
                <div id="art-excel-modificar" style="display:none">
                    <p class="hint">Incluí el ID del artículo a modificar (lo ves en Consultar Stock).</p>
                    <button class="small secondary" onclick="descargarPlantilla('articulos_modificar')">Descargar plantilla Excel</button>
                    <div class="file-drop" onclick="document.getElementById('art-file-mod').click()">Click para elegir archivo .xlsx</div>
                    <input type="file" id="art-file-mod" accept=".xlsx" style="display:none" onchange="cargarExcelArticulos(this, 'articulos_modificar')">
                    <div class="resultados-tabla" id="art-excel-mod-resultados"></div>
                </div>
            </div>
        </div>

        <!-- STOCK: Depósitos -->
        <div class="section" id="depositos">
            <div class="ren-layout">
                <div class="ren-bases">
                    <div class="multibase-selector">
                        <label>Aplicar en</label>
                        <p class="hint" style="margin:4px 0 8px">Destildado = solo base activa</p>
                        <div id="dep-multibase-checklist"></div>
                    </div>
                </div>
                <div class="ren-articulos">
                    <label>Buscar depósito</label>
                    <select id="dep-mod-buscar" onchange="cargarDepositoParaModificar()"><option value="">Elegí un depósito...</option></select>
                    <div id="dep-mod-form" style="display:none">
                        <label>Nombre</label>
                        <input type="text" id="dep-mod-nombre">
                        <button class="full" onclick="guardarModificacionDeposito()">Guardar Cambios</button>
                    </div>
                </div>
            </div>
        </div>
    `,

    cxp: `
    <!-- CXP: Facturas -->
    <div id="cxp-facturas">
        <header class="cxp-header">
            <h1>📄 Cuentas a Pagar</h1>
            <span class="badge">Carga de Facturas</span>
        </header>
        
        <main class="cxp-main">
            <!-- Banner de mensajes -->
            <div id="cxpBanner" class="banner" style="display:none"></div>
            
            <!-- ===== CARD 1: DROPZONE ===== -->
            <div class="card">
                <div class="card-title">
                    <span class="step">1</span> Carga de Factura/s
                </div>
                
                <div class="dropzone" id="dropZone" data-tooltip="dropZone" style="position:relative; overflow:hidden; cursor:pointer;">
                    <div class="dz-icon">📄</div>
                    <div class="dz-title">Arrastrá o <span>hacé clic</span> para subir el archivo</div>
                    <div class="dz-sub">PDF · JPG · PNG · foto de celular</div>
                </div>
                
                <div class="file-info" id="fileInfo" data-tooltip="fileInfo">
                    <span class="file-icon">📎</span>
                    <span class="file-name" id="fileName">archivo.pdf</span>
                    <button class="btn btn-secondary btn-sm" id="btnLimpiarArchivos" data-tooltip="btnLimpiarArchivos">✕</button>
                </div>
                
                <div style="display:flex; gap:8px; margin-top:14px; flex-wrap:wrap;">
                    <button class="btn btn-primary btn-sm" id="btnParsear" data-tooltip="btnParsear">✨ Extraer facturas</button>
                    <button class="btn btn-secondary btn-sm" id="btnDebug" data-tooltip="btnDebug">🔍 Ver texto raw</button>
                </div>
            </div>
            
            <!-- ===== CARD 2: CONFIGURACIÓN ===== -->
            <div class="card" id="rendicionConfig" style="display:none">
                <div class="card-title">
                    <span class="step">2</span> Configuración del lote
                </div>
                
                <div class="grid grid-2">
                    <div class="field">
                        <label>Condición de pago</label>
                        <select id="rendCondPago" data-tooltip="rendCondPago"></select>
                    </div>
                </div>
                
                <div style="margin-top:14px; padding:16px; background:#dbeafe; border-radius:var(--radius); border:1px solid #93c5fd;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <input type="checkbox" id="toggleEventualGlobal" style="width:18px; height:18px; accent-color:var(--primary);" data-tooltip="toggleEventualGlobal">
                        <label for="toggleEventualGlobal" style="font-size:13px; font-weight:500; cursor:pointer; color:var(--text);">
                            Cargar todas como proveedor eventual
                        </label>
                    </div>
                    <div style="font-size:12px; color:var(--text-secondary); margin-top:2px; margin-left:28px;">
                        Todas las facturas se cargarán bajo el mismo proveedor
                    </div>
                    <div id="eventualGlobalPanel" style="display:none; margin-top:12px;">
                        <div class="field">
                            <label>Proveedor</label>
                            <div class="ac-wrap">
                                <input type="text" id="empSearch" placeholder="Buscar por nombre o código…">
                                <ul class="ac-list" id="empList"></ul>
                            </div>
                            <input type="hidden" id="empId">
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- ===== CARD 3: FACTURAS ===== -->
            <div id="facturasContainer"></div>
            
            <!-- ===== CARD 4: BOTONES FINALES ===== -->
            <div id="btnCargarTodo" style="display:none;">
                <div class="card" style="background:var(--bg); border:2px solid var(--primary);">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div>
                            <div style="font-size:14px; font-weight:600; color:var(--text);">
                                📦 Listo para cargar
                            </div>
                            <div style="font-size:12px; color:var(--text-secondary);">
                                Revisá todas las facturas antes de cargar
                            </div>
                        </div>
                        <div style="display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="btn btn-secondary" id="btnLimpiar" data-tooltip="btnLimpiar">🗑 Limpiar</button>
                            <button class="btn btn-primary" id="btnCargar" data-tooltip="btnCargar">⬆ Cargar todas las facturas</button>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
`,

    cotizaciones: `
        <!-- COTIZACIONES -->
        <div class="section active" id="cxp-cotizaciones">
            <div class="card">
                <div class="card-title">Cargar tipo de cambio</div>
                <div style="display:flex;gap:10px;align-items:flex-end;margin-bottom:16px;flex-wrap:wrap">
                    <div class="field" style="flex:0 0 160px">
                        <label>Fecha</label>
                        <input type="date" id="cotiDate">
                    </div>
                    <div class="field" style="flex:0 0 160px">
                        <label>DL → PS (cotización)</label>
                        <input type="number" id="cotiValor" step="0.00001" placeholder="ej: 7,61982">
                    </div>
                    <div class="field" style="flex:1">
                        <label>Aplicar a <span style="color:var(--err);font-size:11px">* obligatorio</span></label>
                        <div id="cotizacionesCheckboxes" style="display:flex;gap:6px;padding-top:8px;flex-wrap:wrap;"></div>
                    </div>
                    <button class="btn-primary" onclick="guardarCotizacion()">Guardar</button>
                </div>

                <div style="border-top:1px solid var(--border);padding-top:14px;margin-top:4px">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
                        <div class="card-title" style="margin-bottom:0">O importar desde Excel</div>
                        <a href="/api/cotizaciones/plantilla" download="plantilla_cotizaciones.xlsx" style="font-size:12px;color:var(--primary);text-decoration:none">⬇ Descargar plantilla</a>
                    </div>
                    <p style="font-size:12px;color:var(--ink-soft);margin-bottom:10px">Columna A: Fecha (DD/MM/AAAA) · Columna B: Cotización (separador decimal: coma)</p>
                    <div style="display:flex;gap:10px;align-items:center">
                        <input type="file" id="cotiExcel" accept=".xlsx,.xls" style="font-size:13px">
                        <button class="btn-secondary" onclick="importarExcelCoti()">Importar</button>
                    </div>
                    <div id="cotiPreview" style="margin-top:12px;display:none"></div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Últimas cotizaciones cargadas</div>
                <div id="cotiHistorico" style="font-size:13px;color:var(--ink-soft)">Cargando…</div>
            </div>
        </div>
    `,

   reportes: `
    <!-- REPORTES -->
    <div id="modulo-reportes" class="modulo-content" style="display:block;">
        <div class="reportes-header">
            <h2>📊 Reportes</h2>
            <p style="color:#64748b;">Seleccioná un reporte desde el menú lateral</p>
        </div>
        
        <!-- ===== REPORTE: PENDIENTE DE FACTURAR (CON FILTROS) ===== -->
        <div id="reporte-contratos" class="reporte-container active">
            <!-- Filtros de año y mes -->
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:16px;padding:12px 16px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">
                <div style="display:flex;align-items:center;gap:6px;">
                    <label style="font-size:12px;font-weight:500;color:#475569;">Año:</label>
                    <select id="filtro-anio" onchange="ejecutarReporte()" style="padding:4px 12px;border:1px solid #d1d5db;border-radius:4px;font-size:13px;background:white;cursor:pointer;min-width:100px;">
                        <option value="">Cargando...</option>
                    </select>
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                    <label style="font-size:12px;font-weight:500;color:#475569;">Mes:</label>
                    <select id="filtro-mes" onchange="ejecutarReporte()" style="padding:4px 12px;border:1px solid #d1d5db;border-radius:4px;font-size:13px;background:white;cursor:pointer;min-width:100px;">
                        <option value="">Todos</option>
                        <option value="1">Enero</option>
                        <option value="2">Febrero</option>
                        <option value="3">Marzo</option>
                        <option value="4">Abril</option>
                        <option value="5">Mayo</option>
                        <option value="6">Junio</option>
                        <option value="7">Julio</option>
                        <option value="8">Agosto</option>
                        <option value="9">Septiembre</option>
                        <option value="10">Octubre</option>
                        <option value="11">Noviembre</option>
                        <option value="12">Diciembre</option>
                    </select>
                </div>
                <button onclick="ejecutarReporte()" style="padding:6px 16px;background:#2563eb;color:white;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500;">🔍 Ejecutar</button>
                <button onclick="exportarExcel()" style="padding:6px 16px;background:#16a34a;color:white;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500;">📥 Exportar</button>
            </div>
            
            <!-- Resumen por moneda -->
            <div id="resumen-moneda"></div>
            
            <!-- Resumen anual -->
            <div style="background:white; border-radius:8px; padding:20px; margin-bottom:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                <h4 style="margin:0 0 15px 0;">📈 Resumen por Año/Mes</h4>
                <div id="resumen-anual"></div>
            </div>
            
            <!-- Botones de moneda -->
            <div style="margin-bottom:20px;">
                <div style="font-size:13px; color:#64748b; font-weight:600; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.04em;">
                    📋 Ver detalle por moneda:
                </div>
                <div style="display:flex; gap:10px; flex-wrap:wrap;">
                    <button class="btn-moneda active" data-moneda="PS" onclick="cambiarMoneda('PS')" style="padding:8px 24px; border-radius:8px; border:2px solid #2563eb; background:#2563eb; color:white; font-weight:600; cursor:pointer; transition:all 0.2s ease; box-shadow:0 2px 4px rgba(37,99,235,0.3);">
                        🇩🇴 PS
                    </button>
                    <button class="btn-moneda" data-moneda="DL" onclick="cambiarMoneda('DL')" style="padding:8px 24px; border-radius:8px; border:2px solid #16a34a; background:white; color:#16a34a; font-weight:600; cursor:pointer; transition:all 0.2s ease;">
                        💵 DL
                    </button>
                </div>
            </div>
            
            <!-- Tabla de datos -->
            <div class="tabla-container">
                <div id="loading-reporte" style="display:none; text-align:center; padding:40px;">⏳ Cargando datos...</div>
                <div id="tabla-dinamica"></div>
            </div>
        </div>
        
        <!-- ===== REPORTE: PENDIENTE DE COBRO ===== -->
        <div id="reporte-pendiente-cobro" class="reporte-container" style="display:none;">
            <!-- Contenido generado por JavaScript -->
        </div>
        
        <!-- ===== REPORTE: VENTAS POR PAÍS ===== -->
        <div id="reporte-consolidado-pais" class="reporte-container" style="display:none;">
            <!-- Contenido generado por JavaScript -->
        </div>
        
        <!-- ===== REPORTE: VENTAS GLOBALES ===== -->
        <div id="reporte-consolidado-total" class="reporte-container" style="display:none;">
            <!-- Contenido generado por JavaScript -->
        </div>
    </div>
`, 
};

// ============================================================
// CARGA DE TEMPLATES - REEMPLAZA EL CONTENIDO
// ============================================================

let templateInicializado = {};

function cargarTemplate(modulo) {
    const container = document.getElementById('module-content');
    if (!container) {
        console.warn('⚠️ No se encontró #module-content');
        return;
    }

    const template = TEMPLATES[modulo];
    if (!template) {
        // ✅ CORREGIDO: Sanitizar módulo antes de mostrarlo
        const moduloSanitizado = escapeHTML(modulo);
        container.innerHTML = `
            <div style="padding:40px;text-align:center;color:#e53e3e;">
                <h3>⚠️ Módulo ${moduloSanitizado} no disponible</h3>
            </div>
        `;
        return;
    }

    container.innerHTML = template;
    templateInicializado[modulo] = false;
    
    console.log(`✅ Template ${modulo} cargado (reemplazado)`);

    setTimeout(() => {
        inicializarModulo(modulo);
    }, 150);
}

function inicializarModulo(modulo) {
    if (templateInicializado[modulo]) {
        console.log(`ℹ️ Módulo ${modulo} ya inicializado`);
        return;
    }
    
    console.log(`🔧 Inicializando módulo: ${modulo}`);
    templateInicializado[modulo] = true;
    
    mostrarSeccionActiva(modulo);
    
    setTimeout(() => {
        switch(modulo) {
            case 'stock':
                if (typeof cargarSelectsStock === 'function') {
                    if (window.stockSelectsCargados) {
                        console.log('ℹ️ Selects de stock ya cargados, omitiendo...');
                    } else {
                        cargarSelectsStock();
                    }
                }
                break;
                
            case 'cxp':
                if (typeof cargarCondicionesPago === 'function') {
                    cargarCondicionesPago();
                }
                if (typeof window.inicializarCXP === 'function') {
                    setTimeout(() => {
                        console.log('🔄 Ejecutando window.inicializarCXP desde templates.js');
                        window.inicializarCXP();
                    }, 600);
                } else {
                    console.warn('⚠️ window.inicializarCXP no está disponible');
                    setTimeout(() => {
                        if (typeof window.inicializarCXP === 'function') {
                            console.log('🔄 Reintentando window.inicializarCXP');
                            window.inicializarCXP();
                        }
                    }, 1000);
                }
                break;
                
            case 'cotizaciones':
                generarCheckboxesCotizaciones();
                
                if (typeof cargarHistoricoCoti === 'function') {
                    const historico = document.getElementById('cotiHistorico');
                    if (historico && historico.innerHTML === 'Cargando…') {
                        cargarHistoricoCoti();
                    }
                }
                const today = new Date().toISOString().split('T')[0];
                const cotiDate = document.getElementById('cotiDate');
                if (cotiDate && !cotiDate.value) cotiDate.value = today;
                break;
                
            case 'reportes':
                const container = document.getElementById('reporte-contratos');
                if (container) {
                    container.style.display = 'block';
                    container.classList.add('active');
                }
                if (typeof cargarAnos === 'function') {
                    cargarAnos();
                }
                break;
                
            default:
                console.log(`📌 Módulo ${modulo} cargado sin inicialización específica`);
        }
    }, 300);
}

// ============================================================
// GENERAR CHECKBOXES DE COTIZACIONES (CON CONTROL GLOBAL)
// ============================================================

function generarCheckboxesCotizaciones() {
    if (window._cotizacionesCheckboxesGenerados) {
        console.log('ℹ️ Checkboxes de cotizaciones ya generados (global), omitiendo...');
        return;
    }
    
    const container = document.getElementById('cotizacionesCheckboxes');
    if (!container) {
        console.warn('⚠️ No se encontró #cotizacionesCheckboxes');
        return;
    }
    
    container.innerHTML = '';
    
    const paises = [
        { id: 'GT', label: 'GT'},
        { id: 'HN', label: 'HN'},
        { id: 'RD', label: 'RD'},
        { id: 'UY', label: 'UY'},
        { id: 'CO', label: 'CO'},
        { id: 'PE', label: 'PE'},
        { id: 'PY', label: 'PY'},
        { id: 'EC', label: 'EC'},
        { id: 'MX', label: 'MX'},
        { id: 'CR', label: 'CR'},
        { id: 'AR', label: 'AR'}
    ];
    
    paises.forEach(p => {
        const label = document.createElement('label');
        label.style.cssText = 'display:inline-flex;align-items:center;gap:4px;font-size:12px;cursor:pointer;padding:4px 8px;border:1px solid var(--border);border-radius:4px;margin:2px;';
        
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.id = `coti${p.id}`;
        input.value = p.id;
        
        label.appendChild(input);
        label.appendChild(document.createTextNode(`${p.label}`));
        container.appendChild(label);
    });
    
    window._cotizacionesCheckboxesGenerados = true;
    console.log('✅ Checkboxes de cotizaciones generados:', paises.length);
}

function mostrarSeccionActiva(modulo) {
    console.log(`🎯 Mostrando sección activa para: ${modulo}`);
    
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.modulo-content').forEach(el => el.style.display = 'none');
    
    if (modulo === 'reportes') {
        const el = document.getElementById('modulo-reportes');
        if (el) {
            el.style.display = 'block';
            console.log('✅ Reportes visible');
        }
        return;
    }
    
    if (modulo === 'stock') {
        const stockSection = document.getElementById('stock');
        if (stockSection) {
            stockSection.style.display = 'block';
            stockSection.classList.add('active');
            console.log('✅ Sección stock activada y visible');
            
            const otrasSecciones = ['ajuste-e', 'ajuste-s', 'transferencia', 'stock-consolidado', 'articulos', 'depositos'];
            otrasSecciones.forEach(id => {
                const el = document.getElementById(id);
                if (el && id !== 'stock') {
                    el.classList.remove('active');
                    el.style.display = 'none';
                }
            });
        } else {
            console.warn('⚠️ No se encontró #stock');
        }
        return;
    }
    
    const sectionMap = {
        'cxp': 'cxp-facturas',
        'cotizaciones': 'cxp-cotizaciones'
    };
    const sectionId = sectionMap[modulo];
    if (sectionId) {
        const el = document.getElementById(sectionId);
        if (el) {
            el.classList.add('active');
            console.log(`✅ Sección ${sectionId} activada`);
        } else {
            console.warn(`⚠️ No se encontró #${sectionId}`);
            if (modulo === 'cxp') {
                console.log('🔄 Reintentando cargar template CXP...');
                const container = document.getElementById('module-content');
                if (container && TEMPLATES.cxp) {
                    container.innerHTML = TEMPLATES.cxp;
                    console.log('✅ Template CXP recargado');
                    setTimeout(() => {
                        if (typeof window.inicializarCXP === 'function') {
                            window.inicializarCXP();
                        }
                    }, 500);
                }
            }
        }
    }
}

// ============================================================
// EXPONER FUNCIONES GLOBALES
// ============================================================

window.cargarTemplate = cargarTemplate;
window.generarCheckboxesCotizaciones = generarCheckboxesCotizaciones;
window.escapeHTML = escapeHTML;

console.log('✅ templates.js cargado (XSS sanitizado)');