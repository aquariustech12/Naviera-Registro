# portal_cliente/mia_proactivo.py — OPR PROACTIVO v4 (Todo por MIA)
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'naviera_registro.settings')

import django
django.setup()

from datetime import datetime, timedelta
from django.utils import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from naviera_registro.models import Naviera, Buque, RequisitoBuque, PuntoPBIP
from portal_cliente.mia_herramientas import enviar_whatsapp_jid, enviar_whatsapp_numero
from django.core.mail import EmailMessage
from portal_cliente.models import AlertaProactiva
from portal_cliente.models import CotizacionPendiente  # Asegúrate de usar la importación exacta de tu app

import logging
from datetime import datetime
from django.core.files import File

from .extractores import extraer_formulario_completo, extraer_texto_pdf
from .tarifario import clasificar_rango_buque, obtener_costo
from .generadores import generar_propuesta_economica
from .models import Entregable, Naviera

logger = logging.getLogger(__name__)


# Números de notificación
JULIAN_JID = "5216444475422@s.whatsapp.net"
FINANZAS_JID = "5215563183674@s.whatsapp.net"  # Asistente de finanzas
ADMIN_EMAIL = "generalmanager@maritimeprotection.mx"


def _ya_se_envio_hoy(naviera, tipo, buque=None):
    hoy = timezone.now().date()
    qs = AlertaProactiva.objects.filter(
        naviera=naviera,
        tipo_alerta=tipo,
        fecha_envio__date=hoy
    )
    if buque:
        qs = qs.filter(buque=buque)
    return qs.exists()


def _registrar_alerta(naviera, tipo, mensaje, canal='whatsapp', buque=None, exito=True):
    AlertaProactiva.objects.create(
        naviera=naviera,
        buque=buque,
        tipo_alerta=tipo,
        mensaje_enviado=mensaje[:1000],
        canal=canal,
        exito=exito
    )


def _enviar_email_cliente(naviera, asunto, cuerpo):
    if not naviera.correo_electronico:
        return False
    try:
        email = EmailMessage(
            subject=asunto,
            body=cuerpo,
            from_email='OPR <08opr.manager@gmail.com>',
            to=[naviera.correo_electronico],
            reply_to=['generalmanager@maritimeprotection.mx'],
        )
        email.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"  ❌ Error email: {e}")
        return False


def _normalizar_numero(numero):
    """Normaliza número mexicano a formato 521XXXXXXXXXX."""
    numero = numero.strip().replace(' ', '').replace('-', '').replace('+', '')
    if numero.startswith('521'):
        return numero
    elif numero.startswith('52'):
        return '521' + numero[2:]
    elif numero.startswith('1'):
        return '52' + numero
    else:
        return '521' + numero


def _enviar_whatsapp_cliente(naviera, mensaje):
    """Envía WhatsApp al cliente vía MIA (puerto 9000)."""
    if not naviera.telefono_contacto:
        return False
    try:
        numero = _normalizar_numero(naviera.telefono_contacto)
        jid = f"{numero}@s.whatsapp.net"
        enviar_whatsapp_jid(jid, mensaje)
        return True
    except Exception as e:
        print(f"  ❌ Error WhatsApp a {naviera.telefono_contacto}: {e}")
        return False


def _notificar_cliente(naviera, asunto_email, cuerpo_email, mensaje_whatsapp):
    """Notifica al cliente por email y WhatsApp (MIA)."""
    wa_ok = False
    email_ok = False

    # WhatsApp via MIA (puerto 9000)
    if naviera.telefono_contacto:
        try:
            wa_ok = _enviar_whatsapp_cliente(naviera, mensaje_whatsapp)
        except Exception as e:
            print(f"  ❌ Error MIA: {e}")

    # Email
    email_ok = _enviar_email_cliente(naviera, asunto_email, cuerpo_email)

    return wa_ok, email_ok


def job_alta_navieras():
    """Revisa navieras con alta incompleta. Envía WhatsApp+Email al cliente."""
    print(f"\n🔔 [{timezone.now()}] job_alta_navieras ejecutando...")

    navieras = Naviera.objects.filter(alta_completa=False)

    if not navieras.exists():
        print("  ✅ Todas las navieras completas")
        return

    for naviera in navieras:
        dias_registro = (timezone.now() - naviera.user.date_joined).days if hasattr(naviera, 'user') and naviera.user else 0

        admin_count = RequisitoBuque.objects.filter(
            naviera=naviera, 
            buque__isnull=True, 
            categoria='ADMINISTRATIVO'
        ).count()

        faltan = 6 - admin_count
        if faltan == 0:
            continue

        if _ya_se_envio_hoy(naviera, 'ALTA_INCOMPLETA'):
            print(f"  ⏭️ Ya alertado hoy: {naviera.nombre_empresa}")
            continue

        # Documentos faltantes
        docs_requeridos = [
            'Acta Constitutiva', 'Poder Notarial', 'INE Representante', 
            'Opinión SAT', 'Estado de Cuenta', 'Directorio de Contactos'
        ]
        docs_subidos = RequisitoBuque.objects.filter(
            naviera=naviera, 
            buque__isnull=True, 
            categoria='ADMINISTRATIVO'
        ).values_list('nombre_documento', flat=True)
        docs_subidos_list = [d.lower() for d in docs_subidos]

        faltantes_lista = [d for d in docs_requeridos if not any(d.lower() in s for s in docs_subidos_list)]
        faltantes_str = "\n".join([f"• {d}" for d in faltantes_lista]) if faltantes_lista else "• Pendiente de verificación"

        # MENSAJE WHATSAPP — Corto, humano
        msg_wa = f"""Buen día {naviera.contacto_principal or ''},

Le escribo de OPR. Vimos que en {naviera.nombre_empresa} aún faltan {faltan} documentos para completar el registro ({admin_count}/6).

¿Podría subirlos esta semana?.

Portal: portal.maritimesecuritymx.com

Cualquier duda me avisa.

Saludos,
OPR Operaciones"""

        # EMAIL — Más formal
        asunto = f"Registro pendiente | {naviera.nombre_empresa}"
        cuerpo = f"""Estimado(a) {naviera.contacto_principal or 'Cliente'},

Por medio de la presente, le recordamos que su proceso de registro en OPR se encuentra incompleto.

🏢 Empresa: {naviera.nombre_empresa}
📋 Documentos faltantes: {faltan}/6

Pendientes:
{faltantes_str}

Por favor, complete la documentación en su portal:
https://portal.maritimesecuritymx.com/portal/

Atentamente,
OPR - Operaciones (Mensaje de Sistema - No responder)
"""

        wa_ok, email_ok = _notificar_cliente(naviera, asunto, cuerpo, msg_wa)

        # Confirmación a equipo
        canales = []
        if wa_ok: canales.append("WhatsApp")
        if email_ok: canales.append("Email")

        msg_julian = f"""✅ *OPR alertó a cliente*

🏢 *{naviera.nombre_empresa}*
👤 *Contacto:* {naviera.contacto_principal}
📱 *WhatsApp:* {'✅' if wa_ok else '❌'} {naviera.telefono_contacto or 'N/A'}
📧 *Email:* {'✅' if email_ok else '❌'} {naviera.correo_electronico}
📋 *Faltan:* {faltan}/6
📅 *Días registrada:* {dias_registro}

Canales usados: {', '.join(canales) if canales else 'NINGUNO - revisar'}"""

        enviar_whatsapp_jid(JULIAN_JID, msg_julian)
        enviar_whatsapp_jid(FINANZAS_JID, msg_julian)
        _registrar_alerta(naviera, 'ALTA_INCOMPLETA', msg_julian, 'mixto', exito=bool(canales))

        print(f"  {'✅' if canales else '❌'} {naviera.nombre_empresa}: WA={'✅' if wa_ok else '❌'} Email={'✅' if email_ok else '❌'}")


def job_docs_pbip_faltantes():
    """Revisa buques con docs PBIP faltantes."""
    print(f"\n🔔 [{timezone.now()}] job_docs_pbip_faltantes ejecutando...")

    total_pbip = PuntoPBIP.objects.count()

    for buque in Buque.objects.all():
        pbip_count = RequisitoBuque.objects.filter(buque=buque, categoria='DOCUMENTAL').count()
        if pbip_count >= total_pbip:
            continue

        faltan = total_pbip - pbip_count
        pct = int((pbip_count / total_pbip) * 100) if total_pbip else 0

        if _ya_se_envio_hoy(buque.naviera, 'DOCS_PBIP_FALTANTES', buque=buque):
            print(f"  ⏭️ Ya alertado: {buque.nombre_buque}")
            continue

        # WHATSAPP
        msg_wa = f"""Buen día,

Le escribo de OPR sobre el buque *{buque.nombre_buque}* (OMI: {buque.OMI}).

El expediente PBIP va al {pct}%, faltan {faltan} documentos. ¿Podría subir lo que falta esta semana?

Portal: portal.maritimesecuritymx.com

Gracias,
OPR Operaciones"""

        # EMAIL
        asunto = f"Documentación PBIP | {buque.nombre_buque}"
        cuerpo = f"""Estimado(a) {buque.naviera.contacto_principal or 'Cliente'},

Le escribimos de OPR respecto a la documentación PBIP del buque {buque.nombre_buque} (OMI: {buque.OMI}).

📊 Progreso: {pbip_count}/{total_pbip} ({pct}%)
❌ Faltan: {faltan} documentos

Por favor, suba la documentación faltante en su portal:
https://portal.maritimesecuritymx.com/portal/

Atentamente,
OPR - Operaciones (Mensaje de Sistema - No responder)
"""

        wa_ok, email_ok = _notificar_cliente(buque.naviera, asunto, cuerpo, msg_wa)

        # Confirmación Julian
        canales = []
        if wa_ok: canales.append("WhatsApp")
        if email_ok: canales.append("Email")

        msg_julian = f"""✅ *OPR alertó PBIP*

🚢 *{buque.nombre_buque}* (OMI:{buque.OMI})
🏢 *Naviera:* {buque.naviera.nombre_empresa}
📊 *Progreso:* {pbip_count}/{total_pbip} ({pct}%)
📱 *WA:* {'✅' if wa_ok else '❌'}
📧 *Email:* {'✅' if email_ok else '❌'}"""

        enviar_whatsapp_jid(JULIAN_JID, msg_julian)
        _registrar_alerta(buque.naviera, 'DOCS_PBIP_FALTANTES', msg_julian, 'mixto', buque=buque, exito=bool(canales))


def job_resumen_matutino():
    """Resumen para Julian — Firma MIA."""
    print(f"\n🔔 [{timezone.now()}] job_resumen_matutino ejecutando...")

    total_navieras = Naviera.objects.count()
    incompletas = Naviera.objects.filter(alta_completa=False).count()
    total_buques = Buque.objects.count()
    total_pbip = PuntoPBIP.objects.count()

    buques_data = []
    for b in Buque.objects.all():
        pbip_count = RequisitoBuque.objects.filter(buque=b, categoria='DOCUMENTAL').count()
        pct = int((pbip_count / total_pbip) * 100) if total_pbip else 0
        buques_data.append((b, pct))

    promedio_pbip = sum(p for _, p in buques_data) // len(buques_data) if buques_data else 0
    criticos = [b for b, p in buques_data if p < 50]

    msg = f"""🤖 *MIA - RESUMEN MATUTINO*
📅 {timezone.now().strftime('%d/%m/%Y %H:%M')}

📊 *ESTADO GENERAL:*
• Navieras: {total_navieras} ({incompletas} sin alta)
• Buques: {total_buques}
• Promedio PBIP: {promedio_pbip}%

🚢 *CRÍTICOS (<50%):*
"""
    if criticos:
        for b in criticos:
            pbip_count = RequisitoBuque.objects.filter(buque=b, categoria='DOCUMENTAL').count()
            pct = int((pbip_count / total_pbip) * 100) if total_pbip else 0
            msg += f"• {b.nombre_buque}: {pct}% ({b.naviera.nombre_empresa})\n"
    else:
        msg += "• Ninguno 🎉\n"

    msg += f"\n📋 *PENDIENTES:*\n"
    for n in Naviera.objects.filter(alta_completa=False):
        admin_count = RequisitoBuque.objects.filter(naviera=n, buque__isnull=True, categoria='ADMINISTRATIVO').count()
        msg += f"• {n.nombre_empresa}: {admin_count}/6 admin\n"

    msg += "\n_¿Algo más, capitán?_ ⚓"

    enviar_whatsapp_jid(JULIAN_JID, msg)
    _registrar_alerta(None, 'RESUMEN_DIARIO', msg)
    print(f"  ✅ Resumen enviado")

def job_procesar_formulario_cotizacion():
    """
    Job que MIA ejecuta periódicamente.
    Busca formularios FGMP-FC-01 pendientes, los valida, 
    complementa con certificado de matrícula si es necesario,
    y genera propuesta económica automática.
    """
    
    # Buscar entregables tipo formulario de cotización no procesados
    formularios = Entregable.objects.filter(
        tipo__icontains='FGMP-FC-01',
        estado='pendiente',
        cotizacion_generada=False
    ).select_related('naviera')
    
    for formulario in formularios:
        naviera = formulario.naviera
        
        try:
            # === PASO 1: EXTRAER Y VALIDAR FORMULARIO ===
            resultado = extraer_formulario_completo(
                formulario.archivo.path, 
                naviera=naviera
            )
            
            # === SI NO ES VÁLIDO Y NO SE PUDO COMPLEMENTAR ===
            if not resultado['valido'] and not resultado['datos_complementados']:
                errores_texto = '\n'.join(resultado['errores'])
                mensaje = (
                    f"🚫 FORMULARIO INCOMPLETO: {naviera.nombre}\n\n"
                    f"Buque: {resultado['datos'].get('nombre_buque', 'N/A')}\n"
                    f"Errores detectados:\n{errores_texto}\n\n"
                    f"➡️ ACCIÓN REQUERIDA: Revisa el formulario en el admin, "
                    f"corrige los datos y vuelve a subirlo. MIA no generará "
                    f"cotización hasta que el formulario esté completo."
                )
                enviar_opr_notificacion(naviera.jid, mensaje)
                
                # Marcar como "rechazado - incompleto"
                formulario.estado = 'incompleto'
                formulario.observaciones = errores_texto
                formulario.save()
                continue
            
            # === PASO 2: DETERMINAR TIPO DE SERVICIO ===
            # Primero: ¿El formulario tiene servicio solicitado?
            servicio_texto = resultado['datos'].get('servicio_solicitado', '').lower()
            
            tipo_servicio = None
            if any(p in servicio_texto for p in ['evaluación', 'evaluacion', 'evaluation']):
                tipo_servicio = 'evaluacion'
            elif any(p in servicio_texto for p in ['verificación', 'verificacion', 
                                                     'renovación', 'renovacion',
                                                     'inicial', 'inspección']):
                tipo_servicio = 'verificacion'
            
            # Si no se detectó del formulario, usar el registrado en la naviera
            if not tipo_servicio and hasattr(naviera, 'tipo_servicio') and naviera.tipo_servicio:
                tipo_servicio = naviera.tipo_servicio
            
            # Si aún no hay, notificar y esperar intervención manual
            if not tipo_servicio:
                mensaje = (
                    f"⚠️ NO SE PUDO DETERMINAR TIPO DE SERVICIO: {naviera.nombre}\n\n"
                    f"El formulario no especifica el servicio (Verificación/Evaluación) "
                    f"y la naviera no tiene tipo de servicio registrado.\n\n"
                    f"➡️ ACCIÓN REQUERIDA: Registra el tipo de servicio en el admin "
                    f"de Django (campo tipo_servicio en la naviera) o corrige el "
                    f"formulario. MIA no generará cotización hasta entonces."
                )
                enviar_opr_notificacion(naviera.jid, mensaje)
                formulario.estado = 'pendiente_servicio'
                formulario.save()
                continue
            
            # === PASO 3: CLASIFICAR BUQUE Y CONSULTAR TARIFARIO ===
            tipo_buque = resultado['datos'].get('tipo_buque', '')
            rango = clasificar_rango_buque(tipo_buque)
            anio_actual = datetime.now().year
            
            try:
                costo = obtener_costo(tipo_servicio, rango, anio_actual)
            except KeyError:
                mensaje = (
                    f"❌ ERROR EN TARIFARIO: {naviera.nombre}\n\n"
                    f"No se encontró tarifa para:\n"
                    f"• Servicio: {tipo_servicio}\n"
                    f"• Rango: {rango}\n"
                    f"• Año: {anio_actual}\n\n"
                    f"Revisa el tarifario hardcodeado."
                )
                enviar_opr_notificacion(naviera.jid, mensaje)
                continue
            
            # === PASO 4: GENERAR PROPUESTA ===
            nombre_archivo = (
                f"PROPUESTA_{resultado['datos'].get('nombre_buque', 'SIN_NOMBRE').replace(' ', '_')}_"
                f"{anio_actual}.docx"
            )
            ruta_temp = os.path.join('/tmp', nombre_archivo)
            
            generar_propuesta_economica(
                datos=resultado['datos'],
                costo=costo,
                tipo_servicio=tipo_servicio,
                rango_buque=rango,
                ruta_salida=ruta_temp
            )
            
            # === PASO 5: CREAR ENTREGABLE ===
            with open(ruta_temp, 'rb') as f:
                propuesta = Entregable.objects.create(
                    naviera=naviera,
                    tipo='FGMP-PE-01',
                    nombre=f"Propuesta Económica - {resultado['datos'].get('nombre_buque', 'Sin nombre')}",
                    archivo=File(f, name=nombre_archivo),
                    estado='generado_auto',
                    generado_automaticamente=True,
                    formulario_origen=formulario,
                    observaciones=(
                        f"Servicio: {tipo_servicio} | "
                        f"Rango: {rango} | "
                        f"Costo: ${costo:,.2f} | "
                        f"Complementado con certificado: {'Sí' if resultado['datos_complementados'] else 'No'}"
                    )
                )
            
            # Marcar formulario como procesado
            formulario.cotizacion_generada = True
            formulario.estado = 'procesado'
            formulario.save()
            
            # Limpiar temporal
            os.remove(ruta_temp)
            
            # === PASO 6: NOTIFICAR A JULIAN ===
            mensaje = (
                f"✅ COTIZACIÓN GENERADA AUTOMÁTICAMENTE\n\n"
                f"Naviera: {naviera.nombre}\n"
                f"Buque: {resultado['datos'].get('nombre_buque', 'N/A')}\n"
                f"OMI: {resultado['datos'].get('omi', 'N/A')}\n"
                f"Tipo: {tipo_buque} ({rango})\n"
                f"Servicio: {tipo_servicio.title()}\n"
                f"Costo: ${costo:,.2f} MXN\n\n"
                f"{'⚠️ NOTA: Datos complementados con certificado de matrícula porque '
                   'el formulario venía incompleto.\n' if resultado['datos_complementados'] else ''}"
                f"📄 Revisa la propuesta en el admin de Django antes de enviar al cliente."
            )
            enviar_opr_notificacion(naviera.jid, mensaje)
            
        except Exception as e:
            logger.error(f"Error procesando formulario {formulario.id}: {e}")
            mensaje = (
                f"❌ ERROR GENERANDO COTIZACIÓN: {naviera.nombre}\n\n"
                f"Error: {str(e)}\n\n"
                f"Revisa los logs y el formulario manualmente."
            )
            enviar_opr_notificacion(naviera.jid, mensaje)

def job_recordatorio_cotizaciones_por_hora():
    """Rastrea cotizaciones en borrador y envía recordatorio por hora a Julian."""
    print(f"⏳ [{timezone.now()}] Ejecutando recordatorio de cotizaciones pendientes...")
    
    # Buscamos cotizaciones que sigan en estado borrador
    borradores = CotizacionPendiente.objects.filter(estado='borrador')
    
    if not borradores.exists():
        print("  ✅ No hay cotizaciones en borrador pendientes de aprobación.")
        return

    for cot in borradores:
        # Armamos el mensaje de presión persistente
        buque_nombre = cot.buque.nombre_buque if cot.buque else "N/A"
        naviera_nombre = cot.naviera.nombre_empresa if cot.naviera else "N/A"
        
        msg_alerta = (
            f"⏳ *MIA - ALERTA DE SEGUIMIENTO (POR HORA)*\n\n"
            f"Capitán, la siguiente cotización sigue en *Borrador* y no se ha enviado al cliente:\n\n"
            f"🏢 *Naviera:* {naviera_nombre}\n"
            f"🚢 *Buque:* {buque_nombre}\n"
            f"🆔 *Cotización ID:* {cot.id}\n\n"
            f"🔗 *Link Directo al Admin:* https://portal.maritimesecuritymx.com/admin/portal_cliente/cotizacionpendiente/{cot.id}/change/\n\n"
            f"⚓ _MIA requiere que selecciones el rango, tipo de servicio y des clic en APROBAR para despacharla._"
        )
        
        # Enviamos directo a tu JID
        enviar_whatsapp_jid(JULIAN_JID, msg_alerta)
        print(f"  📢 Alerta de hora enviada para Cotización ID: {cot.id}")


def iniciar_scheduler():
    scheduler = BackgroundScheduler()

    scheduler.add_job(job_resumen_matutino, CronTrigger(hour=14, minute=0), id='resumen', replace_existing=True)
    scheduler.add_job(job_alta_navieras, CronTrigger(hour=15, minute=0), id='altas', replace_existing=True)
    scheduler.add_job(job_docs_pbip_faltantes, CronTrigger(hour=16, minute=0), id='pbip', replace_existing=True)
    scheduler.add_job(job_recordatorio_cotizaciones_por_hora, CronTrigger(minute=0), id='recordatorio_cotizaciones', replace_existing=True)
    
    scheduler.start()
    print(f"🚀 MIA Proactivo v4 iniciado. Todo por MIA (puerto 9000). Jobs: {len(scheduler.get_jobs())}")
    return scheduler


if __name__ == '__main__':
    scheduler = iniciar_scheduler()
    try:
        while True:
            import time
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("👋 Detenido.")