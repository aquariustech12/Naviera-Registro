import os
import re
from docling.document_converter import DocumentConverter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

# 1. Configuración
PATH_PDF = "../biblioteca_mia/CODIGO PBIP GMP_unlocked.pdf"
CHROMA_PATH = "./chroma_db"
embeddings = OllamaEmbeddings(model="nomic-embed-text")

def limpiar_basura_omi(text):
    # Limpieza global de ruido de escaneo
    text = re.sub(r"(?i)licensed to.*?imo", "", text)
    text = re.sub(r"Global Maritime Protection", "", text)
    # Normalización de caracteres OCR (global para todo el libro)
    text = text.replace("´n", "ñ").replace("´ı", "i").replace("´a", "a").replace("´e", "e").replace("´o", "o").replace("´u", "u")
    return text

def ejecutar_ingesta_pro():
    print("🚀 Docling analizando estructura visual...")
    converter = DocumentConverter()
    result = converter.convert(PATH_PDF)
    markdown_limpio = limpiar_basura_omi(result.document.export_to_markdown())
    
    # PASO 1: Separar por Secciones Reales (H2, H3 del Markdown)
    headers_to_split = [("#", "Parte"), ("##", "Seccion")]
    h_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split)
    secciones = h_splitter.split_text(markdown_limpio)
    
    # PASO 2: Sub-dividir secciones largas para que Ollama no explote (Evita el Error 400)
    # Usamos 2000 caracteres para ir a la segura con el contexto del modelo
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
    
    chunks_finales = []
    for sec in secciones:
        # Extraemos el nombre de la sección para que cada pedacito lo lleve
        nombre_seccion = sec.metadata.get("Seccion", "General")
        sub_chunks = text_splitter.split_documents([sec])
        
        for sub in sub_chunks:
            # Enriquecemos cada trozo con su contexto legal original
            sub.metadata["seccion_legal"] = nombre_seccion
            sub.metadata["fuente"] = "Código Internacional PBIP"
            chunks_finales.append(sub)

    print(f"📦 Guardando {len(chunks_finales)} fragmentos legales estructurados...")
    
    if os.path.exists(CHROMA_PATH):
        import shutil
        shutil.rmtree(CHROMA_PATH)
        
    vector_db = Chroma.from_documents(
        documents=chunks_finales, 
        embedding=embeddings, 
        persist_directory=CHROMA_PATH
    )
    print("✅ MIA ya tiene el cerebro marítimo completo y estructurado.")

if __name__ == "__main__":
    ejecutar_ingesta_pro()