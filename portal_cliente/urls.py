from django.urls import path
from . import views

urlpatterns = [
    path('', views.portal_cliente, name='portal_cliente'),
]
