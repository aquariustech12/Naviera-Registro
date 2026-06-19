# portal_cliente/migrations/0005_remove_orphan_models.py
#
# Elimina las tablas portal_cliente_naviera y portal_cliente_entregable
# que quedaron huérfanas. El campo tipo_servicio se mueve a
# naviera_registro.Naviera (migración 0010 en esa app).
#
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('portal_cliente', '0004_naviera_entregable'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Entregable',
        ),
        migrations.DeleteModel(
            name='Naviera',
        ),
    ]
