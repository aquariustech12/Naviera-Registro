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

    def __str__(self):
        return f"{self.nombre_buque} (OMI: {self.OMI})"

class RequisitoBuque(models.Model):
    CATEGORIAS = [
        ('COTIZACION', 'Formulario de Cotización'),
        ('DOCUMENTAL', 'Verificación Documental PBIP'),
        ('ADMINISTRATIVO', 'Expediente Administrativo'),
    ]
    
    # Se permite null=True para que los documentos de ADMINISTRATIVO (Naviera) no obliguen a elegir un buque
    buque = models.ForeignKey(Buque, on_delete=models.CASCADE, related_name='requisitos', null=True, blank=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS)
    nombre_documento = models.CharField(max_length=255) 
    archivo = models.FileField(upload_to='expedientes_pre_servicio/%Y/%m/')
    fecha_subida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        nombre_referencia = self.buque.nombre_buque if self.buque else "General (Naviera)"
        return f"{self.nombre_documento} - {nombre_referencia}"

class PuntoPBIP(models.Model):
    """
    Catálogo maestro para los 27 puntos del PDF FGMP-RD-01.
    Esto sirve para que el sistema sepa qué estamos evaluando.
    """
    numero = models.IntegerField(unique=True)
    descripcion = models.TextField()

    def __str__(self):
        return f"{self.numero}. {self.descripcion}"