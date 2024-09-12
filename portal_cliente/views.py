from django.shortcuts import render
from django.http import HttpResponse

def portal_cliente(request):
    return render(request, 'portal_cliente.html')

def bienvenida(request):
    return HttpResponse("Bienvenido al portal del cliente. Aquí encontrará las instrucciones de uso.")
