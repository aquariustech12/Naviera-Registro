# portal_cliente/models.py

import os
import io
import threading
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from PyPDF2 import PdfMerger

from .tarifario import TARIFARIO_GMP, TEXTOS_PROPUESTA_COMPLETA

JULIAN_JID = "5216444475422@s.whatsapp.net"


# ============================================================================
# MODELOS
# ============================================================================

class ConversacionMIA(models.Model):
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

    numero_whatsapp = models.CharField(max_length=20)
    rol             = models.CharField(max_length=10, choices=ROL_CHOICES)
    contenido       = models.TextField()
    intencion       = models.CharField(max_length=30, choices=INTENCION_CHOICES, null=True, blank=True)
    metadatos       = models.JSONField(null=True, blank=True)
    timestamp       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Mensaje de Conversación MIA'
        verbose_name_plural = 'Conversaciones MIA'
        indexes = [models.Index(fields=['numero_whatsapp', 'timestamp'])]

    def __str__(self):
        return f"[{self.rol.upper()}] {self.numero_whatsapp} | {self.contenido[:50]}..."


class AlertaProactiva(models.Model):
    TIPOS = [
        ('ALTA_INCOMPLETA',          'Alta de naviera incompleta'),
        ('DOCS_PBIP_FALTANTES',      'Documentos PBIP faltantes'),
        ('DOC_PROXIMO_VENCER',       'Documento próximo a vencer'),
        ('COTIZACION_SIN_RESPUESTA', 'Cotización sin respuesta'),
        ('RESUMEN_DIARIO',           'Resumen diario para auditor'),
    ]

    naviera         = models.ForeignKey('naviera_registro.Naviera', on_delete=models.CASCADE, null=True, blank=True)
    buque           = models.ForeignKey('naviera_registro.Buque',   on_delete=models.CASCADE, null=True, blank=True)
    tipo_alerta     = models.CharField(max_length=30, choices=TIPOS)
    mensaje_enviado = models.TextField()
    fecha_envio     = models.DateTimeField(auto_now_add=True)
    canal           = models.CharField(max_length=20, default='whatsapp')
    exito           = models.BooleanField(default=True)
    reintentos      = models.IntegerField(default=0)

    class Meta:
        unique_together = ['naviera', 'buque', 'tipo_alerta', 'fecha_envio']

    def __str__(self):
        return f"{self.tipo_alerta} | {self.naviera} | {self.fecha_envio.strftime('%d/%m/%Y')}"


class TarifarioGMP(models.Model):
    TIPO_SERVICIO = [
        ('verificacion', 'Verificación'),
        ('evaluacion',   'Evaluación'),
    ]
    RANGO_BUQUE = [
        ('grande',  'Grandes y Complejos (>80m)'),
        ('mediano', 'Medianos y Especializados (<=80m, múltiples cubiertas)'),
        ('pequeno', 'Pequeños y Especializados (<=80m, cubierta simple)'),
    ]

    tipo_servicio = models.CharField(max_length=20, choices=TIPO_SERVICIO)
    rango_buque   = models.CharField(max_length=20, choices=RANGO_BUQUE)
    anio          = models.IntegerField()
    costo_base    = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together     = ['tipo_servicio', 'rango_buque', 'anio']
        verbose_name        = 'Tarifa GMP'
        verbose_name_plural = 'Tarifario GMP'

    def __str__(self):
        return f"{self.get_tipo_servicio_display()} - {self.get_rango_buque_display()} ({self.anio})"

    def costo_con_incremento(self):
        return self.costo_base


class CotizacionPendiente(models.Model):
    ESTADOS = [
        ('borrador',  'Borrador'),
        ('aprobada',  'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    naviera          = models.ForeignKey('naviera_registro.Naviera', on_delete=models.CASCADE)
    buque            = models.ForeignKey('naviera_registro.Buque',   on_delete=models.CASCADE)
    datos_formulario = models.JSONField(default=dict)

    tipo_servicio  = models.CharField(max_length=20, choices=TarifarioGMP.TIPO_SERVICIO, blank=True, null=True)
    rango_buque    = models.CharField(max_length=20, choices=TarifarioGMP.RANGO_BUQUE,   blank=True, null=True)
    eslora         = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    notas_auditor  = models.TextField(blank=True)

    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    iva            = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    total          = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    estado           = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    fecha_creacion   = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(blank=True, null=True)

    documento_generado = models.ForeignKey(
        'naviera_registro.DocumentoEntregable',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Cotización {self.buque.nombre_buque} - {self.get_estado_display()}"


# ============================================================================
# SIGNALS
# ============================================================================

from naviera_registro.models import Naviera as NavieraRegistro  # noqa: E402
from naviera_registro.models import DocumentoEntregable          # noqa: E402
from portal_cliente.mia_herramientas import enviar_whatsapp_jid  # noqa: E402


@receiver(post_save, sender=NavieraRegistro)
def alertar_nueva_naviera_mia(sender, instance, created, **kwargs):
    if created:
        def _notificar():
            msg = (
                f"🏢 *MIA - NUEVA NAVIERA REGISTRADA*\n\n"
                f"🚀 *{instance.nombre_empresa}* se dio de alta en el portal.\n"
                f"👤 *Contacto:* {instance.contacto_principal or 'No especificado'}\n"
                f"📧 *Email:* {instance.correo_electronico or 'No especificado'}\n"
                f"📱 *Teléfono:* {instance.telefono_contacto or 'No especificado'}\n\n"
                f"⏳ Pendiente de completar documentos administrativos."
            )
            enviar_whatsapp_jid(JULIAN_JID, msg)
        threading.Thread(target=_notificar, daemon=True).start()


def _calcular_costo(instance):
    tipo  = instance.tipo_servicio.lower() if instance.tipo_servicio else 'verificacion'
    rango = instance.rango_buque.lower()   if instance.rango_buque   else 'pequeno'
    try:
        base = TARIFARIO_GMP[tipo][rango]['2026']
        instance.costo_unitario = Decimal(str(base))
    except KeyError:
        instance.costo_unitario = Decimal('99998.35')
    instance.iva   = instance.costo_unitario * Decimal('0.16')
    instance.total = instance.costo_unitario + instance.iva


@receiver(pre_save, sender=CotizacionPendiente)
def calcular_costos_en_borrador(sender, instance, **kwargs):
    if not instance.pk:
        _calcular_costo(instance)
        return
    try:
        old = CotizacionPendiente.objects.get(pk=instance.pk)
        if old.tipo_servicio != instance.tipo_servicio or old.rango_buque != instance.rango_buque:
            _calcular_costo(instance)
    except CotizacionPendiente.DoesNotExist:
        _calcular_costo(instance)


@receiver(post_save, sender=CotizacionPendiente)
def procesar_aprobacion_y_activar_portal(sender, instance, created, **kwargs):
    if instance.estado != 'aprobada' or instance.documento_generado_id:
        return

    def hilo_emision_pdf(cot_id):
        from weasyprint import HTML
        from .templatetags.numero_letras import numero_a_letras

        cot     = CotizacionPendiente.objects.get(id=cot_id)
        buque   = cot.buque
        naviera = cot.naviera
        tipo_s  = cot.tipo_servicio.lower()
        rango_b = cot.rango_buque.lower()

        textos            = TEXTOS_PROPUESTA_COMPLETA.get(tipo_s, TEXTOS_PROPUESTA_COMPLETA['verificacion'])
        descripcion_rango = textos['descripcion_rango'].get(rango_b, '')

        context = {
            'cotizacion':       cot,
            'buque':            buque,
            'naviera':          naviera,
            'titulo_servicio':  textos['titulo_servicio'],
            'descripcion_rango': descripcion_rango,
            'actividades':      textos['actividades'],
            'condiciones_pago': textos['condiciones_pago'],
            'clausula_primera': textos['clausula_primera'].format(
                nombre_buque=buque.nombre_buque,
                descripcion_rango=descripcion_rango,
            ),
            'subtotal':      cot.costo_unitario,
            'iva':           cot.iva,
            'total':         cot.total,
            'total_letras':  numero_a_letras(cot.total),
            'fecha':         timezone.now().strftime('%d/%m/%Y'),
            'vigencia':      (timezone.now() + timezone.timedelta(days=30)).strftime('%d/%m/%Y'),
        }

        pdf_bytes = HTML(string=render_to_string('cotizacion_propuesta.html', context)).write_pdf()

        portada_path = os.path.join(settings.MEDIA_ROOT, 'plantillas', 'portada_cotizacion.pdf')
        if os.path.exists(portada_path):
            with open(portada_path, 'rb') as f:
                portada_bytes = f.read()
            merger = PdfMerger()
            merger.append(io.BytesIO(portada_bytes))
            merger.append(io.BytesIO(pdf_bytes))
            buf = io.BytesIO()
            merger.write(buf)
            pdf_final = buf.getvalue()
        else:
            pdf_final = pdf_bytes

        entregable         = DocumentoEntregable()
        entregable.naviera = naviera
        entregable.buque   = buque
        entregable.tipo    = 'COTIZACION'
        entregable.save()

        campo_archivo = next(
            (f.name for f in entregable._meta.get_fields() if isinstance(f, models.FileField)),
            None
        )
        if campo_archivo:
            getattr(entregable, campo_archivo).save(
                f"FGMP_PE_01_COTIZACION_{cot.id}.pdf",
                ContentFile(pdf_final),
                save=True
            )

        CotizacionPendiente.objects.filter(id=cot.id).update(documento_generado=entregable)

        try:
            enviar_whatsapp_jid(JULIAN_JID, (
                f"✅ *MIA - PORTAL ACTUALIZADO*\n\n"
                f"Cotización *ID {cot.id}* de *{naviera.nombre_empresa}* aprobada.\n"
                f"💰 *Monto:* ${cot.total:,.2f} MXN\n"
                f"🟢 PDF disponible para el cliente."
            ))
        except Exception as e:
            print(f"Error WA Julian: {e}")

        if naviera.telefono_contacto:
            try:
                num = naviera.telefono_contacto.replace(' ', '').replace('-', '').replace('+', '')
                if not num.startswith('521'):
                    num = '521' + (num[2:] if num.startswith('52') else num)
                enviar_whatsapp_jid(f"{num}@s.whatsapp.net", (
                    f"📄 *COTIZACIÓN DISPONIBLE*\n\n"
                    f"Estimado(a) {naviera.contacto_principal or 'Cliente'},\n\n"
                    f"La cotización para *{buque.nombre_buque}* ya está lista.\n"
                    f"💰 *Total:* ${cot.total:,.2f} MXN\n\n"
                    f"🔗 https://portal.maritimesecuritymx.com/portal/"
                ))
            except Exception as e:
                print(f"Error WA cliente: {e}")

    threading.Thread(target=hilo_emision_pdf, args=(instance.id,), daemon=True).start()


@receiver(post_delete, sender=DocumentoEntregable)
def notificar_eliminacion_cotizacion(sender, instance, **kwargs):
    if instance.tipo == 'COTIZACION':
        try:
            enviar_whatsapp_jid(JULIAN_JID, (
                f"🗑️ *MIA - COTIZACIÓN ELIMINADA*\n\n"
                f"📄 {getattr(instance, 'nombre_documento', None) or 'COTIZACION'}\n"
                f"🏢 {instance.naviera.nombre_empresa}\n"
                f"🚢 {instance.buque.nombre_buque if instance.buque else 'N/A'}"
            ))
        except Exception as e:
            print(f"Error notificando eliminación: {e}")