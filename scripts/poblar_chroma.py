import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

# 1. Configuración de MIA (Cerebro)
embeddings = OllamaEmbeddings(model="nomic-embed-text") # O el que prefieras
vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

def indexar_biblia_maritima(ruta_pdf, nombre_doc):
    print(f"🚢 Procesando {nombre_doc}...")
    loader = PyPDFLoader(ruta_pdf)
    paginas = loader.load()
    texto_completo = "\n".join([p.page_content for p in paginas])
    
    # 1. Splitter de estructura
    headers_to_split_on = [
        ("SECCIÓN", "Header 1"),
        ("PARTE", "Header 2"),
        ("Regla", "Header 3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    chunks_iniciales = markdown_splitter.split_text(texto_completo)
    
    # 2. Splitter de seguridad para no saturar Ollama (máximo 2000 chars)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000, 
        chunk_overlap=200
    )
    
    # Aplicamos el segundo corte a los resultados del primero
    chunks_finales = text_splitter.split_documents(chunks_iniciales)
    
    for chunk in chunks_finales:
        chunk.metadata["documento"] = nombre_doc
        chunk.metadata["tipo"] = "Referencia Normativa"
    
    vector_db.add_documents(chunks_finales)
    print(f"✅ {nombre_doc} indexado con {len(chunks_finales)} pedazos.")

if __name__ == "__main__":
    # Usamos la ruta relativa subiendo un nivel desde la carpeta scripts
    indexar_biblia_maritima("../biblioteca_mia/CODIGO PBIP GMP_unlocked.pdf", "Código Internacional PBIP")
    indexar_biblia_maritima("../biblioteca_mia/GUIA PROTECCION MARITIMA IENPAC_unlocked.pdf", "Guía de Protección Marítima IENPAC")
