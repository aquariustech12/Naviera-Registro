# portal_cliente/apps.py

import os
from django.apps import AppConfig


class PortalClienteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'portal_cliente'

    def ready(self):
        # Solo registrar signals — el scheduler lo maneja mia_proactivo.service
        import portal_cliente.models  # noqa: F401