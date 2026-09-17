# modules/shared/permisos.py
# ============================================================
# SISTEMA DE PERMISOS - SIDESYS ERP
# ============================================================
# 🔒 ESTE ARCHIVO DEFINE TODOS LOS PERMISOS DEL SISTEMA
#    Los permisos se asignan a roles y usuarios
# ============================================================

class PermisosSistema:
    """Definición de todos los permisos del sistema"""
    
    # ============================================================
    # PERMISOS DE ADMINISTRACIÓN (SOLO ADMIN)
    # ============================================================
    ADMIN_ACCESO = "admin.acceso"
    ADMIN_DASHBOARD = "admin.dashboard"
    ADMIN_USUARIOS_VER = "admin.usuarios.ver"
    ADMIN_USUARIOS_CREAR = "admin.usuarios.crear"
    ADMIN_USUARIOS_EDITAR = "admin.usuarios.editar"
    ADMIN_USUARIOS_ELIMINAR = "admin.usuarios.eliminar"
    ADMIN_USUARIOS_ASIGNAR_ROL = "admin.usuarios.asignar_rol"
    ADMIN_USUARIOS_BLOQUEAR = "admin.usuarios.bloquear"
    ADMIN_ROLES_VER = "admin.roles.ver"
    ADMIN_ROLES_CREAR = "admin.roles.crear"
    ADMIN_ROLES_EDITAR = "admin.roles.editar"
    ADMIN_ROLES_ELIMINAR = "admin.roles.eliminar"
    ADMIN_PERMISOS_ASIGNAR = "admin.permisos.asignar"
    ADMIN_BASES_CONFIG = "admin.bases.config"
    ADMIN_MODULOS_CONFIG = "admin.modulos.config"
    ADMIN_AUDITORIA_VER = "admin.auditoria.ver"
    ADMIN_AUDITORIA_EXPORTAR = "admin.auditoria.exportar"
    ADMIN_DIAGNOSTICO = "admin.diagnostico"
    ADMIN_SISTEMA_CONFIG = "admin.sistema.config"
    ADMIN_BACKUP = "admin.backup"
    ADMIN_RESTAURAR = "admin.restaurar"
    
    # ============================================================
    # PERMISOS POR MÓDULO - CXP (Cuentas por Pagar)
    # ============================================================
    CXP_VER = "cxp.ver"
    CXP_CREAR = "cxp.crear"
    CXP_EDITAR = "cxp.editar"
    CXP_ELIMINAR = "cxp.eliminar"
    CXP_APROBAR = "cxp.aprobar"
    CXP_ANULAR = "cxp.anular"
    CXP_REPORTES = "cxp.reportes"
    CXP_EXPORTAR = "cxp.exportar"
    CXP_IMPORTAR = "cxp.importar"
    CXP_CONFIG = "cxp.config"
    
    # ============================================================
    # PERMISOS POR MÓDULO - STOCK (Inventario)
    # ============================================================
    STOCK_VER = "stock.ver"
    STOCK_CREAR = "stock.crear"
    STOCK_EDITAR = "stock.editar"
    STOCK_ELIMINAR = "stock.eliminar"
    STOCK_AJUSTAR = "stock.ajustar"
    STOCK_TRANSFERIR = "stock.transferir"
    STOCK_REPORTES = "stock.reportes"
    STOCK_EXPORTAR = "stock.exportar"
    STOCK_IMPORTAR = "stock.importar"
    STOCK_CONFIG = "stock.config"
    
    # ============================================================
    # PERMISOS POR MÓDULO - COTIZACIONES
    # ============================================================
    COTIZACIONES_VER = "cotizaciones.ver"
    COTIZACIONES_CREAR = "cotizaciones.crear"
    COTIZACIONES_EDITAR = "cotizaciones.editar"
    COTIZACIONES_ELIMINAR = "cotizaciones.eliminar"
    COTIZACIONES_APROBAR = "cotizaciones.aprobar"
    COTIZACIONES_ANULAR = "cotizaciones.anular"
    COTIZACIONES_REPORTES = "cotizaciones.reportes"
    COTIZACIONES_EXPORTAR = "cotizaciones.exportar"
    COTIZACIONES_CONFIG = "cotizaciones.config"
    
    # ============================================================
    # PERMISOS POR MÓDULO - REPORTES
    # ============================================================
    REPORTES_VER = "reportes.ver"
    REPORTES_CREAR = "reportes.crear"
    REPORTES_EDITAR = "reportes.editar"
    REPORTES_ELIMINAR = "reportes.eliminar"
    REPORTES_EXPORTAR = "reportes.exportar"
    REPORTES_IMPORTAR = "reportes.importar"
    REPORTES_PROGRAMAR = "reportes.programar"
    REPORTES_CONFIG = "reportes.config"
    
    # ============================================================
    # PERMISOS POR BASE DE DATOS
    # ============================================================
    BASE_PRODUCCION_VER = "base.produccion.ver"
    BASE_PRODUCCION_EDITAR = "base.produccion.editar"
    BASE_TEST_VER = "base.test.ver"
    BASE_TEST_EDITAR = "base.test.editar"
    BASE_DESARROLLO_VER = "base.desarrollo.ver"
    BASE_DESARROLLO_EDITAR = "base.desarrollo.editar"

    # ============================================================
    # DESCRIPCIONES (para el panel de administración)
    # ============================================================
    # Qué hace cada permiso, en una línea, para que el admin no tilde a ciegas.
    # El panel las muestra debajo de cada check. El harness del panel
    # (`scripts/verificar_panel_admin.py`) exige que estén TODAS: si se agrega un
    # permiso al catálogo sin descripción, falla.
    DESCRIPCIONES = {
        # --- Administración ---
        "admin.acceso": "Ver la pestaña Administración del ERP. Es el interruptor del panel: sin esto la pestaña no aparece, aunque tenga los demás permisos.",
        "admin.dashboard": "Ver el resumen de administración: cantidad de usuarios, roles y estado general.",
        "admin.usuarios.ver": "Ver la lista de usuarios y el detalle de cada uno.",
        "admin.usuarios.crear": "Dar de alta usuarios nuevos. También habilita la vista de accesos rechazados.",
        "admin.usuarios.editar": "Modificar usuarios: nombre, mail, roles, bases, módulos y permisos por usuario.",
        "admin.usuarios.eliminar": "Eliminar usuarios. Queda una marca de borrado para que se propague a las otras PC.",
        "admin.usuarios.asignar_rol": "Cambiar el rol de un usuario. NO se verifica en el backend: el cambio de rol lo controla 'admin.usuarios.editar'.",
        "admin.usuarios.bloquear": "Bloquear y desbloquear usuarios. Un usuario bloqueado no puede entrar.",
        "admin.roles.ver": "Ver la lista de roles y los permisos de cada uno.",
        "admin.roles.crear": "Crear roles nuevos.",
        "admin.roles.editar": "Editar los permisos de un rol. El rol superadmin está protegido.",
        "admin.roles.eliminar": "Eliminar roles.",
        "admin.permisos.asignar": "Ver el catálogo de permisos y asignar permisos extra o restringidos a un usuario.",
        "admin.bases.config": "Editar qué bases (países) puede usar un usuario.",
        "admin.modulos.config": "Editar a qué módulos (CxP, Stock, etc.) entra un usuario.",
        "admin.auditoria.ver": "Ver la auditoría: quién cambió qué y cuándo.",
        "admin.auditoria.exportar": "Exportar la auditoría. NO se verifica: no hay endpoint de exportación propio; la vista se lee con 'admin.auditoria.ver'.",
        "admin.diagnostico": "Ver la pestaña Diagnóstico: comprueba si el servidor SQL responde en cada base, si el canal de actualizaciones se puede consultar y qué errores registró la aplicación.",
        "admin.sistema.config": "Configuración general del sistema. NO se verifica: no hay pantalla ni endpoint que lo use.",
        "admin.backup": "Exportar un respaldo de la configuración de usuarios y roles del almacén central.",
        "admin.restaurar": "Importar un respaldo de configuración (reemplaza usuarios y roles).",

        # --- CxP ---
        "cxp.ver": "Ver los comprobantes y las facturas de proveedores.",
        "cxp.crear": "Cargar facturas de proveedores: alta manual y extracción desde PDF o imagen.",
        "cxp.editar": "Modificar facturas ya cargadas. NO se verifica en el backend.",
        "cxp.eliminar": "Eliminar facturas cargadas.",
        "cxp.aprobar": "Aprobar facturas. NO se verifica en el backend.",
        "cxp.anular": "Anular facturas. NO se verifica en el backend.",
        "cxp.reportes": "Ver reportes de CxP. NO se verifica: los reportes salen por el módulo Reportes con 'reportes.ver'.",
        "cxp.exportar": "Exportar datos de CxP. NO se verifica en el backend.",
        "cxp.importar": "Importar facturas de proveedores masivamente desde Excel o CSV.",
        "cxp.config": "Configuración del módulo CxP. NO se verifica: no hay pantalla que lo use.",

        # --- Stock ---
        "stock.ver": "Consultar artículos, depósitos, categorías y stock.",
        "stock.crear": "Crear artículos y depósitos.",
        "stock.editar": "Modificar artículos y depósitos.",
        "stock.eliminar": "Eliminar artículos. NO se verifica en el backend.",
        "stock.ajustar": "Cargar ajustes de entrada y de salida, individuales o por lote.",
        "stock.transferir": "Cargar transferencias de stock entre depósitos.",
        "stock.reportes": "Ver el reporte de stock consolidado.",
        "stock.exportar": "Exportar datos de stock. NO se verifica en el backend.",
        "stock.importar": "Importar artículos o movimientos desde Excel o CSV.",
        "stock.config": "Configuración del módulo Stock. NO se verifica: no hay pantalla que lo use.",

        # --- Cotizaciones ---
        "cotizaciones.ver": "Consultar cotizaciones y tipos de cambio.",
        "cotizaciones.crear": "Cargar cotizaciones, a mano o importando un Excel.",
        "cotizaciones.editar": "Modificar cotizaciones cargadas. NO se verifica en el backend.",
        "cotizaciones.eliminar": "Eliminar cotizaciones. NO se verifica en el backend.",
        "cotizaciones.aprobar": "Aprobar cotizaciones. NO se verifica en el backend.",
        "cotizaciones.anular": "Anular cotizaciones. NO se verifica en el backend.",
        "cotizaciones.reportes": "Ver reportes de cotizaciones. NO se verifica en el backend.",
        "cotizaciones.exportar": "Exportar cotizaciones. NO se verifica en el backend.",
        "cotizaciones.config": "Configuración del módulo Cotizaciones. NO se verifica: no hay pantalla que lo use.",

        # --- Reportes ---
        "reportes.ver": "Ver los reportes: Ventas Globales, Ventas por País, Pendiente de Cobro y Contratos.",
        "reportes.crear": "Cargar una Venta Manual en Ventas Globales (carga individual e importación).",
        "reportes.editar": "Modificar reportes. NO se verifica en el backend.",
        "reportes.eliminar": "Eliminar una Venta Manual cargada.",
        "reportes.exportar": "Exportar reportes a Excel. NO se verifica: la exportación sale con 'reportes.ver'.",
        "reportes.importar": "Importar Ventas Manuales masivamente desde Excel o CSV.",
        "reportes.programar": "Programar el envío automático de reportes. NO se verifica: la funcionalidad no está construida.",
        "reportes.config": "Configuración del módulo Reportes. NO se verifica: no hay pantalla que lo use.",

        # --- Bases de datos ---
        "base.produccion.ver": "Ver las bases de producción. NO se verifica: el acceso a cada base se controla con 'Bases permitidas'.",
        "base.produccion.editar": "Editar las bases de producción. NO se verifica: el acceso a cada base se controla con 'Bases permitidas'.",
        "base.test.ver": "Ver las bases de prueba. NO se verifica: el acceso a cada base se controla con 'Bases permitidas'.",
        "base.test.editar": "Editar las bases de prueba. NO se verifica: el acceso a cada base se controla con 'Bases permitidas'.",
        "base.desarrollo.ver": "Ver las bases de desarrollo. NO se verifica: el acceso a cada base se controla con 'Bases permitidas'.",
        "base.desarrollo.editar": "Editar las bases de desarrollo. NO se verifica: el acceso a cada base se controla con 'Bases permitidas'.",
    }

    # Permisos que HOY NO se verifican en ningún endpoint: se pueden tildar pero
    # no cambian nada. El panel los pinta en gris con "sin efecto todavía"
    # (auditoría del 14/09/2026: 29 de 63 permisos del catálogo).
    #
    # Es una lista de EXCLUSIÓN a propósito: cuando se conecte uno, se saca de acá
    # y hay que corregir su descripción (que dice "NO se verifica"). Si se agrega
    # un permiso nuevo y no se clasifica, el harness del panel falla.
    SIN_VERIFICAR = {
        "admin.usuarios.asignar_rol",
        "admin.auditoria.exportar",
        "admin.sistema.config",
        "cxp.editar", "cxp.aprobar", "cxp.anular", "cxp.reportes",
        "cxp.exportar", "cxp.config",
        "stock.eliminar", "stock.exportar", "stock.config",
        "cotizaciones.editar", "cotizaciones.eliminar", "cotizaciones.aprobar",
        "cotizaciones.anular", "cotizaciones.reportes", "cotizaciones.exportar",
        "cotizaciones.config",
        "reportes.editar", "reportes.exportar", "reportes.programar",
        "reportes.config",
        "base.produccion.ver", "base.produccion.editar",
        "base.test.ver", "base.test.editar",
        "base.desarrollo.ver", "base.desarrollo.editar",
    }

    @classmethod
    def descripcion(cls, permiso):
        """Descripción de un permiso ('' si no está documentado)."""
        return cls.DESCRIPCIONES.get(permiso, "")

    @classmethod
    def esta_verificado(cls, permiso):
        """False si el permiso está en el catálogo pero ningún endpoint lo exige."""
        return permiso not in cls.SIN_VERIFICAR
    
    @classmethod
    def obtener_permisos_agrupados(cls):
        """Permisos agrupados por categoría, con el VALOR (no el nombre de la
        constante), su descripción y si el backend lo verifica hoy.

        El panel pinta los checkboxes con esto (arreglo 13.1 #3). Desde el
        14/09/2026 devuelve objetos en vez de strings, para poder mostrar la
        ayuda debajo de cada check y la insignia de los que todavía no controlan
        nada.
        """
        prefijos = {
            "administracion": "ADMIN_",
            "cxp": "CXP_",
            "stock": "STOCK_",
            "cotizaciones": "COTIZACIONES_",
            "reportes": "REPORTES_",
            "bases_datos": "BASE_",
        }
        agrupados = {}
        for grupo, prefijo in prefijos.items():
            valores = []
            vistos = set()
            for nombre in dir(cls):
                if not nombre.startswith(prefijo) or nombre.startswith('_'):
                    continue
                valor = getattr(cls, nombre)
                if not isinstance(valor, str) or valor in vistos:
                    continue
                vistos.add(valor)
                valores.append({
                    "valor": valor,
                    "descripcion": cls.descripcion(valor),
                    "verificado": cls.esta_verificado(valor),
                })
            agrupados[grupo] = sorted(valores, key=lambda v: v["valor"])
        return agrupados

    @classmethod
    def es_permiso_valido(cls, permiso: str) -> bool:
        """True si el string es un permiso del catálogo (para validar entradas)."""
        return isinstance(permiso, str) and permiso in cls.obtener_todos_permisos()
    
    @classmethod
    def obtener_permisos_modulo(cls, modulo):
        """Obtiene permisos de un módulo específico"""
        modulo = modulo.upper()
        return [
            getattr(cls, p) for p in dir(cls)
            if p.startswith(f"{modulo}_") and not p.startswith('_')
        ]
    
    @classmethod
    def obtener_todos_permisos(cls):
        """Obtiene todos los permisos del sistema (solo constantes str).

        Fix C4: el dir(cls) anterior incluía los métodos (@classmethod)
        como si fueran permisos -> rompía la serialización de listas de
        permisos (Object of type method is not JSON serializable)."""
        return [
            getattr(cls, p) for p in dir(cls)
            if not p.startswith('_') and isinstance(getattr(cls, p), str)
        ]
    
    @classmethod
    def obtener_permisos_por_nivel(cls, nivel):
        """Obtiene permisos según nivel de acceso"""
        # Niveles: 1=Lectura, 2=Edición, 3=Admin
        if nivel == 1:
            return [
                cls.CXP_VER, cls.STOCK_VER, cls.COTIZACIONES_VER, 
                cls.REPORTES_VER, cls.BASE_PRODUCCION_VER
            ]
        elif nivel == 2:
            return [
                cls.CXP_VER, cls.CXP_CREAR, cls.CXP_EDITAR,
                cls.STOCK_VER, cls.STOCK_CREAR, cls.STOCK_EDITAR,
                cls.COTIZACIONES_VER, cls.COTIZACIONES_CREAR, cls.COTIZACIONES_EDITAR,
                cls.REPORTES_VER, cls.REPORTES_CREAR,
                cls.BASE_PRODUCCION_VER, cls.BASE_PRODUCCION_EDITAR
            ]
        elif nivel == 3:
            return cls.obtener_todos_permisos()
        return []