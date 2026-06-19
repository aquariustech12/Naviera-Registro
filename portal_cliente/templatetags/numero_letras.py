# portal_cliente/templatetags/numero_letras.py
from django import template
from decimal import Decimal

register = template.Library()

UNIDADES = (
    'CERO', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE',
    'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISEIS', 'DIECISIETE',
    'DIECIOCHO', 'DIECINUEVE', 'VEINTE'
)
DECENAS = (
    'VENTI', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA'
)
CENTENAS = (
    'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 'QUINIENTOS',
    'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS'
)


def _convertir(numero):
    """
    Función interna recursiva. Trabaja solo con la parte entera.
    Renombrada para evitar colisión con el filtro de template.
    """
    entero = int(abs(numero))

    if entero <= 20:
        return UNIDADES[entero]
    elif entero < 30:
        return DECENAS[0] + UNIDADES[entero - 20]
    elif entero < 100:
        decena = entero // 10
        unidad = entero % 10
        if unidad == 0:
            return DECENAS[decena - 2]
        return DECENAS[decena - 2] + ' Y ' + UNIDADES[unidad]
    elif entero < 1000:
        centena = entero // 100
        resto   = entero % 100
        if resto == 0:
            return 'CIEN' if centena == 1 else CENTENAS[centena - 1]
        return CENTENAS[centena - 1] + ' ' + _convertir(resto)
    elif entero < 1_000_000:
        miles = entero // 1000
        resto = entero % 1000
        letras_miles = 'MIL' if miles == 1 else _convertir(miles) + ' MIL'
        if resto == 0:
            return letras_miles
        return letras_miles + ' ' + _convertir(resto)
    elif entero < 1_000_000_000:
        millones = entero // 1_000_000
        resto    = entero % 1_000_000
        letras_m = 'UN MILLÓN' if millones == 1 else _convertir(millones) + ' MILLONES'
        if resto == 0:
            return letras_m
        return letras_m + ' ' + _convertir(resto)
    else:
        return 'NÚMERO DEMASIADO GRANDE'


def numero_a_letras(numero):
    """
    Convierte Decimal/float/int a letras en español (formato mexicano).
    Usable desde Python: numero_a_letras(cot.total)
    """
    if isinstance(numero, str):
        numero = Decimal(numero)

    numero  = abs(numero)
    entero  = int(numero)
    decimal = int(round((numero - entero) * 100))

    letras = _convertir(entero)
    letras += f' PESOS {decimal:02d}/100 M.N.'
    return letras


@register.filter(name='numero_a_letras')
def numero_a_letras_filter(value):
    """Filtro de Django template: {{ cotizacion.total|numero_a_letras }}"""
    try:
        return numero_a_letras(value)
    except Exception:
        return str(value)
