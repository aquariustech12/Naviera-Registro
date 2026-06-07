# portal_cliente/mia_memoria.py — REEMPLAZAR TODO

from .models import ConversacionMIA
import json


def obtener_contexto(numero_whatsapp: str, limite: int = 5) -> list:
    """
    Recupera los últimos N mensajes de la conversación con un número específico.
    """
    mensajes = ConversacionMIA.objects.filter(
        numero_whatsapp=numero_whatsapp
    ).order_by('-timestamp')[:limite]
    
    return [
        {
            "rol": m.rol,
            "contenido": m.contenido,
            "intencion": m.intencion,
            "timestamp": m.timestamp.strftime("%H:%M")
        }
        for m in reversed(mensajes)
    ]


def guardar_mensaje(numero_whatsapp: str, rol: str, contenido: str, intencion: str = None, metadatos: dict = None):
    """
    Guarda un mensaje en la memoria de conversación.
    """
    ConversacionMIA.objects.create(
        numero_whatsapp=numero_whatsapp,
        rol=rol,
        contenido=contenido[:2000],
        intencion=intencion,
        metadatos=json.dumps(metadatos, ensure_ascii=False) if metadatos else None
    )