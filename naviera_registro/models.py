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
    
    def __str__(self):
        if self.buque:
            return f"{self.get_tipo_display()} - {self.buque.nombre_buque}"
        return f"{self.get_tipo_display()} - {self.naviera.nombre_empresa}"

class AnalisisMIA(models.Model):
    # Relacionamos la nota con el archivo que el cliente subió
    documento = models.OneToOneField(RequisitoBuque, on_delete=models.CASCADE, related_name='analisis_mia')
    
    # Lo que MIA extrajo o resumió
    resumen_tecnico = models.TextField(blank=True, null=True)
    alertas = models.TextField(blank=True, null=True) # "Documento vencido", "RFC no coincide", etc.
    
    # Metadatos del análisis
    procesado = models.BooleanField(default=False)
    fecha_analisis = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MIA - {self.documento.nombre_documento}"