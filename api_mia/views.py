import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import get_object_or_404

from naviera_registro.models import Naviera, Buque, RequisitoBuque
from portal_cliente.models import TarifarioGMP, CotizacionPendiente
from portal_cliente.cotizador import calcular_costo_cotizacion

from .auth import requiere_token_mia


@requiere_token_mia
@require_GET
def consultar_buque(request):
    omi = request.GET.get('omi')
    nombre = request.GET.get('nombre')

    if omi:
        buque = get_object_or_404(Buque, OMI=omi)
    elif nombre:
        buque = get_object_or_404(Buque, nombre_buque__icontains=nombre)
    else:
        return JsonResponse({"error": "Se requiere 'omi' o 'nombre'"}, status=400)

    documentos = RequisitoBuque.objects.filter(buque=buque)

    return JsonResponse({
        "nombre_buque": buque.nombre_buque,
        "omi": buque.OMI,
        "naviera": buque.naviera.nombre_empresa,
        "metodo_pago": buque.get_metodo_pago_display(),
        "pago_1_completado": buque.pago_1_completado,
        "pago_2_completado": buque.pago_2_completado,
        "documentos_subidos": documentos.count(),
        "documentos": [
            {"nombre": d.nombre_documento, "categoria": d.categoria, "fecha_subida": d.fecha_subida.isoformat()}
            for d in documentos
        ]
    })


@requiere_token_mia
@require_GET
def consultar_naviera(request):
    nombre = request.GET.get('nombre')
    if not nombre:
        return JsonResponse({"error": "Se requiere 'nombre'"}, status=400)

    naviera = get_object_or_404(Naviera, nombre_empresa__icontains=nombre)
    buques = Buque.objects.filter(naviera=naviera)

    return JsonResponse({
        "nombre_empresa": naviera.nombre_empresa,
        "contacto_principal": naviera.contacto_principal,
        "correo_electronico": naviera.correo_electronico,
        "alta_completa": naviera.alta_completa,
        "buques": [b.nombre_buque for b in buques]
    })


@requiere_token_mia
@require_GET
def reporte_global(request):
    total_navieras = Naviera.objects.count()
    total_buques = Buque.objects.count()
    navieras_incompletas = Naviera.objects.filter(alta_completa=False).count()

    return JsonResponse({
        "total_navieras": total_navieras,
        "total_buques": total_buques,
        "navieras_alta_incompleta": navieras_incompletas,
    })


@csrf_exempt
@requiere_token_mia
@require_POST
def calcular_cotizacion(request):
    try:
        data = json.loads(request.body)
        tipo_servicio = data['tipo_servicio']
        rango_buque = data['rango_buque']
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "Se requiere 'tipo_servicio' y 'rango_buque'"}, status=400)

    try:
        costos = calcular_costo_cotizacion(tipo_servicio, rango_buque)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=404)

    costos_serializables = {k: str(v) for k, v in costos.items()}
    return JsonResponse(costos_serializables)
