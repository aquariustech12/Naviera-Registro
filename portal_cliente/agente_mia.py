import os
import re
import json
import requests
import pdfplumber
from datetime import datetime
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# OCR
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

CHROMA_PATH = "/home/julian/Naviera-Registro/scripts/chroma_db"

print(f"--- MIA INICIANDO ---")
print(f"OCR: {'✅' if OCR_AVAILABLE else '❌'}")

embeddings = OllamaEmbeddings(model="nomic-embed-text")

try:
    vector_db = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name="auditoria_pbip"
    )
    count = vector_db._collection.count()
    print(f"✅ Base de conocimiento (PBIP): {count} documentos")
except Exception as e:
    print(f"❌ ERROR cargando Chroma: {e}")
    vector_db = None

def extraer_texto_pdf(ruta_archivo):
    try:
        texto_nativo = ""
        with pdfplumber.open(ruta_archivo) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    texto_nativo += page_text + "\n"
        if len(texto_nativo.strip()) > 200:
            return texto_nativo
        if OCR_AVAILABLE:
            print("📷 Aplicando OCR...")
            imagenes = convert_from_path(ruta_archivo, dpi=200)
            texto_total = ""
            for i, img in enumerate(imagenes, 1):
                texto = pytesseract.image_to_string(img, lang='spa')
                texto_total += f"\n--- PÁGINA {i} ---\n{texto}"
            return texto_total if texto_total.strip() else "ERROR: OCR vacío"
        return "ERROR: Sin texto y OCR no disponible"
    except Exception as e:
        return f"ERROR: {e}"

def consultar_ollama(prompt, temperature=0.2):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:14b",
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 16384, "temperature": temperature}  # Aumentado contexto para análisis completo
    }
    try:
        r = requests.post(url, json=payload, timeout=300)
        return r.json().get('response', 'Sin respuesta')
    except Exception as e:
        return f"Error IA: {e}"

def consultar_pbip_relevante(texto_documento):
    if vector_db is None:
        return "Base PBIP no disponible"
    try:
        query = texto_documento[:4000]  # Más contexto para mejor búsqueda
        docs = vector_db.similarity_search(query, k=8)  # Más resultados
        if not docs:
            return "No se encontraron artículos relevantes"
        contextos = []
        for doc in docs:
            meta = doc.metadata
            ref = f"{meta.get('seccion', 'PBIP')}"
            if meta.get('articulo'):
                ref += f", {meta['articulo']}"
            content = doc.page_content[:1000]  # Más contenido por artículo
            contextos.append(f"[{ref}]\n{content}")
        return "\n---\n".join(contextos)
    except Exception as e:
        return f"Error consultando PBIP: {e}"

def ejecutar_analisis_mia(documento_obj, jid_remitente=None):
    """
    Análisis PBIP directo SIN clasificador previo.
    El LLM identifica el documento y analiza contra PBIP en una sola pasada.
    """
    try:
        print(f"\n📄 Analizando: {documento_obj.nombre_documento}")
        print(f"📱 Destinatario: {jid_remitente or 'Default'}")
        
        texto = extraer_texto_pdf(documento_obj.archivo.path)
        if texto.startswith("ERROR"):
            return enviar_whatsapp_mia(
                f"🤖 MIA - ERROR\n📄 {documento_obj.nombre_documento}\n❌ {texto}",
                jid_remitente
            )

        fecha_hoy = datetime.now().strftime("%d/%m/%Y")

        # Documento ilegible
        if len(texto.strip()) < 100 or re.match(r'^[\d\s]+$', texto[:500]):
            mensaje = f"""🤖 *MIA - AUDITORÍA*
📄 *Documento:* {documento_obj.nombre_documento}
🏷️ *Tipo:* ILEGIBLE
🔍 *Análisis:* El documento no contiene texto legible.
✅/❌ *Dictamen:* ILEGIBLE
💡 *Recomendación:* Verifique resolución o aplique OCR."""
            return enviar_whatsapp_mia(mensaje, jid_remitente)

        # Buscar en Chroma ANTES de llamar a Ollama
        contexto_pbip = consultar_pbip_relevante(texto)
        
        # UN SOLO PROMPT: Identificación + Análisis PBIP
        prompt = f"""Eres MIA, auditor experto en el Código PBIP (Protección de Buques e Instalaciones Portuarias).

FECHA DE HOY: {fecha_hoy}
DOCUMENTO RECIBIDO: "{documento_obj.nombre_documento}"

CONTENIDO DEL DOCUMENTO:
{texto[:5000]}

ARTÍCULOS RELEVANTES DEL PBIP (de Chroma):
{contexto_pbip}

INSTRUCCIONES DE ANÁLISIS PBIP:
1. IDENTIFICA el tipo de documento leyendo su contenido:
   - ¿Es certificado de OPB (Oficial de Protección del Buque)?
   - ¿Es certificado de PFSO (Oficial de Protección de Instalación Portuaria)?  
   - ¿Es plan de protección del buque (SSP)?
   - ¿Es bitácora de protección?
   - ¿Es documento administrativo sin relación PBIP?
   
2. Si es documento PBIP (OPB, PFSO, plan de protección, etc.):
   - Extrae: nombre del titular, folio/certificado, fecha expedición, vigencia
   - Evalúa contra los artículos del PBIP proporcionados arriba
   - Verifica cumplimiento normativo específico
   
3. Si es documento administrativo sin relación PBIP:
   - Indica que no aplica evaluación PBIP
   
4. NO inventes información. Si no aparece en el documento, indica "No encontrado".
5. PBIP = ISPS (mismo código, distinto idioma).

FORMATO DE RESPUESTA:

🤖 *MIA - AUDITORÍA*
📄 *Documento:* {documento_obj.nombre_documento}
🏷️ *Tipo identificado:* [OPB/PFSO/Plan de protección/Administrativo/etc.]
👤 *Titular/Responsable:* [nombre o No encontrado]
📜 *Folio/Certificado:* [número o No encontrado]
📅 *Expedición:* [fecha o No encontrado]
⏰ *Vigencia:* [fecha o No aplica]
🔍 *Análisis PBIP:* [Evaluación detallada contra artículos citados]
📜 *Base Legal:* [Artículos PBIP aplicables o "No aplica PBIP"]
✅/❌ *Dictamen:* [CUMPLE / NO CUMPLE / CUMPLE CON OBSERVACIONES / NO APLICA PBIP]
💡 *Recomendación:* [solo si hay deficiencias]"""

        resultado = consultar_ollama(prompt, temperature=0.2)
        enviar_whatsapp_mia(resultado, jid_remitente)
        return True

    except Exception as e:
        enviar_whatsapp_mia(
            f"🤖 MIA - ERROR\n📄 {documento_obj.nombre_documento}\n❌ {str(e)}",
            jid_remitente
        )
        return False

def enviar_whatsapp_mia(mensaje, jid=None):
    try:
        destino = jid if jid else "5215581073859@s.whatsapp.net"
        if '@' not in destino:
            destino = f"{destino}@s.whatsapp.net"
            
        print(f"📤 Enviando WhatsApp a: {destino}")
            
        requests.post("http://localhost:9000/enviar", 
                     json={"jid": destino, "mensaje": mensaje}, 
                     timeout=10)
        return True
    except Exception as e:
        print(f"❌ Error enviando WhatsApp: {e}")
        return False

def validar_correspondencia(nombre_esperado, texto_documento):
    prompt = f"""Eres experto en documentación marítima mexicana y PBIP.

TIPO ESPERADO: "{nombre_esperado}"

CONTENIDO:
{texto_documento[:1500]}

Responde ÚNICAMENTE con JSON:
{{"corresponde": true/false, "razon": "breve explicación"}}"""
    
    respuesta = consultar_ollama(prompt, temperature=0.0)
    try:
        data = json.loads(respuesta)
        return data.get("corresponde", False), data.get("razon", "No se pudo determinar")
    except:
        return False, "Error al validar el documento"