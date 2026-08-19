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


@requiere_token_mia
@require_GET
def historial_documentos(request):
    from django.utils import timezone
    naviera_nombre = request.GET.get('naviera')
    buque_nombre = request.GET.get('buque')
    omi = request.GET.get('omi')

    if not naviera_nombre and not buque_nombre and not omi:
        return JsonResponse({"error": "Se requiere 'naviera', 'buque' u 'omi'"}, status=400)

    docs = RequisitoBuque.objects.all()
    if omi:
        docs = docs.filter(buque__OMI=omi)
    elif buque_nombre:
        docs = docs.filter(buque__nombre_buque__icontains=buque_nombre)
    elif naviera_nombre:
        docs = docs.filter(naviera__nombre_empresa__icontains=naviera_nombre)

    docs = docs.order_by('-fecha_subida')

    if not docs.exists():
        return JsonResponse({"encontrado": False, "mensaje": "Sin documentos registrados para ese criterio"})

    ultima_fecha = docs.first().fecha_subida
    primera_fecha = docs.last().fecha_subida
    meses_desde_ultimo = (timezone.now() - ultima_fecha).days // 30

    return JsonResponse({
        "encontrado": True,
        "total_documentos": docs.count(),
        "primera_subida": primera_fecha.isoformat(),
        "ultima_subida": ultima_fecha.isoformat(),
        "meses_desde_ultima_actividad": meses_desde_ultimo,
        "documentos": [
            {
                "nombre": d.nombre_documento,
                "categoria": d.categoria,
                "naviera": d.naviera.nombre_empresa if d.naviera else None,
                "buque": d.buque.nombre_buque if d.buque else None,
                "fecha_subida": d.fecha_subida.isoformat(),
            }
            for d in docs
        ]
    })


@requiere_token_mia
@require_GET
def verificar_documento_duplicado(request):
    """
    Dado naviera/buque + nombre_documento, indica si el más reciente coincide
    en hash con una versión anterior (posible documento no actualizado).
    """
    naviera_nombre = request.GET.get('naviera')
    buque_nombre = request.GET.get('buque')
    nombre_documento = request.GET.get('nombre_documento')

    if not nombre_documento or (not naviera_nombre and not buque_nombre):
        return JsonResponse({"error": "Se requiere 'nombre_documento' y ('naviera' o 'buque')"}, status=400)

    docs = RequisitoBuque.objects.filter(nombre_documento__icontains=nombre_documento)
    if buque_nombre:
        docs = docs.filter(buque__nombre_buque__icontains=buque_nombre)
    elif naviera_nombre:
        docs = docs.filter(naviera__nombre_empresa__icontains=naviera_nombre)

    docs = docs.order_by('-fecha_subida')
    if not docs.exists():
        return JsonResponse({"encontrado": False})

    ultimo = docs.first()
    hay_anterior_identico = ultimo.hash_coincide_con_anterior_id is not None

    resultado = {
        "encontrado": True,
        "nombre_documento": ultimo.nombre_documento,
        "fecha_ultima_subida": ultimo.fecha_subida.isoformat(),
        "tiene_hash": bool(ultimo.hash_documento),
        "es_identico_a_version_anterior": hay_anterior_identico,
    }

    if hay_anterior_identico:
        anterior = ultimo.hash_coincide_con_anterior
        resultado["fecha_version_anterior_identica"] = anterior.fecha_subida.isoformat()

    return JsonResponse(resultado)
