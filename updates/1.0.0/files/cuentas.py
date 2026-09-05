# Cuentas contables de egreso disponibles para facturas de proveedor
# Formato: "codigo": {"nombre": "...", "cco": True/False}
# cco=True  → requiere centro de costo
# cco=False → no requiere centro de costo

CUENTAS = {
    # 51 - Gastos de personal / viáticos
    "510101017": {"nombre": "Peaje/Estacionamiento",        "cco": True},
    "510101018": {"nombre": "Combustible",                   "cco": True},
    "510101020": {"nombre": "Pasajes Aéreos/Transp. Terres", "cco": True},
    "510101021": {"nombre": "Viáticos socio",                "cco": True},
    "510101022": {"nombre": "Alojamiento",                   "cco": True},
    "510101023": {"nombre": "Alimentos/Refrigerios",         "cco": True},

    # 52 - Gastos de administración
    "520101":    {"nombre": "Sueldos",                       "cco": False},
    "520106":    {"nombre": "Gastos Intercompany",           "cco": False},
    "520107":    {"nombre": "Facturas Relacionadas",         "cco": False},

    # 5202 - Comercialización
    "520201":    {"nombre": "Publicidad y Propaganda",       "cco": False},

    # 5203 - Estructura
    "520301":    {"nombre": "Papelería/Librería",            "cco": False},
    "520302":    {"nombre": "Insumos Oficina",               "cco": False},
    "520303":    {"nombre": "Suscripciones",                 "cco": False},
    "520304":    {"nombre": "Correo/Encomiendas",            "cco": False},
    "520306":    {"nombre": "Gastos/Seguro de Rodados",      "cco": False},
    "520310":    {"nombre": "Seguros",                       "cco": False},
    "520311":    {"nombre": "Egresos No Deducibles",         "cco": True},
    "520312":    {"nombre": "Alquileres",                    "cco": False},
    "520313":    {"nombre": "Expensas",                      "cco": False},
    "520314":    {"nombre": "Servicio en la Nube - Sidesys", "cco": False},
    "520316":    {"nombre": "Honorarios Contables",          "cco": False},
    "520317":    {"nombre": "Honorarios Legales",            "cco": False},
    "520318":    {"nombre": "Honorarios Técnicos y Otros",   "cco": False},
    "520319":    {"nombre": "Gastos Varios de Estructura",   "cco": False},
    "520320":    {"nombre": "Reclutamiento Personal",        "cco": False},
    "520321":    {"nombre": "Gastos de Hardware",            "cco": False},
    "520322":    {"nombre": "Reparación y Mantenimiento",    "cco": False},
    "520323":    {"nombre": "Gastos Certificaciones IRAM",   "cco": False},
    "520324":    {"nombre": "Gastos Legales/Cert. Varias",   "cco": False},
    "520325":    {"nombre": "Gastos de Limpieza",            "cco": False},
    "520326":    {"nombre": "Gastos Data Center",            "cco": False},
    "520327":    {"nombre": "Gastos de Software",            "cco": False},

    # 5204 - Servicios
    "520401":    {"nombre": "Telefonía Fija",                "cco": False},
    "520402":    {"nombre": "Telefonía Celular",             "cco": False},
    "520403":    {"nombre": "Internet/Conectividad",         "cco": False},
    "520404":    {"nombre": "Energía Eléctrica",             "cco": False},
    "520405":    {"nombre": "Gas de Red",                    "cco": False},
    "520406":    {"nombre": "Agua/Bidones",                  "cco": False},

    # 5208 - Gastos bancarios
    "520801":    {"nombre": "Gastos/Comisiones Bancarias",   "cco": False},
    "520802":    {"nombre": "Gastos/Com. Bancarias Exterior","cco": True},
    "520804":    {"nombre": "Gastos Transferencias Exteriores","cco": False},

    # 5251 - Otros egresos
    "525101":    {"nombre": "Diferencia Arqueo Neg",         "cco": False},
    "525102":    {"nombre": "Egresos Varios",                "cco": False},
    "525104":    {"nombre": "Diferencia Cambio Neg",         "cco": False},
    "525105":    {"nombre": "Egresos No Computables",        "cco": False},
    "525106":    {"nombre": "Juicios",                       "cco": False},
}

# NITs con cuenta contable fija (independiente del concepto)
# Agregar acá cualquier proveedor que siempre use la misma cuenta
NIT_CUENTA_FIJA = {
    "49728253": "520312",   # Regus → Alquileres
    "8503443":  "520312",   # Bodeguitas → Alquileres
}
