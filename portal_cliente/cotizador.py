# portal_cliente/cotizador.py

import os
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.staticfiles.storage import staticfiles_storage

from weasyprint import HTML, CSS


def calcular_costo_cotizacion(tipo_servicio: str, rango_buque: str, anio: int = 2026) -> dict:
    """
    Busca tarifa en base de datos y calcula costos con IVA.
    """
    from .models import TarifarioGMP
    
    try:
        tarifa = TarifarioGMP.objects.get(
            tipo_servicio=tipo_servicio,
            rango_buque=rango_buque,
            anio=anio
        )
    except TarifarioGMP.DoesNotExist:
        raise ValueError(f"No existe tarifa para {tipo_servicio}/{rango_buque}/{anio}")
    
    costo_base = tarifa.costo_base
    iva = costo_base * Decimal('0.16')
    total = costo_base + iva
    
    return {
        'costo_unitario': costo_base.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'iva': iva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'total': total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'total_antes_iva': costo_base.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
    }


def generar_cotizacion_pdf(cotizacion_pendiente) -> str:
    """
    Genera PDF de cotización aprobada y guarda en entregables.
    Retorna ruta del archivo generado.
    """
    from naviera_registro.models import DocumentoEntregable
    
    naviera = cotizacion_pendiente.naviera
    buque = cotizacion_pendiente.buque
    
    # Calcular costos
    costos = calcular_costo_cotizacion(
        cotizacion_pendiente.tipo_servicio,
        cotizacion_pendiente.rango_buque
    )
    
    # Fechas
    fecha_hoy = datetime.now()
    vigencia = fecha_hoy + timedelta(days=30)
    
    # Contexto para plantilla
    context = {
        'naviera': naviera,
        'buque': buque,
        'cotizacion': cotizacion_pendiente,
        'costo_unitario': costos['costo_unitario'],
        'iva': costos['iva'],
        'total': costos['total'],
        'total_antes_iva': costos['total_antes_iva'],
        'fecha': fecha_hoy.strftime('%d/%m/%Y'),
        'vigencia': vigencia.strftime('%d/%m/%Y'),
        'cliente_id': f"ID-{naviera.id:04d}",
        'metodo_pago': buque.get_metodo_pago_display(),
        'rango_buque': cotizacion_pendiente.get_rango_buque_display(),
        'tipo_servicio': cotizacion_pendiente.get_tipo_servicio_display(),
        'anio': 2026,
        'notas_auditor': cotizacion_pendiente.notas_auditor or '',
    }
    
    # Renderizar HTML
    html_string = render_to_string('cotizacion_propuesta.html', context)
    
    # Directorio de salida
    output_dir = os.path.join(settings.MEDIA_ROOT, 'entregables', fecha_hoy.strftime('%Y/%m'))
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"FGMP-PE-01_COTIZACION_{buque.nombre_buque.replace(' ', '_')}_{fecha_hoy.strftime('%Y%m%d')}.pdf"
    output_path = os.path.join(output_dir, filename)
    
    # Generar PDF con WeasyPrint
    HTML(string=html_string, base_url=settings.BASE_DIR).write_pdf(output_path)
    
    # Crear DocumentoEntregable
    doc = DocumentoEntregable.objects.create(
        naviera=naviera,
        buque=buque,
        tipo='COTIZACION',
        archivo=output_path.replace(settings.MEDIA_ROOT, '').lstrip('/')
    )
    
    # Linkar a la cotización
    cotizacion_pendiente.documento_generado = doc
    cotizacion_pendiente.save()
    
    return output_path