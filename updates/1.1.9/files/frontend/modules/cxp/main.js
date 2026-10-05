// ============================================================
// MAIN - FUNCIONES PRINCIPALES (CON SANITIZACIÓN)
// ============================================================

import { mostrarMsg, mostrarAviso, mostrarErrores, mostrarProgreso, ocultarProgreso,
         baseCxPHabilitada } from './ui.js';
import { renderFacturas } from './render.js';

// ============================================================
// COMPUERTA POR BASE (el circuito es de Guatemala)
// ============================================================
// Medido el 03/10/2026 con una captura del usuario: estando en la base RD se podia
// arrastrar un comprobante y quedaban a la vista la configuracion del lote y el boton
// "Cargar todas las facturas". El bloqueo visual era "esconder tarjetas" y el propio
// parseo las volvia a mostrar (ver `validarBaseCxP`), y las acciones no tenian guarda:
// `window.parsearFacturas()` desde la consola pasaba derecho.
//
// La escritura en el ERP nunca estuvo en riesgo: el servicio rechaza la base sin CxP
// (`CXP_VAL_BASE`). Esto cierra la pantalla y la extraccion, con el backend como ultima
// palabra (`/parsear_pdf` y `/debug_pdf` rechazan la misma base).

/**
 * Corta la accion si la base activa no tiene CxP habilitado. Devuelve `true` si bloqueo.
 *
 * Lo llaman las tres acciones que tocan un archivo o cargan un comprobante. El aviso es
 * por si la accion se dispara igual (drag&drop sobre un nodo oculto, consola del
 * navegador): la pantalla ya muestra el cartel.
 */
function bloqueadoPorBase() {
    if (baseCxPHabilitada()) return false;
    mostrarAviso('El cargador de facturas es exclusivo de Guatemala: cambiá la base para usarlo.',
                 [], 'err');
    return true;
}

// ============================================================
// ARCHIVOS YA LEIDOS (el parseo ACUMULA, no reemplaza)
// ============================================================
// Reportado y reproducido EN PANTALLA por el usuario el 03/10/2026: cargar 3 comprobantes,
// apretar "＋ Agregar más", sumar 1 y perder los 3 (quedaba solo el ultimo archivo). Eran
// dos lineas: `handleFiles` reemplazaba `window.currentFiles` y `parsearFacturas` arrancaba
// con `window.facturasData = []`.
//
// Ahora la lista de archivos y la de comprobantes solo CRECEN, se lee unicamente el archivo
// que todavia no se leyo, y el render agrega las tarjetas nuevas sin repintar las viejas
// (repintarlas perderia lo que el operador ya corrigio a mano).
//
// El registro sigue a la LISTA DE COMPROBANTES, no a la barra de adjuntos: lo vacia
// "Limpiar" (que tambien vacia los comprobantes). "Limpiar archivos" solo saca los adjuntos
// y por eso NO lo toca: volver a agregar el mismo archivo avisa que ya se extrajo, en vez
// de duplicar tarjetas.
window.archivosParseados = window.archivosParseados || [];

/** Identidad de un archivo para no volver a leerlo: nombre + tamano + fecha. */
function claveArchivo(archivo) {
    return `${archivo.name}|${archivo.size}|${archivo.lastModified || 0}`;
}

// ============================================================
// FUNCIÓN DE SANITIZACIÓN
// ============================================================

function sanitizarValor(val) {
    if (val === undefined || val === null) return '';
    return escapeHTML(String(val));
}

export function handleFiles(files) {
    if (bloqueadoPorBase()) return;
    if (!files || files.length === 0) {
        console.warn('⚠️ No hay archivos para procesar');
        return;
    }
    
    console.log('📂 handleFiles llamado con', files.length, 'archivos');
    // ACUMULA (no reemplaza): agregar un archivo no puede tirar los que ya estan. Se
    // comparan por nombre+tamano+fecha, asi que volver a elegir la rendicion completa no
    // engorda la lista ni vuelve a leer lo mismo.
    const yaEnLaLista = new Set((window.currentFiles || []).map(claveArchivo));
    const nuevos = Array.from(files).filter(f => !yaEnLaLista.has(claveArchivo(f)));
    window.currentFiles = (window.currentFiles || []).concat(nuevos);
    
    const fileNameEl = document.getElementById('fileName');
    const fileInfoEl = document.getElementById('fileInfo');
    
    if (fileNameEl) {
        // ✅ CORREGIDO: Sanitizar nombres de archivo
        fileNameEl.textContent = window.currentFiles.length === 1 
            ? sanitizarValor(window.currentFiles[0].name)
            : `${window.currentFiles.length} archivos seleccionados`;
    }
    if (fileInfoEl) {
        fileInfoEl.style.display = 'flex';
    }

    if (!nuevos.length) {
        // Nada nuevo que leer: no se toca NADA de lo que ya esta en pantalla.
        mostrarAviso('Esos archivos ya estaban en la lista: no se adjuntó nada nuevo.', [], 'warn');
        return;
    }
    
    mostrarProgreso(`📎 ${nuevos.length} archivo(s) nuevo(s). Procesando...`, 10);
    
    console.log('🔄 Llamando a parsearFacturas automáticamente...');
    setTimeout(() => {
        parsearFacturas();
    }, 300);
}

export function toBase64(file) {
    return new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result.split(',')[1]);
        r.onerror = rej;
        r.readAsDataURL(file);
    });
}

export async function parsearFacturas() {
    if (bloqueadoPorBase()) return;
    const files = window.currentFiles || [];
    if (!files || files.length === 0) {
        mostrarMsg('⚠️ Primero selecciona un archivo PDF o imagen', false);
        ocultarProgreso();
        return;
    }
    
    // Solo los archivos que NO se leyeron todavia: agregar uno nuevo lee ese y nada mas.
    // `facturasData` NO se reinicia (era el defecto: desaparecian los comprobantes ya
    // extraidos y quedaba solo el ultimo archivo).
    const parseados = window.archivosParseados || (window.archivosParseados = []);
    const pendientes = files.filter(f => !parseados.includes(claveArchivo(f)));
    if (!pendientes.length) {
        mostrarAviso('Los comprobantes de esos archivos ya se extrajeron. Si querés volver '
            + 'a leerlos, usá "Limpiar" y adjuntalos de nuevo.', [], 'warn');
        ocultarProgreso();
        return;
    }
    
    console.log('🔄 parsearFacturas iniciado con', pendientes.length, 'archivo(s) nuevo(s)');
    mostrarProgreso(`📄 Procesando archivo 1 de ${pendientes.length}...`, 20);
    
    const btn = document.getElementById('btnParsear');
    if (btn) {
        btn.innerHTML = '<span class="spinner"></span>Procesando…';
        btn.disabled = true;
    }

    // Donde arranca lo nuevo: el render pinta desde aca y deja las tarjetas viejas como
    // estan (con sus correcciones a mano). Se cuentan las tarjetas PINTADAS y no el largo
    // de `facturasData` a proposito: si un archivo falla despues de otro que si se leyo,
    // esas facturas quedan en la lista SIN tarjeta, y el proximo intento tiene que
    // pintarlas (contando la lista quedarian invisibles para siempre: nadie las revisa y
    // el alta las rechaza por "faltan datos").
    const contenedor = document.getElementById('facturasContainer');
    const desde = contenedor ? contenedor.querySelectorAll('.factura-item').length : 0;
    let nuevas = 0;
    
    try {
        for (let idx = 0; idx < pendientes.length; idx++) {
            const file = pendientes[idx];
            const progreso = 20 + ((idx / pendientes.length) * 50);
            // ✅ CORREGIDO: Sanitizar nombre de archivo
            const nombreSanitizado = sanitizarValor(file.name);
            mostrarProgreso(`📄 Procesando ${nombreSanitizado} (${idx + 1}/${pendientes.length})...`, progreso);
            
            console.log(`📄 Procesando archivo ${idx + 1}/${pendientes.length}: ${file.name}`);
            const b64 = await toBase64(file);
            const res = await fetch('/api/parsear_pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_b64: b64, file_type: file.type || 'application/pdf' })
            }).then(r => r.json());
            
            if (!res.ok) throw new Error(`${file.name}: ${res.error || 'Error al parsear'}`);
            // Se marca como leido SOLO si salio bien: un archivo que fallo se reintenta
            // (agregando otro o con "Extraer facturas") en vez de quedar perdido.
            parseados.push(claveArchivo(file));
            if (res.facturas && res.facturas.length > 0) {
                console.log(`✅ ${res.facturas.length} facturas encontradas en ${file.name}`);
                res.facturas.forEach(f => { 
                    f.archivo = file.name; 
                    window.facturasData.push(f); 
                    nuevas++;
                });
            } else {
                console.warn(`⚠️ No se detectaron facturas en ${file.name}`);
            }
        }
        
        if (!nuevas) {
            // Nada nuevo: lo que ya estaba en la lista no se toca (ni se vuelve a pintar).
            if (window.facturasData.length === 0) {
                mostrarMsg('⚠️ No se detectaron facturas en los archivos', false);
            } else {
                mostrarAviso('Los archivos nuevos no trajeron comprobantes: los que ya '
                    + 'estaban siguen en la lista.', [], 'warn');
            }
            ocultarProgreso();
            return;
        }
        
        console.log(`📊 Total en la lista: ${window.facturasData.length} (${nuevas} nueva/s)`);
        mostrarProgreso(`✅ ${nuevas} factura(s) nueva(s). Cargando datos...`, 75);
        
        let ccos = [];
        try {
            const response = await fetch('/api/centros_costo');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            ccos = await response.json();
            console.log('✅ Centros de costo cargados:', ccos.length);
        } catch (e) {
            console.warn('⚠️ Usando centros de costo por defecto:', e.message);
            ccos = [
                {codigo: "001", nombre: "Centro de Costo 1", cco: "S"},
                {codigo: "002", nombre: "Centro de Costo 2", cco: "S"},
                {codigo: "003", nombre: "Centro de Costo 3", cco: "S"},
                {codigo: "004", nombre: "Centro de Costo 4", cco: "S"},
                {codigo: "005", nombre: "Centro de Costo 5", cco: "S"},
            ];
        }
        
        window.cuentasList = ccos;
        mostrarProgreso(`📋 Renderizando ${nuevas} factura(s) nueva(s)...`, 90);
        // `desde`: se AGREGAN las tarjetas nuevas. Las que ya estaban no se repintan, asi
        // que no se pierde nada de lo que el operador haya corregido a mano.
        await renderFacturas(window.facturasData, ccos, desde);
        
        const rendicionConfig = document.getElementById('rendicionConfig');
        const btnCargarTodo = document.getElementById('btnCargarTodo');
        if (rendicionConfig) rendicionConfig.style.display = 'block';
        if (btnCargarTodo) btnCargarTodo.style.display = 'block';

        // Ya extrajo: el panel de carga se colapsa (el operador pidio liberar espacio)
        // y el boton grande queda con el texto que corresponde a la seleccion.
        colapsarCarga(window.facturasData.length);
        actualizarBotonCargar();
        
        mostrarProgreso(`✅ ${nuevas} factura(s) nueva(s) · ${window.facturasData.length} en la lista`, 100);
        mostrarMsg(`✅ ${nuevas} factura(s) nueva(s) · ${window.facturasData.length} en la lista`, true);
        
        setTimeout(() => ocultarProgreso(), 2500);
        
    } catch (e) {
        console.error('❌ Error en parsearFacturas:', e);
        mostrarMsg(`❌ Error: ${sanitizarValor(e.message)}`, false);
        ocultarProgreso();
    } finally {
        if (btn) { 
            btn.innerHTML = '✨ Extraer facturas'; 
            btn.disabled = false; 
        }
    }
}

/**
 * Correcciones que hizo el operador a mano en una factura (campo -> propuesto/final).
 *
 * El parser propuso estos campos y `render.js` prelleno el formulario con EXACTAMENTE
 * estos valores y este formato (por eso se comparan como texto y con el mismo
 * `toFixed(2)`): lo que difiera es un error de lectura del parser, y registrarlo es
 * lo unico que permite despues arreglar el patron sin IA ni tokens.
 *
 * Se comparan SOLO los campos que el operador puede tocar de verdad. Los derivados
 * (`imp_bruto`, `imp_iva`, `base_imponible`, `tasa_iva`) quedan afuera: son readonly
 * y se recalculan solos cuando cambia el total, asi que registrarlos llenaria el
 * informe de "correcciones" que nadie hizo.
 */
function correccionesDeFactura(i, f) {
    const propuesta = {
        numero_dte: f.numero_dte || '',
        fecha: f.fecha || '',
        tipo: f.tipo || '',
        moneda: f.moneda || 'PS',
        total: f.total ? f.total.toFixed(2) : '',
        imp_especial: f.imp_especial ? f.imp_especial.toFixed(2) : '',
        nit_emisor: f.nit_emisor || '',
    };
    // `render.js` prellena el nombre del emisor con `eventual_nombre` cuando existe:
    // en ese caso el input NO arranca con lo que propuso el parser y compararlo daria
    // una correccion falsa.
    if (!f.eventual_nombre) propuesta.nombre_emisor = f.nombre_emisor || '';

    const inputs = {
        numero_dte: `f${i}_ref`,
        fecha: `f${i}_fecha`,
        tipo: `f${i}_tipo`,
        moneda: `f${i}_moneda`,
        total: `f${i}_total`,
        imp_especial: `f${i}_especial`,
        nit_emisor: `f${i}_evnit`,
        nombre_emisor: `f${i}_evnom`,
    };

    const correcciones = {};
    for (const campo of Object.keys(propuesta)) {
        const valor = document.getElementById(inputs[campo])?.value ?? '';
        if (String(valor).trim() !== String(propuesta[campo]).trim()) {
            correcciones[campo] = { propuesto: propuesta[campo], final: valor };
        }
    }
    return correcciones;
}

// ============================================================
// SELECCION, ACORDEON Y COLAPSO DEL PANEL DE CARGA
// ============================================================
// Tres cosas que pidio el operador el 03/10/2026, despues de que un error pasara
// inadvertido ("aprete dos veces y no hizo nada"): ver los avisos, liberar espacio
// cuando ya extrajo, y poder cargar SOLO ALGUNAS facturas.
//
// Regla de la seleccion (decidida con el usuario): si no hay ninguna casilla tildada
// se cargan TODAS las pendientes (lo de siempre); si hay tildes, solo esas. Las ya
// cargadas (`nro_interno`) no entran nunca: el ERP las rechazaria como duplicadas.
//
// La tildada se guarda en los DATOS (`facturasData[i].seleccionada`) y no en el DOM: el
// re-render de las tarjetas reconstruye las casillas y las tildes se perdian (lo reporto
// el usuario). Ver `sincronizarSeleccion`, el unico lugar que lee el DOM.

/** Indices de las facturas que todavia se pueden cargar (ni quitadas, ni borradas, ni cargadas). */
function indicesPendientes() {
    const indices = [];
    window.facturasData.forEach((f, i) => {
        if (f.borrada || f.descartada || f.nro_interno) return;
        indices.push(i);
    });
    return indices;
}

/**
 * La seleccion vive en los DATOS (`facturasData[i].seleccionada`), no en el DOM.
 *
 * El DOM de las tarjetas lo rehace `renderFacturas` entero (y `eliminarFactura` lo
 * pisa): una casilla tildada que viviera solo ahi nacia destildada en el proximo
 * re-pintado y el boton volvia a "Cargar todas". Lo reporto el usuario el 03/10/2026 al
 * tildar "proveedor eventual". Este es el UNICO lugar que lee la casilla; el resto de la
 * pantalla lee y escribe los datos, asi que la seleccion sobrevive a cualquier re-render.
 */
function sincronizarSeleccion() {
    window.facturasData.forEach((f, i) => {
        const chk = document.getElementById(`f${i}_chk`);
        if (chk) f.seleccionada = chk.checked;
    });
    return indicesPendientes();
}

/** Indices a cargar: las tildadas, o todas las pendientes si no hay ninguna. */
function indicesSeleccionados() {
    // Se sincroniza tambien aca: el conteo del boton y el de la carga no pueden
    // discrepar, y el DOM (cuando la casilla existe) es el ultimo estado del operador.
    const pendientes = sincronizarSeleccion();
    const tildadas = pendientes.filter(i => window.facturasData[i].seleccionada);
    return tildadas.length ? tildadas : pendientes;
}

/** Abre o cierra el detalle de una factura (acordeon). */
export function toggleFactura(i) {
    const card = document.getElementById(`fact-${i}`);
    if (!card) return;
    const colapsada = card.classList.toggle('colapsada');
    const chev = document.getElementById(`f${i}_chev`);
    if (chev) chev.textContent = colapsada ? '▸' : '▾';
}

/** Tilda o destilda todas las pendientes (el enlace del pie). */
export function marcarTodas(tildar) {
    const valor = !!tildar;
    indicesPendientes().forEach(i => {
        // Primero los DATOS (la fuente de verdad) y despues la casilla, que puede no
        // estar (tarjeta eliminada) o volver a pintarse despues.
        window.facturasData[i].seleccionada = valor;
        const chk = document.getElementById(`f${i}_chk`);
        if (chk) chk.checked = valor;
    });
    actualizarBotonCargar();
}

/** El boton grande y el estado de la seleccion, siempre con el texto correcto. */
export function actualizarBotonCargar() {
    // Se dispara al cambiar una casilla, asi que antes de contar hay que llevar el DOM a
    // los datos: es el unico punto donde el operador tilda una factura suelta.
    const pendientes = sincronizarSeleccion();
    const tildadas = pendientes.filter(i => window.facturasData[i].seleccionada);

    const btn = document.getElementById('btnCargar');
    if (btn) {
        btn.innerHTML = tildadas.length
            ? `⬆ Cargar las seleccionadas (${tildadas.length} de ${pendientes.length})`
            : `⬆ Cargar todas las facturas (${pendientes.length})`;
    }
    const info = document.getElementById('seleccionInfo');
    if (info) {
        info.textContent = tildadas.length
            ? `${tildadas.length} tildada(s) de ${pendientes.length} pendiente(s)`
            : `${pendientes.length} pendiente(s)`;
    }
    const lnk = document.getElementById('lnkSeleccion');
    if (lnk) {
        lnk.textContent = (tildadas.length === pendientes.length && pendientes.length)
            ? 'Desmarcar todas' : 'Marcar todas';
    }
    // Los que el operador saco de la lista a mano: se ofrecen para volver a incluirlos aca
    // (un clic equivocado no tiene que costar la rendicion entera).
    const quitadas = window.facturasData.filter(f => f.descartada).length;
    const lnkQuitados = document.getElementById('lnkQuitados');
    if (lnkQuitados) {
        lnkQuitados.textContent = quitadas ? `↩ Volver a incluir (${quitadas})` : '';
        lnkQuitados.style.display = quitadas ? '' : 'none';
    }
}

// ============================================================
// QUITAR DE LA LISTA (sin tocar el ERP)
// ============================================================
// La tarjeta de un comprobante PENDIENTE ofrecia "Eliminar factura", que es la BAJA del
// ERP: en una pendiente contestaba "no se cargo desde aca", asi que no habia forma de
// descartar uno que no se queria cargar. Esto lo saca de la carga sin escribir nada.
//
// La tarjeta se OCULTA, no se saca del DOM: el render incremental cuenta las tarjetas
// pintadas (`querySelectorAll('.factura-item')`) para saber desde donde agregar las
// nuevas, y sacar un nodo desalinearia el proximo "Agregar mas".

/** Saca de la carga una factura TODAVIA no cargada (no escribe nada en el ERP). */
export function quitarDeLaLista(i) {
    const f = window.facturasData?.[i];
    if (!f) return;
    if (f.nro_interno) {
        // Ya esta en el ERP: lo unico que la saca de ahi es la baja ("Eliminar factura").
        mostrarMsg('Este comprobante ya se cargó: para sacarlo del ERP usá "Eliminar factura".',
                   false);
        return;
    }
    f.descartada = true;
    const card = document.getElementById(`fact-${i}`);
    if (card) card.classList.add('descartada');
    actualizarBotonCargar();
    mostrarMsg('Comprobante quitado de la lista: no se va a cargar.', true);
}

/** Vuelve a incluir TODOS los comprobantes quitados de la lista. */
export function volverAIncluir() {
    let vueltos = 0;
    window.facturasData.forEach((f, i) => {
        if (!f.descartada) return;
        f.descartada = false;
        const card = document.getElementById(`fact-${i}`);
        if (card) card.classList.remove('descartada');
        vueltos++;
    });
    actualizarBotonCargar();
    if (vueltos) mostrarMsg(`${vueltos} comprobante(s) vuelto(s) a incluir.`, true);
}

/** Colapsa el panel de carga a una linea, para liberar espacio. */
export function colapsarCarga(cantidad) {
    const panel = document.getElementById('cargaPanel');
    const resumen = document.getElementById('cargaResumen');
    const texto = document.getElementById('cargaResumenTexto');
    if (!panel || !resumen) return;
    if (texto) {
        texto.textContent = `✅ ${cantidad} comprobante(s) extraído(s). `
            + 'Revisá y cargá abajo.';
    }
    panel.style.display = 'none';
    resumen.style.display = 'flex';
}

/** Vuelve a mostrar el panel de carga ("Agregar más"). */
export function agregarMas() {
    const panel = document.getElementById('cargaPanel');
    const resumen = document.getElementById('cargaResumen');
    if (panel) panel.style.display = '';
    if (resumen) resumen.style.display = 'none';
}

export async function cargarTodo() {
    if (bloqueadoPorBase()) return;
    const btn = document.getElementById('btnCargar');
    if (!btn) return;
    btn.innerHTML = '<span class="spinner"></span>Cargando…';
    btn.disabled = true;

    mostrarProgreso('📦 Cargando facturas en el sistema...', 10);

    let ok = 0, errores = [];
    const total = window.facturasData.length;

    // CASILLAS: sin ninguna tildada se cargan TODAS las pendientes (lo de siempre);
    // con tildes, SOLO esas. Las ya cargadas (`nro_interno`) quedan afuera: reenviarlas
    // hacia que el ERP las rechace como duplicadas, un error por factura sin sentido.
    const seleccion = indicesSeleccionados();
    if (!seleccion.length) {
        mostrarMsg('No hay facturas pendientes de carga.', false);
        // Misma regla que al final del recorrido: el texto lo escribe el que conoce la
        // seleccion (aca queda en "0 pendiente(s)"), no un literal escrito a mano.
        actualizarBotonCargar();
        btn.disabled = false;
        ocultarProgreso();
        return;
    }

    for (let i = 0; i < total; i++) {
        const f = window.facturasData[i];
        if (!seleccion.includes(i)) continue;
        // Las facturas ya eliminadas quedan en la lista marcadas (`borrada`), sin
        // sacarlas (sacarlas corria los indices y el borrado siguiente mandaba el
        // `nro_interno` de OTRA factura): al re-cargar hay que SALTARLAS. Sin esto,
        // `getRenglones(i)` viene vacio para una fila ya borrada y "Cargar todas"
        // sumaba un error falso ("falta cuenta contable") justo despues de una baja.
        // `descartada` entra por el mismo motivo: el operador puede quitarla MIENTRAS el
        // recorrido esta cargando (hay `await` en el medio) y la seleccion ya esta armada.
        if (f.borrada || f.descartada) continue;
        const progreso = 10 + ((i / total) * 80);
        mostrarProgreso(`📦 Cargando factura ${i + 1} de ${total}...`, progreso);
        
        const tipo = document.getElementById(`f${i}_tipo`)?.value || '';

        // El tipo NO se adivina: si el parser no pudo leer la leyenda, el select
        // arranca con la opcion vacia y aca se pide el tipo antes de mandar nada.
        // Antes el default era 'FCP' y un operador que "arreglaba" el badge a FCC
        // cargaba en silencio un FCP real como pequeno contribuyente (IVA 0 y sin
        // ninguna fila de impuesto); y un default 'FCP' mandaba `bruto = total,
        // iva = 0`, que el servicio rechazaba con un mensaje sobre el IVA.
        if (!tipo) {
            errores.push(`Factura ${i+1}: elegí el tipo de factura (FCP con IVA o FCC pequeño contribuyente).`);
            const factEl = document.getElementById(`fact-${i}`);
            if (factEl) factEl.style.borderColor = '#f5b8b8';
            continue;
        }

        const esEv = document.getElementById(`f${i}_esev`)?.checked || false;
        const provId = esEv
            ? (parseInt(document.getElementById(`f${i}_provid`)?.value) || parseInt(document.getElementById('empId')?.value) || null)
            : (f.proveedor_id || null);

        if (!provId) {
            // ✅ CORREGIDO: Sanitizar mensaje de error
            errores.push(`Factura ${i+1}: falta proveedor.`);
            const factEl = document.getElementById(`fact-${i}`);
            if (factEl) factEl.style.borderColor = '#f5b8b8';
            continue;
        }

        const bruto = parseFloat(document.getElementById(`f${i}_bruto`)?.value) || 0;
        const iva = parseFloat(document.getElementById(`f${i}_iva`)?.value) || 0;
        // El impuesto especial se manda tal cual lo cargó el usuario; en FCC no
        // aplica (ahí el total es el bruto y no hay nada que separar).
        const especial = parseFloat(document.getElementById(`f${i}_especial`)?.value) || 0;
        const renglones = getRenglones(i);

        if (!renglones.length) {
            errores.push(`Factura ${i+1}: falta cuenta contable.`);
            const factEl = document.getElementById(`fact-${i}`);
            if (factEl) factEl.style.borderColor = '#f5b8b8';
            continue;
        }

        const payload = {
            division: window.divisionActiva || 7,
            proveedor_id: provId,
            proveedor_nombre: esEv
                ? (document.getElementById(`f${i}_provsearch`)?.value || document.getElementById('empSearch')?.value || '')
                : (f.proveedor_nombre || ''),
            cuenta_prov: f.cuenta_prov || '',
            // D3: los dos van VACIOS si el operador no puso fecha (antes caian en la de
            // hoy, en silencio). `fecha_vto` no lo produce el parser: aca el vacio es el
            // estado inicial. El servicio valida `fecha`, asi que el alta se frena.
            fecha: document.getElementById(`f${i}_fecha`)?.value || '',
            fecha_vto: document.getElementById(`f${i}_fecha`)?.value || '',
            ref_prov: document.getElementById(`f${i}_ref`)?.value.trim() || '',
            descripcion: document.getElementById(`f${i}_desc`)?.value.trim() || '',
            cond_pago: document.getElementById('rendCondPago')?.value || '00',
            moneda: document.getElementById(`f${i}_moneda`)?.value || 'PS',
            cotizacion: parseFloat(document.getElementById(`f${i}_coti`)?.value) || 1,
            tipo_comp: tipo,
            imp_bruto: bruto,
            imp_iva: iva,
            imp_especial: tipo === 'FCC' ? 0 : especial,
            tasa_iva: tipo === 'FCC' ? 0 : 12,
            renglones: renglones,
            // Lo que el operador corrigio a mano (campo -> propuesto/final), el texto
            // de la pagina para poder recortar y de que comprobante salio. Con esto
            // el backend audita una linea `cxp.correccion` por campo.
            correcciones: correccionesDeFactura(i, f),
            texto: f.texto || '',
            origen: {
                archivo: f.archivo || '',
                pagina: f.pagina || '',
                numero_dte: f.numero_dte || '',
            },
        };

        if (esEv) {
            payload.eventual = {
                nombre: document.getElementById(`f${i}_evnom`)?.value || f.nombre_emisor || '',
                nit: document.getElementById(`f${i}_evnit`)?.value || f.nit_emisor || '',
                domicilio: '',
                localidad: document.getElementById(`f${i}_evloc`)?.value || 'Guatemala',
            };
        }

        try {
            const res = await fetch('/api/cargar_factura', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(r => r.json());
            if (res.ok) {
                ok++;
                // La respuesta del alta trae el numero INTERNO del comprobante:
                // sin el, la pantalla no puede borrar esta factura (la baja se
                // identifica por numero interno, no por el Nro. DTE del PDF).
                f.nro_interno = res.nro_comprobante;
                f.tipo_cargado = res.tipo;
                f.ctacte = res.ctacte;
                const factEl = document.getElementById(`fact-${i}`);
                if (factEl) {
                    factEl.style.borderColor = '#a3d9c0';
                    factEl.style.opacity = '0.6';
                }
            } else {
                // ✅ CORREGIDO: Sanitizar error de API
                errores.push(`Factura ${i+1}: ${sanitizarValor(res.error)}`);
                const factEl = document.getElementById(`fact-${i}`);
                if (factEl) factEl.style.borderColor = '#f5b8b8';
            }
        } catch(e) {
            errores.push(`Factura ${i+1}: ${sanitizarValor(e.message)}`);
        }
    }

    // El texto del boton sale SIEMPRE de `actualizarBotonCargar`: escrito a mano decia
    // "Cargar todas" con tildes puestas (una factura fallada conserva su tildada) y el
    // proximo clic cargaba solo esas. Despues de una carga parcial es cuando mas se ve.
    actualizarBotonCargar();
    btn.disabled = false;
    
    if (errores.length === 0) {
        mostrarProgreso(`✅ ${ok} factura(s) cargadas exitosamente.`, 100);
        mostrarMsg(`✅ ${ok} factura(s) cargadas exitosamente.`, true);
        setTimeout(() => ocultarProgreso(), 2000);
    } else {
        // Los errores van a un AVISO con la lista completa, una linea por factura: la
        // linea unica con " | " no se podia leer y encima se borraba sola.
        mostrarProgreso(`⚠️ ${ok} ok · ${errores.length} errores`, 100);
        mostrarErrores(`${errores.length} de ${seleccion.length} no se pudieron cargar `
                       + `(${ok} ok)`, errores.map(e => `${e}`));
        setTimeout(() => ocultarProgreso(), 3000);
    }
}

export function limpiarRendicion() {
    window.currentFiles = [];
    window.facturasData = [];
    // Y el registro de leidos: "Limpiar" es el unico camino para empezar de cero (y el
    // unico que vacia tambien los comprobantes), asi que despues se pueden volver a
    // adjuntar los mismos archivos.
    window.archivosParseados = [];
    const fileInput = document.getElementById('fileInput');
    if (fileInput) fileInput.value = '';
    const fileInfo = document.getElementById('fileInfo');
    if (fileInfo) fileInfo.style.display = 'none';
    const fileName = document.getElementById('fileName');
    if (fileName) fileName.textContent = '';
    const facturasContainer = document.getElementById('facturasContainer');
    if (facturasContainer) facturasContainer.innerHTML = '';
    const rendicionConfig = document.getElementById('rendicionConfig');
    if (rendicionConfig) rendicionConfig.style.display = 'none';
    const btnCargarTodo = document.getElementById('btnCargarTodo');
    if (btnCargarTodo) btnCargarTodo.style.display = 'none';
    const empSearch = document.getElementById('empSearch');
    if (empSearch) empSearch.value = '';
    const empId = document.getElementById('empId');
    if (empId) empId.value = '';
    const toggleEventualGlobal = document.getElementById('toggleEventualGlobal');
    if (toggleEventualGlobal) toggleEventualGlobal.checked = false;
    const eventualGlobalPanel = document.getElementById('eventualGlobalPanel');
    if (eventualGlobalPanel) eventualGlobalPanel.style.display = 'none';
    ocultarProgreso();
    console.log('✅ Rendición limpiada');
}

export async function debugPDF() {
    if (!window.currentFiles?.length) return;
    const btn = document.getElementById('btnDebug');
    if (!btn) return;
    btn.textContent = 'Procesando…';
    btn.disabled = true;
    
    mostrarProgreso('🔍 Extrayendo texto raw del PDF...', 30);
    
    try {
        for (let idx = 0; idx < window.currentFiles.length; idx++) {
            const file = window.currentFiles[idx];
            const progreso = 30 + ((idx / window.currentFiles.length) * 60);
            const nombreSanitizado = sanitizarValor(file.name);
            mostrarProgreso(`🔍 Procesando ${nombreSanitizado} (${idx + 1}/${window.currentFiles.length})...`, progreso);
            
            const b64 = await toBase64(file);
            const res = await fetch('/api/debug_pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_b64: b64 })
            }).then(r => r.json());
            console.log(`=== ${file.name} ===`);
            res.forEach(p => console.log(`--- Pág ${p.pagina} ---\n${p.texto}`));
        }
        mostrarProgreso('✅ Texto extraído correctamente. Revisá la consola (F12)', 100);
        alert('Texto copiado a consola del navegador (F12)');
        setTimeout(() => ocultarProgreso(), 2000);
    } catch (e) {
        console.error('❌ Error en debugPDF:', e);
        mostrarMsg(`❌ Error: ${sanitizarValor(e.message)}`, false);
        ocultarProgreso();
    } finally {
        btn.textContent = '🔍 Ver texto raw';
        btn.disabled = false;
    }
}