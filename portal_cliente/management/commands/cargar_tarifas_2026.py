# portal_cliente/management/commands/cargar_tarifas_2026.py

from django.core.management.base import BaseCommand
from decimal import Decimal
from portal_cliente.models import TarifarioGMP


TARIFAS_2026 = [
    # Verificación
    ('verificacion', 'grande', 2026, Decimal('126287.74')),
    ('verificacion', 'mediano', 2026, Decimal('118359.77')),
    ('verificacion', 'pequeno', 2026, Decimal('99998.35')),
    # Evaluación
    ('evaluacion', 'grande', 2026, Decimal('151745.67')),
    ('evaluacion', 'mediano', 2026, Decimal('134495.63')),
    ('evaluacion', 'pequeno', 2026, Decimal('117221.05')),
]


class Command(BaseCommand):
    help = 'Carga tarifas GMP 2026'

    def handle(self, *args, **kwargs):
        for tipo, rango, anio, costo in TARIFAS_2026:
            TarifarioGMP.objects.update_or_create(
                tipo_servicio=tipo,
                rango_buque=rango,
                anio=anio,
                defaults={'costo_base': costo}
            )
            self.stdout.write(
                self.style.SUCCESS(f'Tarifa {tipo}/{rango}/{anio}: ${costo}')
            )