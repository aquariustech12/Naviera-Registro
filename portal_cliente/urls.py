from django.urls import path
from . import views

urlpatterns = [
    path('portal/', views.portal_cliente, name='portal_cliente'),
    path('cambiar-password/', views.cambiar_password_obligatorio, name='cambiar_password'),
    path('agregar-buque/', views.agregar_buque, name='agregar_buque'),
    path('actualizar-metodo-pago/<int:buque_id>/', views.actualizar_metodo_pago, name='actualizar_metodo_pago'),
    path('subir-finanzas/', views.subir_documento_finanzas, name='subir_documento_finanzas'),
    path('subir-comprobante-pago/<int:buque_id>/', views.subir_comprobante_pago, name='subir_comprobante_pago'),
    path('subir-comprobante-pago/', views.subir_comprobante_pago, name='subir_comprobante_pago'),
    path('webhook-mia/', views.webhook_mia, name='webhook_mia'),
    path('webhook-mia-documento/', views.webhook_mia_documento, name='webhook_mia_documento'),
    path('descargar/<int:doc_id>/', views.descargar_entregable, name='descargar_entregable'),
    path('descargar/<int:doc_id>/<str:formato>/', views.descargar_entregable, name='descargar_entregable_formato'),
    path('admin/eliminar-documento/<int:doc_id>/', views.eliminar_documento_con_motivo, name='eliminar_documento_con_motivo'),
    path('portal/admin/', views.portal_admin, name='portal_admin'),
    path('solicitud-cotizacion/', views.registrar_formulario_fc01, name='registrar_formulario_fc01'),
]