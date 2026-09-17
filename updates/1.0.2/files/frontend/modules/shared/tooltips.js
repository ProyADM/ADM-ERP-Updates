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
    'moduloInicio': {
        titulo: '🏠 Inicio',
        descripcion: 'Panel de inicio con el resumen de stock, ventas y contratos.',
        accion: 'Es la pantalla que se abre al entrar.'
    },
    'moduloAdmin': {
        titulo: '⚙️ Administración',
        descripcion: 'Usuarios, roles y permisos, estado del almacén compartido, auditoría y accesos rechazados.',
        accion: 'Solo visible para quien tenga el permiso de administración.'
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
    },
    'drawerVentasPais': {
        titulo: '🌍 Ventas por País',
        descripcion: 'Ventas del país de la base activa, mes por mes.',
        accion: 'Toma las cuentas 410101/410102 y descuenta las operaciones entre empresas del grupo.'
    },
    // Estas cuatro claves ya estaban referenciadas en index.html pero NUNCA se
    // habían definido: las pestañas de reportes del menú lateral quedaban sin
    // ícono de ayuda (y el sistema avisaba por consola "Tooltip no encontrado").
    'drawerReportesPendienteFacturar': {
        titulo: '📄 Pendiente de Facturar',
        descripcion: 'Contratos y trabajos pendientes de facturar.',
        accion: 'Permite exportar el listado a Excel.'
    },
    'drawerReportesPendienteCobro': {
        titulo: '💰 Pendiente de Cobro',
        descripcion: 'Saldos pendientes de cobro, agrupados por cliente con subtotales.',
        accion: 'Usá el botón ↻ Actualizar para volver a consultar.'
    },
    'drawerReportesConsolidadoPais': {
        titulo: '🌍 Ventas por País',
        descripcion: 'Ventas de la base activa, mes por mes y por cuenta contable.',
        accion: 'Se puede filtrar por año y exportar a Excel.'
    },
    'drawerReportesConsolidadoTotal': {
        titulo: '🌐 Ventas Globales',
        descripcion: 'Consolidado de ventas de todas las bases habilitadas para tu usuario.',
        accion: 'Si tenés bases acotadas, el reporte avisa que el total es parcial.'
    },
    'proveedorEventual': {
        titulo: '👤 Proveedor eventual',
        descripcion: 'Marca la factura como de un proveedor sin alta en el sistema.',
        accion: 'Se carga el nombre o la razón social a mano en el comprobante.'
    },
    'drawerVentasGlobales': {
        titulo: '🌐 Ventas Globales',
        descripcion: 'Consolidado de ventas de todas las bases a las que tenés acceso.',
        accion: 'Si tu usuario tiene bases acotadas, el reporte aclara que es parcial.'
    },
    'drawerPendienteCobro': {
        titulo: '💰 Pendiente de Cobro',
        descripcion: 'Saldos pendientes de cobro agrupados por cliente.',
        accion: 'Usá el botón Actualizar para volver a consultar.'
    },
    'drawerPendienteFacturar': {
        titulo: '📄 Pendiente de Facturar',
        descripcion: 'Contratos y trabajos pendientes de facturar.',
        accion: 'Permite exportar el listado a Excel.'
    },
    'drawerAdminUsuarios': {
        titulo: '👤 Usuarios (administración)',
        descripcion: 'Alta y edición de usuarios, con sus roles, bases y permisos.',
        accion: 'Un usuario que no esté acá no puede entrar: el sistema no los crea solo.'
    },
    'drawerAdminDiagnostico': {
        titulo: '🩺 Diagnóstico',
        descripcion: 'Responde "¿por qué no anda?": comprueba si el servidor SQL responde en cada base, si el canal de actualizaciones se puede consultar, de dónde lee esta PC los usuarios y si se puede escribir en esas carpetas.',
        accion: 'Abajo muestra los errores que registró la aplicación, con el detalle técnico para copiar y enviar.'
    },
    'adminDiagRefrescar': {
        titulo: '🔄 Volver a comprobar',
        descripcion: 'Vuelve a probar el SQL de cada base y el canal de actualizaciones ahora mismo.',
        accion: 'La comprobación normal se guarda 45 segundos para no castigar al servidor; este botón la fuerza.'
    },
    'adminDiagBuscar': {
        titulo: '🔎 Filtrar errores',
        descripcion: 'Filtra la lista de errores por tipo o por texto del mensaje.',
        accion: 'Sirve para encontrar rápido, por ejemplo, todos los de conexión.'
    },
    'adminDiagRecargar': {
        titulo: '📄 Recargar errores',
        descripcion: 'Vuelve a leer el archivo de registro de la aplicación.',
        accion: 'Solo lee el log: no sondea el SQL y es instantáneo.'
    },
    'adminDiagDetalle': {
      titulo: '🔍 Detalle técnico',
      descripcion: 'Muestra el error completo tal como quedó registrado, con su traza.',
      accion: 'Desde ahí se puede copiar para enviarlo a soporte o a TI.'
    },
    'adminDiagCopiar': {
      titulo: '📋 Copiar detalle',
      descripcion: 'Copia el texto técnico completo al portapapeles.',
      accion: 'Si el navegador bloquea el portapapeles, el texto queda seleccionado para copiar con Ctrl+C.'
    },
    'drawerAdminRoles': {
        titulo: '🔑 Roles y permisos',
        descripcion: 'Define qué puede hacer cada rol del sistema.',
        accion: 'Los permisos marcados "sin efecto todavía" están en el catálogo pero ningún control los verifica hoy.'
    },
    'drawerAdminEstado': {
        titulo: '🗄️ Estado del almacén',
        descripcion: 'Muestra si esta PC está leyendo el almacén central de usuarios y permisos.',
        accion: 'Debe decir "central" y mostrar el mismo sello que las demás PCs.'
    },
    'drawerAdminAuditoria': {
        titulo: '🧾 Auditoría',
        descripcion: 'Registro de quién cambió qué y cuándo (usuarios, roles y configuración).',
        accion: 'Los cambios viajan al almacén compartido, así que se ven desde todas las PCs.'
    },
    'drawerAdminAccesos': {
        titulo: '🚫 Accesos rechazados',
        descripcion: 'Personas que intentaron entrar y el sistema no reconoció (usuario no dado de alta, desactivado o bloqueado).',
        accion: 'Desde acá se los puede dar de alta con un clic.'
    },
    'barraBase': {
        titulo: '🌍 Base activa',
        descripcion: 'País o división sobre el que trabajan los módulos (stock, CxP y reportes).',
        accion: 'Solo podés elegir las bases que tu usuario tiene permitidas.'
    },
    'barraUsuario': {
        titulo: '👤 Usuario conectado',
        descripcion: 'Muestra quién está operando y con qué rol.',
        accion: 'Los permisos del backend son los que manda: la interfaz solo oculta lo que no podés usar.'
    },
    'barraNotificaciones': {
        titulo: '🔔 Notificaciones',
        descripcion: 'Avisos de movimientos recientes del sistema (por ejemplo, cargas hechas por otros usuarios).',
        accion: 'El número rojo indica cuántos avisos nuevos hay sin leer.'
    },
    'botonActualizar': {
        titulo: '🔄 Actualizar',
        descripcion: 'Vuelve a consultar los datos al servidor.',
        accion: 'Útil cuando otra persona cargó movimientos hace instantes.'
    },

    // ===== ADMINISTRACIÓN - Vistas del panel =====
    'adminChipEstado': {
        titulo: '🗄️ Estado del almacén',
        descripcion: 'Indica de dónde lee esta PC los usuarios, roles y permisos.',
        accion: '"central" = comparte con las demás PCs; "local" o "degradado" = está usando una copia propia y los cambios no se propagan.'
    },
    'adminUsuariosBuscar': {
        titulo: '🔎 Buscar usuario',
        descripcion: 'Filtra la lista por usuario de Windows, nombre o email.',
        accion: 'La búsqueda es sobre los usuarios ya cargados en la lista.'
    },
    'adminUsuariosNuevo': {
        titulo: '➕ Nuevo usuario',
        descripcion: 'Da de alta a una persona para que pueda entrar al ERP.',
        accion: 'El usuario debe existir en Windows/AD: acá se lo habilita y se le asignan roles, bases y permisos.'
    },
    'adminUsuarioUsername': {
        titulo: '🪟 Usuario de Windows',
        descripcion: 'El nombre con el que la persona inicia sesión en su PC (sin dominio), por ejemplo jbonaldi.',
        accion: 'Si no coincide exactamente con el de Windows, el sistema no la reconoce y le responde "usuario no autorizado".'
    },
    'adminUsuarioNombre': {
        titulo: '🏷️ Nombre',
        descripcion: 'Nombre y apellido que se muestra en la interfaz.',
        accion: 'Es solo para mostrar: no interviene en el login.'
    },
    'adminUsuarioEmail': {
        titulo: '✉️ Email',
        descripcion: 'Correo de la persona, usado en avisos y reportes.',
        accion: 'Opcional, pero conviene completarlo.'
    },
    'adminUsuarioRoles': {
        titulo: '🔑 Roles del usuario',
        descripcion: 'Los permisos salen del o los roles asignados.',
        accion: 'Se pueden sumar o restar permisos puntuales más abajo, sin cambiar el rol.'
    },
    'adminUsuarioBases': {
        titulo: '🌍 Bases permitidas',
        descripcion: 'Países o divisiones que esta persona puede consultar y operar.',
        accion: '"Todas las bases" guarda el comodín (*) y es lo único que habilita los reportes multi-base.'
    },
    'adminUsuarioBaseDefault': {
        titulo: '🏁 Base por defecto',
        descripcion: 'Es la base con la que esta persona ARRANCA la aplicación al entrar.',
        accion: 'No es un permiso: si tiene varias bases permitidas, después puede cambiarse. Solo se pueden elegir bases que tenga permitidas.'
    },
    'adminUsuarioModulos': {
        titulo: '🧩 Módulos permitidos',
        descripcion: 'Módulos que le aparecen disponibles (stock, CxP, cotizaciones, reportes).',
        accion: '"Todos los módulos" guarda el comodín (*).'
    },
    'adminUsuarioPermisosExtra': {
        titulo: '➕ Permisos extra',
        descripcion: 'Permisos que se AGREGAN a los que ya da el rol.',
        accion: 'Usalo para dar una excepción puntual sin crear un rol nuevo.'
    },
    'adminUsuarioPermisosRestringidos': {
        titulo: '➖ Permisos restringidos',
        descripcion: 'Permisos que se QUITAN de los que da el rol.',
        accion: 'Gana la restricción: si está acá, el usuario no puede hacerlo aunque su rol lo permita.'
    },
    'adminUsuarioActivo': {
        titulo: '✅ Activo',
        descripcion: 'Si está destildado, la persona no puede entrar (el sistema responde "usuario desactivado").',
        accion: 'Es la forma prolija de dar de baja temporalmente sin borrar la cuenta.'
    },
    'adminUsuarioBloqueado': {
        titulo: '🚫 Bloqueado',
        descripcion: 'Bloquea el acceso sin desactivar la cuenta (el sistema responde "usuario bloqueado").',
        accion: 'Se usa ante un uso indebido o una investigación en curso.'
    },
    'adminUsuarioGuardar': {
        titulo: '💾 Guardar',
        descripcion: 'Aplica los cambios y los publica en el almacén compartido.',
        accion: 'Las demás PCs los toman en pocos segundos, sin reiniciar la aplicación.'
    },
    'adminGrupoPlegarTodos': {
        titulo: '📂 Colapsar / Expandir todo',
        descripcion: 'Cierra todos los grupos de permisos de una sola vez, o los vuelve a abrir.',
        accion: 'Cada grupo se abre y se cierra por separado haciendo clic en su título, y el navegador recuerda cómo los dejaste.'
    },
    'adminRolTildarGrupo': {
        titulo: '☑️ Tildar/destildar todo el grupo',
        descripcion: 'Marca o desmarca de una sola vez todos los permisos de ese grupo.',
        accion: 'Después podés destildar los que no correspondan.'
    },
    'adminRolNombre': {
        titulo: '🏷️ Nombre del rol',
        descripcion: 'Cómo se llama el rol en la interfaz y en el editor de usuarios.',
        accion: 'El identificador (sin espacios) no se puede cambiar una vez creado.'
    },
    'adminRolDescripcion': {
        titulo: '📝 Descripción del rol',
        descripcion: 'Explica para qué sirve el rol, para que otro administrador lo entienda.',
        accion: 'Recomendado: deja claro a quién está destinado.'
    },
    'adminRolPermisos': {
        titulo: '🔐 Permisos del rol',
        descripcion: 'Cada tarjeta es un permiso: lo que quede tildado es lo que este rol puede hacer.',
        accion: 'Los marcados "sin efecto todavía" están en el catálogo pero hoy ningún control del backend los verifica.'
    },
    'adminRolNuevo': {
        titulo: '➕ Nuevo rol',
        descripcion: 'Crea un rol nuevo, sin permisos, para después tildárselos.',
        accion: 'Conviene crear el rol y recién después asignárselo a los usuarios.'
    },
    'adminRolId': {
        titulo: '🆔 Identificador del rol',
        descripcion: 'Nombre técnico del rol, sin espacios ni acentos (por ejemplo "deposito").',
        accion: 'No se puede cambiar después de creado: es el que queda guardado en cada usuario.'
    },
    'adminRolGuardar': {
        titulo: '💾 Guardar permisos',
        descripcion: 'Aplica los permisos tildados al rol y los publica en el almacén compartido.',
        accion: 'Los usuarios con ese rol reciben el cambio en pocos segundos, sin reiniciar la aplicación.'
    },
    'adminRolCrear': {
        titulo: '➕ Crear rol',
        descripcion: 'Da de alta el rol con el identificador y el nombre elegidos.',
        accion: 'El rol nace sin permisos: se los tildás en la pantalla siguiente.'
    },
    'adminEstadoRecargar': {
        titulo: '🔄 Traer cambios ahora',
        descripcion: 'Fuerza la relectura del almacén compartido sin esperar el intervalo automático.',
        accion: 'Útil justo después de que otra PC cambió usuarios o permisos.'
    },
    'adminEstadoRespaldo': {
        titulo: '💾 Respaldo del almacén',
        descripcion: 'Copia de seguridad de usuarios, roles y permisos.',
        accion: 'Sirve como rollback si un cambio deja a alguien sin acceso.'
    },
    'adminAuditoriaExportar': {
        titulo: '⬇️ Exportar auditoría',
        descripcion: 'Descarga el registro de cambios para revisarlo o archivarlo.',
        accion: 'Incluye quién hizo el cambio, cuándo y sobre qué usuario o rol.'
    },
    'adminAccesoAlta': {
        titulo: '➕ Dar de alta',
        descripcion: 'Crea el usuario en el ERP a partir del intento rechazado, con el nombre ya escrito.',
        accion: 'Es la vía más rápida cuando alguien no puede entrar por no estar dado de alta.'
    },
    'adminAuditoriaBuscar': {
        titulo: '🔎 Filtrar auditoría',
        descripcion: 'Filtra los movimientos por acción o por usuario.',
        accion: 'Se filtra sobre los eventos ya traídos (los últimos 30 días).'
    },
    'adminAuditoriaMas': {
        titulo: '➕ Mostrar más',
        descripcion: 'Trae más eventos de auditoría (de a 100 por vez).',
        accion: 'El servidor entrega como máximo 500 eventos por consulta.'
    },
    'adminEstadoImportar': {
        titulo: '📂 Ruta del respaldo',
        descripcion: 'Ruta del archivo de respaldo en el disco de la PC donde corre el ERP (no en el navegador).',
        accion: 'Es la ruta que devolvió "Exportar respaldo", por ejemplo data\\config_export_20260912_190000.json.'
    },
    'adminEstadoImportarBtn': {
        titulo: '⚠️ Importar respaldo',
        descripcion: 'Reemplaza los usuarios, roles y permisos del almacén por los del archivo indicado.',
        accion: 'Es una operación destructiva: revisá que el archivo sea el correcto antes de confirmar.'
    }
};