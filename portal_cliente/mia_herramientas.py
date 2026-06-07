# portal_cliente/mia_herramientas.py
import os
import re
import json
import requests
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

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from PIL import Image
import pdfplumber

# Django models
from naviera_registro.models import Naviera, Buque, RequisitoBuque, PuntoPBIP, AnalisisMIA

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CHROMA_PATH = "/home/julian/Naviera-Registro/scripts/chroma_db"

print(f"--- MIA HERRAMIENTAS INICIANDO ---")
print(f"OCR: {'✅' if OCR_AVAILABLE else '❌'}")
print(f"DOCX: {'✅' if DOCX_AVAILABLE else '❌'}")

embeddings = OllamaEmbeddings(model="nomic-embed-text")

try:
    vector_db = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name="auditoria_pbip"
    )
    count = vector_db._collection.count()
    print(f"✅ Base PBIP: {count} documentos")
except Exception as e:
    print(f"❌ ERROR Chroma: {e}")
    vector_db = None


# ============================================================================
# LLM (Ollama)
# ============================================================================

def consultar_ollama(prompt: str, temperature: float = 0.2, num_ctx: int = 16384) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:14b",
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": num_ctx, "temperature": temperature}
    }
    try:
        r = requests.post(url, json=payload, timeout=300)
        return r.json().get('response', 'Sin respuesta')
    except Exception as e:
        return f"Error IA: {e}"


# ============================================================================
# EXTRACCIÓN DE TEXTO (de agente_mia.py)
# ============================================================================

def extraer_texto_universal(ruta_archivo: str) -> str:
    if not os.path.exists(ruta_archivo):
        return "Error: El archivo no existe."

    extension = os.path.splitext(ruta_archivo)[1].lower()
    texto_extraido = ""

    try:
        if extension == '.docx' and DOCX_AVAILABLE:
            print(f"📝 Word: {os.path.basename(ruta_archivo)}")
            doc = Document(ruta_archivo)
            parrafos = [p.text for p in doc.paragraphs if p.text]
            texto_extraido = "\n".join(parrafos)
            for tabla in doc.tables:
                for fila in tabla.rows:
                    for celda in fila.cells:
                        if celda.text.strip():
                            texto_extraido += f"\n{celda.text.strip()}"

        elif extension in ['.jpg', '.jpeg', '.png']:
            print(f"📷 Imagen: {os.path.basename(ruta_archivo)}")
            if OCR_AVAILABLE:
                imagen = Image.open(ruta_archivo)
                texto_extraido = pytesseract.image_to_string(imagen, lang='spa')
            else:
                return "Error: OCR no disponible."

        elif extension == '.pdf':
            print(f"📄 PDF: {os.path.basename(ruta_archivo)}")
            with pdfplumber.open(ruta_archivo) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        texto_extraido += page_text + "\n"
            
            if len(texto_extraido.strip()) < 200 and OCR_AVAILABLE:
                print("📷 PDF plano, aplicando OCR...")
                paginas = convert_from_path(ruta_archivo)
                texto_ocr = ""
                for img in paginas:
                    texto_ocr += pytesseract.image_to_string(img, lang='spa') + "\n"
                texto_extraido = texto_ocr

        else:
            return f"Error: Formato {extension} no soportado."

        if len(texto_extraido.strip()) > 10:
            return texto_extraido
        else:
            return "Error: No se extrajo texto suficiente."

    except Exception as e:
        return f"Error interno: {str(e)}"


# ============================================================================
# CHROMA / PBIP
# ============================================================================

def herramienta_consultar_pbip(tema: str, k: int = 5) -> str:
    if vector_db is None:
        return "Base PBIP no disponible"
    
    try:
        docs = vector_db.similarity_search(tema, k=k)
        if not docs:
            return f"No encontré información sobre '{tema}' en el código PBIP."
        
        resultados = []
        for doc in docs:
            meta = doc.metadata
            ref = f"{meta.get('seccion', 'PBIP')}"
            if meta.get('articulo'):
                ref += f", {meta['articulo']}"
            resultados.append(f"[{ref}]\n{doc.page_content[:800]}")
        
        return "\n---\n".join(resultados)
    except Exception as e:
        return f"Error consultando PBIP: {e}"


# ============================================================================
# DJANGO ORM - ESTADO DE EXPEDIENTES
# ============================================================================

def herramienta_consultar_estado(naviera_nombre: str = None, buque_nombre: str = None, omi: str = None) -> str:
    try:
        if omi:
            try:
                b = Buque.objects.get(OMI=omi)
                return _formato_buque(b)
            except Buque.DoesNotExist:
                return f"❌ No encontré buque con OMI: {omi}"

        if buque_nombre:
            buques = Buque.objects.filter(nombre_buque__icontains=buque_nombre)
            if buques.count() == 1:
                return _formato_buque(buques.first())
            elif buques.count() > 1:
                return f"⚠️ {buques.count()} buques coinciden:\n" + "\n".join([f"• {b.nombre_buque} (OMI:{b.OMI})" for b in buques[:5]])

        if naviera_nombre:
            navieras = Naviera.objects.filter(nombre_empresa__icontains=naviera_nombre)
            if navieras.count() == 1:
                return _formato_naviera(navieras.first())
            elif navieras.count() > 1:
                return f"⚠️ {navieras.count()} navieras:\n" + "\n".join([f"• {n.nombre_empresa}" for n in navieras[:5]])

        return "Especifica naviera, buque u OMI."

    except Exception as e:
        return f"Error consultando estado: {e}"


def _formato_buque(buque) -> str:
    total_pbip = PuntoPBIP.objects.count()
    pbip_subidos = RequisitoBuque.objects.filter(buque=buque, categoria='DOCUMENTAL').count()
    pct = int((pbip_subidos / total_pbip) * 100) if total_pbip else 0
    
    return f"""🚢 *{buque.nombre_buque}*
📋 OMI: {buque.OMI}
🏢 {buque.naviera.nombre_empresa}
📊 PBIP: {pbip_subidos}/{total_pbip} ({pct}%)"""


def _formato_naviera(naviera) -> str:
    buques = Buque.objects.filter(naviera=naviera)
    lineas = [f"🏢 *{naviera.nombre_empresa}*\n🚢 Buques: {buques.count()}"]
    
    total_pbip = PuntoPBIP.objects.count()
    for b in buques:
        pbip_subidos = RequisitoBuque.objects.filter(buque=b, categoria='DOCUMENTAL').count()
        pct = int((pbip_subidos / total_pbip) * 100) if total_pbip else 0
        lineas.append(f"• {b.nombre_buque} (OMI:{b.OMI}): {pct}%")
    
    return "\n".join(lineas)

def herramienta_reporte_global() -> str:
    buques = Buque.objects.all()
    total_pbip = PuntoPBIP.objects.count()
    total_admin = 6  # Acta, Poder, INE, SAT, Estado Cuenta, Directorio
    
    lineas = ["🤖 *MIA - ESTADO GLOBAL*\n"]
    
    for buque in buques:
        # PBIP por buque
        pbip_subidos = RequisitoBuque.objects.filter(
            buque=buque, 
            categoria='DOCUMENTAL'
        ).count()
        pct_pbip = int((pbip_subidos / total_pbip) * 100) if total_pbip else 0
        
        # Admin por naviera (solo una vez por naviera, no por buque)
        naviera = buque.naviera
        admin_subidos = RequisitoBuque.objects.filter(
            naviera=naviera,
            buque__isnull=True,
            categoria='ADMINISTRATIVO'
        ).count()
        pct_admin = int((admin_subidos / total_admin) * 100)
        
        estado_pbip = "✅" if pct_pbip == 100 else f"{pct_pbip}%"
        estado_admin = "✅" if pct_admin == 100 else f"{pct_admin}%"
        
        lineas.append(
            f"• {buque.nombre_buque[:20]} (OMI:{buque.OMI})\n"
            f"  📊 PBIP: {estado_pbip} | 🏢 Admin: {estado_admin}"
        )
    
    # Resumen por naviera
    lineas.append("\n🏢 *RESUMEN POR NAVIERA:*")
    navieras = Naviera.objects.all()
    for nav in navieras:
        admin_count = RequisitoBuque.objects.filter(
            naviera=nav,
            buque__isnull=True,
            categoria='ADMINISTRATIVO'
        ).count()
        buques_nav = Buque.objects.filter(naviera=nav)
        pbip_total = sum(
            RequisitoBuque.objects.filter(buque=b, categoria='DOCUMENTAL').count()
            for b in buques_nav
        )
        lineas.append(
            f"• {nav.nombre_empresa[:25]}: "
            f"Admin {admin_count}/6 | PBIP {pbip_total}/{total_pbip * buques_nav.count()}"
        )
    
    lineas.append(f"\n_Total: {buques.count()} buques | {navieras.count()} navieras_")
    return "\n".join(lineas)

# ============================================================================
# WHATSAPP
# ============================================================================

def enviar_whatsapp_jid(jid: str, mensaje: str) -> bool:
    if '@' not in jid:
        jid = f"{jid}@s.whatsapp.net"
    
    # Fire and forget - no esperar respuesta
    try:
        requests.post(
            "http://localhost:9000/enviar",
            json={"jid": jid, "mensaje": mensaje},
            timeout=10  # Muy corto, solo enviar
        )
    except:
        pass  # No importa si falla
    
    return True

def enviar_whatsapp_numero(numero: str, mensaje: str) -> bool:
    try:
        requests.post(
            "http://localhost:9000/enviar",
            json={"numero": numero, "mensaje": mensaje},
            timeout=10
        )
        return True
    except Exception as e:
        print(f"❌ Error WhatsApp: {e}")
        return False