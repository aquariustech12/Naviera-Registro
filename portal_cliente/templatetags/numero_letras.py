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

def numero_a_letras(numero):
    """
    Convierte un número a letras en español (formato mexicano para moneda).
    """
    if isinstance(numero, str):
        numero = Decimal(numero)
    
    numero = abs(numero)
    entero = int(numero)
    decimal = int((numero - entero) * 100)
    
    if entero <= 20:
        letras = UNIDADES[entero]
    elif entero < 30:
        letras = DECENAS[0] + UNIDADES[entero - 20]
    elif entero < 100:
        decena = entero // 10
        unidad = entero % 10
        if unidad == 0:
            letras = DECENAS[decena - 2]
        else:
            letras = DECENAS[decena - 2] + ' Y ' + UNIDADES[unidad]
    elif entero < 1000:
        centena = entero // 100
        resto = entero % 100
        if resto == 0:
            if centena == 1:
                letras = 'CIEN'
            else:
                letras = CENTENAS[centena - 1]
        else:
            letras = CENTENAS[centena - 1] + ' ' + numero_a_letras(resto)
    elif entero < 1000000:
        miles = entero // 1000
        resto = entero % 1000
        if miles == 1:
            letras_miles = 'MIL'
        else:
            letras_miles = numero_a_letras(miles) + ' MIL'
        if resto == 0:
            letras = letras_miles
        else:
            letras = letras_miles + ' ' + numero_a_letras(resto)
    elif entero < 1000000000:
        millones = entero // 1000000
        resto = entero % 1000000
        if millones == 1:
            letras_millones = 'UN MILLÓN'
        else:
            letras_millones = numero_a_letras(millones) + ' MILLONES'
        if resto == 0:
            letras = letras_millones
        else:
            letras = letras_millones + ' ' + numero_a_letras(resto)
    else:
        return 'NÚMERO DEMASIADO GRANDE'
    
    if decimal > 0:
        letras += ' PESOS ' + str(decimal).zfill(2) + '/100 M.N.'
    else:
        letras += ' PESOS 00/100 M.N.'
    
    return letras

@register.filter
def numero_a_letras(value):
    try:
        return numero_a_letras(value)
    except:
        return str(value)