# portal_cliente/mia_documentos.py
import os
from datetime import datetime
from .mia_herramientas import (
    extraer_texto_universal,
    herramienta_consultar_pbip,
    consultar_ollama,
    enviar_whatsapp_jid
)


def herramienta_analizar_documento(documento_obj, jid_remitente=None):
    try:
        print(f"\n📄 Analizando: {documento_obj.nombre_documento}")
        
        # Obtener ruta del archivo - funciona con Django FileField y objeto simulado
        ruta_archivo = None
        try:
            # Caso 1: Objeto simulado (WhatsApp) o Django FileField guardado
            ruta_archivo = documento_obj.archivo.path
        except (AttributeError, ValueError):
            # Caso 2: Django FileField en memoria, guardar temporalmente
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                for chunk in documento_obj.archivo.chunks():
                    tmp.write(chunk)
                ruta_archivo = tmp.name
            print(f"💾 Archivo temporal creado: {ruta_archivo}")
        
        if not ruta_archivo or not os.path.exists(ruta_archivo):
            error_msg = "Error: No se pudo obtener el archivo"
            if jid_remitente:
                enviar_whatsapp_jid(jid_remitente, error_msg)
            return False
        
        texto = extraer_texto_universal(ruta_archivo)
        
        texto = extraer_texto_universal(documento_obj.archivo.path)
        
        if texto.startswith("Error"):
            error_msg = f"🤖 MIA - ERROR\n📄 {documento_obj.nombre_documento}\n❌ {texto}"
            if jid_remitente:
                enviar_whatsapp_jid(jid_remitente, error_msg)
            return False

        # Filtro administrativos
        admin_keywords = [
    'factura', 'cotizacion', 'pago', 'rfc', 'domicilio', 'fgmp-fc-01',
    'acta constitutiva', 'poder notarial', 'ine', 'opinion sat', 
    'estado de cuenta', 'directorio contactos', 'comprobante de pago',
    'comprobante', 'recibo', 'transferencia', 'deposito', 'sat', 'constitutiva', 'notarial', 'representante', 'contactos'
]
        es_admin = any(key in documento_obj.nombre_documento.lower() for key in admin_keywords)

        if es_admin:
            mensaje = f"""🤖 *MIA - REGISTRO*
📄 *Documento:* {documento_obj.nombre_documento}
🏷️ *Tipo:* Administrativo
🔍 *Análisis:* No requiere evaluación técnica.
✅/❌ *Dictamen:* NO APLICA PBIP"""
            if jid_remitente:
                enviar_whatsapp_jid(jid_remitente, mensaje)
            return True

        # Análisis PBIP Técnico
        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        contexto_pbip = herramienta_consultar_pbip(texto[:4000], k=8)

        prompt = f"""Eres MIA, auditor experto en Código PBIP.
FECHA: {fecha_hoy}
DOCUMENTO: "{documento_obj.nombre_documento}"
CONTENIDO: {texto[:5000]}
ARTÍCULOS PBIP: {contexto_pbip}

INSTRUCCIONES:
1. Identifica tipo de documento.
2. Extrae Titular, Folio, Expedición, Vigencia.
3. Analiza contra artículos PBIP.
4. Evalúa cumplimiento.

FORMATO:
🤖 *MIA - AUDITORÍA*
📄 *Documento:* {documento_obj.nombre_documento}
🏷️ *Tipo:* [OPB/PFSO/Plan/Admin/etc.]
👤 *Titular:* [nombre o No encontrado]
📜 *Folio:* [número o No encontrado]
📅 *Expedición:* [fecha o No encontrado]
⏰ *Vigencia:* [fecha o No aplica]
🔍 *Análisis:* [evaluación detallada]
📜 *Base Legal:* [artículos aplicables]
✅/❌ *Dictamen:* [CUMPLE/NO CUMPLE/NO APLICA]
💡 *Recomendación:* [solo si hay deficiencias]"""

        resultado = consultar_ollama(prompt, temperature=0.2)
        
        if jid_remitente:
            enviar_whatsapp_jid(jid_remitente, resultado)
        
        return True

    except Exception as e:
        import traceback
        error_msg = f"🤖 MIA - ERROR\n📄 {documento_obj.nombre_documento}\n❌ {str(e)}"
        print(f"ERROR en analisis: {e}")
        print(traceback.format_exc())
        if jid_remitente:
            enviar_whatsapp_jid(jid_remitente, error_msg)
        return False