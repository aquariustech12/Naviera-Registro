# portal_cliente/mia_comandos.py
# Comunicación bidireccional WhatsApp + Tareas automáticas

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'naviera_registro.settings')
django.setup()

from naviera_registro.models import Buque, RequisitoBuque, PuntoPBIP, Naviera
from django.core.mail import EmailMessage
from django.utils import timezone
import requests


def procesar_comando_whatsapp(mensaje):
    """Procesa comandos del auditor vía WhatsApp"""
    mensaje = mensaje.lower().strip()
    
    if mensaje == "estado":
        return reporte_global_estado()
    
    if mensaje.startswith("buque "):
        omi = mensaje.replace("buque ", "").strip()
        return estado_buque_por_omi(omi)
    
    if mensaje.startswith("naviera "):
        nombre = mensaje.replace("naviera ", "").strip()
        return estado_naviera_por_nombre(nombre)
    
    if mensaje.startswith("recordar "):
        omi = mensaje.replace("recordar ", "").strip()
        return enviar_recordatorio_especifico(omi)
    
    if mensaje == "reporte":
        return "📊 Reporte Excel: En desarrollo. Se enviará a generalmanager@maritimeprotection.mx"
    
    if mensaje in ["ayuda", "help", "comandos"]:
        return """🤖 *MIA - COMANDOS*

• *estado* → Todos los buques y % avance
• *buque [OMI]* → Detalle de un buque
• *naviera [nombre]* → Buques de naviera
• *recordar [OMI]* → Recordatorio AHORA
• *reporte* → Generar Excel
• *ayuda* → Ver esta lista"""
    
    return responder_con_ia(mensaje)



def reporte_global_estado():
    """Resumen de todos los buques"""
    buques = Buque.objects.all()
    total_pbip = PuntoPBIP.objects.count()
    lineas = ["🤖 *MIA - ESTADO GLOBAL*\n"]
    
    for buque in buques:
        pbip_subidos = RequisitoBuque.objects.filter(
            buque=buque, categoria='DOCUMENTAL'
        ).count()
        
        pct = int((pbip_subidos / total_pbip) * 100)
        estado = "✅" if pct == 100 else f"{pct}%"
        
        lineas.append(f"• {buque.nombre_buque[:20]} (OMI:{buque.OMI}): {estado}")
    
    if not buques:
        lineas.append("• No hay buques registrados")
    
    lineas.append(f"\n_Total: {buques.count()} buques | {total_pbip} docs PBIP_")
    return "\n".join(lineas)


def estado_buque_por_omi(omi):
    """Detalle completo de un buque específico"""
    try:
        buque = Buque.objects.get(OMI=omi)
    except Buque.DoesNotExist:
        return f"❌ No encontré buque con OMI: {omi}"
    
    # PBIP
    pbip_subidos = list(RequisitoBuque.objects.filter(
        buque=buque, categoria='DOCUMENTAL'
    ).values_list('nombre_documento', flat=True))
    
    todos_pbip = list(PuntoPBIP.objects.values_list('descripcion', flat=True))
    faltantes_pbip = [p for p in todos_pbip if p not in pbip_subidos]
    
    # Cotización
    cotizacion_ok = RequisitoBuque.objects.filter(
        buque=buque, categoria='COTIZACION'
    ).exists()
    
    # Administrativos
    naviera = buque.naviera
    admin_subidos = list(RequisitoBuque.objects.filter(
        naviera=naviera, buque=None, categoria='ADMINISTRATIVO'
    ).values_list('nombre_documento', flat=True))
    
    admin_requeridos = [
        "Acta Constitutiva", "Poder Notarial", "INE Representante",
        "Opinión SAT", "Estado de Cuenta", "Directorio Contactos"
    ]
    faltantes_admin = [a for a in admin_requeridos if a not in admin_subidos]
    
    # Última actividad
    ultimo = RequisitoBuque.objects.filter(
        buque=buque
    ).order_by('-fecha_subida').first()
    
    dias = "N/A"
    if ultimo:
        dias = (timezone.now() - ultimo.fecha_subida).days
    
    # Construir respuesta
    lineas = [
        f"🤖 *BUQUE: {buque.nombre_buque}*",
        f"📋 OMI: {buque.OMI}",
        f"🏢 {naviera.nombre_empresa}",
        f"\n📊 *PROGRESO:*",
        f"• Cotización: {'✅' if cotizacion_ok else '❌'}",
        f"• PBIP: {len(pbip_subidos)}/{len(todos_pbip)} ({int(len(pbip_subidos)/len(todos_pbip)*100)}%)",
    ]
    
    if faltantes_pbip:
        lineas.append(f"\n❌ *Faltan PBIP ({len(faltantes_pbip)}):*")
        for f in faltantes_pbip[:5]:
            lineas.append(f"  - {f[:35]}...")
        if len(faltantes_pbip) > 5:
            lineas.append(f"  ... y {len(faltantes_pbip) - 5} más")
    
    if faltantes_admin:
        lineas.append(f"\n⚠️ *Admin ({len(faltantes_admin)}):*")
        for f in faltantes_admin:
            lineas.append(f"  - {f}")
    
    lineas.append(f"\n⏰ Última subida: hace {dias} días")
    
    return "\n".join(lineas)


def estado_naviera_por_nombre(nombre_busqueda):
    """Busca naviera por nombre parcial"""
    navieras = Naviera.objects.filter(nombre_empresa__icontains=nombre_busqueda)
    
    if not navieras:
        return f"❌ No encontré naviera: '{nombre_busqueda}'"
    
    if navieras.count() > 1:
        nombres = [n.nombre_empresa for n in navieras[:5]]
        return f"⚠️ {navieras.count()} navieras:\n" + "\n".join(f"• {n}" for n in nombres)
    
    naviera = navieras.first()
    buques = Buque.objects.filter(naviera=naviera)
    
    lineas = [
        f"🤖 *NAVIERA: {naviera.nombre_empresa}*",
        f"\n🚢 *BUQUES ({buques.count()}):*"
    ]
    
    for b in buques:
        pbip_count = RequisitoBuque.objects.filter(buque=b, categoria='DOCUMENTAL').count()
        total_pbip = PuntoPBIP.objects.count()
        pct = int((pbip_count / total_pbip) * 100)
        lineas.append(f"• {b.nombre_buque} (OMI:{b.OMI}): {pct}%")
    
    return "\n".join(lineas)


def enviar_recordatorio_especifico(omi):
    """Envía recordatorio inmediato a naviera"""
    try:
        buque = Buque.objects.get(OMI=omi)
    except Buque.DoesNotExist:
        return f"❌ OMI no encontrado: {omi}"
    
    naviera = buque.naviera
    
    # Obtener faltantes PBIP
    pbip_subidos = list(RequisitoBuque.objects.filter(
        buque=buque, categoria='DOCUMENTAL'
    ).values_list('nombre_documento', flat=True))
    
    todos_pbip = list(PuntoPBIP.objects.values_list('descripcion', flat=True))
    faltantes = [p for p in todos_pbip if p not in pbip_subidos]
    
    if not faltantes:
        return f"✅ {buque.nombre_buque} ya está completo"
    
    pct = int(((len(todos_pbip) - len(faltantes)) / len(todos_pbip)) * 100)
    
    # Enviar email
    asunto = f"RECORDATORIO: Documentación pendiente - {buque.nombre_buque}"
    
    cuerpo = f"""Estimado cliente {naviera.nombre_empresa},

Le recordamos que el buque "{buque.nombre_buque}" (OMI: {buque.OMI}) tiene {pct}% de documentación completada.

FALTAN {len(faltantes)} DOCUMENTOS:
{chr(10).join(f"• {doc}" for doc in faltantes[:10])}
{f"• ... y {len(faltantes) - 10} más" if len(faltantes) > 10 else ""}

Suba la documentación en:
https://maritimeprotection.mx/portal_cliente/

--
Global Maritime Protection
"""
    
    try:
        email = EmailMessage(
            subject=asunto,
            body=cuerpo,
            from_email='generalmanager@maritimeprotection.mx',
            to=[naviera.correo_electronico],
            bcc=['generalmanager@maritimeprotection.mx'],
        )
        email.send(fail_silently=False)
        
        return f"✅ Recordatorio enviado a {naviera.nombre_empresa} sobre {buque.nombre_buque} ({len(faltantes)} docs faltantes)"
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ============================================================================
# TAREAS AUTOMÁTICAS (Cron: Lunes y Jueves 9:00 AM)
# ============================================================================

def revision_automatica_lunes_jueves():
    """
    Ejecutar vía cron: Lunes y Jueves
    Revisa todos los buques y envía recordatorios si faltan documentos
    """
    buques = Buque.objects.all()
    total_pbip = PuntoPBIP.objects.count()
    reporte = []
    
    for buque in buques:
        pbip_subidos = RequisitoBuque.objects.filter(
            buque=buque, categoria='DOCUMENTAL'
        ).count()
        
        if pbip_subidos >= total_pbip:
            continue  # Completo, no molestar
        
        # Enviar recordatorio
        resultado = enviar_recordatorio_automatico(buque, pbip_subidos, total_pbip)
        reporte.append(resultado)
    
    # Resumen para auditor por WhatsApp
    if reporte:
        enviados = sum(1 for r in reporte if r['enviado'])
        lineas = [
            f"🤖 *MIA - REVISIÓN AUTOMÁTICA*",
            f"📅 {timezone.now().strftime('%d/%m/%Y %H:%M')}",
            f"\n📊 Resumen:",
            f"• Buques revisados: {buques.count()}",
            f"• Incompletos: {len(reporte)}",
            f"• Recordatorios enviados: {enviados}",
            f"\n📋 Detalle:"
        ]
        for r in reporte[:10]:
            icono = "✅" if r['enviado'] else "❌"
            lineas.append(f"{icono} {r['buque']} ({r['pct']}%) - {r['naviera'][:20]}")
        
        if len(reporte) > 10:
            lineas.append(f"... y {len(reporte) - 10} más")
        
        enviar_whatsapp_auditor("\n".join(lineas))
    
    return len(reporte)


def enviar_recordatorio_automatico(buque, pbip_subidos, total_pbip):
    """Envía recordatorio automático, retorna dict para reporte"""
    naviera = buque.naviera
    pct = int((pbip_subidos / total_pbip) * 100)
    
    # Faltantes
    subidos_nombres = list(RequisitoBuque.objects.filter(
        buque=buque, categoria='DOCUMENTAL'
    ).values_list('nombre_documento', flat=True))
    
    todos_nombres = list(PuntoPBIP.objects.values_list('descripcion', flat=True))
    faltantes = [p for p in todos_nombres if p not in subidos_nombres]
    
    asunto = f"RECORDATORIO AUTOMÁTICO MIA - Documentación pendiente - {buque.nombre_buque}"
    
    cuerpo = f"""Estimado cliente {naviera.nombre_empresa},

Nuestro sistema MIA detecta que el buque "{buque.nombre_buque}" (OMI: {buque.OMI}) requiere atención.

PROGRESO: {pbip_subidos}/{total_pbip} documentos ({pct}%)

DOCUMENTOS FALTANTES:
{chr(10).join(f"• {doc}" for doc in faltantes[:8])}
{f"• ... y {len(faltantes) - 8} más" if len(faltantes) > 8 else ""}

Este es un mensaje automático del sistema de gestión MIA.
Global Maritime Protection
"""
    
    try:
        email = EmailMessage(
            subject=asunto,
            body=cuerpo,
            from_email='Portal OPR 08opr.manager@gmail.com',
            to=[naviera.correo_electronico],
            bcc=['generalmanager@maritimeprotection.mx'],
        )
        email.send(fail_silently=True)
        
        return {
            'buque': buque.nombre_buque,
            'omi': buque.OMI,
            'naviera': naviera.nombre_empresa,
            'pct': pct,
            'enviado': True
        }
    except Exception as e:
        return {
            'buque': buque.nombre_buque,
            'omi': buque.OMI,
            'naviera': naviera.nombre_empresa,
            'pct': pct,
            'enviado': False,
            'error': str(e)
        }


def enviar_whatsapp_auditor(mensaje):
    """Envía WhatsApp al auditor (tu número)"""
    try:
        requests.post(
            "http://localhost:9000/enviar",
            json={"numero": "5215581073859", "mensaje": mensaje},
            timeout=10
        )
    except:
        pass

# Agregar esta función al final del archivo (antes de las funciones existentes o donde prefieras)
def enviar_whatsapp(numero, mensaje):
    """Envía un mensaje WhatsApp a un número específico a través del puente Node.js"""
    try:
        import requests
        requests.post(
            "http://localhost:9000/enviar",
            json={"numero": numero, "mensaje": mensaje},
            timeout=10
        )
    except Exception as e:
        print(f"Error enviando WhatsApp: {e}")

# Modificar la función existente enviar_whatsapp_auditor para que use la genérica
def enviar_whatsapp_auditor(mensaje):
    enviar_whatsapp("5215581073859", mensaje)   # Reemplaza con tu número fijo si es necesario

def enviar_whatsapp_jid(jid, mensaje):
    """Envía un mensaje WhatsApp a un JID completo (con sufijo)"""
    try:
        import requests
        requests.post(
            "http://localhost:9000/enviar",
            json={"jid": jid, "mensaje": mensaje},
            timeout=10
        )
    except Exception as e:
        print(f"Error enviando WhatsApp: {e}")

def consultar_ollama(prompt):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:14b",
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 4096, "temperature": 0.1, "top_p": 0.9}
    }
    try:
        r = requests.post(url, json=payload, timeout=120)
        return r.json().get('response', 'Sin respuesta')
    except Exception as e:
        return f"Error consultando IA: {e}"

def obtener_contexto_bd():
    """Obtiene datos actuales de la BD para dar contexto al LLM"""
    from naviera_registro.models import Buque, RequisitoBuque, PuntoPBIP, Naviera
    total_pbip = PuntoPBIP.objects.count()
    navieras = Naviera.objects.all()
    buques = Buque.objects.all()

    contexto = "DATOS ACTUALES:\n"
    for nav in navieras:
        contexto += f"Naviera: {nav.nombre_empresa}\n"
        for buque in nav.buques.all():
            pbip_subidos = RequisitoBuque.objects.filter(buque=buque, categoria='DOCUMENTAL').count()
            pct = int((pbip_subidos / total_pbip) * 100) if total_pbip else 0
            contexto += f"  - Buque: {buque.nombre_buque} (OMI: {buque.OMI}) → {pct}% completado\n"
        contexto += "\n"
    return contexto

def responder_con_ia(pregunta):
    """Responde cualquier pregunta usando el LLM con el contexto actual"""
    contexto = obtener_contexto_bd()
    prompt = f"""Eres MIA, el asistente de auditoría de protección marítima. Responde en español de forma clara, concisa y amigable.

CONTEXTO ACTUAL:
{contexto}

PREGUNTA DEL USUARIO:
{pregunta}

INSTRUCCIONES:
- Usa solo los datos proporcionados. Si no hay información suficiente, responde con lo que sabes y sugiere qué datos faltan.
- No inventes información.
- Si el usuario pregunta por un buque o naviera que no existe, indícalo.
- Sé útil, directo y con un tono profesional pero cercano.
- Incluye emojis relevantes si es natural.
- La respuesta debe ser para WhatsApp, así que usa texto plano con formato simple (*negritas*).
"""
    return consultar_ollama(prompt)
