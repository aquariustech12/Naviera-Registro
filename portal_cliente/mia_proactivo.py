# portal_cliente/mia_proactivo.py — OPR PROACTIVO v3 (WhatsApp + Email)
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
from portal_cliente.mia_herramientas import enviar_whatsapp_jid, enviar_whatsapp_numero, enviar_opr_notificacion
from django.core.mail import EmailMessage
from portal_cliente.models import AlertaProactiva

JULIAN_JID = "5216444475422@s.whatsapp.net"
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
            from_email='OPR <08opr.manager@gmail.com>',  # Nombre corto
            to=[naviera.correo_electronico],
            reply_to=['generalmanager@maritimeprotection.mx'],
        )
        # NO poner BCC a ADMIN_EMAIL en cada email — eso también dispara spam filters
        email.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"  ❌ Error email: {e}")
        return False


def _enviar_whatsapp_cliente(naviera, mensaje):
    """Envía WhatsApp al cliente si tenemos número."""
    if not naviera.telefono_contacto:
        return False
    try:
        numero = naviera.telefono_contacto.strip().replace(' ', '').replace('-', '').replace('+', '')
        if not numero.startswith('52'):
            numero = '52' + numero
        jid = f"{numero}@s.whatsapp.net"
        enviar_whatsapp_jid(jid, mensaje)
        return True
    except Exception as e:
        print(f"  ❌ Error WhatsApp a {naviera.telefono_contacto}: {e}")
        return False


def _notificar_cliente(naviera, asunto_email, cuerpo_email, mensaje_whatsapp):
    """Notifica al cliente por email y WhatsApp (OPR Gateway)."""
    wa_ok = False
    email_ok = False
    
    # WhatsApp via OPR Gateway (solo notificaciones, no interactivo)
    if naviera.telefono_contacto:
        try:
            numero = naviera.telefono_contacto.strip().replace(' ', '').replace('-', '').replace('+', '')
            if not numero.startswith('52'):
                numero = '52' + numero
            jid = f"{numero}@s.whatsapp.net"
            wa_ok = enviar_opr_notificacion(jid, mensaje_whatsapp)
        except Exception as e:
            print(f"  ❌ Error OPR: {e}")
    
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

¿Podría subirlos esta semana? Así avanzamos con la auditoría.

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
OPR - Organización de Protección Reconocida
"""
        
        wa_ok, email_ok = _notificar_cliente(naviera, asunto, cuerpo, msg_wa)
        
        # Confirmación a Julian
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
OPR - Organización de Protección Reconocida
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


def iniciar_scheduler():
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(job_resumen_matutino, CronTrigger(hour=14, minute=0), id='resumen', replace_existing=True)
    scheduler.add_job(job_alta_navieras, CronTrigger(hour=15, minute=0), id='altas', replace_existing=True)
    scheduler.add_job(job_docs_pbip_faltantes, CronTrigger(hour=16, minute=0), id='pbip', replace_existing=True)
    
    scheduler.start()
    print(f"🚀 MIA/OPR Proactivo iniciado. Jobs: {len(scheduler.get_jobs())}")
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