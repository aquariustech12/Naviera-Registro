# portal_cliente/models.py
# AGREGAR AL FINAL DEL ARCHIVO EXISTENTE

from django.db import models
from django.contrib.auth.models import User

class ConversacionMIA(models.Model):
    """
    Memoria de conversación de MIA.
    Usa numero_whatsapp como identificador en lugar de usuario Django,
    porque MIA se accede vía WhatsApp, no vía portal web.
    """
    ROL_CHOICES = [
        ('user', 'Auditor'),
        ('mia', 'MIA'),
    ]
    INTENCION_CHOICES = [
        ('ANALISIS_DOCUMENTO', 'Análisis de Documento'),
        ('CONSULTA_NORMATIVA', 'Consulta Normativa PBIP'),
        ('CONSULTA_ESTADO', 'Consulta Estado Expediente'),
        ('CONVERSACION_GENERAL', 'Conversación General'),
        ('RECORDATORIO', 'Recordatorio/Alerta'),
    ]
    
    # CAMBIO CLAVE: numero_whatsapp en lugar de usuario ForeignKey
    numero_whatsapp = models.CharField(
        max_length=20,
        help_text="Número de WhatsApp del interlocutor (ej: 5216444475422)"
    )
    
    rol = models.CharField(max_length=10, choices=ROL_CHOICES)
    contenido = models.TextField()
    intencion = models.CharField(max_length=30, choices=INTENCION_CHOICES, null=True, blank=True)
    metadatos = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Mensaje de Conversación MIA'
        verbose_name_plural = 'Conversaciones MIA'
        indexes = [
            models.Index(fields=['numero_whatsapp', 'timestamp']),
        ]
    
    def __str__(self):
        return f"[{self.rol.upper()}] {self.numero_whatsapp} | {self.contenido[:50]}..."