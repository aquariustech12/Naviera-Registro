from django.urls import path
from . import views

urlpatterns = [
    path('', views.portal_cliente, name='portal_cliente'),
    path('cambiar-password/', views.cambiar_password_obligatorio, name='cambiar_password_obligatorio'),
    path('agregar-buque/', views.agregar_buque, name='agregar_buque'),
    path('subir-archivo/<int:buque_id>/', views.subir_archivo_pre_servicio, name='subir_archivo_pre_servicio'),
    path('subir-finanzas/', views.subir_documento_finanzas, name='subir_documento_finanzas'),
    path('subir-comprobante/', views.subir_comprobante_pago, name='subir_comprobante_pago'),
]