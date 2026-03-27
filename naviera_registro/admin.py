from django.contrib import admin
from .models import Naviera, Buque, RequisitoBuque
from .models import DocumentoEntregable

# 1. Creamos la vista "en línea" para los Buques
class BuqueInline(admin.TabularInline):
    model = Buque
    extra = 1  # Te deja un espacio vacío listo para agregar un barco nuevo
    fields = ('nombre_buque', 'OMI') # Solo los campos que importan

@admin.register(Naviera)
class NavieraAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'contacto_principal')
    # 2. Metemos los buques dentro de la Naviera
    inlines = [BuqueInline]

# Mantenemos este por si quieres ver la lista global de barcos, 
# pero ya no es estrictamente necesario
@admin.register(Buque)
class BuqueAdmin(admin.ModelAdmin):
    list_display = ('nombre_buque', 'OMI', 'naviera')
    list_filter = ('naviera',) # Para filtrar barcos por empresa

@admin.register(RequisitoBuque)
class RequisitoBuqueAdmin(admin.ModelAdmin):
    list_display = ('nombre_documento', 'buque', 'categoria', 'fecha_subida')

@admin.register(DocumentoEntregable)
class DocumentoEntregableAdmin(admin.ModelAdmin):
    list_display = ['naviera', 'buque', 'tipo', 'fecha_subida']
    list_filter = ['tipo', 'fecha_subida']