# ============================================================
# CONFIGURACIÓN DE CLIENTES - VERSIÓN ESCALABLE
# ============================================================

# ============================================================
# 1. CLIENTES CON MONEDA FORZADA POR DIVISIÓN
# ============================================================

# 🔴 Clientes que siempre deben mostrarse en PESOS (PS)
# Estructura: { 'division': [lista_de_clientes] }
CLIENTES_FORZADOS_PS = {
    # República Dominicana (división 5)
    '5': [
        'CERILAB',
        'HOSPITAL MOSCOSO PUELLO',
        'CENTRO MEDICO DOMINICO CUBANO',
        'DGM',
        'ACAP',
        'INSTITUTO MATERNO INFANTIL',
        'COOPADEPE',
        'GAMMA DIAGNOSTICO DEL SUR SRL',
        'CONSEJO DEL PODER JUDICIAL',
        'EDESUR DOMINICANA, S. A.',
        'DR JULIO VARGAS',
        'OFIT SRL',
        'ARAP',
    ],
    # Guatemala (división 7)
    '7': [
        # Clientes de Guatemala que deben ir en PS
    ],
    # México (división 4)
    '4': [
        # Clientes de México que deben ir en PS
    ],
    # Default (aplica a todas las divisiones)
    'default': [
        # Clientes que siempre deben ir en PS en cualquier división
    ],
}

# 🔴 Clientes que siempre deben mostrarse en DOLARES (DL)
CLIENTES_FORZADOS_DL = {
    '5': [
        'SIDESYS COSTA RICA',
        'SIDESYS HONDURAS',
        'SIDESYS GUATEMALA',
        'SIDESYS PERU',
        'SIDESYS MEXICO',
        'NOVALOGIQ - BANRESERVAS',
        'DHL Express Dominicana, S. A.',
        'CAMARA DE COMERCIO SD',
        'MAPFRE BHD SEGUROS',
        'HUMANO SEGUROS',
        'APAP',
    ],
    '7': [
        # Clientes de Guatemala que deben ir en DL
    ],
    '4': [
        # Clientes de México que deben ir en DL
    ],
    'default': [
        # Clientes que siempre deben ir en DL en cualquier división
    ],
}

# ============================================================
# 2. FUNCIONES PARA OBTENER CONFIGURACIÓN POR DIVISIÓN
# ============================================================

def get_clientes_forzados_ps(division=None):
    """
    Obtiene la lista de clientes forzados a PS para una división específica.
    Si no hay configuración para la división, usa 'default'.
    """
    if division is None:
        division = 'default'
    
    division_str = str(division)
    clientes = []
    
    # Agregar clientes de la división específica
    if division_str in CLIENTES_FORZADOS_PS:
        clientes.extend(CLIENTES_FORZADOS_PS[division_str])
    
    # Agregar clientes default (aplican a todas las divisiones)
    if 'default' in CLIENTES_FORZADOS_PS:
        clientes.extend(CLIENTES_FORZADOS_PS['default'])
    
    return clientes

def get_clientes_forzados_dl(division=None):
    """
    Obtiene la lista de clientes forzados a DL para una división específica.
    Si no hay configuración para la división, usa 'default'.
    """
    if division is None:
        division = 'default'
    
    division_str = str(division)
    clientes = []
    
    if division_str in CLIENTES_FORZADOS_DL:
        clientes.extend(CLIENTES_FORZADOS_DL[division_str])
    
    if 'default' in CLIENTES_FORZADOS_DL:
        clientes.extend(CLIENTES_FORZADOS_DL['default'])
    
    return clientes

def get_tipo_cliente_excluir():
    """
    Retorna los tipos de cliente que deben excluirse de ciertos reportes.
    Por defecto, excluye intercompany (tipo 5).
    """
    return ['5']  # Intercompany

# ============================================================
# 3. CONFIGURACIÓN PARA REPORTES ESPECÍFICOS
# ============================================================

# 🔴 Clientes que deben excluirse del consolidado de ventas
EXCLUIR_CONSOLIDADO_VENTAS = {
    '5': [  # División 5 - República Dominicana
        # Clientes específicos a excluir
    ],
    'default': [
        # Clientes a excluir en cualquier división
    ],
}

def get_clientes_excluir_consolidado(division=None):
    """Obtiene la lista de clientes a excluir del consolidado de ventas"""
    if division is None:
        division = 'default'
    
    division_str = str(division)
    clientes = []
    
    if division_str in EXCLUIR_CONSOLIDADO_VENTAS:
        clientes.extend(EXCLUIR_CONSOLIDADO_VENTAS[division_str])
    
    if 'default' in EXCLUIR_CONSOLIDADO_VENTAS:
        clientes.extend(EXCLUIR_CONSOLIDADO_VENTAS['default'])
    
    return clientes

# ============================================================
# 4. MAPEO DE DIVISIONES
# ============================================================

DIVISIONES = {
    '5': 'República Dominicana',
    '7': 'Guatemala',
    '4': 'México',
    '10': 'Honduras',
    '11': 'Paraguay',
    '12': 'Perú',
    '6': 'Uruguay',
    '8': 'Ecuador',
    '9': 'Colombia',
    '1': 'Argentina',
}

def get_division_label(division):
    """Obtiene el nombre de la división a partir del código"""
    return DIVISIONES.get(str(division), f'División {division}')