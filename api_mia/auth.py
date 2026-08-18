from functools import wraps
from django.conf import settings
from django.http import JsonResponse
from decouple import config


def requiere_token_mia(view_func):
    """Valida que la request traiga el token compartido del cerebro MIA 2.0."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token_esperado = config('MIA_CEREBRO_TOKEN', default=None)
        if not token_esperado:
            return JsonResponse({"error": "MIA_CEREBRO_TOKEN no configurado en el servidor"}, status=500)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return JsonResponse({"error": "Falta header Authorization: Bearer <token>"}, status=401)

        token_recibido = auth_header.split('Bearer ')[1].strip()
        if token_recibido != token_esperado:
            return JsonResponse({"error": "Token inválido"}, status=403)

        return view_func(request, *args, **kwargs)
    return wrapper
