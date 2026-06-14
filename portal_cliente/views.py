from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from naviera_registro.models import Buque, RequisitoBuque, PuntoPBIP, DocumentoEntregable
from django.core.mail import EmailMessage
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
# Importamos el motor de MIA
from .mia_core import procesar_input_mia
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
import json
from .mia_herramientas import enviar_whatsapp_jid  # Solo si lo usas directamente
import threading
import os
import hashlib

@login_required
@csrf_protect
def cambiar_password_obligatorio(request):
    print(f"DEBUG: Entrando a cambiar_password_obligatorio")
    print(f"DEBUG: Usuario: {request.user.username} | is_staff: {request.user.is_staff}")

    if request.user.is_staff:
        print("DEBUG: El usuario YA es staff. Redirigiendo al portal_cliente directamente.")
        return redirect('portal_cliente')

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save(commit=False) 
            user.is_staff = True 
            user.save() 
            update_session_auth_hash(request, user)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Contraseña establecida correctamente.')
            return redirect('portal_cliente')
    else:
        form = PasswordChangeForm(request.user)
        
    return render(request, 'cambiar_password.html', {'form': form})

@login_required
def portal_cliente(request):
    print(f"DEBUG: Entrando a vista portal_cliente")
    if not request.user.is_staff:
        print("DEBUG: Usuario NO es staff. Redirigiendo a cambio de password.")
        return redirect('cambiar_password_obligatorio')
    
    try:
        naviera = request.user.naviera
        print(f"DEBUG: Naviera encontrada: {naviera}")
        buques = naviera.buques.all() 
        puntos_pbip = PuntoPBIP.objects.all().order_by('numero')
        
        # --- FIX: Todos los docs admin de la naviera, con o sin buque ---
        admin_docs = RequisitoBuque.objects.filter(
            naviera=naviera,
            categoria='ADMINISTRATIVO'
        ).values_list('nombre_documento', flat=True)
        # ----------------------------------------------------------------
        naviera.docs_admin_listos = list(admin_docs)
        
    except Exception:
        naviera = None
        buques = []
        puntos_pbip = []

    for buque in buques:
        docs_subidos = RequisitoBuque.objects.filter(
            buque=buque, 
            categoria__in=['COTIZACION', 'DOCUMENTAL']
        ).values_list('nombre_documento', flat=True)
        buque.docs_listos = list(docs_subidos)
        
        try:
            informe = DocumentoEntregable.objects.get(
                naviera=naviera,
                buque=buque,
                tipo='INFORME_PBIP'
            )
            buque.informe_pbip = informe
        except DocumentoEntregable.DoesNotExist:
            buque.informe_pbip = None
            
        buque.propuesta_economica = DocumentoEntregable.objects.filter(naviera=naviera, buque=buque, tipo='COTIZACION').first()

    factura = DocumentoEntregable.objects.filter(
        naviera=naviera,
        tipo='FACTURA'
    ).first()
    naviera.factura_disponible = factura
    
    comprobante = DocumentoEntregable.objects.filter(
        naviera=naviera,
        tipo='COMPROBANTE_PAGO'
    ).first()
    naviera.comprobante_pago = comprobante
    context = {'naviera': naviera, 'buques': buques, 'puntos_pbip': puntos_pbip}
    return render(request, 'portal_cliente.html', context)

# === VISTA DE ALERTA Y DESCARGA PARA LOS ENTREGABLES ===
@login_required
def descargar_entregable(request, doc_id, formato='pdf'):
    doc = get_object_or_404(DocumentoEntregable, id=doc_id, naviera=request.user.naviera)
    
    # Elegir si se despacha el PDF o el XML
    archivo_final = doc.archivo_xml if formato == 'xml' else doc.archivo
    
    if not archivo_final or not os.path.exists(archivo_final.path):
        raise Http404("El archivo solicitado no existe en el servidor.")

    buque_txt = doc.buque.nombre_buque if doc.buque else "General (Naviera)"
    tipo_txt = f"{doc.tipo} ({formato.upper()})".replace('_', ' ')

    # Notificar descarga a tu WhatsApp por medio de MIA (en segundo plano)
    try:
        msg_descarga = (
            f"📥 *MIA - ARCHIVO DESCARGADO*\n\n"
            f"🏢 *Naviera:* {doc.naviera.nombre_empresa}\n"
            f"🚢 *Buque:* {buque_txt}\n"
            f"📄 *Documento:* {tipo_txt}\n"
            f"👤 *Descargado por:* {request.user.username}"
        )
        threading.Thread(target=enviar_whatsapp_jid, args=("5216444475422@s.whatsapp.net", msg_descarga), daemon=True).start()
    except Exception as wa_err:
        print(f"❌ Error alerta de descarga: {wa_err}")

    return FileResponse(open(archivo_final.path, 'rb'), as_attachment=True, filename=os.path.basename(archivo_final.name))

@login_required
@csrf_protect
def agregar_buque(request):
    if request.method == "POST":
        nombre = request.POST.get('nombre_buque')
        omi = request.POST.get('omi')
        metodo_pago = request.POST.get('metodo_pago', '100')
        if nombre and omi:
            Buque.objects.create(
                naviera=request.user.naviera, 
                nombre_buque=nombre, 
                OMI=omi,
                metodo_pago=metodo_pago
            )
            messages.success(request, f'Buque "{nombre}" registrado.')
    return redirect('portal_cliente')

@login_required
@csrf_protect
def actualizar_metodo_pago(request, buque_id):
    if request.method == 'POST':
        buque = get_object_or_404(Buque, id=buque_id, naviera=request.user.naviera)
        metodo = request.POST.get('metodo_pago')
        if metodo in ['100', '50_50']:
            buque.metodo_pago = metodo
            buque.save()
            messages.success(request, f'Método de pago actualizado para el buque "{buque.nombre_buque}".')
    return redirect('portal_cliente')

@login_required
@csrf_protect
def subir_archivo_pre_servicio(request, buque_id):
    if request.method == 'POST':
        buque = get_object_or_404(Buque, id=buque_id, naviera=request.user.naviera)
        archivo = request.FILES.get('archivo_documento')
        nombre_doc = request.POST.get('nombre_documento')
        categoria = request.POST.get('categoria')

        if archivo:
            doc_obj, created = RequisitoBuque.objects.update_or_create(
                naviera=request.user.naviera,
                buque=buque, 
                categoria=categoria, 
                nombre_documento=nombre_doc,
                defaults={'archivo': archivo}
            )
            try:
                threading.Thread(target=procesar_input_mia, kwargs={"documento_obj": doc_obj, "numero_whatsapp": "5216444475422", "jid_remitente": "5216444475422@s.whatsapp.net"}, daemon=True).start()
            except Exception as mia_err:
                print(f"❌ Error en análisis MIA: {mia_err}")

            if categoria == 'COTIZACION':
                asunto = f"SOLICITUD COTIZACIÓN | {buque.nombre_buque} | ID-{buque.id}"
                mensaje_especifico = f"Se ha recibido el formulario para la cotización del buque {buque.nombre_buque}."
            else:
                asunto = f"ACUSE [{buque.id}] | {nombre_doc} | {buque.nombre_buque}"
                mensaje_especifico = f"Confirmamos la recepción del documento: {nombre_doc}\nBuque: {buque.nombre_buque}"

            cuerpo = (
                f"{mensaje_especifico}\n\n"
                f"El archivo ha sido integrado para su respectivo proceso Asignado.\n\n"
                f"Atentamente,\n"
                f"Portal de Notificaciones - OPR"
            )

            try:
                email = EmailMessage(
                    subject=asunto,
                    body=cuerpo,
                    from_email='Portal OPR <08opr.manager@gmail.com>', 
                    to=[request.user.email],
                    bcc=['generalmanager@maritimeprotection.mx'], 
                    reply_to=['generalmanager@maritimeprotection.mx'],
                )
                email.send(fail_silently=False)
                messages.success(request, f"Archivo '{nombre_doc}' guardado y notificado.")
            except Exception as e:
                print(f"❌ Error envío correo: {e}")
    return redirect('portal_cliente')

@login_required
@csrf_protect
def subir_documento_finanzas(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo_documento')
        archivo = request.FILES.get('archivo')
        if archivo:
            doc_obj, created = RequisitoBuque.objects.update_or_create(
                naviera=request.user.naviera,
                buque=None, 
                nombre_documento=tipo, 
                categoria='ADMINISTRATIVO',
                defaults={'archivo': archivo}
            )
            try:
                threading.Thread(target=procesar_input_mia, kwargs={"documento_obj": doc_obj, "numero_whatsapp": "5216444475422", "jid_remitente": "5216444475422@s.whatsapp.net"}, daemon=True).start()
            except Exception as mia_err:
                print(f"❌ Error en análisis MIA Administrativo: {mia_err}")
            
            # --- VERIFICAR ALTA COMPLETA ---
            naviera = request.user.naviera
            admin_count = RequisitoBuque.objects.filter(naviera=naviera, buque__isnull=True, categoria='ADMINISTRATIVO').count()
            
            if admin_count >= 6 and not naviera.alta_completa:
                naviera.alta_completa = True
                from django.utils import timezone
                naviera.fecha_alta_completa = timezone.now()
                naviera.save()
                
                # 🔔 WHATSAPP MIA
                from portal_cliente.mia_herramientas import enviar_whatsapp_jid
                enviar_whatsapp_jid(
                    "5216444475422@s.whatsapp.net",
                    f"🤖 *MIA - ALTA COMPLETA*\n\n🏢 *Naviera:* {naviera.nombre_empresa}\n📋 Documentos administrativos: {admin_count}/6\n✅ *Estado:* Dada de alta como cliente\n📅 Fecha: {naviera.fecha_alta_completa.strftime('%d/%m/%Y')}"
                )
                
                # 📧 CORREO DE ALTA COMPLETADA AL CLIENTE
                try:
                    email_alta = EmailMessage(
                        subject=f"✅ ALTA COMPLETADA | {naviera.nombre_empresa} | Portal OPR",
                        body=(
                            f"Estimado(a) {request.user.first_name or request.user.username},\n\n"
                            f"Nos complace informarle que su proceso de registro como cliente ha sido completado exitosamente.\n\n"
                            f"🏢 *Naviera:* {naviera.nombre_empresa}\n"
                            f"📋 *Documentos administrativos:* {admin_count}/6 completados\n"
                            f"📅 *Fecha de alta:* {naviera.fecha_alta_completa.strftime('%d/%m/%Y %H:%M')}\n\n"
                            f"A partir de este momento puede:\n"
                            f"• Subir documentación operativa\n"
                            f"• Descargar entregables e informes al termino de sus respectivos procesos\n\n"
                            f"Atentamente,\n"
                            f"Equipo de Operaciones - Maritime Protection"
                        ),
                        from_email='Portal OPR <08opr.manager@gmail.com>',
                        to=[request.user.email],
                        bcc=['generalmanager@maritimeprotection.mx'],
                        reply_to=['generalmanager@maritimeprotection.mx'],
                    )
                    email_alta.send(fail_silently=False)
                    print(f"✅ Correo de alta completada enviado a {request.user.email}")
                except Exception as mail_err:
                    print(f"❌ Error envío correo alta completada: {mail_err}")
            # -------------------------------
            
            # 📧 ACUSE NORMAL (solo si no fue alta completa, o adicional)
            asunto = f"ACUSE ADMIN | {tipo} | {request.user.username}"
            cuerpo = f"Confirmamos la recepción del documento: {tipo}\n\nEl archivo ha sido integrado para su respectivo proceso Asignado.\n\nAtentamente,\nPortal de Notificaciones - OPR"

            try:
                email = EmailMessage(
                    subject=asunto,
                    body=cuerpo,
                    from_email='Portal OPR <08opr.manager@gmail.com>', 
                    to=[request.user.email],
                    bcc=['generalmanager@maritimeprotection.mx'], 
                    reply_to=['generalmanager@maritimeprotection.mx'],
                )
                email.send(fail_silently=False)
                messages.success(request, f"Documento '{tipo}' subido y notificado.")
            except Exception as e:
                print(f"❌ Error envío administrativo: {e}")
    return redirect('portal_cliente')

@login_required
@csrf_protect
def subir_comprobante_pago(request, buque_id=None):
    if request.method == 'POST':
        tipo_pago = request.POST.get('tipo_pago', '100')
        archivo = request.FILES.get('archivo_comprobante')
        
        if buque_id:
            buque = get_object_or_404(Buque, id=buque_id, naviera=request.user.naviera)
            naviera = buque.naviera
        else:
            naviera = request.user.naviera
            buque = None
        
        if archivo:
            md5 = hashlib.md5()
            for chunk in archivo.chunks():
                md5.update(chunk)
            hash_nuevo = md5.hexdigest()
            sec_val = 0 if tipo_pago == '100' else (1 if tipo_pago == 'pago_1' else 2)
            
            duplicado = False
            documentos_existentes = DocumentoEntregable.objects.filter(naviera=naviera, buque=buque, tipo='COMPROBANTE_PAGO')
            
            for doc_existente in documentos_existentes:
                if doc_existente.archivo:
                    try:
                        md5_existente = hashlib.md5()
                        with doc_existente.archivo.open('rb') as f:
                            for chunk in f.chunks():
                                md5_existente.update(chunk)
                        if hash_nuevo == md5_existente.hexdigest():
                            duplicado = True
                            break
                    except Exception:
                        pass
            
            if duplicado:
                messages.error(request, "Error: Ya has subido este mismo comprobante de pago anteriormente.")
                return redirect('portal_cliente')
            
            doc, created = DocumentoEntregable.objects.update_or_create(
                naviera=naviera, buque=buque, tipo='COMPROBANTE_PAGO', secuencia=sec_val,
                defaults={'archivo': archivo}
            )
            
            if buque:
                if tipo_pago == '100' or tipo_pago == 'pago_1':
                    buque.pago_1_completado = True
                elif tipo_pago == 'pago_2':
                    buque.pago_2_completado = True
                buque.save()
            
            messages.success(request, "Comprobante de pago procesado correctamente.")
            
            try:
                from portal_cliente.mia_herramientas import enviar_whatsapp_jid
                nombre_buque_txt = buque.nombre_buque if buque else 'N/A'
                esquema_txt = "PAGO TOTAL (100%)" if tipo_pago == '100' else f"ESQUEMA 50/50 ({tipo_pago.upper()})"
                
                enviar_whatsapp_jid(
                    "5216444475422@s.whatsapp.net",
                    f"🤖 *MIA - PAGO RECIBIDO*\n\n🏢 *Naviera:* {naviera.nombre_empresa}\n🚢 *Buque:* {nombre_buque_txt}\n💰 *Esquema:* {esquema_txt}\n📄 *Archivo:* {archivo.name}"
                )
            except Exception as wa_err:
                print(f"❌ Error al enviar WhatsApp: {wa_err}")
    return redirect('portal_cliente')

@staff_member_required
@csrf_protect
def eliminar_documento_con_motivo(request, doc_id):
    if request.method == 'POST':
        motivo = request.POST.get('motivo', '').strip()
        if not motivo:
            messages.error(request, "Debes proporcionar un motivo para eliminar el documento.")
            return redirect('admin:naviera_registro_requisitobuque_changelist')
        
        doc = get_object_or_404(RequisitoBuque, id=doc_id)
        
        # Guardar datos antes de eliminar
        naviera = doc.naviera
        nombre_doc = doc.nombre_documento
        categoria = doc.categoria
        cliente_email = naviera.correo_electronico
        nombre_empresa = naviera.nombre_empresa
        
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
        
        # --- ELIMINAR DOCUMENTO ---
        doc.delete()
        messages.success(request, f"Documento '{nombre_doc}' eliminado. Alertas enviadas.")
        
    return redirect('admin:naviera_registro_requisitobuque_changelist')

@csrf_exempt
def webhook_mia(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        jid = data.get('jid')
        mensaje = data.get('mensaje', '')
        numero_remitente = jid.split('@')[0] if jid else ''
        AUDITOR_NUMBERS = ["5216444475422", "59708652171346"]
        if numero_remitente not in AUDITOR_NUMBERS:
            return JsonResponse({'status': 'ignored'})
        respuesta = procesar_input_mia(texto_usuario=mensaje, numero_whatsapp=numero_remitente, jid_remitente=jid)
        return JsonResponse({'status': 'ok', 'respuesta': respuesta})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@csrf_exempt
def webhook_mia_documento(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        jid = request.POST.get('jid')
        nombre_documento = request.POST.get('nombre_documento')
        archivo = request.FILES.get('archivo')
        if not archivo or not jid:
            return JsonResponse({'error': 'Missing file or jid'}, status=400)
        
        # GUARDAR ARCHIVO PERMANENTEMENTE antes de procesar
        import os
        from django.core.files.storage import default_storage
        from django.conf import settings
        
        # Guardar en MEDIA_ROOT/mia_uploads/ para que persista
        upload_path = f'mia_uploads/{nombre_documento}'
        ruta_permanente = default_storage.save(upload_path, archivo)
        ruta_completa = os.path.join(settings.MEDIA_ROOT, ruta_permanente)
        
        class ArchivoProxy:
            def __init__(self, path):
                self.path = path
                self.name = os.path.basename(path)
            def __str__(self):
                return self.path
        
        class DocObj:
            def __init__(self, nombre, path):
                self.nombre_documento = nombre
                self.archivo = ArchivoProxy(path)
        
        doc_obj = DocObj(nombre_documento, ruta_completa)
        
        # Procesar en background (el archivo ya está guardado permanentemente)
        import threading
        def procesar_y_limpiar():
            try:
                procesar_input_mia(documento_obj=doc_obj, numero_whatsapp=jid.split('@')[0], jid_remitente=jid)
            finally:
                # Limpiar después de procesar
                if os.path.exists(ruta_completa):
                    try:
                        os.unlink(ruta_completa)
                        # También limpiar de default_storage si existe
                        if default_storage.exists(ruta_permanente):
                            default_storage.delete(ruta_permanente)
                    except:
                        pass
        
        threading.Thread(target=procesar_y_limpiar, daemon=True).start()
        return JsonResponse({'status': 'processing'})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)