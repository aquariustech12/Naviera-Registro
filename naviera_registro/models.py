from django.db import models

class Naviera(models.Model):
    nombre_empresa = models.CharField(max_length=255)
    nombre_buque = models.CharField(max_length=255)
    contacto_principal = models.CharField(max_length=255)
    correo_electronico = models.EmailField()

    def __str__(self):
        return self.correo_electronico
    
    