# portal_cliente/models.py
# AGREGAR AL FINAL DEL ARCHIVO EXISTENTE

from django.db import models
from django.contrib.auth.models import User
from .tarifario import TARIFARIO_GMP, TEXTOS_COTIZACION, TEXTOS_PROPUESTA_COMPLETA

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

# portal_cliente/models.py — AGREGAR ESTO

class AlertaProactiva(models.Model):
    TIPOS = [
        ('ALTA_INCOMPLETA', 'Alta de naviera incompleta'),
        ('DOCS_PBIP_FALTANTES', 'Documentos PBIP faltantes'),
        ('DOC_PROXIMO_VENCER', 'Documento próximo a vencer'),
        ('COTIZACION_SIN_RESPUESTA', 'Cotización sin respuesta'),
        ('RESUMEN_DIARIO', 'Resumen diario para auditor'),
    ]
    
    naviera = models.ForeignKey('naviera_registro.Naviera', on_delete=models.CASCADE, null=True, blank=True)
    buque = models.ForeignKey('naviera_registro.Buque', on_delete=models.CASCADE, null=True, blank=True)
    tipo_alerta = models.CharField(max_length=30, choices=TIPOS)
    mensaje_enviado = models.TextField()
    fecha_envio = models.DateTimeField(auto_now_add=True)
    canal = models.CharField(max_length=20, default='whatsapp')  # whatsapp, email
    exito = models.BooleanField(default=True)
    reintentos = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['naviera', 'buque', 'tipo_alerta', 'fecha_envio']  # Evitar duplicados diarios
    
    def __str__(self):
        return f"{self.tipo_alerta} | {self.naviera} | {self.fecha_envio.strftime('%d/%m/%Y')}"

# portal_cliente/models.py (AGREGAR AL FINAL)

class TarifarioGMP(models.Model):
    TIPO_SERVICIO = [
        ('verificacion', 'Verificación'),
        ('evaluacion', 'Evaluación'),
    ]
    RANGO_BUQUE = [
        ('grande', 'Grandes y Complejos (>80m)'),
        ('mediano', 'Medianos y Especializados (≤80m, múltiples cubiertas)'),
        ('pequeno', 'Pequeños y Especializados (≤80m, cubierta simple)'),
    ]
    
    tipo_servicio = models.CharField(max_length=20, choices=TIPO_SERVICIO)
    rango_buque = models.CharField(max_length=20, choices=RANGO_BUQUE)
    anio = models.IntegerField()
    costo_base = models.DecimalField(max_digits=12, decimal_places=2)
    
    class Meta:
        unique_together = ['tipo_servicio', 'rango_buque', 'anio']
        verbose_name = 'Tarifa GMP'
        verbose_name_plural = 'Tarifario GMP'
    
    def __str__(self):
        return f"{self.get_tipo_servicio_display()} - {self.get_rango_buque_display()} ({self.anio})"
    
    def costo_con_incremento(self):
        return self.costo_base


class CotizacionPendiente(models.Model):
    """
    Cotización en estado borrador, pendiente de aprobación del auditor.
    """
    ESTADOS = [
        ('borrador', 'Borrador'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]
    
    naviera = models.ForeignKey('naviera_registro.Naviera', on_delete=models.CASCADE)
    buque = models.ForeignKey('naviera_registro.Buque', on_delete=models.CASCADE)
    
    # Datos del formulario extraídos
    datos_formulario = models.JSONField(default=dict)
    
    # Selección del auditor
    tipo_servicio = models.CharField(max_length=20, choices=TarifarioGMP.TIPO_SERVICIO, blank=True, null=True)
    rango_buque = models.CharField(max_length=20, choices=TarifarioGMP.RANGO_BUQUE, blank=True, null=True)
    eslora = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, help_text="Eslora en metros")
    notas_auditor = models.TextField(blank=True, help_text="Notas o ajustes del auditor")
    
    # Costos calculados
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    iva = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(blank=True, null=True)
    
    # Si se aprobó, link al documento generado
    documento_generado = models.ForeignKey('naviera_registro.DocumentoEntregable', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"Cotización {self.buque.nombre_buque} - {self.get_estado_display()}"

class Entregable(models.Model):
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('incompleto', 'Incompleto - Rechazado'),
        ('pendiente_servicio', 'Pendiente - Tipo de servicio no definido'),
        ('procesado', 'Procesado'),
        ('generado_auto', 'Generado Automáticamente'),
        ('aprobado', 'Aprobado'),
        ('enviado_cliente', 'Enviado al Cliente'),
    ]
    
    estado = models.CharField(max_length=30, choices=ESTADOS, default='pendiente')
    cotizacion_generada = models.BooleanField(default=False)
    generado_automaticamente = models.BooleanField(default=False)
    formulario_origen = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='cotizaciones_generadas'
    )
    observaciones = models.TextField(blank=True)

class Naviera(models.Model):
    
    # Campo opcional para registrar el tipo de servicio desde el oficio
    TIPO_SERVICIO_CHOICES = [
        ('verificacion', 'Verificación'),
        ('evaluacion', 'Evaluación'),
    ]
    tipo_servicio = models.CharField(
        max_length=20, 
        choices=TIPO_SERVICIO_CHOICES,
        blank=True,
        null=True,
        help_text="Tipo de servicio según oficio de asignación de la autoridad"
    )

# ============================================================================
# SIGNALS - ALERTAS AUTOMÁTICAS DE MIA
# ============================================================================
from django.db.models.signals import post_save
from django.dispatch import receiver
from naviera_registro.models import Naviera  # Importación segura
from portal_cliente.mia_herramientas import enviar_whatsapp_jid
from .tarifario import TEXTOS_COTIZACION
import threading

@receiver(post_save, sender=Naviera)
def alertar_nueva_naviera_mia(sender, instance, created, **kwargs):
    """
    Detecta de forma automática cuando se registra una nueva naviera
    en la base de datos y dispara la alerta a MIA.
    """
    if created:
        def hilo_notificacion():
            JULIAN_JID = "5216444475422@s.whatsapp.net"
            msg = (
                f"🏢 *MIA - NUEVA NAVIERA REGISTRADA*\n\n"
                f"🚀 La empresa *{instance.nombre_empresa}* se ha dado de alta con éxito en el portal.\n"
                f"👤 *Contacto Principal:* {instance.contacto_principal or 'No especificado'}\n"
                f"📧 *Email:* {instance.correo_electronico or 'No especificado'}\n"
                f"📱 *Teléfono:* {instance.telefono_contacto or 'No especificado'}\n\n"
                f"⏳ Queda a la espera de que completen sus documentos administrativos."
            )
            enviar_whatsapp_jid(JULIAN_JID, msg)
            
        threading.Thread(target=hilo_notificacion, daemon=True).start()

# ===========================================================================
# CORRECCIÓN DE SEÑALES: FLUJO HÍBRIDO DE COTIZACIONES OPR (GLOBAL MARITIME PROTECTION)
# ===========================================================================
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from decimal import Decimal
import threading

from naviera_registro.models import DocumentoEntregable
from .models import CotizacionPendiente
from .tarifario import TARIFARIO_GMP, TEXTOS_COTIZACION  
from .mia_herramientas import enviar_whatsapp_jid

@receiver(pre_save, sender=CotizacionPendiente)
def calcular_costos_en_borrador(sender, instance, **kwargs):
    """
    Recalcula costos SIEMPRE que cambie tipo_servicio o rango_buque.
    """
    # Si es nueva instancia, calcular
    if not instance.pk:
        _calcular_costo(instance)
        return
    
    # Si existe, verificar si cambió algo relevante
    try:
        old = CotizacionPendiente.objects.get(pk=instance.pk)
        if old.tipo_servicio != instance.tipo_servicio or old.rango_buque != instance.rango_buque:
            _calcular_costo(instance)
    except CotizacionPendiente.DoesNotExist:
        _calcular_costo(instance)


def _calcular_costo(instance):
    """Función auxiliar para calcular costos."""
    tipo_servicio = instance.tipo_servicio.lower() if instance.tipo_servicio else 'verificacion'
    rango_buque = instance.rango_buque.lower() if instance.rango_buque else 'pequeno'
    
    try:
        costo_base = TARIFARIO_GMP[tipo_servicio][rango_buque]['2026']
        instance.costo_unitario = Decimal(str(costo_base))
    except KeyError:
        instance.costo_unitario = Decimal('99998.35')
    
    instance.iva = instance.costo_unitario * Decimal('0.16')
    instance.total = instance.costo_unitario + instance.iva

@receiver(post_save, sender=CotizacionPendiente)
def procesar_aprobacion_y_activar_portal(sender, instance, created, **kwargs):
    """
    Solo actúa cuando pasa a 'aprobada'. Genera el PDF físico, inyecta el 
    entregable en VERDE (cargado) y activa el botón de descarga en el portal.
    """
    if instance.estado == 'aprobada' and not instance.documento_generado_id:
        
        def hilo_emision_pdf(cot_id):
            # Traer instancia fresca de la base de datos
            cot = CotizacionPendiente.objects.get(id=cot_id)
            buque = cot.buque
            naviera = cot.naviera
            
            tipo_servicio = cot.tipo_servicio.lower()
            rango_buque = cot.rango_buque.lower()
            
            # Obtener textos del diccionario de la OPR en tarifario.py
            textos = TEXTOS_PROPUESTA_COMPLETA.get(tipo_servicio, TEXTOS_PROPUESTA_COMPLETA['verificacion'])
            titulo_servicio = textos['titulo_servicio']
            descripcion_rango = textos['descripcion_rango'].get(rango_buque, '')
            actividades = textos['actividades']
            condiciones_pago = textos['condiciones_pago']
            # Formatear cláusula primera con variables
            clausula_primera = textos['clausula_primera'].format(
                nombre_buque=buque.nombre_buque,
                descripcion_rango=descripcion_rango,
            )
            # Convertir número a letras
            from .templatetags.numero_letras import numero_a_letras
            total_letras = numero_a_letras(cot.total)

            # Generar el archivo binario del PDF con WeasyPrint
            from weasyprint import HTML
            context = {
                'cotizacion': cot,
                'buque': buque,
                'naviera': naviera,
                'titulo_servicio': titulo_servicio,
                'descripcion_rango': descripcion_rango,
                'actividades': actividades,
                'condiciones_pago': condiciones_pago,
                'clausula_primera': clausula_primera,
                'subtotal': cot.costo_unitario,
                'iva': cot.iva,
                'total': cot.total,
                'total_letras': total_letras,
                'fecha': timezone.now().strftime('%d/%m/%Y'),
                'vigencia': (timezone.now() + timezone.timedelta(days=30)).strftime('%d/%m/%Y'),
            }          

            html_string = render_to_string('cotizacion_propuesta.html', context)
            pdf_bytes = HTML(string=html_string).write_pdf()
            
            # Crear el entregable forzando el estatus a "cargado" para que pinte en VERDE
            entregable = DocumentoEntregable()
            entregable.naviera = naviera
            entregable.buque = buque
            entregable.tipo = 'COTIZACION'
            
            # Inspección dinámica de nombres de columnas de tu base de datos
            for f_name in ['nombre_documento', 'nombre', 'descripcion']:
                if hasattr(entregable, f_name):
                    setattr(entregable, f_name, f"Propuesta Económica Oficial - ID {cot.id}")
                    break
                    
            for f_status in ['estado', 'estatus', 'validado']:
                if hasattr(entregable, f_status):
                    setattr(entregable, f_status, 'cargado')  # Pone el semáforo en verde de inmediato
                    break

            entregable.save()
            
            # Guardar el PDF en el FileField que tenga asignado el entregable
            campo_archivo = None
            for f in entregable._meta.get_fields():
                if isinstance(f, models.FileField):
                    campo_archivo = f.name
                    break
            
            if campo_archivo:
                file_field = getattr(entregable, campo_archivo)
                file_field.save(f"FGMP_PE_01_COTIZACION_{cot.id}.pdf", ContentFile(pdf_bytes), save=True)
            
            # Vinculamos el documento generado usando un update directo para no disparar señales cíclicas
            CotizacionPendiente.objects.filter(id=cot.id).update(documento_generado=entregable)
            
            # Alerta MIA por WhatsApp
            try:
                JULIAN_JID = "5216444475422@s.whatsapp.net"
                msg = (
                    f"✅ *MIA - PORTAL ACTUALIZADO*\n\n"
                    f"La cotización *ID {cot.id}* de *{naviera.nombre_empresa}* fue aprobada.\n"
                    f"💰 *Monto:* ${cot.total:,.2f} MXN\n\n"
                    f"🟢 El estatus del expediente cambió a *Cargado (Verde)* y el botón de descarga ya está activo para el cliente."
                )
                enviar_whatsapp_jid(JULIAN_JID, msg)
            except Exception as e:
                print(f"Error en notificación de WhatsApp: {e}")

        threading.Thread(target=hilo_emision_pdf, args=(instance.id,), daemon=True).start()