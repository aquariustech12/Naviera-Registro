"""
Generacion y regeneracion del PDF de cotizacion a partir de los campos de
CotizacionPendiente (costo_unitario, iva, total). Una sola fuente de verdad
para la aprobacion y para las acciones de admin "Regenerar PDF".
"""
import io
import os
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models as dj_models
from django.template.loader import render_to_string
from django.utils import timezone


def generar_pdf_cotizacion(cot):
    """Devuelve los bytes del PDF final (con portada si existe) con los montos actuales de `cot`."""
    from weasyprint import HTML
    from . import models as m  # reutiliza TEXTOS_PROPUESTA_COMPLETA y PdfMerger ya importados ahi
    from .templatetags.numero_letras import numero_a_letras

    if cot.costo_unitario is None or cot.iva is None or cot.total is None:
        raise ValueError("La cotizacion no tiene costo, IVA o total capturados.")

    buque   = cot.buque
    naviera = cot.naviera
    tipo_s  = cot.tipo_servicio.lower()
    rango_b = cot.rango_buque.lower()

    textos = m.TEXTOS_PROPUESTA_COMPLETA.get(tipo_s, m.TEXTOS_PROPUESTA_COMPLETA['verificacion'])
    descripcion_rango = textos['descripcion_rango'].get(rango_b, '')

    context = {
        'cotizacion':        cot,
        'buque':             buque,
        'naviera':           naviera,
        'titulo_servicio':   textos['titulo_servicio'],
        'descripcion_rango': descripcion_rango,
        'actividades':       textos['actividades'],
        'condiciones_pago':  textos['condiciones_pago'],
        'clausula_primera':  textos['clausula_primera'].format(
            nombre_buque=buque.nombre_buque,
            descripcion_rango=descripcion_rango,
        ),
        'subtotal':     cot.costo_unitario,
        'iva':          cot.iva,
        'total':        cot.total,
        'total_letras': numero_a_letras(cot.total),
        'fecha':        timezone.now().strftime('%d/%m/%Y'),
        'vigencia':     (timezone.now() + timedelta(days=30)).strftime('%d/%m/%Y'),
    }

    pdf_bytes = HTML(string=render_to_string('cotizacion_propuesta.html', context)).write_pdf()

    portada_path = os.path.join(settings.MEDIA_ROOT, 'plantillas', 'portada_cotizacion.pdf')
    if os.path.exists(portada_path):
        with open(portada_path, 'rb') as f:
            portada_bytes = f.read()
        merger = m.PdfMerger()
        merger.append(io.BytesIO(portada_bytes))
        merger.append(io.BytesIO(pdf_bytes))
        buf = io.BytesIO()
        merger.write(buf)
        return buf.getvalue()
    return pdf_bytes


def regenerar_pdf_cotizacion(cot):
    """Reemplaza el archivo del entregable existente por un PDF nuevo con los montos actuales."""
    ent = cot.documento_generado
    if ent is None:
        raise ValueError("La cotizacion aun no tiene entregable; usa 'Aprobar y enviar al cliente'.")
    pdf = generar_pdf_cotizacion(cot)
    campo = next((f.name for f in ent._meta.get_fields() if isinstance(f, dj_models.FileField)), None)
    if not campo:
        raise ValueError("El entregable no tiene campo de archivo.")
    viejo = getattr(ent, campo)
    if viejo:
        viejo.delete(save=False)
    getattr(ent, campo).save(f"FGMP_PE_01_COTIZACION_{cot.id}.pdf", ContentFile(pdf), save=True)
    return ent
