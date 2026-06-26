# portal_cliente/mia_documentos.py — VERSIÓN ESTABLE
import os
import traceback
from datetime import datetime
from .mia_herramientas import (
    extraer_texto_universal,
    herramienta_consultar_pbip,
    consultar_ollama,
    enviar_whatsapp_jid
)


ADMIN_KEYWORDS = [
    'factura', 'cotizacion', 'pago', 'rfc', 'domicilio', 'fgmp-fc-01',
    'acta constitutiva', 'poder notarial', 'ine', 'opinion sat', 
    'estado de cuenta', 'directorio contactos', 'comprobante de pago',
    'comprobante', 'recibo', 'transferencia', 'deposito', 'sat', 'constitutiva', 'notarial', 'representante', 'contactos'
]


def herramienta_analizar_documento(documento_obj, jid_remitente=None):
    """
    Analiza un documento contra el código PBIP.
    """
    # VALIDACIÓN DE ENTRADA
    if documento_obj is None:
        _notificar_error(jid_remitente, "SIN_DOCUMENTO", "No se recibió documento para analizar.")
        return False

    nombre_doc = getattr(documento_obj, 'nombre_documento', None)
    if not nombre_doc:
        _notificar_error(jid_remitente, "SIN_NOMBRE", "El documento no tiene nombre.")
        return False

    archivo = getattr(documento_obj, 'archivo', None)
    if archivo is None:
        _notificar_error(jid_remitente, nombre_doc, "El documento no tiene archivo adjunto.")
        return False

    # OBTENER RUTA DEL ARCHIVO
    ruta_archivo = None
    es_temporal = False

    try:
        ruta_archivo = archivo.path
    except (AttributeError, ValueError):
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                for chunk in archivo.chunks():
                    tmp.write(chunk)
                ruta_archivo = tmp.name
            es_temporal = True
            print(f"💾 Archivo temporal creado: {ruta_archivo}")
        except Exception as e:
            _notificar_error(jid_remitente, nombre_doc, f"No se pudo crear archivo temporal: {e}")
            return False

    if not ruta_archivo or not os.path.exists(ruta_archivo):
        _notificar_error(jid_remitente, nombre_doc, "El archivo no existe en disco.")
        return False

    # EXTRAER TEXTO (UNA SOLA VEZ)
    try:
        texto = extraer_texto_universal(ruta_archivo)
    finally:
        if es_temporal and os.path.exists(ruta_archivo):
            try:
                os.unlink(ruta_archivo)
            except:
                pass

    if texto.startswith("Error"):
        _notificar_error(jid_remitente, nombre_doc, texto)
        return False

    # CLASIFICAR Y ANALIZAR
    try:
        es_admin = any(key in nombre_doc.lower() for key in ADMIN_KEYWORDS)

        if es_admin:
            mensaje = f"""🤖 *MIA - REGISTRO*
📄 *Documento:* {nombre_doc}
🏷️ *Tipo:* Administrativo
🔍 *Análisis:* No requiere evaluación técnica.
✅/❌ *Dictamen:* NO APLICA PBIP"""
            _notificar(jid_remitente, mensaje)
            return True

        # Análisis PBIP Técnico
        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        contexto_pbip = herramienta_consultar_pbip(texto[:4000], k=8)

        prompt = f"""Eres MIA, auditor experto en Código PBIP. Analiza el documento con precisión quirúrgica.
FECHA: {fecha_hoy}
DOCUMENTO: "{nombre_doc}"

CONTENIDO EXTRAÍDO:
{texto[:5000]}

MARCO LEGAL PBIP (RAG):
{contexto_pbip}

INSTRUCCIONES CRÍTICAS:
1. Identifica el tipo exacto de documento (Designación OPB, Designación PFSO, Plan de Protección, Certificado, etc.)
2. Para DESIGNACIONES (OPB, PFSO, OCPM):
   - Extrae TODOS los titulares nombrados — puede haber varios
   - El firmante es el OCPM o autoridad que designa, NO el titular
   - Busca: nombres de capitanes, oficiales o personal designado
   - La vigencia suele ser "Permanente mientras dure el cargo" si no hay fecha explícita
3. Para PLANES o EVALUACIONES: extrae secciones y verifica estructura mínima
4. Dictamen pragmático:
   - CUMPLE si el documento cumple su función principal (designar, certificar, planificar)
   - NO CUMPLE solo si faltan datos esenciales o está vencido
   - NO inventes requisitos que no están en los artículos recuperados
5. Cita SOLO artículos que aparezcan en el MARCO LEGAL PBIP de arriba

FORMATO OBLIGATORIO:
🤖 *MIA - AUDITORÍA*
📄 *Documento:* {nombre_doc}
🏷️ *Tipo:* [tipo exacto]
👤 *Titular(es):* [todos los nombres encontrados, separados por coma, o "No encontrado"]
✍️ *Firmante/Autoridad:* [quien expide o firma]
📜 *Folio:* [número o "No encontrado"]
📅 *Expedición:* [fecha encontrada o "No especificada"]
⏰ *Vigencia:* [fecha o "Permanente mientras dure el cargo"]
🔍 *Análisis:* [evaluación real basada en el contenido, sin inventar]
📜 *Base Legal:* [solo artículos que aparecen en el marco legal RAG]
✅/❌ *Dictamen:* [CUMPLE / NO CUMPLE / NO APLICA]
💡 *Recomendación:* [solo si hay deficiencias reales]"""

        resultado = consultar_ollama(prompt, temperature=0.2, num_ctx=16384)
        _notificar(jid_remitente, resultado)
        return True

    except Exception as e:
        _notificar_error(jid_remitente, nombre_doc, f"Error en análisis PBIP: {e}")
        traceback.print_exc()
        return False


def _notificar(jid, mensaje):
    """Envía mensaje por WhatsApp si hay JID."""
    if jid:
        enviar_whatsapp_jid(jid, mensaje)


def _notificar_error(jid, nombre_doc, error_msg):
    """Notifica error de forma segura."""
    safe_name = nombre_doc or "DOCUMENTO_DESCONOCIDO"
    mensaje = f"🤖 MIA - ERROR\n📄 {safe_name}\n❌ {error_msg}"
    print(f"ERROR documento [{safe_name}]: {error_msg}")
    if jid:
        enviar_whatsapp_jid(jid, mensaje)