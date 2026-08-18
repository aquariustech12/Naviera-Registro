from django.urls import path
from . import views

urlpatterns = [
    path('buque/', views.consultar_buque, name='api_mia_buque'),
    path('naviera/', views.consultar_naviera, name='api_mia_naviera'),
    path('reporte/', views.reporte_global, name='api_mia_reporte'),
    path('cotizacion/calcular/', views.calcular_cotizacion, name='api_mia_calcular_cotizacion'),
]
