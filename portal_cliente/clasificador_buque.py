# portal_cliente/clasificador_buque.py

def clasificar_por_eslora_y_cubiertas(eslora: float, cubiertas: int = 1) -> str:
    """
    Clasifica buque según criterio GMP:
    - ≤80m + 1 cubierta = pequeño
    - ≤80m + 2+ cubiertas = mediano  
    - >80m = grande (sin importar cubiertas)
    """
    if eslora > 80:
        return 'grande'
    elif eslora <= 80 and cubiertas >= 2:
        return 'mediano'
    else:
        return 'pequeno'


def descripcion_rango(rango: str) -> str:
    descripciones = {
        'grande': 'Grandes y Complejos (>80m)',
        'mediano': 'Medianos y Especializados (≤80m, múltiples cubiertas)',
        'pequeno': 'Pequeños y Especializados (≤80m, cubierta simple)',
    }
    return descripciones.get(rango, 'Desconocido')