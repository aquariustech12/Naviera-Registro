from django.db import models
from django.contrib.auth.models import User

class Naviera(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nombre_empresa = models.CharField(max_length=255)
    contacto_principal = models.CharField(max_length=255)
    correo_electronico = models.EmailField()
    alta_completa = models.BooleanField(default=False)
    fecha_alta_completa = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nombre_empresa

class Buque(models.Model):
    naviera = models.ForeignKey(Naviera, on_delete=models.CASCADE, related_name='buques')
    nombre_buque = models.CharField(max_length=255)
    OMI = models.CharField(max_length=50)
    
    # NUEVO: Método de pago
    METODOS_PAGO = [
        ('100', '100%'),
        ('50_50', '50% - 50%'),
    ]
    metodo_pago = models.CharField(max_length=10, choices=METODOS_PAGO, default='100')
    
    # NUEVO: Estado de pagos
    pago_1_completado = models.BooleanField(default=False)
    pago_2_completado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.nombre_buque} (OMI: {self.OMI})"

class RequisitoBuque(models.Model):
    CATEGORIAS = [
        ('COTIZACION', 'Formulario de Cotización'),
        ('DOCUMENTAL', 'Verificación Documental PBIP'),
        ('ADMINISTRATIVO', 'Expediente Administrativo'),
    ]
    
    # Campo clave para evitar el cruce de documentos entre navieras
    naviera = models.ForeignKey(Naviera, on_delete=models.CASCADE, related_name='todos_los_requisitos', null=True, blank=True)
    buque = models.ForeignKey(Buque, on_delete=models.CASCADE, related_name='requisitos', null=True, blank=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS)
    nombre_documento = models.CharField(max_length=255) 
    archivo = models.FileField(upload_to='expedientes_pre_servicio/%Y/%m/')
    fecha_subida = models.DateTimeField(auto_now_add=True)
    motivo_rechazo = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Motivo de rechazo/eliminación")
    
    def __str__(self):
        ref = self.buque.nombre_buque if self.buque else f"Admin - {self.naviera}"
        return f"{self.nombre_documento} ({ref})"

class PuntoPBIP(models.Model):
    numero = models.IntegerField(unique=True)
    descripcion = models.TextField()

    def __str__(self):
        return f"{self.numero}. {self.descripcion}"

class DocumentoEntregable(models.Model):
    TIPOS = [
        ('COTIZACION', 'Propuesta Económica (Cotización)'),
        ('INFORME_PBIP', 'Informe PBIP Terminado'),
        ('FACTURA', 'Factura'),
        ('COMPROBANTE_PAGO', 'Comprobante de Pago'),
    ]
    naviera = models.ForeignKey(Naviera, on_delete=models.CASCADE, related_name='entregables')
    buque = models.ForeignKey(Buque, on_delete=models.CASCADE, null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    archivo = models.FileField(upload_to='entregables/%Y/%m/')
    archivo_xml = models.FileField(upload_to='entregables/xmls/', null=True, blank=True, verbose_name="Archivo XML (Opcional)")
    fecha_subida = models.DateTimeField(auto_now_add=True)
    secuencia = models.IntegerField(default=1)

    class Meta:
        unique_together = ['naviera', 'buque', 'tipo', 'secuencia']

    def __str__(self):
        return f"{self.tipo} - {self.naviera.nombre_empresa}"

    # === ENVÍO DE CORREO AUTOMÁTICO DIRECTO AL GUARDAR ===
    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None  # Detecta si se está creando el registro en el Admin
        super().save(*args, **kwargs)  # Guarda primero el archivo en la base de datos

        if es_nuevo:
            import threading
            from django.core.mail import EmailMessage

            # Mapeo de nombres limpios para el texto del correo
            nombres_tipos = {
                'COTIZACION': 'Propuesta Económica (Cotización)',
                'INFORME_PBIP': 'Informe PBIP Terminado',
                'FACTURA': 'Factura',
                'COMPROBANTE_PAGO': 'Comprobante de Pago'
            }

            naviera_obj = self.naviera
            buque_txt = self.buque.nombre_buque if self.buque else "General (Administrativo)"
            tipo_txt = nombres_tipos.get(self.tipo, self.tipo)
            correo_destino = naviera_obj.correo_electronico

            # Solo se dispara si la naviera tiene un correo registrado
            if correo_destino:
                asunto = f"DOCUMENTO DISPONIBLE PARA DESCARGA | {tipo_txt} | {buque_txt}"
                cuerpo = (
                    f"Estimado Cliente de {naviera_obj.nombre_empresa},\n\n"
                    f"Le informamos que un nuevo documento oficial ha sido cargado en su expediente digital y ya se encuentra listo para su descarga:\n\n"
                    f"• Documento: {tipo_txt}\n"
                    f"• Origen/Buque: {buque_txt}\n\n"
                    f"Por favor, ingrese a su portal comercial para descargar los archivos correspondientes.\n\n"
                    f"Atentamente,\n"
                    f"Portal de Notificaciones - OPR"
                )
                try:
                    email = EmailMessage(
                        subject=asunto,
                        body=cuerpo,
                        from_email='Portal OPR <08opr.manager@gmail.com>',
                        to=[correo_destino],
                        bcc=['generalmanager@maritimeprotection.mx']
                    )
                    # Forzamos el envío síncrono seguro (Quitamos el threading)
                    email.send(fail_silently=True)
                except Exception as e:
                    print(f"❌ Error al despachar correo automático al cliente: {e}")

class AnalisisMIA(models.Model):
    documento = models.OneToOneField(RequisitoBuque, on_delete=models.CASCADE, related_name='analisis_mia')
    resumen_tecnico = models.TextField(blank=True, null=True)
    alertas = models.TextField(blank=True, null=True)
    procesado = models.BooleanField(default=False)
    fecha_analisis = models.DateTimeField(auto_now_add=True)