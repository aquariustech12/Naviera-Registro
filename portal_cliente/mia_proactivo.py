# portal_cliente/mia_proactivo.py — OPR PROACTIVO v4 (Todo por MIA)
#
# NOTA: Este archivo se ejecuta como servicio independiente (systemd).
# NO importar django.setup() desde módulos Django — solo aplica al bloque __main__.
#
import os
import sys
import logging

# ── Solo necesario cuando se ejecuta como __main__ (servicio standalone) ──
if __name__ == '__main__':
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'naviera_registro.settings')
    import django
    django.setup()

from datetime import datetime, timedelta
from django.utils import timezone
from django.core.mail import EmailMessage
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from naviera_registro.models import Naviera, Buque, RequisitoBuque, PuntoPBIP
from portal_cliente.mia_herramientas import (
    enviar_whatsapp_jid,
    enviar_whatsapp_numero,
    enviar_opr_notificacion,
)
from portal_cliente.models import AlertaProactiva, CotizacionPendiente

logger = logging.getLogger(__name__)

# ── JIDs de notificación ──
JULIAN_JID   = "5216444475422@s.whatsapp.net"
FINANZAS_JID = "5215563183674@s.whatsapp.net"
ADMIN_EMAIL  = "generalmanager@maritimeprotection.mx"


# ============================================================================
# HELPERS
# ============================================================================

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
    """Notifica al cliente por email y WhatsApp."""
    wa_ok = False
    email_ok = False

    if naviera.telefono_contacto:
        try:
            wa_ok = _enviar_whatsapp_cliente(naviera, mensaje_whatsapp)
        except Exception as e:
            print(f"  ❌ Error MIA: {e}")

    email_ok = _enviar_email_cliente(naviera, asunto_email, cuerpo_email)
    return wa_ok, email_ok


# ============================================================================
# JOBS
# ============================================================================

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

        msg_wa = (
            f"Buen día {naviera.contacto_principal or ''},\n\n"
            f"Le escribo de OPR. Vimos que en {naviera.nombre_empresa} aún faltan {faltan} "
            f"documentos para completar el registro ({admin_count}/6).\n\n"
            f"¿Podría subirlos esta semana?\n\n"
            f"Portal: portal.maritimesecuritymx.com\n\n"
            f"Cualquier duda me avisa.\n\nSaludos,\nOPR Operaciones"
        )

        asunto = f"Registro pendiente | {naviera.nombre_empresa}"
        cuerpo = (
            f"Estimado(a) {naviera.contacto_principal or 'Cliente'},\n\n"
            f"Por medio de la presente, le recordamos que su proceso de registro en OPR se encuentra incompleto.\n\n"
            f"🏢 Empresa: {naviera.nombre_empresa}\n"
            f"📋 Documentos faltantes: {faltan}/6\n\n"
            f"Pendientes:\n{faltantes_str}\n\n"
            f"Por favor, complete la documentación en su portal:\n"
            f"https://portal.maritimesecuritymx.com/portal/\n\n"
            f"Atentamente,\nOPR - Operaciones (Mensaje de Sistema - No responder)"
        )

        wa_ok, email_ok = _notificar_cliente(naviera, asunto, cuerpo, msg_wa)

        canales = []
        if wa_ok: canales.append("WhatsApp")
        if email_ok: canales.append("Email")

        msg_julian = (
            f"✅ *OPR alertó a cliente*\n\n"
            f"🏢 *{naviera.nombre_empresa}*\n"
            f"👤 *Contacto:* {naviera.contacto_principal}\n"
            f"📱 *WhatsApp:* {'✅' if wa_ok else '❌'} {naviera.telefono_contacto or 'N/A'}\n"
            f"📧 *Email:* {'✅' if email_ok else '❌'} {naviera.correo_electronico}\n"
            f"📋 *Faltan:* {faltan}/6\n"
            f"📅 *Días registrada:* {dias_registro}\n\n"
            f"Canales usados: {', '.join(canales) if canales else 'NINGUNO - revisar'}"
        )

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

        msg_wa = (
            f"Buen día,\n\n"
            f"Le escribo de OPR sobre el buque *{buque.nombre_buque}* (OMI: {buque.OMI}).\n\n"
            f"El expediente PBIP va al {pct}%, faltan {faltan} documentos. "
            f"¿Podría subir lo que falta esta semana?\n\n"
            f"Portal: portal.maritimesecuritymx.com\n\nGracias,\nOPR Operaciones"
        )

        asunto = f"Documentación PBIP | {buque.nombre_buque}"
        cuerpo = (
            f"Estimado(a) {buque.naviera.contacto_principal or 'Cliente'},\n\n"
            f"Le escribimos de OPR respecto a la documentación PBIP del buque "
            f"{buque.nombre_buque} (OMI: {buque.OMI}).\n\n"
            f"📊 Progreso: {pbip_count}/{total_pbip} ({pct}%)\n"
            f"❌ Faltan: {faltan} documentos\n\n"
            f"Por favor, suba la documentación faltante en su portal:\n"
            f"https://portal.maritimesecuritymx.com/portal/\n\n"
            f"Atentamente,\nOPR - Operaciones (Mensaje de Sistema - No responder)"
        )

        wa_ok, email_ok = _notificar_cliente(buque.naviera, asunto, cuerpo, msg_wa)

        canales = []
        if wa_ok: canales.append("WhatsApp")
        if email_ok: canales.append("Email")

        msg_julian = (
            f"✅ *OPR alertó PBIP*\n\n"
            f"🚢 *{buque.nombre_buque}* (OMI:{buque.OMI})\n"
            f"🏢 *Naviera:* {buque.naviera.nombre_empresa}\n"
            f"📊 *Progreso:* {pbip_count}/{total_pbip} ({pct}%)\n"
            f"📱 *WA:* {'✅' if wa_ok else '❌'}\n"
            f"📧 *Email:* {'✅' if email_ok else '❌'}"
        )

        enviar_whatsapp_jid(JULIAN_JID, msg_julian)
        _registrar_alerta(buque.naviera, 'DOCS_PBIP_FALTANTES', msg_julian, 'mixto', buque=buque, exito=bool(canales))


def job_resumen_matutino():
    """Resumen para Julian — Firma MIA."""
    print(f"\n🔔 [{timezone.now()}] job_resumen_matutino ejecutando...")

    total_navieras = Naviera.objects.count()
    incompletas    = Naviera.objects.filter(alta_completa=False).count()
    total_buques   = Buque.objects.count()
    total_pbip     = PuntoPBIP.objects.count()

    buques_data = []
    for b in Buque.objects.all():
        pbip_count = RequisitoBuque.objects.filter(buque=b, categoria='DOCUMENTAL').count()
        pct = int((pbip_count / total_pbip) * 100) if total_pbip else 0
        buques_data.append((b, pct))

    promedio_pbip = sum(p for _, p in buques_data) // len(buques_data) if buques_data else 0
    criticos = [b for b, p in buques_data if p < 50]

    msg = (
        f"🤖 *MIA - RESUMEN MATUTINO*\n"
        f"📅 {timezone.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"📊 *ESTADO GENERAL:*\n"
        f"• Navieras: {total_navieras} ({incompletas} sin alta)\n"
        f"• Buques: {total_buques}\n"
        f"• Promedio PBIP: {promedio_pbip}%\n\n"
        f"🚢 *CRÍTICOS (<50%):*\n"
    )

    if criticos:
        for b in criticos:
            pbip_count = RequisitoBuque.objects.filter(buque=b, categoria='DOCUMENTAL').count()
            pct = int((pbip_count / total_pbip) * 100) if total_pbip else 0
            msg += f"• {b.nombre_buque}: {pct}% ({b.naviera.nombre_empresa})\n"
    else:
        msg += "• Ninguno 🎉\n"

    msg += "\n📋 *PENDIENTES:*\n"
    for n in Naviera.objects.filter(alta_completa=False):
        admin_count = RequisitoBuque.objects.filter(naviera=n, buque__isnull=True, categoria='ADMINISTRATIVO').count()
        msg += f"• {n.nombre_empresa}: {admin_count}/6 admin\n"

    msg += "\n_¿Algo más, capitán?_ ⚓"

    enviar_whatsapp_jid(JULIAN_JID, msg)
    _registrar_alerta(None, 'RESUMEN_DIARIO', msg)
    print("  ✅ Resumen enviado")


def job_recordatorio_cotizaciones_por_hora():
    """Rastrea cotizaciones en borrador y envía recordatorio por hora a Julian."""
    print(f"⏳ [{timezone.now()}] Ejecutando recordatorio de cotizaciones pendientes...")

    borradores = CotizacionPendiente.objects.filter(estado='borrador')

    if not borradores.exists():
        print("  ✅ No hay cotizaciones en borrador pendientes de aprobación.")
        return

    for cot in borradores:
        buque_nombre   = cot.buque.nombre_buque if cot.buque else "N/A"
        naviera_nombre = cot.naviera.nombre_empresa if cot.naviera else "N/A"

        msg_alerta = (
            f"⏳ *MIA - ALERTA DE SEGUIMIENTO (POR HORA)*\n\n"
            f"Capitán, la siguiente cotización sigue en *Borrador* y no se ha enviado al cliente:\n\n"
            f"🏢 *Naviera:* {naviera_nombre}\n"
            f"🚢 *Buque:* {buque_nombre}\n"
            f"🆔 *Cotización ID:* {cot.id}\n\n"
            f"🔗 *Link Directo al Admin:* "
            f"https://portal.maritimesecuritymx.com/admin/portal_cliente/cotizacionpendiente/{cot.id}/change/\n\n"
            f"⚓ _MIA requiere que selecciones el rango, tipo de servicio y des clic en APROBAR para despacharla._"
        )

        enviar_whatsapp_jid(JULIAN_JID, msg_alerta)
        print(f"  📢 Alerta de hora enviada para Cotización ID: {cot.id}")


# ============================================================================
# SCHEDULER
# ============================================================================

def iniciar_scheduler():
    from apscheduler.executors.pool import ThreadPoolExecutor

    executors = {
        'default': ThreadPoolExecutor(1)  # un job a la vez
    }
    job_defaults = {
        'coalesce': True,          # si se perdieron N ejecuciones, corre solo 1
        'max_instances': 1,        # nunca dos instancias del mismo job simultáneas
        'misfire_grace_time': 60   # si llega tarde menos de 60s, lo corre; si no, lo descarta
    }

    scheduler = BackgroundScheduler(
        executors=executors,
        job_defaults=job_defaults
    )

    scheduler.add_job(job_resumen_matutino,                   CronTrigger(hour=14, minute=0), id='resumen',                   replace_existing=True)
    scheduler.add_job(job_alta_navieras,                      CronTrigger(hour=15, minute=0), id='altas',                     replace_existing=True)
    scheduler.add_job(job_docs_pbip_faltantes,                CronTrigger(hour=16, minute=0), id='pbip',                      replace_existing=True)
    scheduler.add_job(job_recordatorio_cotizaciones_por_hora, CronTrigger(minute=0),          id='recordatorio_cotizaciones',  replace_existing=True)

    scheduler.start()
    print(f"🚀 MIA Proactivo v4 iniciado. Jobs: {len(scheduler.get_jobs())}")
    return scheduler

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    iniciar_scheduler()

    # Mantener el thread principal vivo para que el daemon thread del scheduler no muera
    import time
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        pass