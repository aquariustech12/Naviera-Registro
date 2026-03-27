from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from naviera_registro.models import Buque, RequisitoBuque, PuntoPBIP, DocumentoEntregable
from django.core.mail import EmailMessage

@login_required
@csrf_protect
def cambiar_password_obligatorio(request):
    if request.user.is_staff:
        return redirect('portal_cliente')
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
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
    if not request.user.is_staff:
        return redirect('cambiar_password_obligatorio')
    
    try:
        naviera = request.user.naviera 
        buques = naviera.buques.all() 
        puntos_pbip = PuntoPBIP.objects.all().order_by('numero')
        
        admin_docs = RequisitoBuque.objects.filter(
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
        buque = get_object_or_404(Buque, id=buque_id)
        archivo = request.FILES.get('archivo_documento')
        nombre_doc = request.POST.get('nombre_documento')
        categoria = request.POST.get('categoria')

        if archivo:
            RequisitoBuque.objects.update_or_create(
                buque=buque, 
                categoria=categoria, 
                nombre_documento=nombre_doc,
                defaults={'archivo': archivo}
            )
            
            # Ajuste de Asunto y Cuerpo para Cotizaciones
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
                    # Alias corto para Outlook
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
            RequisitoBuque.objects.update_or_create(
                buque=None, 
                nombre_documento=tipo, 
                categoria='ADMINISTRATIVO',
                defaults={'archivo': archivo}
            )
            
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