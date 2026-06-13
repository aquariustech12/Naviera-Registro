# portal_cliente/mia_herramientas.py
import os
import re
import json
import shutil
import requests
import numpy as np
from datetime import datetime

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# BM25 para búsqueda híbrida
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("⚠️ rank-bm25 no instalado. Ejecuta: pip install rank-bm25")

# OCR
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from PIL import Image
import pdfplumber

# Django models
from naviera_registro.models import Naviera, Buque, RequisitoBuque, PuntoPBIP, DocumentoEntregable, AnalisisMIA

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CHROMA_PATH = "/home/julian/Naviera-Registro/scripts/chroma_db"
COLLECTION_NAME = "auditoria_pbip"

print(f"--- MIA HERRAMIENTAS INICIANDO ---")
print(f"OCR: {'✅' if OCR_AVAILABLE else '❌'}")
print(f"DOCX: {'✅' if DOCX_AVAILABLE else '❌'}")
print(f"BM25: {'✅' if BM25_AVAILABLE else '❌'}")

embeddings = OllamaEmbeddings(model="nomic-embed-text")

# ============================================================================
# INICIALIZACIÓN DE CHROMA + ÍNDICE BM25 (caché global)
# ============================================================================

vector_db = None
_bm25_index = None
_corpus_texts = None
_corpus_metadatas = None

def _inicializar_chroma():
    """Inicializa Chroma y construye índice BM25 en memoria."""
    global vector_db, _bm25_index, _corpus_texts, _corpus_metadatas

    try:
        vector_db = Chroma(
            persist_directory=CHROMA_PATH,
            embedding_function=embeddings,
            collection_name=COLLECTION_NAME
        )
        count = vector_db._collection.count()
        print(f"✅ Base PBIP: {count} documentos")

        # Construir índice BM25
        if BM25_AVAILABLE and count > 0:
            _construir_bm25()

    except Exception as e:
        print(f"❌ ERROR Chroma: {e}")
        vector_db = None


def _construir_bm25():
    """Construye el índice BM25 desde Chroma. Se ejecuta una sola vez."""
    global _bm25_index, _corpus_texts, _corpus_metadatas

    if _bm25_index is not None:
        return

    if vector_db is None:
        return

    try:
        all_docs = vector_db.get()
        _corpus_texts = all_docs['documents']
        _corpus_metadatas = all_docs['metadatas']

        tokenized = [re.findall(r'\b\w+\b', doc.lower()) for doc in _corpus_texts]
        _bm25_index = BM25Okapi(tokenized)

        print(f"✅ Índice BM25 construido: {len(_corpus_texts)} documentos")
    except Exception as e:
        print(f"❌ Error construyendo BM25: {e}")
        _bm25_index = None


# Inicializar al cargar el módulo
_inicializar_chroma()


# ============================================================================
# MOTOR DE BÚSQUEDA HÍBRIDA (BM25 + SEMÁNTICO + RERANK)
# ============================================================================

def _tokenize(text: str) -> list:
    return re.findall(r'\b\w+\b', text.lower())


def _cosine_similarity(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def _buscar_bm25(query: str, k: int = 15, parte: str = None) -> list:
    """Búsqueda pura BM25. Ideal para definiciones, números exactos, términos técnicos."""
    if _bm25_index is None or _corpus_texts is None:
        return []

    tokenized_query = _tokenize(query)
    scores = _bm25_index.get_scores(tokenized_query)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    results = []
    for idx, score in ranked:
        meta = _corpus_metadatas[idx]
        if parte and meta.get('parte') != parte:
            continue
        results.append({
            'text': _corpus_texts[idx],
            'metadata': meta,
            'bm25_score': float(score),
            'index': idx
        })
        if len(results) >= k:
            break
    return results


def _rerank_semantico(query: str, candidatos: list, k_final: int = 5) -> list:
    """Re-ranquea candidatos BM25 usando embeddings semánticos."""
    if not candidatos:
        return []

    texts = [c['text'] for c in candidatos]
    query_emb = embeddings.embed_query(query)
    doc_embs = embeddings.embed_documents(texts)

    max_bm25 = max(c['bm25_score'] for c in candidatos) or 1.0

    for i, cand in enumerate(candidatos):
        sem_score = _cosine_similarity(query_emb, doc_embs[i])
        bm25_norm = cand['bm25_score'] / max_bm25

        cand['semantic_score'] = sem_score
        cand['final_score'] = 0.6 * bm25_norm + 0.4 * sem_score

    candidatos.sort(key=lambda x: x['final_score'], reverse=True)
    return candidatos[:k_final]


def _detectar_estrategia(query: str) -> str:
    """
    Detecta la mejor estrategia según el tipo de consulta.
    - 'bm25': definiciones, números exactos, términos técnicos específicos
    - 'rerank': procedimientos, medidas, planes, obligaciones
    - 'semantico': conceptos vagos, preguntas abiertas
    """
    q = query.lower()

    exactas = ['arqueo', 'tonelaje', '500', 'eslora', 'definición', 'ámbito',
               'aplica', 'cuál', 'cuáles', 'qué es', 'tipos de', 'artículo',
               'sección', 'capítulo', 'número', 'fecha', 'omi', 'imo', 'gt', 'dw',
               'toneladas', 'metros', 'pies', 'longitud', 'manga', 'calado']

    procedimientos = ['cómo', 'procedimiento', 'medida', 'paso', 'debe', 'deberá',
                      'obligación', 'nivel de protección', 'plan de protección',
                      'evaluación', 'control', 'acceso', 'registro', 'oficial',
                      'declaración', 'certificado', 'inspección', 'auditoría',
                      'riesgo', 'amenaza', 'vulnerabilidad', 'mitigación']

    score_exacta = sum(1 for w in exactas if w in q)
    score_proc = sum(1 for w in procedimientos if w in q)

    if score_exacta > score_proc:
        return 'bm25'
    elif score_proc > 0:
        return 'rerank'
    else:
        return 'semantico'


def buscar_pbip_hibrido(query: str, k: int = 5, parte: str = None,
                        estrategia: str = 'auto') -> list[dict]:
    """
    Motor de búsqueda híbrida completa.

    Args:
        query: Texto de búsqueda
        k: Número de resultados finales
        parte: Filtrar por 'A' o 'B' (None = ambas)
        estrategia: 'auto', 'bm25', 'semantico', 'rerank'

    Returns:
        Lista de dicts con 'text', 'metadata', scores
    """
    if vector_db is None:
        return []

    if estrategia == 'auto':
        estrategia = _detectar_estrategia(query)

    if estrategia == 'bm25':
        results = _buscar_bm25(query, k=k, parte=parte)
        for r in results:
            r['final_score'] = r['bm25_score']
        return results

    elif estrategia == 'semantico':
        filter_dict = {'parte': parte} if parte else None
        docs = vector_db.similarity_search(query, k=k, filter=filter_dict)
        return [{
            'text': doc.page_content,
            'metadata': doc.metadata,
            'bm25_score': 0.0,
            'semantic_score': 0.0,
            'final_score': 0.0
        } for doc in docs]

    elif estrategia == 'rerank':
        candidatos = _buscar_bm25(query, k=15, parte=parte)
        return _rerank_semantico(query, candidatos, k_final=k)

    return []


# ============================================================================
# LLM (Ollama)
# ============================================================================

def consultar_ollama(prompt: str, temperature: float = 0.2, num_ctx: int = 16384) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen3.5:latest",
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": num_ctx, "temperature": temperature, "num_gpu": 99}
    }
    try:
        r = requests.post(url, json=payload, timeout=300)
        return r.json().get('response', 'Sin respuesta')
    except Exception as e:
        return f"Error IA: {e}"


# ============================================================================
# EXTRACCIÓN DE TEXTO UNIVERSAL
# ============================================================================

def extraer_texto_universal(ruta_archivo: str) -> str:
    if not os.path.exists(ruta_archivo):
        return "Error: El archivo no existe."

    extension = os.path.splitext(ruta_archivo)[1].lower()
    texto_extraido = ""

    try:
        if extension == '.docx' and DOCX_AVAILABLE:
            print(f"📝 Word: {os.path.basename(ruta_archivo)}")
            doc = DocxDocument(ruta_archivo)
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
# HERRAMIENTA CONSULTAR PBIP (VERSIÓN HÍBRIDA)
# ============================================================================

def herramienta_consultar_pbip(tema: str, k: int = 5, parte: str = None) -> str:
    """
    Consulta el Código PBIP usando búsqueda híbrida (BM25 + semántico + rerank).
    Esta función es usada por:
      - mia_core.py (consultas del auditor por WhatsApp)
      - mia_documentos.py (análisis de documentos subidos por navieras)
    """
    try:
        resultados = buscar_pbip_hibrido(tema, k=k, parte=parte, estrategia='auto')

        if not resultados:
            return f"No encontré información sobre '{tema}' en el código PBIP."

        lineas = []
        for r in resultados:
            meta = r['metadata']
            seccion = meta.get('seccion', 'PBIP')
            parte_doc = meta.get('parte', '')
            frag = " [FRAGMENTO]" if meta.get('es_fragmento') else ""

            ref = f"Parte {parte_doc} | {seccion}{frag}"
            if r.get('final_score', 0) > 0:
                ref += f" (relevancia: {r['final_score']:.2f})"

            contenido = r['text'][:1200] if len(r['text']) > 600 else r['text']
            lineas.append(f"[{ref}]\n{contenido}")

        return "\n\n---\n\n".join(lineas)

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
    total_admin = 6

    lineas = ["🤖 *MIA - ESTADO GLOBAL*\n"]

    for buque in buques:
        pbip_subidos = RequisitoBuque.objects.filter(
            buque=buque, 
            categoria='DOCUMENTAL'
        ).count()
        pct_pbip = int((pbip_subidos / total_pbip) * 100) if total_pbip else 0

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

    try:
        requests.post(
            "http://localhost:9000/enviar",
            json={"jid": jid, "mensaje": mensaje},
            timeout=10
        )
    except:
        pass

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