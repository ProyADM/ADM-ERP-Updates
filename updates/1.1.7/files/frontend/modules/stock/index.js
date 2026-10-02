// ============================================================
// STOCK - PUNTO DE ENTRADA (INDEX) - CORREGIDO
// ============================================================

function inicializarStock() {
    console.log('📦 Inicializando Stock...');
    
    // Idempotente: si las caches ya están, re-aplica las opciones al DOM del
    // módulo recién montado (bug de combos vacíos de stock).
    if (typeof cargarSelectsStock === 'function') {
        setTimeout(() => {
            cargarSelectsStock();
        }, 100);
    }
    
    if (typeof closeDrawer === 'function') {
        setTimeout(() => {
            closeDrawer();
        }, 200);
    }
}

function navegarStock(seccionId) {
    console.log(`📂 Navegando a sección de stock: ${seccionId}`);
    
    const secciones = ['ajuste-e', 'ajuste-s', 'transferencia', 'stock', 'stock-consolidado', 'articulos', 'depositos'];
    secciones.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.classList.remove('active');
            el.style.display = 'none';
        }
    });
    
    const target = document.getElementById(seccionId);
    if (target) {
        target.classList.add('active');
        target.style.display = 'block';
        console.log(`✅ Sección ${seccionId} mostrada`);

        // Limpiar resultados/mensajes viejos al entrar a la sección (evita
        // mensajes "precargados" del movimiento anterior).
        const idResultados = {
            'ajuste-e': 'ae-resultados',
            'ajuste-s': 'as-resultados',
            'transferencia': 'trm-resultados'
        }[seccionId];
        if (idResultados) {
            const elResult = document.getElementById(idResultados);
            if (elResult) elResult.textContent = '';
        }
        
        const titulo = document.getElementById('seccion-activa');
        if (titulo) {
            const tab = document.querySelector(`.drawer-tab[data-tab="${seccionId}"]`);
            if (tab) {
                titulo.textContent = tab.textContent.trim();
            } else {
                const nombres = {
                    'stock': 'Consultar Stock',
                    'stock-consolidado': 'Stock Consolidado',
                    'ajuste-e': 'Ajuste +',
                    'ajuste-s': 'Ajuste -',
                    'transferencia': 'Transferencia',
                    'articulos': 'Artículos',
                    'depositos': 'Depósitos'
                };
                titulo.textContent = nombres[seccionId] || seccionId;
            }
            titulo.style.display = 'block';
        }
        
        if (seccionId === 'stock' && typeof consultarStock === 'function') {
            setTimeout(() => {
                consultarStock();
            }, 100);
        }
        
        if (seccionId === 'stock-consolidado' && typeof buscarConsolidado === 'function') {
            setTimeout(() => {
                buscarConsolidado(true);
            }, 100);
        }
        
    } else {
        console.warn(`⚠️ No se encontró la sección ${seccionId}`);
    }
}

// ============================================================
// EXPORTAR FUNCIONES GLOBALES
// ============================================================

window.inicializarStock = inicializarStock;
window.navegarStock = navegarStock;

console.log('📦 Módulo Stock index cargado');
console.log('✅ Funciones de stock disponibles:', Object.keys(window).filter(k => 
    ['agregarFila', 'hacerAjusteIndividual', 'cargarPartidas', 'consultarStock', 
     'buscarConsolidado', 'crearArticulo', 'cargarDepositoParaModificar', 
     'cargarSelectsStock', 'inicializarStock'].includes(k)
));