# portal_cliente/tarifario.py

TARIFARIO_GMP = {
    'verificacion': {
        'grande':  {'2026' : 126287.74},
        'mediano': {'2026': 118359.77},
        'pequeno': {'2026': 99998.35},
    },
    'evaluacion': {
        'grande':  {'2026': 151745.67},
        'mediano': {'2026': 134495.63},
        'pequeno': {'2026': 117221.05},
    }
}

TEXTOS_COTIZACION = {
    'verificacion': {
        'titulo_servicio': 'VERIFICACIÓN INICIAL',
        'descripcion_rango': {
            'grande': 'Buques Grandes y Complejos (Eslora > 80m).',
            'mediano': 'Buques Medianos y Especializados (≤80m, múltiples cubiertas).',
            'pequeno': 'Buques Pequeños y Especializados (Lancha con Cubierta, Carga y Pasaje).'
        },
        'actividades': [
            'Apertura de verificación.',
            'Verificación documental.',
            'Verificación de equipos y sistemas de protección del buque.',
            'Ejercicio de Protección establecido en el PPB.',
            'Reporte de deficiencias en materia de Protección Marítima.',
            'Cierre de verificación.'
        ],
        'condiciones_pago': [
            'Pago del 100% de los honorarios previo a la entrega del informe final y trámite ante la autoridad.'
        ]
    },
    'evaluacion': {
        'titulo_servicio': 'EVALUACIÓN DE PROTECCIÓN',
        'descripcion_rango': {
            'grande': 'Buques Grandes y Complejos (Eslora > 80m).',
            'mediano': 'Buques Medianos y Especializados (Estructura Multicubierta).',
            'pequeno': 'Buques Pequeños y Especializados (Estructura Monocubierta).'
        },
        'actividades': [
            'Identificación de las medidas de protección existentes, los procedimientos y las operaciones.',
            'Identificación y evaluación de las funciones clave del buque que es importante proteger.',
            'Identificación de las posibles amenazas a las funciones clave del buque y la probabilidad de que se materialicen.',
            'Identificación de los puntos vulnerables, incluidos los factores humanos, en la infraestructura, políticas y procedimientos.'
        ],
        'condiciones_pago': [
            'Anticipo del 50% al inicio del proyecto para el desarrollo de la metodología de evaluación.',
            'Finiquito del 50% contra la entrega formal del reporte técnico aprobatorio.'
        ]
    }
}

RANGO_KEYWORDS = {
    'grande': [
        'supertanquero', 'superpetrolero', 'plataforma', 'perforación',
        'construcción naval', 'portacontenedor', 'multipropósito',
        'crucero', 'ro-ro', 'turismo', 'buque de turismo', 'petrolero'
    ],
    'mediano': [
        'gasero', 'productos químicos', 'carga refrigerada', 'tanque',
        'granelero', 'abastecimiento', 'quimiquero', 'refrigerado'
    ],
    'pequeno': [
        'investigación', 'intervención en pozos', 'limpieza de derrames',
        'geofísica', 'instalación de equipos', 'mantenimiento', 'salvamento',
        'remolcador', 'asistencia', 'embarcación', 'lancha', 'pasajeros',
        'velero', 'yate', 'peschereccio', 'barco', 'embarcación menor'
    ]
}

def clasificar_rango_buque(tipo_buque: str) -> str:
    texto = tipo_buque.lower()
    for rango, keywords in RANGO_KEYWORDS.items():
        if any(kw in texto for kw in keywords):
            return rango
    return 'pequeno'  # fallback conservador

def obtener_costo(tipo_servicio: str, rango: str, anio: int) -> float:
    anio_str = str(anio)
    return TARIFARIO_GMP[tipo_servicio][rango][anio_str]

# Textos para la propuesta económica completa (páginas 2-4 del PDF)
TEXTOS_PROPUESTA_COMPLETA = {
    'verificacion': {
        'titulo_servicio': 'VERIFICACIÓN INICIAL',
        'descripcion_rango': {
            'grande': 'Buques Grandes y Complejos (Eslora > 80m).',
            'mediano': 'Buques Medianos y Especializados (≤80m, múltiples cubiertas).',
            'pequeno': 'Buques Pequeños y Especializados (Lancha con Cubierta, Carga y Pasaje).'
        },
        'actividades': [
            'Apertura de verificación.',
            'Verificación documental.',
            'Verificación de equipos y sistemas de protección del buque.',
            'Ejercicio de Protección establecido en el PPB.',
            'Reporte de deficiencias en materia de Protección Marítima.',
            'Cierre de verificación.',
            'Carpeta de Servicio.'
        ],
        'condiciones_pago': [
            'A. Pago en una sola exhibición a la firma de la cotización.',
            'B. Pago del 50% a la firma de la cotización y el 50% restante en la fecha establecida para el servicio.'
        ],
        'clausula_primera': 'Verificación Inicial del Buque "{nombre_buque}"; {descripcion_rango}, el cual incluye; 1. Apertura de verificación; 2. Verificación documental; 3. Verificación de equipos y sistemas de protección del buque; 4. Ejercicio de Protección establecido en el PPB; 5. Reporte de deficiencias en materia de Protección Marítima; 6. Cierre de verificación; 7. Carpeta de Servicio.',
    },
    'evaluacion': {
        'titulo_servicio': 'EVALUACIÓN DE LA PROTECCIÓN DEL BUQUE',
        'descripcion_rango': {
            'grande': 'Buques Grandes y Complejos (Eslora > 80m).',
            'mediano': 'Buques Medianos y Especializados (Estructura Multicubierta).',
            'pequeno': 'Buques Pequeños y Especializados (Estructura Monocubierta).'
        },
        'actividades': [
            'Medidas de la protección del Código PBIP adoptadas en el Buque.',
            'Examen de las personas actividades, operaciones y servicios que es necesario proteger.',
            'Identificación de posibles amenazas y probabilidad de ocurrencia para establecer la necesidad de adoptar medidas de mitigación.',
            'Identificación de las vulnerabilidades y medidas correctivas.',
            'Conclusiones y modo de acción emergentes.',
            'Informe en Carpeta correspondiente.'
        ],
        'condiciones_pago': [
            'A. Pago en una sola exhibición a la firma de la cotización.',
            'B. Pago del 50% a la firma de la cotización y el 50% restante en la fecha establecida para el servicio.'
        ],
        'clausula_primera': 'Evaluación de la Protección del Buque "{nombre_buque}" que incluye: Medidas de la protección del Código PBIP adoptadas en el Buque. Examen de las personas actividades, operaciones y servicios que es necesario proteger. Identificación de posibles amenazas y probabilidad de ocurrencia para establecer la necesidad de adoptar medidas de mitigación. Identificación de las vulnerabilidades y medidas correctivas. Conclusiones y modo de acción emergente.',
    },
}