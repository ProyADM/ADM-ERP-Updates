// modules/cxp/init.js
// ============================================================
// INIT - INICIALIZACIÓN (CORREGIDO - SIN LOOP INFINITO)
// ============================================================

import { validarBaseGT } from './ui.js';
import { handleFiles, parsearFacturas, cargarTodo, limpiarRendicion, debugPDF } from './main.js';
import { aplicarEventualGlobal } from './eventuales.js';
import { setupAC } from './utils.js';
import { initTooltips, injectTooltipStyles } from '../shared/tooltip-component.js';

let cxpInicializado = false;
let listenersConfigurados = false;
let intentosCXP = 0;
const MAX_INTENTOS = 10;
const INTERVALO_INTENTO = 800; // ms

// 🔴 NUEVO: Recordar última sección del drawer
// (antes: process.env.CXP_STORAGE_KEY — process no existe en el navegador y
// rompía la evaluación de este módulo; se usa un literal)
const STORAGE_KEY = 'cxp_ultima_seccion';

export function crearBotonSelector() {
    console.log('ℹ️ Botón selector eliminado - El dropzone maneja la selección de archivos');
}

export function inicializarCXP() {
    // ✅ Si ya está inicializado, no hacer nada
    if (cxpInicializado) {
        console.log('ℹ️ CXP ya inicializado, omitiendo...');
        return;
    }
    
    // ✅ Verificar que el template existe
    const modulo = document.getElementById('cxp-facturas');
    if (!modulo) {
        intentosCXP++;
        if (intentosCXP >= MAX_INTENTOS) {
            console.warn(`⚠️ CXP no disponible después de ${MAX_INTENTOS} intentos. Abortando.`);
            console.warn('   Verifica que el template CXP esté definido en templates.js');
            return;
        }
        console.log(`⏳ Esperando template CXP... (intento ${intentosCXP}/${MAX_INTENTOS})`);
        setTimeout(() => inicializarCXP(), INTERVALO_INTENTO);
        return;
    }
    
    // ✅ Resetear contador de intentos
    intentosCXP = 0;
    cxpInicializado = true;
    
    console.log('🔄 Inicializando CXP...');
    injectTooltipStyles();
    configurarEventListenersCXP();
    if (typeof validarBaseGT === 'function') validarBaseGT();
}

export function configurarEventListenersCXP() {
    if (listenersConfigurados) {
        console.log('ℹ️ Listeners ya configurados, omitiendo...');
        return;
    }
    
    console.log('🔧 Configurando event listeners de CXP...');
    
    const dropZone = document.getElementById('dropZone');
    if (!dropZone) {
        console.error('❌ No se encontró dropZone');
        return;
    }
    
    // 🔴 BUSCAR EL FILEINPUT
    let fileInput = document.getElementById('fileInput');
    
    // 🔴 SI NO EXISTE, CREARLO DENTRO DEL DROPZONE
    if (!fileInput) {
        console.warn('⚠️ No se encontró fileInput, creando uno...');
        fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.id = 'fileInput';
        fileInput.multiple = true;
        fileInput.accept = '.pdf,.jpg,.jpeg,.png';
        fileInput.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            cursor: pointer;
            z-index: 10;
        `;
        dropZone.style.position = 'relative';
        dropZone.appendChild(fileInput);
        console.log('✅ fileInput creado dentro del dropzone (cubre todo el área)');
    } else {
        fileInput.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            cursor: pointer;
            z-index: 10;
        `;
        dropZone.style.position = 'relative';
        console.log('✅ fileInput ajustado para cubrir todo el dropzone');
    }
    
    console.log('✅ fileInput configurado:', fileInput.id);
    
    // 🔴 ELIMINAR LISTENERS ANTERIORES DEL FILEINPUT
    const newFileInput = fileInput.cloneNode(true);
    fileInput.parentNode.replaceChild(newFileInput, fileInput);
    fileInput = newFileInput;
    
    // 🔴 LISTENER DEL FILEINPUT
    fileInput.addEventListener('change', function(e) {
        e.stopPropagation();
        console.log('📂 Archivos seleccionados (change):', this.files.length);
        
        if (this.files && this.files.length > 0) {
            if (typeof handleFiles === 'function') {
                handleFiles(this.files);
            } else {
                console.error('❌ handleFiles no está definido');
                window.currentFiles = Array.from(this.files);
                const fileInfo = document.getElementById('fileInfo');
                if (fileInfo) fileInfo.style.display = 'flex';
                const fileName = document.getElementById('fileName');
                if (fileName) {
                    fileName.textContent = window.currentFiles.length === 1 
                        ? window.currentFiles[0].name 
                        : `${window.currentFiles.length} archivos seleccionados`;
                }
                if (typeof parsearFacturas === 'function') {
                    setTimeout(() => parsearFacturas(), 300);
                }
            }
        }
        this.value = '';
    });
    
    // 🔴 CLICK EN DROPZONE
    dropZone.addEventListener('click', function(e) {
        if (e.target.closest('button') || e.target.closest('.btn')) {
            return;
        }
        
        console.log('🖱️ Click en dropZone');
        
        const input = this.querySelector('input[type="file"]') || document.getElementById('fileInput');
        if (input) {
            input.value = '';
            input.click();
            console.log('✅ Click en fileInput desde dropZone');
        } else {
            console.error('❌ No se encontró fileInput');
        }
    });
    
    // 🔴 DRAG OVER
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.classList.add('drag');
    });
    
    // 🔴 DRAG LEAVE
    dropZone.addEventListener('dragleave', function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.classList.remove('drag');
    });
    
    // 🔴 DROP
    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.classList.remove('drag');
        console.log('📂 Archivos soltados (drop):', e.dataTransfer.files.length);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            if (typeof handleFiles === 'function') {
                handleFiles(e.dataTransfer.files);
            }
        }
    });
    
    console.log('✅ DropZone configurado');
    
    // ===== BOTONES =====
    const btnParsear = document.getElementById('btnParsear');
    if (btnParsear && !btnParsear._listenerAgregado) {
        btnParsear.addEventListener('click', function(e) {
            e.stopPropagation();
            e.preventDefault();
            console.log('🔄 Botón Extraer facturas clickeado');
            if (!window.currentFiles || window.currentFiles.length === 0) {
                alert('⚠️ Primero selecciona un archivo arrastrándolo o haciendo clic en el dropzone');
                return;
            }
            if (typeof parsearFacturas === 'function') {
                parsearFacturas();
            }
        });
        btnParsear._listenerAgregado = true;
        console.log('✅ Botón Parsear configurado');
    }
    
    const btnCargar = document.getElementById('btnCargar');
    if (btnCargar && !btnCargar._listenerAgregado) {
        btnCargar.addEventListener('click', function(e) {
            e.stopPropagation();
            cargarTodo();
        });
        btnCargar._listenerAgregado = true;
        console.log('✅ Botón Cargar configurado');
    }
    
    const btnLimpiar = document.getElementById('btnLimpiar');
    if (btnLimpiar && !btnLimpiar._listenerAgregado) {
        btnLimpiar.addEventListener('click', function(e) {
            e.stopPropagation();
            limpiarRendicion();
        });
        btnLimpiar._listenerAgregado = true;
        console.log('✅ Botón Limpiar configurado');
    }
    
    const btnLimpiarArchivos = document.getElementById('btnLimpiarArchivos');
    if (btnLimpiarArchivos && !btnLimpiarArchivos._listenerAgregado) {
        btnLimpiarArchivos.addEventListener('click', function(e) {
            e.stopPropagation();
            window.currentFiles = [];
            const fileInfo = document.getElementById('fileInfo');
            if (fileInfo) fileInfo.style.display = 'none';
            const fileName = document.getElementById('fileName');
            if (fileName) fileName.textContent = '';
            const input = document.getElementById('fileInput');
            if (input) input.value = '';
            console.log('✅ Archivos limpiados');
        });
        btnLimpiarArchivos._listenerAgregado = true;
        console.log('✅ Botón Limpiar Archivos configurado');
    }
    
    const btnDebug = document.getElementById('btnDebug');
    if (btnDebug && !btnDebug._listenerAgregado) {
        btnDebug.addEventListener('click', function(e) {
            e.stopPropagation();
            debugPDF();
        });
        btnDebug._listenerAgregado = true;
        console.log('✅ Botón Debug configurado');
    }
    
    const toggleGlobal = document.getElementById('toggleEventualGlobal');
    if (toggleGlobal && !toggleGlobal._listenerAgregado) {
        toggleGlobal.addEventListener('change', function(e) {
            e.stopPropagation();
            aplicarEventualGlobal();
        });
        toggleGlobal._listenerAgregado = true;
        console.log('✅ Toggle Eventual Global configurado');
    }
    
    // ===== AUTOCOMPLETE =====
    setupAC('empSearch', 'empList', 'empId',
        q => fetch(`/api/proveedores?q=${encodeURIComponent(q)}`).then(r => r.json()),
        p => `${p.id} · ${p.nombre}`);
    
    setTimeout(() => {
        initTooltips();
        console.log('✅ Tooltips inicializados desde CXP');
    }, 600);
    
    listenersConfigurados = true;
    console.log('✅ Todos los event listeners de CXP configurados');
}