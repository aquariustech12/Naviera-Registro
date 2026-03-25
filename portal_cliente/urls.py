from django.urls import path
from . import views

urlpatterns = [
    path('', views.portal_cliente, name='portal_cliente'),
    path('cambiar-password/', views.cambiar_password_obligatorio, name='cambiar_password'),
    path('agregar-buque/', views.agregar_buque, name='agregar_buque'),
]