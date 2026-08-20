from django.urls import path
from . import views

urlpatterns = [
    path('buque/', views.consultar_buque, name='api_mia_buque'),
    path('naviera/', views.consultar_naviera, name='api_mia_naviera'),
    path('reporte/', views.reporte_global, name='api_mia_reporte'),
    path('cotizacion/calcular/', views.calcular_cotizacion, name='api_mia_calcular_cotizacion'),
    path('historial/', views.historial_documentos, name='api_mia_historial'),
    path('verificar-duplicado/', views.verificar_documento_duplicado, name='api_mia_verificar_duplicado'),
    path('servicios-por-cerrar/', views.servicios_por_cerrar, name='api_mia_servicios_por_cerrar'),
]
