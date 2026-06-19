# naviera_registro/migrations/0010_naviera_tipo_servicio.py
#
# Agrega el campo tipo_servicio a la Naviera real (naviera_registro).
# Depende de que portal_cliente ya eliminó su Naviera huérfana (0005).
#
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('naviera_registro', '0009_naviera_telefono_contacto'),
        ('portal_cliente',   '0005_remove_orphan_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='naviera',
            name='tipo_servicio',
            field=models.CharField(
                blank=True,
                choices=[('verificacion', 'Verificación'), ('evaluacion', 'Evaluación')],
                help_text='Tipo de servicio según oficio de asignación de la autoridad',
                max_length=20,
                null=True,
            ),
        ),
    ]
