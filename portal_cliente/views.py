from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from naviera_registro.models import Buque, RequisitoBuque

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
            messages.success(request, 'Contraseña definitiva establecida correctamente.')
            return redirect('portal_cliente')
        else:
            messages.error(request, 'La contraseña no cumple con los requisitos o no coinciden.')
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
    except Exception:
        naviera = None
        buques = []

    context = {
        'naviera': naviera,
        'buques': buques,
    }
    # ESTA ES LA LÍNEA QUE FALTABA Y CAUSABA EL ERROR 500
    return render(request, 'portal_cliente.html', context)

@login_required
@csrf_protect
def agregar_buque(request):
    if not request.user.is_staff:
        return redirect('cambiar_password_obligatorio')

    if request.method == "POST":
        nombre = request.POST.get('nombre_buque')
        omi = request.POST.get('omi')
        
        if nombre and omi:
            try:
                Buque.objects.create(
                    naviera=request.user.naviera,
                    nombre_buque=nombre,
                    OMI=omi
                )
                messages.success(request, f'Buque "{nombre}" registrado.')
            except Exception as e:
                messages.error(request, f'Error al registrar: {e}')

def subir_archivo_pre_servicio(request, buque_id):
    if request.method == 'POST':
        buque = get_object_or_404(Buque, id=buque_id)
        archivo = request.FILES.get('archivo_documento')
        
        # Obtenemos los datos ocultos del formulario
        categoria = request.POST.get('categoria')
        nombre_doc = request.POST.get('nombre_documento')

        if archivo:
            RequisitoBuque.objects.create(
                buque=buque,
                categoria=categoria,
                nombre_documento=nombre_doc,
                archivo=archivo
            )
            messages.success(request, f"¡Éxito! El archivo '{nombre_doc}' se guardó para el buque {buque.nombre_buque}.")
        else:
            messages.error(request, "Error: No seleccionaste ningún archivo para subir.")

@login_required
def subir_documento_finanzas(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo_documento') # Ej: "Acta Constitutiva" [cite: 4]
        archivo = request.FILES.get('archivo')
        
        if archivo:
            # Se guarda con categoría ADMINISTRATIVO para diferenciarlo del PBIP
            nuevo_doc = RequisitoBuque(
                buque=None, # Documentos de la Naviera/Cliente [cite: 3]
                nombre_documento=tipo,
                archivo=archivo,
                categoria='ADMINISTRATIVO'
            )
            nuevo_doc.save()
            messages.success(request, f"Documento {tipo} subido correctamente.")
    
    return redirect('portal_cliente')