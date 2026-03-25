import random
import string
import requests
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from .models import Naviera  # Asegura que esto esté importado

def generar_contraseña():
    caracteres = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(caracteres) for i in range(10))

def validar_captcha_enterprise(token):
    # TUS CREDENCIALES EXACTAS
    api_key = "AIzaSyCX9G-lJLX_sZAPtG3_k8odO6Q09wkXoHE" 
    project_id = "project-2bb9862c-efe0-410a-a98"
    site_key = "6Lf8CZUsAAAAAHeMvEjIMPBHy-7GHepqM-zRG84b"
    url = f"https://recaptchaenterprise.googleapis.com/v1/projects/{project_id}/assessments?key={api_key}"
    
    payload = {
        "event": {
            "token": token,
            "siteKey": site_key,
            "expectedAction": "REGISTRO"
        }
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        result = response.json()
        # Restaurado el análisis de riesgo y el score que pediste
        token_valido = result.get("tokenProperties", {}).get("valid") == True
        score = result.get("riskAnalysis", {}).get("score", 0)
        
        # Solo pasa si es válido y el score es humano (>= 0.5)
        return token_valido and score >= 0.5
    except Exception:
        return False

def registrar_naviera(request):
    if request.method == "POST":
        token = request.POST.get('g-recaptcha-response')
        nombre_empresa = request.POST.get('nombre_empresa')
        # nombre_buque ya no es obligatorio aquí según tu nueva lógica de flota
        contacto = request.POST.get('contacto_principal')
        correo = request.POST.get('correo_electronico')
        privacidad = request.POST.get('aceptar_privacidad')

        # 1. Validación de Captcha con Score (INTACTO)
        if not validar_captcha_enterprise(token):
            messages.error(request, 'Error de seguridad: Verificación de identidad fallida o riesgo alto.')
            return render(request, 'registro_naviera.html')

        if nombre_empresa and correo and privacidad:
            contraseña_temporal = generar_contraseña()
            try:
                # 2. CREAR USUARIO
                user = User.objects.create_user(
                    username=nombre_empresa, 
                    email=correo, 
                    password=contraseña_temporal, 
                )
                user.is_staff = False
                user.is_superuser = False
                user.save()
                
                # 3. CREAR NAVIERA vinculada al Usuario
                # Ajustado para que use el campo 'user' que añadiste en models.py
                Naviera.objects.create(
                    user=user,
                    nombre_empresa=nombre_empresa,
                    contacto_principal=contacto,
                    correo_electronico=correo
                )
                
                # 4. Envío de correo (Simplificado para la Empresa)
                send_mail(
                    'Registro de Naviera - Global Maritime Protection',
                    f'Estimado/a {contacto},\n\nSe ha completado el registro de su empresa: {nombre_empresa}.\n\nUsuario: {nombre_empresa}\nContraseña Temporal: {contraseña_temporal}\n\nAcceda al portal para registrar su flota y certificados PBIP.',
                    settings.DEFAULT_FROM_EMAIL,
                    [correo],
                    fail_silently=False,
                )
                messages.success(request, 'Registro exitoso. Revise su correo para obtener su contraseña temporal.')
                return redirect('registro_naviera')
            except Exception as e:
                messages.error(request, f'Error al registrar: {str(e)}')
    return render(request, 'registro_naviera.html')

def login_view(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        print(f"DEBUG: Intentando login con Usuario: '{u}' y Password: '{p}'") # Esto saldrá en tu terminal
        user = authenticate(request, username=u, password=p)
        
        if user:
            print("DEBUG: Autenticación exitosa")
            login(request, user)
            if not user.is_superuser:
                return redirect('cambiar_password')
            return redirect('portal_cliente')
        
        print("DEBUG: Autenticación fallida")
        messages.error(request, 'Credenciales incorrectas.')
    return render(request, 'registro_naviera.html')

def politica_privacidad(request):
    return render(request, 'politica_privacidad.html')

def configuracion_cookies(request):
    return render(request, 'configuracion-cookies.html')