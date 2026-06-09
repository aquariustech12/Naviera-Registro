import os
import re
import hashlib
import shutil
from docling.document_converter import DocumentConverter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

# === CONFIGURACIÓN ===
PATH_PDF = "biblioteca_mia/DOF_PBIP.pdf"
CHROMA_PATH = "scripts/chroma_db"
SAMPLE_FILE = "scripts/sample_fragments.txt"

# LÍMITE DURO: 800 caracteres (~200 tokens) para estar 100% seguros con nomic-embed-text
MAX_CHARS = 800
OVERLAP = 50

embeddings = OllamaEmbeddings(model="nomic-embed-text")

# ==========================================================================
# LIMPIEZA OCR
# ==========================================================================
def limpiar_ocr(texto: str) -> str:
    texto = re.sub(r'===== Page \d+ =====\s*\n?', '', texto)
    texto = re.sub(r'===== Page \d+ \[text layer\] =====\s*\n?', '', texto)
    texto = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', texto)
    
    texto = re.sub(r'([a-z])([A-Z])', r'\1 \2', texto)
    texto = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', texto)
    texto = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', texto)
    
    correcciones = {
        "Co ´digo": "Código", "Edicio ±": "Edición", "proteccio ±": "protección",
        "ORGANIZACIO ´ N MARI ´ TIMA": "ORGANIZACIÓN MARÍTIMA", "electro ±ica": "electrónica",
        "Nu ´mero": "Número", "PUBLICACIO ´ N": "PUBLICACIÓN",
        "´n": "ñ", "´ı": "í", "´a": "á", "´e": "é", "´o": "ó", "´u": "ú",
    }
    for mal, bien in correcciones.items():
        texto = texto.replace(mal, bien)
    
    texto = re.sub(r'([a-zA-Z])-\s*\n\s*([a-zA-Z])', r'\1\2', texto)
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'\n\s*\n', '\n\n', texto)
    return texto.strip()

# ==========================================================================
# CHUNKING GARANTIZADO - NUNCA EXCEDE MAX_CHARS
# ==========================================================================
def chunk_garantizado(texto: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[str]:
    """
    Divide texto en chunks garantizando que NINGUNO exceda max_chars.
    Estrategia: párrafos → oraciones → palabras
    """
    if len(texto) <= max_chars:
        return [texto]
    
    chunks = []
    parrafos = re.split(r'\n\s*\n', texto)
    
    for parrafo in parrafos:
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        
        # Caso 1: El párrafo entero cabe
        if len(parrafo) <= max_chars:
            chunks.append(parrafo)
            continue
        
        # Caso 2: Dividir por oraciones
        oraciones = re.split(r'(?<=[.!?])\s+', parrafo)
        buffer = ""
        
        for oracion in oraciones:
            oracion = oracion.strip()
            if not oracion:
                continue
            
            # Si la oración cabe en el buffer
            if len(buffer) + len(oracion) + 1 <= max_chars:
                buffer += oracion + " "
            else:
                # Guardar buffer actual
                if buffer:
                    chunks.append(buffer.strip())
                
                # Si la oración sola es más larga que max_chars, dividir por palabras
                if len(oracion) > max_chars:
                    palabras = oracion.split()
                    temp = ""
                    for palabra in palabras:
                        if len(temp) + len(palabra) + 1 <= max_chars:
                            temp += palabra + " "
                        else:
                            if temp:
                                chunks.append(temp.strip())
                            temp = palabra + " "
                    if temp:
                        buffer = temp  # Continuar con el resto
                else:
                    buffer = oracion + " "
        
        if buffer:
            chunks.append(buffer.strip())
    
    return chunks

def chunk_documentos(documentos: list[Document]) -> list[Document]:
    """Aplica chunking garantizado a todos los documentos."""
    resultado = []
    for doc in documentos:
        chunks = chunk_garantizado(doc.page_content, MAX_CHARS, OVERLAP)
        for i, chunk_texto in enumerate(chunks):
            if len(chunk_texto) > 20:
                meta = doc.metadata.copy()
                meta["chunk_index"] = i
                resultado.append(Document(page_content=chunk_texto, metadata=meta))
    return resultado

# ==========================================================================
# EXTRACCIÓN BÁSICA
# ==========================================================================
def extraer_fragmentos(texto: str) -> list[Document]:
    """Divide por headers markdown o párrafos grandes."""
    fragmentos = []
    
    # Intentar headers markdown
    partes = re.split(r'^(##\s+.+)$', texto, flags=re.MULTILINE)
    
    if len(partes) > 3:
        current_header = "Inicio"
        for parte in partes:
            if parte.startswith("##"):
                current_header = parte.replace("##", "").strip()
            elif len(parte.strip()) > 50:
                fragmentos.append(Document(
                    page_content=parte.strip(),
                    metadata={"fuente": "PBIP", "seccion": current_header}
                ))
    
    # Fallback: párrafos agrupados
    if len(fragmentos) < 2:
        parrafos = re.split(r'\n\s*\n', texto)
        current = ""
        for p in parrafos:
            if len(current) + len(p) < 3000:
                current += p + "\n\n"
            else:
                if current:
                    fragmentos.append(Document(page_content=current.strip(), metadata={"fuente": "PBIP"}))
                current = p + "\n\n"
        if current:
            fragmentos.append(Document(page_content=current.strip(), metadata={"fuente": "PBIP"}))
    
    return fragmentos

# ==========================================================================
# DEDUPLICACIÓN
# ==========================================================================
def deduplicar(fragmentos: list[Document]) -> list[Document]:
    vistos = set()
    unicos = []
    for doc in fragmentos:
        key = re.sub(r'\s+', '', doc.page_content[:150]).lower()
        if key not in vistos and len(doc.page_content) > 20:
            vistos.add(key)
            unicos.append(doc)
    return unicos

# ==========================================================================
# PROCESO PRINCIPAL
# ==========================================================================
def ejecutar():
    print("🚀 Extrayendo PDF...")
    converter = DocumentConverter()
    result = converter.convert(PATH_PDF)
    texto = result.document.export_to_markdown()
    
    print("🧹 Limpiando OCR...")
    texto = limpiar_ocr(texto)
    print(f"Texto total: {len(texto)} caracteres")
    
    print("📚 Extrayendo estructura...")
    fragmentos = extraer_fragmentos(texto)
    print(f"Fragmentos iniciales: {len(fragmentos)}")
    
    print(f"✂️ Chunking garantizado (max {MAX_CHARS} chars)...")
    chunks = chunk_documentos(fragmentos)
    print(f"Chunks: {len(chunks)}")
    
    print("🔄 Deduplicando...")
    chunks = deduplicar(chunks)
    print(f"Únicos: {len(chunks)}")
    
    # VALIDACIÓN Estricta
    longitudes = [len(c.page_content) for c in chunks]
    if longitudes:
        max_len = max(longitudes)
        print(f"📊 Stats: min={min(longitudes)}, max={max_len}, avg={sum(longitudes)//len(longitudes)}")
        
        # Si aún hay chunks grandes, forzar corte
        if max_len > MAX_CHARS:
            print(f"⚠️ Forzando recorte de {max_len} a {MAX_CHARS}...")
            chunks = [Document(
                page_content=c.page_content[:MAX_CHARS],
                metadata=c.metadata
            ) for c in chunks]
    
    if not chunks:
        print("❌ Error: no hay chunks")
        return
    
    # Guardar muestra
    with open(SAMPLE_FILE, "w", encoding="utf-8") as f:
        for i, c in enumerate(chunks[:20]):
            f.write(f"=== {i} | {len(c.page_content)} chars ===\n{c.page_content[:400]}\n\n")
    
    print(f"📦 Guardando en Chroma...")
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
    
    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PATH,
        collection_name="auditoria_pbip"
    )
    print(f"✅ {len(chunks)} chunks guardados correctamente")

if __name__ == "__main__":
    ejecutar()