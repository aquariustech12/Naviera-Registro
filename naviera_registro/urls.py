"""
URL configuration for naviera_registro project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views
from django.conf import settings
from django.conf.urls.static import static
from naviera_registro import views

urlpatterns = [
    # Ruta raíz
    path('', views.registrar_naviera, name='registro_naviera'),
    path('admin/', admin.site.urls),
    path('registro-naviera/', views.registrar_naviera, name='registro_naviera'),
    path('politica-privacidad/', views.politica_privacidad, name='politica_privacidad'),
    path('configuracion-cookies/', views.configuracion_cookies, name='configuracion_cookies'),
    path('portal/', include('portal_cliente.urls')),  # Incluir URLs del portal del cliente
    path('login/', views.login_view, name='login'),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
