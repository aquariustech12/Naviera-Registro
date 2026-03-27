import os
import django
from django.core.mail import send_mail

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'naviera_registro.settings')
django.setup()

try:
    send_mail(
        'Prueba de Identidad Real',
        'Si este llega, el servidor local y la cuenta de Gmail están bien.',
        '08opr.manager@gmail.com', # REMITENTE IGUAL AL USER DE SETTINGS
        ['tu-correo-personal@loque-sea.com'], # Un correo que puedas revisar (Gmail o Hotmail)
        fail_silently=False,
    )
    print("✅ Intento de envío completado")
except Exception as e:
    print(f"❌ Error real: {e}")