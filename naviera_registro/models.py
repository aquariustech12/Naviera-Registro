from django.db import models
from django.contrib.auth.models import User

class Naviera(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE) # El login
    nombre_empresa = models.CharField(max_length=255)
    contacto_principal = models.CharField(max_length=255)
    correo_electronico = models.EmailField()

    def __str__(self):
        return self.nombre_empresa

class Buque(models.Model):
    naviera = models.ForeignKey(Naviera, on_delete=models.CASCADE, related_name='buques')
    nombre_buque = models.CharField(max_length=255)
    OMI = models.CharField(max_length=50) # El ID internacional del barco

class RequisitoBuque(models.Model):
    CATEGORIAS = [
        ('COTIZACION', 'Formulario de Cotización'),
        ('DOCUMENTAL', 'Verificación Documental PBIP'),
        ('ADMINISTRATIVO', 'Expediente Administrativo'),
    ]
    
    buque = models.ForeignKey(Buque, on_delete=models.CASCADE, related_name='requisitos')
    categoria = models.CharField(max_length=20, choices=CATEGORIAS)
    # Aquí guardamos el nombre real (ej: "Certificado de Matrícula" o "Acta Constitutiva")
    nombre_documento = models.CharField(max_length=255) 
    archivo = models.FileField(upload_to='expedientes_pre_servicio/%Y/%m/')
    fecha_subida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre_documento} - {self.buque.nombre_buque}"