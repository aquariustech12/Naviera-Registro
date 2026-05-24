from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from naviera_registro.models import Buque, RequisitoBuque, PuntoPBIP, DocumentoEntregable
from django.core.mail import EmailMessage
# Importamos el motor de MIA
from .agente_mia import ejecutar_analisis_mia
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .mia_comandos import procesar_comando_whatsapp, enviar_whatsapp, enviar_whatsapp_auditor
import threading
import os

@login_required
@csrf_protect
def cambiar_password_obligatorio(request):

    # --- DEBUG PARA VER POR QUÉ TE REBOTA ---
    print(f"DEBUG: Entrando a cambiar_password_obligatorio")
    print(f"DEBUG: Usuario: {request.user.username} | is_staff: {request.user.is_staff}")

    if request.user.is_staff:
        print("DEBUG: El usuario YA es staff. Redirigiendo al portal_cliente directamente.")
        return redirect('portal_cliente')

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            # 1. Obtenemos el objeto SIN guardar en DB todavía
            user = form.save(commit=False) 
            
            # 2. Seteamos el flag de staff (que es tu llave al portal)
            user.is_staff = True 
            
            # 3. Guardamos TODO de un solo golpe
            user.save() 
            
            # 4. Actualizamos el hash de la sesión (VITAL)
            update_session_auth_hash(request, user)
            
            # 5. Re-autenticamos para que el middleware vea el is_staff=True YA
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
        
        admin_docs = RequisitoBuque.objects.filter(
            naviera=naviera,
            buque__isnull=True, 
            categoria='ADMINISTRATIVO'
        ).values_list('nombre_documento', flat=True)
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
    
    try:
        factura = DocumentoEntregable.objects.get(
            naviera=naviera,
            tipo='FACTURA'
        )
        naviera.factura_disponible = factura
    except DocumentoEntregable.DoesNotExist:
        naviera.factura_disponible = None
        
    try:
        comprobante = DocumentoEntregable.objects.get(
            naviera=naviera,
            tipo='COMPROBANTE_PAGO'
        )
        naviera.comprobante_pago = comprobante
    except DocumentoEntregable.DoesNotExist:
        naviera.comprobante_pago = None

    context = {'naviera': naviera, 'buques': buques, 'puntos_pbip': puntos_pbip}
    return render(request, 'portal_cliente.html', context)

@login_required
@csrf_protect
def agregar_buque(request):
    if request.method == "POST":
        nombre = request.POST.get('nombre_buque')
        omi = request.POST.get('omi')
        if nombre and omi:
            Buque.objects.create(naviera=request.user.naviera, nombre_buque=nombre, OMI=omi)
            messages.success(request, f'Buque "{nombre}" registrado.')
    return redirect('portal_cliente')

@login_required
@csrf_protect
def subir_archivo_pre_servicio(request, buque_id):
    if request.method == 'POST':
        # CAMBIO 1: El buque DEBE ser de la naviera del usuario logueado
        buque = get_object_or_404(Buque, id=buque_id, naviera=request.user.naviera)
        
        archivo = request.FILES.get('archivo_documento')
        nombre_doc = request.POST.get('nombre_documento')
        categoria = request.POST.get('categoria')

        if archivo:
            # CAMBIO 2: Guardamos con la naviera explícita para el aislamiento
            doc_obj, created = RequisitoBuque.objects.update_or_create(
                naviera=request.user.naviera, # <--- Este es el muro de seguridad
                buque=buque, 
                categoria=categoria, 
                nombre_documento=nombre_doc,
                defaults={'archivo': archivo}
            )
            # --- DISPARO DE MIA ---
            try:
                threading.Thread(target=ejecutar_analisis_mia, args=(doc_obj, None), daemon=True).start()
            except Exception as mia_err:
                print(f"❌ Error en análisis MIA: {mia_err}")
            # ----------------------

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
                messages.warning(request, f"Archivo guardado, pero falló la notificación.")

    return redirect('portal_cliente')

@login_required
@csrf_protect
def subir_documento_finanzas(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo_documento')
        archivo = request.FILES.get('archivo')
        if archivo:
            # Guardamos el objeto para pasárselo a MIA
            doc_obj, created = RequisitoBuque.objects.update_or_create(
                naviera=request.user.naviera,
                buque=None, 
                nombre_documento=tipo, 
                categoria='ADMINISTRATIVO',
                defaults={'archivo': archivo}
            )
            
            # --- DISPARO DE MIA ---
            try:
                threading.Thread(target=ejecutar_analisis_mia, args=(doc_obj, None), daemon=True).start()
            except Exception as mia_err:
                print(f"❌ Error en análisis MIA Administrativo: {mia_err}")
            # ----------------------
            
            asunto = f"ACUSE ADMIN | {tipo} | {request.user.username}"
            cuerpo = (
                f"Confirmamos la recepción del documento: {tipo}\n\n"
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
                messages.success(request, f"Documento '{tipo}' subido y notificado.")
            except Exception as e:
                print(f"❌ Error envío administrativo: {e}")

    return redirect('portal_cliente')

@login_required
@csrf_protect
def subir_comprobante_pago(request):
    if request.method == 'POST':
        naviera = request.user.naviera
        archivo = request.FILES.get('archivo_comprobante')
        if archivo:
            DocumentoEntregable.objects.update_or_create(
                naviera=naviera,
                tipo='COMPROBANTE_PAGO',
                defaults={'archivo': archivo}
            )
            messages.success(request, "Comprobante de pago subido correctamente.")
    return redirect('portal_cliente')

@csrf_exempt
def webhook_mia(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        jid = data.get('jid')               # JID completo del remitente
        mensaje = data.get('mensaje', '')

        # Extrae el número del JID para comparar (sin el sufijo)
        numero_remitente = jid.split('@')[0] if jid else ''

        # Tu número personal autorizado (cambia por el tuyo)
        AUDITOR_NUMBERS = ["5216444475422", "59708652171346"]   # <-- Ajusta este número

        if numero_remitente not in AUDITOR_NUMBERS:
            return JsonResponse({'status': 'ignored'})

        respuesta = procesar_comando_whatsapp(mensaje)

        # Enviar la respuesta usando el JID completo
        from .mia_comandos import enviar_whatsapp_jid
        enviar_whatsapp_jid(jid, respuesta)

        return JsonResponse({'status': 'ok', 'respuesta_enviada': True})

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
        
        # Guardar el archivo temporalmente
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        
        # Crear objeto simulado
        class DocObj:
            def __init__(self, nombre, path):
                self.nombre_documento = nombre
                self.archivo = type('obj', (object,), {'path': path})()
        
        doc_obj = DocObj(nombre_documento, tmp_path)
        
        # ✅ PASAR EL JID AL ANÁLISIS PARA QUE RESPONDA AL USUARIO CORRECTO
        import threading
        threading.Thread(
            target=ejecutar_analisis_mia, 
            args=(doc_obj, jid),  # <-- jid va como segundo argumento
            daemon=True
        ).start()
        
        return JsonResponse({'status': 'processing'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)