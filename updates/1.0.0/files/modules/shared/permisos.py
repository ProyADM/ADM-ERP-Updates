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
    
    @classmethod
    def obtener_permisos_agrupados(cls):
        """Retorna permisos agrupados por categoría"""
        return {
            "administracion": [
                p for p in dir(cls) 
                if p.startswith('ADMIN_') and not p.startswith('_')
            ],
            "cxp": [
                p for p in dir(cls) 
                if p.startswith('CXP_') and not p.startswith('_')
            ],
            "stock": [
                p for p in dir(cls) 
                if p.startswith('STOCK_') and not p.startswith('_')
            ],
            "cotizaciones": [
                p for p in dir(cls) 
                if p.startswith('COTIZACIONES_') and not p.startswith('_')
            ],
            "reportes": [
                p for p in dir(cls) 
                if p.startswith('REPORTES_') and not p.startswith('_')
            ],
            "bases_datos": [
                p for p in dir(cls) 
                if p.startswith('BASE_') and not p.startswith('_')
            ]
        }
    
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