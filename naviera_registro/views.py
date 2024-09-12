from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
import random
import string
from django.contrib.auth.decorators import login_required
from django import forms
# Import from django-recaptcha
from django_recaptcha.fields import ReCaptchaV2Checkbox  # Or ReCaptchaV2InvisibleField

class registro_naviera(forms.Form):
    nombre_empresa = forms.CharField(max_length=100)
    nombre_buque = forms.CharField(max_length=100)
    contacto_principal = forms.CharField(max_length=100)
    correo_electronico = forms.EmailField()
    captcha = ReCaptchaV2Checkbox()
    
@login_required
def politica_privacidad(request):
    # Lógica de la vista
    return render(request, 'politica_privacidad.html')  # Nombre de la plantilla de política de privacidad

def configuracion_cookies(request):
    # Lógica de la vista
    return render(request, 'configuracion-cookies.html')  # Nombre de la plantilla de configuracion cookies

def generar_contraseña():
    # Genera una contraseña aleatoria
    caracteres = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(caracteres) for i in range(10))

def registrar_naviera(request):
    if request.method == "POST":
        nombre_empresa = request.POST.get('nombre_empresa')
        nombre_buque = request.POST.get('nombre_buque')
        contacto_principal = request.POST.get('contacto_principal')
        correo_electronico = request.POST.get('correo_electronico')
        aceptar_privacidad = request.POST.get('aceptar_privacidad')

        if nombre_empresa and nombre_buque and contacto_principal and correo_electronico and aceptar_privacidad:
            contraseña = generar_contraseña()
            
            try:
                usuario = User.objects.create_user(username=nombre_empresa, email=correo_electronico, password=contraseña)
                
                send_mail(
                    'Registro Exitoso',
                    f'Hola {contacto_principal},\n\nTu usuario ha sido creado exitosamente.\n\nUsuario: {nombre_empresa}\nContraseña: {contraseña}\n\nPor favor, cambia tu contraseña después de iniciar sesión.',
                    settings.DEFAULT_FROM_EMAIL,
                    [correo_electronico],
                    fail_silently=False,
                )
                
                messages.success(request, 'La naviera ha sido registrada con éxito. Revisa tu correo electrónico para obtener tu usuario y contraseña.')
                return redirect('registro_naviera')
            except Exception as e:
                messages.error(request, f'Error al crear el usuario: {str(e)}')
        else:
            messages.error(request, 'Por favor, completa todos los campos y acepta la política de privacidad.')
    
    return render(request, 'registro_naviera.html')
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('portal_cliente')  # Ajusta 'portal_cliente' al nombre de la URL del portal del cliente
        else:
            messages.error(request, 'Credenciales incorrectas. Inténtalo de nuevo.')
    return render(request, 'registro_naviera.html')