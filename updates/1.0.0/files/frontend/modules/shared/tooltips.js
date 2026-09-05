// ============================================================
// TOOLTIPS - Configuración centralizada para TODO el ERP
// ============================================================

export const TOOLTIPS = {
    // ===== TOPBAR - Navegación principal =====
    'moduloStock': {
        titulo: '📦 Módulo Stock',
        descripcion: 'Gestioná el inventario de artículos, depósitos y movimientos de stock.',
        accion: 'Incluye consultas, ajustes, transferencias y edición de artículos.'
    },
    'moduloCxp': {
        titulo: '💳 Módulo CxP',
        descripcion: 'Cuentas a Pagar - Cargá y gestioná facturas de proveedores.',
        accion: 'Extrae datos automáticamente desde PDFs o imágenes.'
    },
    'moduloCotizaciones': {
        titulo: '💱 Módulo Cotizaciones',
        descripcion: 'Consultá y administrá los tipos de cambio de monedas.',
        accion: 'Se actualiza automáticamente con fuentes oficiales.'
    },
    'moduloReportes': {
        titulo: '📊 Módulo Reportes',
        descripcion: 'Generá reportes de diferentes áreas del sistema.',
        accion: 'Podés filtrar por fechas y criterios específicos.'
    },
    'selectorBase': {
        titulo: '🌍 Seleccionar Base',
        descripcion: 'Cambiá entre las diferentes bases de datos (Guatemala, República Dominicana, etc.).',
        accion: 'Cada base tiene su propia configuración contable y fiscal.'
    },
    'selectorSociedad': {
        titulo: '🏢 Seleccionar Sociedad',
        descripcion: 'Cambiá entre las diferentes sociedades o empresas del sistema.',
        accion: 'Cada sociedad tiene su propia configuración y datos.'
    },

    // ===== CXP - Carga de Facturas =====
    'dropZone': {
        titulo: '📂 Área de carga',
        descripcion: 'Arrastrá tus archivos PDF, JPG o PNG aquí, o hacé clic para seleccionarlos desde tu computadora.',
        accion: 'Soportamos archivos individuales o múltiples facturas en un solo PDF.'
    },
    'btnParsear': {
        titulo: '✨ Extraer facturas',
        descripcion: 'Procesa los archivos seleccionados y extrae automáticamente los datos de las facturas (número, fecha, monto, emisor, etc.).',
        accion: 'Usa IA para reconocer facturas de diferentes formatos.'
    },
    'btnCargar': {
        titulo: '⬆ Cargar todas las facturas',
        descripcion: 'Guarda todas las facturas procesadas en el sistema contable.',
        accion: 'Verifica que cada factura tenga su cuenta contable asignada antes de cargar.'
    },
    'btnLimpiar': {
        titulo: '🧹 Limpiar todo',
        descripcion: 'Elimina todas las facturas de la interfaz y reinicia el proceso de carga.',
        accion: 'No afecta facturas ya cargadas en el sistema.'
    },
    'btnDebug': {
        titulo: '🔍 Ver texto raw',
        descripcion: 'Muestra el texto extraído del PDF en la consola del navegador (F12).',
        accion: 'Útil para verificar qué datos está reconociendo el sistema.'
    },
    'toggleEventualGlobal': {
        titulo: '👤 Proveedor eventual',
        descripcion: 'Activa el modo "Proveedor eventual" para todas las facturas del lote.',
        accion: 'Úsalo cuando los emisores no están registrados como proveedores en el sistema.'
    },
    'rendCondPago': {
        titulo: '💳 Condición de pago',
        descripcion: 'Selecciona la condición de pago que se aplicará a todas las facturas del lote.',
        accion: 'La opción "00 · CONTADO" es la más común para facturas de gastos.'
    },
    'eliminarFactura': {
        titulo: '🗑️ Eliminar factura',
        descripcion: 'Elimina esta factura del sistema (solo si ya fue cargada en la base de datos).',
        accion: 'Si la factura aún no fue cargada, solo la elimina de la lista.'
    },
    'fechaFacturaInput': {
        titulo: '📅 Fecha de emisión',
        descripcion: 'Fecha en que se emitió la factura.',
        accion: 'El sistema la extrae automáticamente del documento.'
    },
    'tipoFacturaSelect': {
        titulo: '🏷️ Tipo de factura',
        descripcion: 'FCP = Factura con IVA (12%), FCC = Pequeño Contribuyente (exento de IVA).',
        accion: 'Determina cómo se calcula el IVA y la retención.'
    },
    'monedaFacturaSelect': {
        titulo: '💱 Moneda',
        descripcion: 'PS = Quetzales (moneda local), DL = Dólares.',
        accion: 'Si seleccionás Dólares, se usará la cotización del día de la fecha.'
    },
    'totalFacturaInput': {
        titulo: '💰 Total factura',
        descripcion: 'Monto total de la factura (incluye IVA).',
        accion: 'El sistema calcula automáticamente el bruto y el IVA a partir de este valor.'
    },
    'brutoFacturaInput': {
        titulo: '💰 Bruto (sin IVA)',
        descripcion: 'Monto base de la factura antes de aplicar el IVA.',
        accion: 'Se calcula automáticamente y se valida con la suma de los renglones.'
    },
    'ivaFacturaInput': {
        titulo: '💰 IVA',
        descripcion: 'Impuesto al Valor Agregado (12% para FCP, 0% para FCC).',
        accion: 'Se calcula automáticamente a partir del total.'
    },
    'descripcionFacturaInput': {
        titulo: '📝 Descripción',
        descripcion: 'Concepto o motivo del gasto. Sirve para identificar la factura en reportes.',
        accion: 'El sistema sugiere una descripción automática que podés modificar.'
    },
    'agregarRenglonBtn': {
        titulo: '➕ Agregar renglón',
        descripcion: 'Agregá una nueva línea contable para distribuir el gasto.',
        accion: 'Cada renglón debe tener una cuenta contable y un importe.'
    },
    'eliminarRenglonBtn': {
        titulo: '✕ Eliminar renglón',
        descripcion: 'Eliminá esta línea contable.',
        accion: 'El importe se restará del total del bruto.'
    },
    'btnLimpiarArchivos': {
        titulo: '🧹 Limpiar archivos',
        descripcion: 'Elimina los archivos seleccionados de la lista.',
        accion: 'No afecta las facturas ya procesadas.'
    },
    'btnSeleccionarArchivos': {
        titulo: '📎 Seleccionar archivos',
        descripcion: 'Hacé clic para buscar archivos en tu computadora.',
        accion: 'Soportamos PDFs, imágenes JPG/PNG y fotos de celular.'
    },
    'fileInfo': {
        titulo: '📋 Archivos seleccionados',
        descripcion: 'Lista de archivos que serán procesados al hacer clic en "Extraer facturas".',
        accion: 'Podés agregar más archivos o limpiar la selección.'
    },
    'cotizacionInput': {
        titulo: '💱 Cotización',
        descripcion: 'Valor de la moneda extranjera en quetzales.',
        accion: 'Se carga automáticamente según la fecha de la factura.'
    },
    'providHidden': {
        titulo: '🔢 ID del proveedor',
        descripcion: 'Identificador único del proveedor en el sistema.',
        accion: 'Se asigna automáticamente al seleccionar un proveedor.'
    },
    'cuentaContable': {
        titulo: '🔢 Cuenta contable',
        descripcion: 'Cuenta del plan contable que se debitará con este gasto.',
        accion: 'Escribí el código o nombre de la cuenta para buscarla automáticamente.'
    },
    'importeRenglon': {
        titulo: '💵 Importe',
        descripcion: 'Monto bruto (sin IVA) que se asignará a esta cuenta contable.',
        accion: 'La suma de los importes debe coincidir con el bruto total de la factura.'
    },
    'centroCosto': {
        titulo: '🏢 Centro de costo',
        descripcion: 'Centro de costo al que se imputa el gasto (solo para cuentas que lo requieren).',
        accion: 'Algunas cuentas contables requieren obligatoriamente un centro de costo.'
    },

    // ===== STOCK =====
    'stockBuscar': {
        titulo: '🔍 Buscar artículo',
        descripcion: 'Buscá artículos por código, nombre o descripción.',
        accion: 'Podés usar el código de barras o el nombre completo.'
    },
    'stockAjuste': {
        titulo: '📦 Ajuste de stock',
        descripcion: 'Agregá o quitá unidades de un artículo en un depósito específico.',
        accion: 'El ajuste genera un movimiento de stock registrado.'
    },
    'stockTransferencia': {
        titulo: '🔄 Transferencia',
        descripcion: 'Mové artículos entre diferentes depósitos.',
        accion: 'Se registra como egreso en origen y ingreso en destino.'
    },
    'stockCodigoBuscar': {
        titulo: '🔍 Código o nombre',
        descripcion: 'Buscá artículos por código, nombre o descripción.',
        accion: 'Podés usar el código de barras o el nombre completo.'
    },
    'stockDepositoFiltrar': {
        titulo: '🏢 Filtrar por depósito',
        descripcion: 'Filtrá los resultados por un depósito específico.',
        accion: 'Mostrará solo el stock del depósito seleccionado.'
    },
    'stockResultados': {
        titulo: '📊 Resultados de búsqueda',
        descripcion: 'Lista de artículos que coinciden con tu búsqueda.',
        accion: 'Hacé clic en un artículo para ver su detalle.'
    },
    'stockAjusteCodigo': {
        titulo: '📦 Código del artículo',
        descripcion: 'Código único del artículo a ajustar.',
        accion: 'Podés buscarlo escribiendo el código o nombre.'
    },
    'stockAjusteDeposito': {
        titulo: '🏢 Depósito',
        descripcion: 'Depósito donde se realizará el ajuste.',
        accion: 'El ajuste afecta solo a este depósito.'
    },
    'stockAjusteCantidad': {
        titulo: '🔢 Cantidad',
        descripcion: 'Cantidad de unidades a agregar o quitar.',
        accion: 'Usá números positivos para agregar, negativos para quitar.'
    },
    'stockAjusteMotivo': {
        titulo: '📝 Motivo del ajuste',
        descripcion: 'Razón por la cual se realiza el ajuste.',
        accion: 'Ej: "Ingreso por compra", "Merma", "Corrección".'
    },
    'stockTransferenciaOrigen': {
        titulo: '🏢 Depósito origen',
        descripcion: 'Depósito desde donde se retiran las unidades.',
        accion: 'Debe tener stock disponible del artículo.'
    },
    'stockTransferenciaDestino': {
        titulo: '🏢 Depósito destino',
        descripcion: 'Depósito donde se recibirán las unidades.',
        accion: 'Puede ser el mismo u otro depósito.'
    },
    'stockTransferenciaCantidad': {
        titulo: '🔢 Cantidad a transferir',
        descripcion: 'Unidades que se moverán del origen al destino.',
        accion: 'No puede ser mayor al stock disponible en origen.'
    },
    'stockArticuloCrear': {
        titulo: '➕ Crear artículo',
        descripcion: 'Agregá un nuevo artículo al sistema.',
        accion: 'Completá todos los campos obligatorios.'
    },
    'stockArticuloModificar': {
        titulo: '✏️ Modificar artículo',
        descripcion: 'Editá los datos de un artículo existente.',
        accion: 'Buscá el artículo por código o nombre.'
    },
    'stockArticuloExcel': {
        titulo: '📊 Cargar Excel',
        descripcion: 'Cargá múltiples artículos desde un archivo Excel.',
        accion: 'Descargá la plantilla para conocer el formato requerido.'
    },

    // ===== COTIZACIONES =====
    'cotizacionMoneda': {
        titulo: '💱 Tipo de cambio',
        descripcion: 'Valor de la moneda extranjera en quetzales para la fecha seleccionada.',
        accion: 'Se actualiza automáticamente con el BCR.'
    },
    'cotizacionFecha': {
        titulo: '📅 Fecha de cotización',
        descripcion: 'Fecha para la cual se consulta el tipo de cambio.',
        accion: 'Se usa el tipo de cambio vigente en esa fecha.'
    },
    'cotizacionMonedaOrigen': {
        titulo: '💱 Moneda origen',
        descripcion: 'Moneda desde la cual se quiere convertir.',
        accion: 'Ej: USD, EUR, etc.'
    },
    'cotizacionMonedaDestino': {
        titulo: '💱 Moneda destino',
        descripcion: 'Moneda a la cual se quiere convertir.',
        accion: 'Generalmente PS (Quetzales).'
    },
    'cotizacionValor': {
        titulo: '💰 Valor de cotización',
        descripcion: 'Precio de la moneda origen en moneda destino.',
        accion: 'Se actualiza automáticamente.'
    },
    'cotizacionActualizar': {
        titulo: '🔄 Actualizar cotización',
        descripcion: 'Forzar la actualización del tipo de cambio desde la fuente oficial.',
        accion: 'Útil si la cotización no se actualizó automáticamente.'
    },

    // ===== REPORTES =====
    'reporteFecha': {
        titulo: '📅 Rango de fechas',
        descripcion: 'Seleccioná el período para generar el reporte.',
        accion: 'Podés usar fechas predefinidas o personalizadas.'
    },
    'reporteTipo': {
        titulo: '📊 Tipo de reporte',
        descripcion: 'Seleccioná el tipo de reporte que deseas generar.',
        accion: 'Cada reporte muestra información específica.'
    },
    'reporteFechaInicio': {
        titulo: '📅 Fecha inicial',
        descripcion: 'Fecha de inicio del período a reportar.',
        accion: 'Incluye los registros desde esta fecha.'
    },
    'reporteFechaFin': {
        titulo: '📅 Fecha final',
        descripcion: 'Fecha de fin del período a reportar.',
        accion: 'Incluye los registros hasta esta fecha.'
    },
    'reporteFormato': {
        titulo: '📄 Formato de salida',
        descripcion: 'Formato en el que se generará el reporte.',
        accion: 'Opciones: PDF, Excel, CSV, etc.'
    },
    'reporteGenerar': {
        titulo: '🔄 Generar reporte',
        descripcion: 'Ejecutar la generación del reporte con los filtros seleccionados.',
        accion: 'El reporte se descargará automáticamente.'
    },

    // ===== DRAWER - Menú lateral =====
    'drawerStockConsultar': {
        titulo: '📦 Consultar Stock',
        descripcion: 'Ver el stock actual de todos los artículos en los depósitos.',
        accion: 'Podés filtrar por código, nombre o categoría.'
    },
    'drawerStockConsolidado': {
        titulo: '📊 Stock Consolidado',
        descripcion: 'Vista resumida del stock total por artículo, sumando todos los depósitos.',
        accion: 'Ideal para ver disponibilidad global.'
    },
    'drawerAjusteMas': {
        titulo: '➕ Ajuste +',
        descripcion: 'Agregar unidades a un artículo en un depósito específico.',
        accion: 'Usado para ingresos de mercadería o correcciones positivas.'
    },
    'drawerAjusteMenos': {
        titulo: '➖ Ajuste -',
        descripcion: 'Quitar unidades de un artículo en un depósito específico.',
        accion: 'Usado para egresos, ventas o correcciones negativas.'
    },
    'drawerTransferencia': {
        titulo: '🔄 Transferencia',
        descripcion: 'Mover unidades de un artículo entre diferentes depósitos.',
        accion: 'Se registra como egreso en origen e ingreso en destino.'
    },
    'drawerArticulos': {
        titulo: '📝 Artículos',
        descripcion: 'Crear, modificar o cargar artículos en el sistema.',
        accion: 'Podés crear individualmente o cargar desde Excel.'
    },
    'drawerDepositos': {
        titulo: '🏢 Depósitos',
        descripcion: 'Administrar los depósitos o almacenes del sistema.',
        accion: 'Cada depósito puede tener su propia ubicación y responsable.'
    },
    'drawerCxpFacturas': {
        titulo: '💳 Facturas CxP',
        descripcion: 'Cargar facturas de proveedores desde PDFs o imágenes.',
        accion: 'El sistema extrae los datos automáticamente.'
    },
    'drawerCotizaciones': {
        titulo: '💱 Tipo de Cambio',
        descripcion: 'Consultar y administrar las cotizaciones de monedas.',
        accion: 'Se actualiza automáticamente con el BCR.'
    },
    'drawerReportes': {
        titulo: '📊 Reportes',
        descripcion: 'Generar reportes de contratos y otras áreas.',
        accion: 'Podés filtrar por fechas y criterios específicos.'
    }
};