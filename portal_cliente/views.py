from django.shortcuts import render, redirect
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from naviera_registro.models import Buque

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
            
    return redirect('portal_cliente')