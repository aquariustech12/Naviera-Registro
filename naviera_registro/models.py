from django.db import models
from django.contrib.auth.models import User

class Naviera(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nombre_empresa = models.CharField(max_length=255)
    contacto_principal = models.CharField(max_length=255)
    correo_electronico = models.EmailField()

    def __str__(self):
        return self.nombre_empresa

class Buque(models.Model):
    naviera = models.ForeignKey(Naviera, on_delete=models.CASCADE, related_name='buques')
    nombre_buque = models.CharField(max_length=255)
    OMI = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.nombre_buque} (OMI: {self.OMI})"

class RequisitoBuque(models.Model):
    CATEGORIAS = [
        ('COTIZACION', 'Formulario de Cotización'),
        ('DOCUMENTAL', 'Verificación Documental PBIP'),
        ('ADMINISTRATIVO', 'Expediente Administrativo'),
    ]
    
    # Campo clave para evitar el cruce de documentos entre navieras
    naviera = models.ForeignKey(Naviera, on_delete=models.CASCADE, related_name='todos_los_requisitos', null=True, blank=True)
    buque = models.ForeignKey(Buque, on_delete=models.CASCADE, related_name='requisitos', null=True, blank=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS)
    nombre_documento = models.CharField(max_length=255) 
    archivo = models.FileField(upload_to='expedientes_pre_servicio/%Y/%m/')
    fecha_subida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        ref = self.buque.nombre_buque if self.buque else f"Admin - {self.naviera}"
        return f"{self.nombre_documento} ({ref})"

class PuntoPBIP(models.Model):
    numero = models.IntegerField(unique=True)
    descripcion = models.TextField()

    def __str__(self):
        return f"{self.numero}. {self.descripcion}"

class DocumentoEntregable(models.Model):
    TIPOS = [
        ('INFORME_PBIP', 'Informe PBIP Terminado'),
        ('FACTURA', 'Factura'),
        ('COMPROBANTE_PAGO', 'Comprobante de Pago'),
    ]
    naviera = models.ForeignKey(Naviera, on_delete=models.CASCADE, related_name='entregables')
    buque = models.ForeignKey(Buque, on_delete=models.CASCADE, null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    archivo = models.FileField(upload_to='entregables/%Y/%m/')
    fecha_subida = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['naviera', 'buque', 'tipo']

class AnalisisMIA(models.Model):
    documento = models.OneToOneField(RequisitoBuque, on_delete=models.CASCADE, related_name='analisis_mia')
    resumen_tecnico = models.TextField(blank=True, null=True)
    alertas = models.TextField(blank=True, null=True)
    procesado = models.BooleanField(default=False)
    fecha_analisis = models.DateTimeField(auto_now_add=True)