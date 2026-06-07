from django.contrib import admin
from django.core.mail import EmailMessage
from django.utils import timezone
from django.contrib import messages
import threading
from .models import Naviera, Buque, RequisitoBuque, DocumentoEntregable
from portal_cliente.mia_herramientas import enviar_whatsapp_jid

# 1. Vista en línea para los Buques dentro de Naviera
class BuqueInline(admin.TabularInline):
    model = Buque
    extra = 1
    fields = ('nombre_buque', 'OMI')

@admin.register(Naviera)
class NavieraAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'contacto_principal', 'alta_completa', 'fecha_alta_completa')
    inlines = [BuqueInline]

@admin.register(Buque)
class BuqueAdmin(admin.ModelAdmin):
    list_display = ('nombre_buque', 'OMI', 'naviera', 'metodo_pago')
    list_filter = ('naviera',)

@admin.register(RequisitoBuque)
class RequisitoBuqueAdmin(admin.ModelAdmin):
    list_display = ('nombre_documento', 'naviera', 'buque', 'categoria', 'fecha_subida')
    list_filter = ('categoria', 'naviera', 'fecha_subida')
    search_fields = ('nombre_documento', 'naviera__nombre_empresa', 'buque__nombre_buque')
    
    def delete_model(self, request, obj):
        """
        Intercepta la eliminación desde la pantalla de confirmación del admin.
        Se dispara SOLO cuando el admin confirma el borrado.
        """
        naviera = obj.naviera
        nombre_doc = obj.nombre_documento
        categoria = obj.categoria
        cliente_email = naviera.correo_electronico if naviera else None
        nombre_empresa = naviera.nombre_empresa if naviera else "Desconocida"
        motivo = obj.motivo_rechazo or "No especificado"
        
        # --- ALERTA MIA A TI ---
        try:
            tipo_txt = "ADMINISTRATIVO" if categoria == 'ADMINISTRATIVO' else "PBIP/OPERATIVO"
            msg_mia = (
                f"🗑️ *MIA - DOCUMENTO ELIMINADO*\n\n"
                f"🏢 *Naviera:* {nombre_empresa}\n"
                f"📄 *Documento:* {nombre_doc}\n"
                f"📂 *Categoría:* {tipo_txt}\n"
                f"👤 *Eliminado por:* {request.user.username}\n"
                f"❌ *Motivo:* {motivo}\n"
                f"📅 *Fecha:* {timezone.now().strftime('%d/%m/%Y %H:%M')}"
            )
            threading.Thread(
                target=enviar_whatsapp_jid, 
                args=("5216444475422@s.whatsapp.net", msg_mia), 
                daemon=True
            ).start()
        except Exception as wa_err:
            print(f"❌ Error alerta MIA eliminación: {wa_err}")
        
        # --- CORREO AL CLIENTE ---
        if cliente_email:
            try:
                asunto_rechazo = f"Documento rechazado | {nombre_doc} | {nombre_empresa}"
                cuerpo_rechazo = (
                    f"Estimado(a) cliente,\n\n"
                    f"Le informamos que el documento '{nombre_doc}' ha sido revisado y no cumple "
                    f"con los requisitos establecidos para su procesamiento.\n\n"
                    f"Motivo: {motivo}\n\n"
                    f"Por favor, suba nuevamente el documento correcto desde su portal de cliente.\n\n"
                    f"Si tiene dudas, puede contactarnos respondiendo a este correo.\n\n"
                    f"Atentamente,\n"
                    f"Equipo de Operaciones - OPR"
                )
                email_rechazo = EmailMessage(
                    subject=asunto_rechazo,
                    body=cuerpo_rechazo,
                    from_email='Portal OPR <08opr.manager@gmail.com>',
                    to=[cliente_email],
                    bcc=['generalmanager@maritimeprotection.mx'],
                    reply_to=['generalmanager@maritimeprotection.mx'],
                )
                email_rechazo.send(fail_silently=False)
                print(f"✅ Correo de rechazo enviado a {cliente_email}")
            except Exception as mail_err:
                print(f"❌ Error correo rechazo: {mail_err}")
        
        # --- ELIMINAR EL DOCUMENTO ---
        super().delete_model(request, obj)
        
        # Mensaje de confirmación en el admin
        messages.success(request, f"Documento '{nombre_doc}' eliminado. Alerta MIA y correo al cliente enviados.")
    
    def delete_queryset(self, request, queryset):
        """
        Si eliminan varios documentos a la vez desde el listado (acción en masa).
        """
        for obj in queryset:
            self.delete_model(request, obj)

@admin.register(DocumentoEntregable)
class DocumentoEntregableAdmin(admin.ModelAdmin):
    list_display = ['naviera', 'buque', 'tipo', 'fecha_subida']
    list_filter = ['tipo', 'fecha_subida']