from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.core.mail import EmailMessage
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.template.loader import render_to_string

# MODELOS E INFRAESTRUCTURA REAL
from naviera_registro.models import Buque, RequisitoBuque, PuntoPBIP, DocumentoEntregable, Naviera
from .models import CotizacionPendiente, TarifarioGMP

# LOGICA DE NEGOCIO Y AGENTES (MIA)
from .mia_core import procesar_input_mia
from .clasificador_buque import clasificar_por_eslora_y_cubiertas  
from .cotizador import calcular_costo_cotizacion
from .mia_herramientas import enviar_whatsapp_jid  

# DEPENDENCIAS EXTERNAS Y PYTHON STANDARD
from weasyprint import HTML
import json
import threading
import os
import hashlib
# JIDs de notificación
JULIAN_JID = "5216444475422@s.whatsapp.net"
FINANZAS_JID = "5215563183674@s.whatsapp.net"

@login_required
@csrf_protect
def cambiar_password_obligatorio(request):
    print(f"DEBUG: Entrando a cambiar_password_obligatorio")
    print(f"DEBUG: Usuario: {request.user.username} | is_staff: {request.user.is_staff}")

    if request.user.is_staff:
        print("DEBUG: El usuario YA es staff. Redirigiendo al portal_cliente directamente.")
        return redirect('portal_cliente')

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save(commit=False) 
            user.is_staff = True 
            user.save() 
            update_session_auth_hash(request, user)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Contraseña establecida correctamente.')
            return redirect('portal_cliente')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'cambiar_password.html', {'form': form})

@login_required
def portal_cliente(request):
    print(f"DEBUG: Entrando a vista portal_cliente")
    if not request.user.is_staff:
        print("DEBUG: Usuario NO es staff. Redirigiendo a cambio de password.")
        return redirect('cambiar_password_obligatorio')

    if request.user.is_superuser:
        return redirect('portal_admin')

    if request.method == 'POST' and request.POST.get('action') == 'subir_documento':
        buque_id = request.POST.get('buque_id')
        nombre_documento = request.POST.get('nombre_documento')
        categoria = request.POST.get('categoria', 'DOCUMENTAL')
        archivo = request.FILES.get('archivo_documento')
        
        if buque_id and nombre_documento and archivo:
            try:
                buque = get_object_or_404(Buque, id=buque_id, naviera=request.user.naviera)
                requisito, created = RequisitoBuque.objects.update_or_create(
                    buque=buque,
                    naviera=request.user.naviera,
                    nombre_documento=nombre_documento,
                    categoria=categoria,
                    defaults={'archivo': archivo}
                )
                messages.success(request, f"Documento '{nombre_documento}' subido correctamente.")
                
                # === ANALIZAR CON MIA ===
                try:
                    threading.Thread(
                        target=procesar_input_mia,
                        kwargs={
                            "documento_obj": requisito,
                            "numero_whatsapp": "5216444475422",
                            "jid_remitente": JULIAN_JID
                        },
                        daemon=True
                    ).start()
                except Exception as e:
                    print(f"Error análisis MIA PBIP: {e}")

                # Notificar a MIA
                try:
                    msg = f"📄 *MIA - DOCUMENTO PBIP SUBIDO*\n\n🏢 *Naviera:* {request.user.naviera.nombre_empresa}\n🚢 *Buque:* {buque.nombre_buque}\n📋 *Documento:* {nombre_documento}\n👤 *Subido por:* {request.user.username}"
                    threading.Thread(target=enviar_whatsapp_jid, args=(JULIAN_JID, msg), daemon=True).start()
                except Exception as e:
                    print(f"Error notificación MIA PBIP: {e}")
                    
            except Exception as e:
                messages.error(request, f"Error al subir documento: {str(e)}")
        return redirect('portal_cliente')
    # =========================================

    try:
        naviera = request.user.naviera
        print(f"DEBUG: Naviera encontrada: {naviera}")
        buques = naviera.buques.all() 
        puntos_pbip = PuntoPBIP.objects.all().order_by('numero')

        # --- FIX: Todos los docs admin de la naviera, con o sin buque ---
        admin_docs = RequisitoBuque.objects.filter(
            naviera=naviera,
            categoria='ADMINISTRATIVO'
        ).values_list('nombre_documento', flat=True)
        # ----------------------------------------------------------------
        naviera.docs_admin_listos = list(admin_docs)

    except Exception:
        naviera = None
        buques = []
        puntos_pbip = []

    for buque in buques:
        docs_subidos = RequisitoBuque.objects.filter(
            buque=buque, 
            categoria__in=['COTIZACION', 'DOCUMENTAL']
        ).values_list('nombre_documento', flat=True)
        buque.docs_listos = list(docs_subidos)

        try:
            informe = DocumentoEntregable.objects.get(
                naviera=naviera,
                buque=buque,
                tipo='INFORME_PBIP'
            )
            buque.informe_pbip = informe
        except DocumentoEntregable.DoesNotExist:
            buque.informe_pbip = None

        buque.propuesta_economica = DocumentoEntregable.objects.filter(naviera=naviera, buque=buque, tipo='COTIZACION').first()

    if naviera:
        factura = DocumentoEntregable.objects.filter(
            naviera=naviera,
            tipo='FACTURA'
        ).first()
        naviera.factura_disponible = factura

        comprobante = DocumentoEntregable.objects.filter(
            naviera=naviera,
            tipo='COMPROBANTE_PAGO'
        ).first()
        naviera.comprobante_pago = comprobante

    context = {'naviera': naviera, 'buques': buques, 'puntos_pbip': puntos_pbip}
    return render(request, 'portal_cliente.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def portal_admin(request):
    total_navieras = Naviera.objects.count()
    total_buques = Buque.objects.count()
    navieras_incompletas = Naviera.objects.filter(alta_completa=False)

    return render(request, 'portal_admin.html', {
        'total_navieras': total_navieras,
        'total_buques': total_buques,
        'navieras_incompletas': navieras_incompletas,
    })

# === VISTA DE ALERTA Y DESCARGA PARA LOS ENTREGABLES ===
@login_required
def descargar_entregable(request, doc_id, formato='pdf'):
    doc = get_object_or_404(DocumentoEntregable, id=doc_id, naviera=request.user.naviera)

    # Elegir si se despacha el PDF o el XML
    archivo_final = doc.archivo_xml if formato == 'xml' else doc.archivo

    if not archivo_final or not os.path.exists(archivo_final.path):
        raise Http404("El archivo solicitado no existe en el servidor.")

    buque_txt = doc.buque.nombre_buque if doc.buque else "General (Naviera)"
    tipo_txt = f"{doc.tipo} ({formato.upper()})".replace('_', ' ')

    # Notificar descarga a tu WhatsApp por medio de MIA (en segundo plano)
    try:
        msg_descarga = (
            f"📥 *MIA - ARCHIVO DESCARGADO*\n\n"
            f"🏢 *Naviera:* {doc.naviera.nombre_empresa}\n"
            f"🚢 *Buque:* {buque_txt}\n"
            f"📄 *Documento:* {tipo_txt}\n"
            f"👤 *Descargado por:* {request.user.username}"
        )
        threading.Thread(target=enviar_whatsapp_jid, args=(JULIAN_JID, msg_descarga), daemon=True).start()
    except Exception as wa_err:
        print(f"❌ Error alerta de descarga: {wa_err}")

    return FileResponse(open(archivo_final.path, 'rb'), as_attachment=True, filename=os.path.basename(archivo_final.name))

@login_required
@csrf_protect
def agregar_buque(request):
    if request.method == "POST":
        nombre = request.POST.get('nombre_buque')
        omi = request.POST.get('omi')
        metodo_pago = request.POST.get('metodo_pago', '100')
        if nombre and omi:
            Buque.objects.create(
                naviera=request.user.naviera, 
                nombre_buque=nombre, 
                OMI=omi,
                metodo_pago=metodo_pago
            )
            messages.success(request, f'Buque "{nombre}" registrado.')
    return redirect('portal_cliente')

@login_required
@csrf_protect
def actualizar_metodo_pago(request, buque_id):
    if request.method == 'POST':
        buque = get_object_or_404(Buque, id=buque_id, naviera=request.user.naviera)
        metodo = request.POST.get('metodo_pago')
        if metodo in ['100', '50_50']:
            buque.metodo_pago = metodo
            buque.save()
            messages.success(request, f'Método de pago actualizado para el buque "{buque.nombre_buque}".')
    return redirect('portal_cliente')

# ===========================================================================
#  NUEVA FUNCIÓN: registrar_formulario_fc01 (reemplaza subir_archivo_pre_servicio)
# ===========================================================================
@login_required
@csrf_protect
def registrar_formulario_fc01(request):
    """
    Vista Híbrida Corregida:
    Usa el clasificador oficial y el cotizador de la base de datos para evitar ImportErrors.
    """
    JULIAN_JID = "5216444475422@s.whatsapp.net"

    if request.method == 'POST':
        try:
            buque_id = request.POST.get('buque_id')
            if not buque_id:
                messages.error(request, "Error: No se seleccionó ningún buque válido.")
                return redirect('registrar_formulario_fc01')

            # Obtener el buque asociado a la naviera del usuario
            buque = get_object_or_404(Buque, id=buque_id, naviera=request.user.naviera)
            
            # 1. CLASIFICACIÓN USANDO TU ARCHIVO REAL (clasificador_buque.py)
            eslora_buque = float(getattr(buque, 'eslora', 0.0) or 0.0)
            cubiertas_buque = int(getattr(buque, 'cubiertas', 1) or 1)
            
            # Llama a tu función nativa: pequeña, mediana o grande
            rango_buque = clasificar_por_eslora_y_cubiertas(eslora_buque, cubiertas_buque)

            # 2. DETERMINAR TIPO DE SERVICIO DESDE EL SELECTOR DEL FORMULARIO
            tipo_servicio = request.POST.get('servicios_solicitados', 'verificacion').strip().lower()
            if 'evalua' in tipo_servicio:
                tipo_servicio = 'evaluacion'
            else:
                tipo_servicio = 'verificacion'

            # 3. EXTRAER DATOS EN EL JSON ESTRUCTURADO
            datos_formulario = {
                'codigo_form': 'FGMP-FC-01',
                'edicion': '02',
                'fecha_emision_form': '06/10/21',
                'nombre_buque': buque.nombre_buque.upper(),
                'servicios_solicitados': tipo_servicio.upper(),
                'tipo_buque': request.POST.get('tipo_buque', 'GENERAL').strip().upper(),
                'razon_social': request.POST.get('razon_social', '').strip() or request.user.naviera.nombre_empresa,
                'rfc': request.POST.get('rfc', '').strip().upper(),
                'domicilio_fiscal': {
                    'calle_numero': request.POST.get('calle', '').strip(),
                    'ciudad_estado': request.POST.get('ciudad', '').strip(),
                    'municipio_alcaldia': request.POST.get('municipio', '').strip(),
                    'cp': request.POST.get('cp', '').strip(),
                },
                'telefono': request.POST.get('tel_fiscal', '').strip(),
                'ubicacion_buque': request.POST.get('localizacion', '').strip(),
                'representante_legal': {
                    'nombre': request.POST.get('rep_nombre', '').strip(),
                    'telefono': request.POST.get('rep_tel', '').strip(),
                    'email': request.POST.get('rep_email', '').strip(),
                },
                'capitan': {
                    'nombre': request.POST.get('capitan_nombre', '').strip(),
                    'telefono': request.POST.get('capitan_tel', '').strip(),
                    'email': request.POST.get('capitan_email', '').strip(),
                },
                'requerimientos_ingreso': {
                    'ropa_epp': request.POST.get('ropa_epp', '').strip(),
                    'documentacion': request.POST.get('documentacion', '').strip(),
                    'equipo_computo': request.POST.get('equipo_computo', '').strip(),
                    'covid': request.POST.get('covid', '').strip(),
                },
                'fecha_solicitud': timezone.now().strftime('%d/%m/%Y'),
            }

            if not datos_formulario['rfc'] or not datos_formulario['ubicacion_buque']:
                messages.error(request, "Error: El RFC y la localización del buque son obligatorios.")
                return redirect('registrar_formulario_fc01')

            # 4. CALCULAR COSTOS USANDO TU FUNCIÓN REAL (cotizador.py)
            anio_actual = timezone.now().year
            try:
                costos = calcular_costo_cotizacion(tipo_servicio, rango_buque, anio_actual)
                subtotal = costos['costo_unitario']
                iva = costos['iva']
                total = costos['total']
            except ValueError:
                # Fallback por si no encuentra la tarifa exacta del año en curso
                try:
                    costos = calcular_costo_cotizacion(tipo_servicio, rango_buque, 2026)
                    subtotal = costos['costo_unitario']
                    iva = costos['iva']
                    total = costos['total']
                except ValueError:
                    # Contingencia absoluta si la base de datos está vacía
                    from decimal import Decimal
                    subtotal = Decimal('115000.00')
                    iva = subtotal * Decimal('0.16')
                    total = subtotal + iva

            # 5. CREAR EL OBJETO COTIZACION PENDIENTE EN LA BD
            cotizacion = CotizacionPendiente.objects.create(
                naviera=request.user.naviera,
                buque=buque,
                datos_formulario=datos_formulario,
                tipo_servicio=tipo_servicio,
                rango_buque=rango_buque,
                eslora=eslora_buque,
                costo_unitario=subtotal,
                iva=iva,
                total=total,
                estado='borrador'
            )

            # 6. GENERAR PDF DEL FORMULARIO ELECTRÓNICO Y GUARDAR EN REQUISITOS DEL BUQUE (ESTATUS VERDE)
            html_form_string = render_to_string('formulario_fc01_pdf.html', {
                'datos': datos_formulario,
                'buque': buque,
                'cotizacion_id': cotizacion.id,
            })

            pdf_form_bytes = HTML(string=html_form_string).write_pdf()

            nombre_pdf_fc01 = f"FGMP_FC_01_{buque.nombre_buque.replace(' ', '_')}_{cotizacion.id}.pdf"

            # CORRECCIÓN CLAVE: nombre_documento EXACTO al template + categoria='COTIZACION'
            requisito_fc01 = RequisitoBuque.objects.create(
                buque=buque,
                naviera=request.user.naviera,
                nombre_documento="Formulario de Cotización FGMP-FC-01",
                categoria='COTIZACION',
            )

            if hasattr(requisito_fc01, 'archivo'):
                requisito_fc01.archivo.save(nombre_pdf_fc01, ContentFile(pdf_form_bytes), save=True)

            # 7. GENERAR PDF DE LA COTIZACIÓN COMERCIAL DESDE TU TEMPLATE
            html_cot_string = render_to_string('cotizacion_propuesta.html', {
                'naviera': request.user.naviera,
                'buque': buque,
                'cotizacion': cotizacion,
                'subtotal': subtotal,
                'iva': iva,
                'total': total,
                'fecha': datos_formulario['fecha_solicitud'],
                'vigencia': (timezone.now() + timezone.timedelta(days=30)).strftime('%d/%m/%Y'),
            })
            pdf_cot_bytes = HTML(string=html_cot_string).write_pdf()

            nombre_pdf_cot = f"FGMP_PE_01_COTIZACION_{buque.nombre_buque.replace(' ', '_')}_{cotizacion.id}.pdf"
            entregable = DocumentoEntregable.objects.create(
                naviera=request.user.naviera,
                buque=buque,
                tipo='COTIZACION',
            )
            if hasattr(entregable, 'archivo'):
                entregable.archivo.save(nombre_pdf_cot, ContentFile(pdf_cot_bytes), save=True)

            # Relacionamos el documento generado en la cotización pendiente
            cotizacion.documento_generado = entregable
            cotizacion.save()

            # 8. RESPONDER ASÍNCRONAMENTE A TU WHATSAPP CON MIA
            def notificar_mia_completa():
                try:
                    msg = (
                        f"🏢 *MIA - COTIZACIÓN INTEGRADA Y PROCESADA*\n\n"
                        f"La naviera *{request.user.naviera.nombre_empresa}* ha completado su formulario web con éxito.\n\n"
                        f"🚢 *Buque:* {buque.nombre_buque} [Eslora: {eslora_buque}m]\n"
                        f"📊 *Clasificación Rango:* {rango_buque.upper()}\n"
                        f"🛠️ *Servicio:* {tipo_servicio.upper()}\n"
                        f"💰 *Subtotal:* ${subtotal:,.2f} MXN\n"
                        f"➕ *IVA (16%):* ${iva:,.2f} MXN\n"
                        f"💵 *Total:* ${total:,.2f} MXN\n\n"
                        f"📄 *PDF Formulario:* Guardado en Requisitos Buque.\n"
                        f"📄 *PDF Cotización:* Listo en Documentos Entregables.\n"
                        f"🆔 *ID Cotización:* {cotizacion.id}\n\n"
                        f"🔗 *Gestionar en Admin:* https://portal.maritimesecuritymx.com/admin/portal_cliente/cotizacionpendiente/{cotizacion.id}/change/"
                    )
                    enviar_whatsapp_jid(JULIAN_JID, msg)
                except Exception as wa_err:
                    print(f"MIA WHATSAPP ERROR: {str(wa_err)}")

            threading.Thread(target=notificar_mia_completa, daemon=True).start()

            messages.success(request, "El trámite se completó correctamente. Tus documentos PDF oficiales ya están listos en el portal.")
            return redirect('portal_cliente')

        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f"Fallo crítico en el pipeline de Cotizaciones: {str(e)}")
            return redirect('registrar_formulario_fc01')

    # GET: Intentar preseleccionar un buque si se pasa por parámetro (?buque_id=X)
    buques = Buque.objects.filter(naviera=request.user.naviera)
    buque_seleccionado = None
    buque_id_param = request.GET.get('buque_id')
    if buque_id_param:
        buque_seleccionado = buques.filter(id=buque_id_param).first()

    context = {
        'buques': buques,
        'buque_seleccionado': buque_seleccionado,
    }
    return render(request, 'formulario_fc01_web.html', {'buques': buques})

# ===========================================================================

@login_required
@csrf_protect
def subir_documento_finanzas(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo_documento')
        archivo = request.FILES.get('archivo')
        if archivo:
            doc_obj, created = RequisitoBuque.objects.update_or_create(
                naviera=request.user.naviera,
                buque=None, 
                nombre_documento=tipo, 
                categoria='ADMINISTRATIVO',
                defaults={'archivo': archivo}
            )
            try:
                threading.Thread(target=procesar_input_mia, kwargs={"documento_obj": doc_obj, "numero_whatsapp": "5216444475422", "jid_remitente": JULIAN_JID}, daemon=True).start()
            except Exception as mia_err:
                print(f"❌ Error en análisis MIA Administrativo: {mia_err}")

            # --- VERIFICAR ALTA COMPLETA ---
            naviera = request.user.naviera
            admin_count = RequisitoBuque.objects.filter(naviera=naviera, buque__isnull=True, categoria='ADMINISTRATIVO').count()

            if admin_count >= 6 and not naviera.alta_completa:
                naviera.alta_completa = True
                naviera.fecha_alta_completa = timezone.now()
                naviera.save()

                # 🔔 WHATSAPP MIA - AMBOS
                msg_alta = f"🤖 *MIA - ALTA COMPLETA*\n\n🏢 *Naviera:* {naviera.nombre_empresa}\n📋 Documentos administrativos: {admin_count}/6\n✅ *Estado:* Dada de alta como cliente\n📅 Fecha: {naviera.fecha_alta_completa.strftime('%d/%m/%Y')}"
                enviar_whatsapp_jid(JULIAN_JID, msg_alta)
                enviar_whatsapp_jid(FINANZAS_JID, msg_alta)

                # 📧 CORREO DE ALTA COMPLETADA AL CLIENTE
                try:
                    email_alta = EmailMessage(
                        subject=f"✅ ALTA COMPLETADA | {naviera.nombre_empresa} | Portal OPR",
                        body=(
                            f"Estimado(a) {request.user.first_name or request.user.username},\n\n"
                            f"Nos complace informarle que su proceso de registro como cliente ha sido completado exitosamente.\n\n"
                            f"🏢 *Naviera:* {naviera.nombre_empresa}\n"
                            f"📋 *Documentos administrativos:* {admin_count}/6 completados\n"
                            f"📅 *Fecha de alta:* {naviera.fecha_alta_completa.strftime('%d/%m/%Y %H:%M')}\n\n"
                            f"A partir de este momento puede:\n"
                            f"• Subir documentación operativa\n"
                            f"• Descargar entregables e informes al termino de sus respectivos procesos\n\n"
                            f"Atentamente,\n"
                            f"Equipo de Operaciones - Maritime Protection"
                        ),
                        from_email='Portal OPR <08opr.manager@gmail.com>',
                        to=[request.user.email],
                        bcc=['generalmanager@maritimeprotection.mx'],
                        reply_to=['generalmanager@maritimeprotection.mx'],
                    )
                    email_alta.send(fail_silently=False)
                    print(f"✅ Correo de alta completada enviado a {request.user.email}")
                except Exception as mail_err:
                    print(f"❌ Error envío correo alta completada: {mail_err}")
            # -------------------------------

            # 📧 ACUSE NORMAL (solo si no fue alta completa, o adicional)
            asunto = f"ACUSE ADMIN | {tipo} | {request.user.username}"
            cuerpo = f"Confirmamos la recepción del documento: {tipo}\n\nEl archivo ha sido integrado para su respectivo proceso Asignado.\n\nAtentamente,\nPortal de Notificaciones - OPR"

            try:
                email = EmailMessage(
                    subject=asunto,
                    body=cuerpo,
                    from_email='Portal OPR <08opr.manager@gmail.com>', 
                    to=[request.user.email],
                    bcc=['generalmanager@maritimeprotection.mx'], 
                    reply_to=['generalmanager@maritimeprotection.mx'],
                )
                email.send(fail_silently=False)
                messages.success(request, f"Documento '{tipo}' subido y notificado.")
            except Exception as e:
                print(f"❌ Error envío administrativo: {e}")
    return redirect('portal_cliente')

@login_required
@csrf_protect
def subir_comprobante_pago(request, buque_id=None):
    if request.method == 'POST':
        tipo_pago = request.POST.get('tipo_pago', '100')
        archivo = request.FILES.get('archivo_comprobante')

        if buque_id:
            buque = get_object_or_404(Buque, id=buque_id, naviera=request.user.naviera)
            naviera = buque.naviera
        else:
            naviera = request.user.naviera
            buque = None

        if archivo:
            md5 = hashlib.md5()
            for chunk in archivo.chunks():
                md5.update(chunk)
            hash_nuevo = md5.hexdigest()
            sec_val = 0 if tipo_pago == '100' else (1 if tipo_pago == 'pago_1' else 2)

            duplicado = False
            documentos_existentes = DocumentoEntregable.objects.filter(naviera=naviera, buque=buque, tipo='COMPROBANTE_PAGO')

            for doc_existente in documentos_existentes:
                if doc_existente.archivo:
                    try:
                        md5_existente = hashlib.md5()
                        with doc_existente.archivo.open('rb') as f:
                            for chunk in f.chunks():
                                md5_existente.update(chunk)
                        if hash_nuevo == md5_existente.hexdigest():
                            duplicado = True
                            break
                    except Exception:
                        pass

            if duplicado:
                messages.error(request, "Error: Ya has subido este mismo comprobante de pago anteriormente.")
                return redirect('portal_cliente')

            doc, created = DocumentoEntregable.objects.update_or_create(
                naviera=naviera, buque=buque, tipo='COMPROBANTE_PAGO', secuencia=sec_val,
                defaults={'archivo': archivo}
            )

            if buque:
                if tipo_pago == '100' or tipo_pago == 'pago_1':
                    buque.pago_1_completado = True
                elif tipo_pago == 'pago_2':
                    buque.pago_2_completado = True
                buque.save()

            messages.success(request, "Comprobante de pago procesado correctamente.")

            try:
                nombre_buque_txt = buque.nombre_buque if buque else 'N/A'
                esquema_txt = "PAGO TOTAL (100%)" if tipo_pago == '100' else f"ESQUEMA 50/50 ({tipo_pago.upper()})"

                msg_pago = f"🤖 *MIA - PAGO RECIBIDO*\n\n🏢 *Naviera:* {naviera.nombre_empresa}\n🚢 *Buque:* {nombre_buque_txt}\n💰 *Esquema:* {esquema_txt}\n📄 *Archivo:* {archivo.name}"

                # Notificar a ambos
                enviar_whatsapp_jid(JULIAN_JID, msg_pago)
                enviar_whatsapp_jid(FINANZAS_JID, msg_pago)
            except Exception as wa_err:
                print(f"❌ Error al enviar WhatsApp: {wa_err}")
    return redirect('portal_cliente')

@staff_member_required
@csrf_protect
def eliminar_documento_con_motivo(request, doc_id):
    if request.method == 'POST':
        motivo = request.POST.get('motivo', '').strip()
        if not motivo:
            messages.error(request, "Debes proporcionar un motivo para eliminar el documento.")
            return redirect('admin:naviera_registro_requisitobuque_changelist')

        doc = get_object_or_404(RequisitoBuque, id=doc_id)

        # Guardar datos antes de eliminar
        naviera = doc.naviera
        nombre_doc = doc.nombre_documento
        categoria = doc.categoria
        cliente_email = naviera.correo_electronico
        nombre_empresa = naviera.nombre_empresa

        # --- ALERTA MIA A TI ---
        try:
            tipo_txt = "ADMINISTRATIVO" if categoria == 'ADMINISTRATIVO' else "PBIP/OPERATIVO"
            msg_mia = (
                f"🗑️ *MIA - DOCUMENTO ELIMINADO*\n\n"
                f"🏢 *Naviera:* {nombre_empresa}\n"
                f"📄 *Documento:* {nombre_doc}\n"
                f"📂 *Categoría:* {tipo_txt}\n"
                f"👤 *Eliminado por:* {request.user.username}\n"
                f"❌ *Motivo:* {motivo}\n"
                f"📅 *Fecha:* {timezone.now().strftime('%d/%m/%Y %H:%M')}"
            )
            threading.Thread(
                target=enviar_whatsapp_jid, 
                args=(JULIAN_JID, msg_mia), 
                daemon=True
            ).start()
        except Exception as wa_err:
            print(f"❌ Error alerta MIA eliminación: {wa_err}")

        # --- CORREO AL CLIENTE ---
        if cliente_email:
            try:
                asunto_rechazo = f"Documento rechazado | {nombre_doc} | {nombre_empresa}"
                cuerpo_rechazo = (
                    f"Estimado(a) cliente,\n\n"
                    f"Le informamos que el documento '{nombre_doc}' ha sido revisado y no cumple "
                    f"con los requisitos establecidos para su procesamiento.\n\n"
                    f"Motivo: {motivo}\n\n"
                    f"Por favor, suba nuevamente el documento correcto desde su portal de cliente.\n\n"
                    f"Si tiene dudas, puede contactarnos respondiendo a este correo.\n\n"
                    f"Atentamente,\n"
                    f"Equipo de Operaciones - OPR"
                )
                email_rechazo = EmailMessage(
                    subject=asunto_rechazo,
                    body=cuerpo_rechazo,
                    from_email='Portal OPR <08opr.manager@gmail.com>',
                    to=[cliente_email],
                    bcc=['generalmanager@maritimeprotection.mx'],
                    reply_to=['generalmanager@maritimeprotection.mx'],
                )
                email_rechazo.send(fail_silently=False)
                print(f"✅ Correo de rechazo enviado a {cliente_email}")
            except Exception as mail_err:
                print(f"❌ Error correo rechazo: {mail_err}")

        # --- ELIMINAR DOCUMENTO ---
        doc.delete()
        messages.success(request, f"Documento '{nombre_doc}' eliminado. Alertas enviadas.")

    return redirect('admin:naviera_registro_requisitobuque_changelist')

@csrf_exempt
def webhook_mia(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        jid = data.get('jid')
        mensaje = data.get('mensaje', '')
        numero_remitente = jid.split('@')[0] if jid else ''
        AUDITOR_NUMBERS = ["5216444475422", "59708652171346"]
        if numero_remitente not in AUDITOR_NUMBERS:
            return JsonResponse({'status': 'ignored'})
        respuesta = procesar_input_mia(texto_usuario=mensaje, numero_whatsapp=numero_remitente, jid_remitente=jid)
        return JsonResponse({'status': 'ok', 'respuesta': respuesta})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def webhook_mia_documento(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        jid = request.POST.get('jid')
        nombre_documento = request.POST.get('nombre_documento')
        archivo = request.FILES.get('archivo')
        if not archivo or not jid:
            return JsonResponse({'error': 'Missing file or jid'}, status=400)

        # GUARDAR ARCHIVO PERMANENTEMENTE antes de procesar
        from django.core.files.storage import default_storage
        from django.conf import settings

        # Guardar en MEDIA_ROOT/mia_uploads/ para que persista
        upload_path = f'mia_uploads/{nombre_documento}'
        ruta_permanente = default_storage.save(upload_path, archivo)
        ruta_completa = os.path.join(settings.MEDIA_ROOT, ruta_permanente)

        class ArchivoProxy:
            def __init__(self, path):
                self.path = path
                self.name = os.path.basename(path)
            def __str__(self):
                return self.path

        class DocObj:
            def __init__(self, nombre, path):
                self.nombre_documento = nombre
                self.archivo = ArchivoProxy(path)

        doc_obj = DocObj(nombre_documento, ruta_completa)

        # Procesar en background (el archivo ya está guardado permanentemente)
        def procesar_y_limpiar():
            try:
                procesar_input_mia(documento_obj=doc_obj, numero_whatsapp=jid.split('@')[0], jid_remitente=jid)
            finally:
                # Limpiar después de procesar
                if os.path.exists(ruta_completa):
                    try:
                        os.unlink(ruta_completa)
                        # También limpiar de default_storage si existe
                        if default_storage.exists(ruta_permanente):
                            default_storage.delete(ruta_permanente)
                    except:
                        pass

        threading.Thread(target=procesar_y_limpiar, daemon=True).start()
        return JsonResponse({'status': 'processing'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)