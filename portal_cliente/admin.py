# portal_cliente/admin.py

import os
from decimal import Decimal
from django.contrib import admin
from django.urls import path
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

from .models import CotizacionPendiente, TarifarioGMP
from .cotizador import calcular_costo_cotizacion, generar_cotizacion_pdf
from .mia_herramientas import enviar_whatsapp_jid


JULIAN_JID   = "5216444475422@s.whatsapp.net"
FINANZAS_JID = "5215563183674@s.whatsapp.net"


@admin.register(CotizacionPendiente)
class CotizacionPendienteAdmin(admin.ModelAdmin):
    list_display   = ['buque', 'naviera', 'tipo_servicio', 'rango_buque', 'estado', 'costo_unitario', 'fecha_creacion']
    list_filter    = ['estado', 'tipo_servicio', 'rango_buque', 'fecha_creacion']
    search_fields  = ['buque__nombre_buque', 'naviera__nombre_empresa']

    fieldsets = (
        ('Datos del Formulario', {
            'fields': ('naviera', 'buque', 'datos_formulario', 'eslora'),
            'description': 'Datos extraídos del formulario FGMP-FC-01'
        }),
        ('Clasificación del Auditor', {
            'fields': ('tipo_servicio', 'rango_buque', 'notas_auditor'),
            'description': 'Seleccione el tipo de servicio y clasificación del buque'
        }),
        ('Costos (editables: úsalos para aplicar descuentos)', {
            'fields': ('costo_unitario', 'iva', 'total'),
            'description': 'Al cambiar el costo unitario, el IVA y el total se recalculan solos, salvo que los captures a mano.'
        }),
        ('Estado', {
            'fields': ('estado', 'fecha_aprobacion', 'documento_generado'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ['fecha_creacion', 'fecha_aprobacion', 'documento_generado']

    def save_model(self, request, obj, form, change):
        """Costos editables. Si cambia tipo/rango (sin tocar costos) se recalculan desde la tarifa;
        si cambia solo el costo unitario, IVA y total se recalculan; lo capturado a mano se respeta."""
        if change:
            cambios = set(form.changed_data)
            costos_tocados = cambios & {'costo_unitario', 'iva', 'total'}
            if ('tipo_servicio' in cambios or 'rango_buque' in cambios) and not costos_tocados \
                    and obj.tipo_servicio and obj.rango_buque:
                try:
                    costos = calcular_costo_cotizacion(obj.tipo_servicio, obj.rango_buque)
                    obj.costo_unitario = costos['costo_unitario']
                    obj.iva            = costos['iva']
                    obj.total          = costos['total']
                except Exception as e:
                    self.message_user(request, f"Error recalculando costos: {e}", level='error')
            elif 'costo_unitario' in cambios and not ({'iva', 'total'} & cambios) \
                    and obj.costo_unitario is not None:
                obj.iva   = (obj.costo_unitario * Decimal('0.16')).quantize(Decimal('0.01'))
                obj.total = obj.costo_unitario + obj.iva

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

    def _aprobar(self, request, cotizacion):
        """Marca la cotización como aprobada. La señal procesar_aprobacion_y_activar_portal genera
        el PDF, crea el entregable y avisa al cliente. Devuelve un texto de error o None."""
        if cotizacion.estado != 'borrador':
            return f"La cotización ya está {cotizacion.get_estado_display()}"
        if not cotizacion.tipo_servicio or not cotizacion.rango_buque:
            return "Debe seleccionar tipo de servicio y rango de buque antes de aprobar"
        if cotizacion.costo_unitario is None or cotizacion.iva is None or cotizacion.total is None:
            return "Capture costo unitario, IVA y total antes de aprobar"

        cotizacion.estado           = 'aprobada'
        cotizacion.fecha_aprobacion = timezone.now()
        cotizacion.save()

        msg = (
            f"✅ *COTIZACIÓN APROBADA*\n\n"
            f"🏢 *Naviera:* {cotizacion.naviera.nombre_empresa}\n"
            f"🚢 *Buque:* {cotizacion.buque.nombre_buque}\n"
            f"📄 *Servicio:* {cotizacion.get_tipo_servicio_display()}\n"
            f"📊 *Rango:* {cotizacion.get_rango_buque_display()}\n"
            f"💰 *Total:* ${cotizacion.total:,.2f}\n\n"
            f"El PDF se está generando y se enviará al cliente."
        )
        enviar_whatsapp_jid(JULIAN_JID, msg)
        enviar_whatsapp_jid(FINANZAS_JID, msg)
        return None

    def aprobar_cotizacion(self, request, cotizacion_id):
        """Vista del botón Aprobar."""
        cotizacion = get_object_or_404(CotizacionPendiente, id=cotizacion_id)
        error = self._aprobar(request, cotizacion)
        if error:
            messages.error(request, error)
        else:
            messages.success(request, "Cotización aprobada. El PDF se genera y se envía al cliente en unos segundos.")
        return redirect('admin:portal_cliente_cotizacionpendiente_change', cotizacion_id)

    actions = ['aprobar_y_enviar']

    def aprobar_y_enviar(self, request, queryset):
        aprobadas = 0
        for cotizacion in queryset:
            error = self._aprobar(request, cotizacion)
            if error:
                self.message_user(request, f"Cotización {cotizacion.id}: {error}", level=messages.WARNING)
            else:
                aprobadas += 1
        if aprobadas:
            self.message_user(request, f"{aprobadas} cotización(es) aprobada(s). Los PDF se generan y se envían en segundos.")
    aprobar_y_enviar.short_description = "Aprobar y enviar al cliente"

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Agregar botón de aprobar en la vista de edición."""
        extra_context = extra_context or {}
        if object_id:
            cotizacion = self.get_object(request, object_id)
            if cotizacion and cotizacion.estado == 'borrador':
                extra_context['show_aprobar'] = True
                extra_context['aprobar_url']  = f'../../aprobar/{object_id}/'
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(TarifarioGMP)
class TarifarioGMPAdmin(admin.ModelAdmin):
    # CORREGIDO: 'año' → 'anio' (nombre real del campo en el modelo)
    list_display = ['tipo_servicio', 'rango_buque', 'anio', 'costo_base']
    list_filter  = ['tipo_servicio', 'rango_buque', 'anio']


# ---------------------------------------------------------------------------
# Regenerar el PDF de una cotizacion (aprobada o no) desde los campos del admin
# ---------------------------------------------------------------------------
def _regenerar_pdf_cotizaciones(modeladmin, request, queryset, avisar):
    from django.contrib import messages as _messages
    from .cotizacion_pdf import regenerar_pdf_cotizacion
    from .models import enviar_whatsapp_jid

    for cot in queryset:
        if cot.costo_unitario is None or cot.iva is None or cot.total is None:
            modeladmin.message_user(request, f"Cotizacion {cot.id}: faltan costo, IVA o total.", _messages.ERROR)
            continue
        if not cot.documento_generado_id:
            modeladmin.message_user(request, f"Cotizacion {cot.id}: aun no tiene PDF; usa 'Aprobar y enviar al cliente'.", _messages.WARNING)
            continue
        try:
            regenerar_pdf_cotizacion(cot)
        except Exception as exc:
            modeladmin.message_user(request, f"Cotizacion {cot.id}: error al regenerar el PDF: {exc}", _messages.ERROR)
            continue

        msg = f"Cotizacion {cot.id}: PDF regenerado (total ${cot.total:,.2f})."
        if avisar:
            naviera = cot.naviera
            if naviera.telefono_contacto:
                num = naviera.telefono_contacto.replace(' ', '').replace('-', '').replace('+', '')
                if not num.startswith('521'):
                    num = '521' + (num[2:] if num.startswith('52') else num)
                try:
                    ok = enviar_whatsapp_jid(f"{num}@s.whatsapp.net", (
                        f"📄 *COTIZACIÓN ACTUALIZADA*\n\n"
                        f"Estimado(a) {naviera.contacto_principal or 'Cliente'},\n\n"
                        f"La cotización para *{cot.buque.nombre_buque}* fue actualizada.\n"
                        f"💰 *Total:* ${cot.total:,.2f} MXN\n\n"
                        f"🔗 https://portal.maritimesecuritymx.com/portal/"
                    ))
                except Exception:
                    ok = False
                msg += " Cliente avisado por WhatsApp." if ok else " No se pudo avisar al cliente por WhatsApp."
            else:
                msg += " La naviera no tiene telefono de contacto: no se aviso."
        modeladmin.message_user(request, msg, _messages.SUCCESS)


def regenerar_pdf_desde_campos(modeladmin, request, queryset):
    _regenerar_pdf_cotizaciones(modeladmin, request, queryset, avisar=False)
regenerar_pdf_desde_campos.short_description = "Regenerar PDF desde los campos (sin avisar al cliente)"


def regenerar_pdf_y_avisar(modeladmin, request, queryset):
    _regenerar_pdf_cotizaciones(modeladmin, request, queryset, avisar=True)
regenerar_pdf_y_avisar.short_description = "Regenerar PDF desde los campos y avisar al cliente por WhatsApp"


from django.contrib import admin as _admin
from .models import CotizacionPendiente as _CotPend
_ma = _admin.site._registry.get(_CotPend)
if _ma is not None:
    _ma.actions = list(_ma.actions or []) + [regenerar_pdf_desde_campos, regenerar_pdf_y_avisar]
