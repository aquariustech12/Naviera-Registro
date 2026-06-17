# portal_cliente/admin.py (nuevo archivo o modificar existente)

from django.contrib import admin
from django.urls import path
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

from .models import CotizacionPendiente, TarifarioGMP
from .cotizador import calcular_costo_cotizacion, generar_cotizacion_pdf
from .mia_herramientas import enviar_whatsapp_jid


JULIAN_JID = "5216444475422@s.whatsapp.net"
FINANZAS_JID = "5215563183674@s.whatsapp.net"


@admin.register(CotizacionPendiente)
class CotizacionPendienteAdmin(admin.ModelAdmin):
    list_display = ['buque', 'naviera', 'tipo_servicio', 'rango_buque', 'estado', 'costo_unitario', 'fecha_creacion']
    list_filter = ['estado', 'tipo_servicio', 'rango_buque', 'fecha_creacion']
    search_fields = ['buque__nombre_buque', 'naviera__nombre_empresa']
    
    fieldsets = (
        ('Datos del Formulario', {
            'fields': ('naviera', 'buque', 'datos_formulario', 'eslora'),
            'description': 'Datos extraídos del formulario FGMP-FC-01'
        }),
        ('Clasificación del Auditor', {
            'fields': ('tipo_servicio', 'rango_buque', 'notas_auditor'),
            'description': 'Seleccione el tipo de servicio y clasificación del buque'
        }),
        ('Costos Calculados', {
            'fields': ('costo_unitario', 'iva', 'total'),
            'classes': ('collapse',),
            'description': 'Se calcula automáticamente al aprobar'
        }),
        ('Estado', {
            'fields': ('estado', 'fecha_aprobacion', 'documento_generado'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ['costo_unitario', 'iva', 'total', 'fecha_creacion', 'fecha_aprobacion', 'documento_generado']
    
    def save_model(self, request, obj, form, change):
        """Recalcular costos siempre que cambie tipo_servicio o rango_buque."""
        if change:
            # Si cambió algo relevante, recalcular
            if 'tipo_servicio' in form.changed_data or 'rango_buque' in form.changed_data:
                try:
                    costos = calcular_costo_cotizacion(obj.tipo_servicio, obj.rango_buque)
                    obj.costo_unitario = costos['costo_unitario']
                    obj.iva = costos['iva']
                    obj.total = costos['total']
                except Exception as e:
                    self.message_user(request, f"Error recalculando costos: {e}", level='error')
        
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:cotizacion_id>/aprobar/',
                self.admin_site.admin_view(self.aprobar_cotizacion),
                name='aprobar_cotizacion',
            ),
        ]
        return custom_urls + urls
    
    def aprobar_cotizacion(self, request, cotizacion_id):
        """Vista para aprobar cotización y generar PDF."""
        cotizacion = get_object_or_404(CotizacionPendiente, id=cotizacion_id)
        
        if cotizacion.estado != 'borrador':
            messages.error(request, f"La cotización ya está {cotizacion.get_estado_display()}")
            return redirect('admin:portal_cliente_cotizacionpendiente_change', cotizacion_id)
        
        if not cotizacion.tipo_servicio or not cotizacion.rango_buque:
            messages.error(request, "Debe seleccionar tipo de servicio y rango de buque antes de aprobar")
            return redirect('admin:portal_cliente_cotizacionpendiente_change', cotizacion_id)
        
        try:
            # Calcular costos
            costos = calcular_costo_cotizacion(cotizacion.tipo_servicio, cotizacion.rango_buque)
            cotizacion.costo_unitario = costos['costo_unitario']
            cotizacion.iva = costos['iva']
            cotizacion.total = costos['total']
            
            # Generar PDF
            ruta_pdf = generar_cotizacion_pdf(cotizacion)
            
            # Actualizar estado
            cotizacion.estado = 'aprobada'
            cotizacion.fecha_aprobacion = timezone.now()
            cotizacion.save()
            
            # Notificaciones
            msg = f"""✅ *COTIZACIÓN APROBADA*

🏢 *Naviera:* {cotizacion.naviera.nombre_empresa}
🚢 *Buque:* {cotizacion.buque.nombre_buque}
📄 *Servicio:* {cotizacion.get_tipo_servicio_display()}
📊 *Rango:* {cotizacion.get_rango_buque_display()}
💰 *Total:* ${cotizacion.total}

PDF generado y disponible en portal."""
            
            enviar_whatsapp_jid(JULIAN_JID, msg)
            enviar_whatsapp_jid(FINANZAS_JID, msg)
            
            messages.success(request, f"Cotización aprobada. PDF generado: {os.path.basename(ruta_pdf)}")
            
        except Exception as e:
            messages.error(request, f"Error generando cotización: {str(e)}")
        
        return redirect('admin:portal_cliente_cotizacionpendiente_change', cotizacion_id)
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Agregar botón de aprobar en la vista de edición."""
        extra_context = extra_context or {}
        
        if object_id:
            cotizacion = self.get_object(request, object_id)
            if cotizacion and cotizacion.estado == 'borrador':
                extra_context['show_aprobar'] = True
                extra_context['aprobar_url'] = f'../../aprobar/{object_id}/'
        
        return super().changeform_view(request, object_id, form_url, extra_context)

@admin.register(TarifarioGMP)
class TarifarioGMPAdmin(admin.ModelAdmin):
    list_display = ['tipo_servicio', 'rango_buque', 'año', 'costo_base']
    list_filter = ['tipo_servicio', 'rango_buque', 'año']