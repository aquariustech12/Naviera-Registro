from django.db import models

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    # Otros campos necesarios

    def __str__(self):
        return self.nombre
