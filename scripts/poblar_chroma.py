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
    
    # --- LIMPIEZA DE TEXTO (Lo que te faltaba) ---
    for p in paginas:
        # Quitamos la marca de agua/licencia que marea al buscador
        p.page_content = p.page_content.replace("Licensed to Global Maritime Protection for 1 copy. © IMO", "")
        p.page_content = p.page_content.replace("Licensed to Global Maritime Protection for 1 copy. IMO", "")
        # Opcional: Limpiar saltos de línea raros que el OCR viejo mete a mitad de palabra
        p.page_content = p.page_content.replace("-\n", "") 
    # --------------------------------------------

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,        # Más pequeño para que la respuesta sea más precisa
        chunk_overlap=100,
        separators=[
            "Regla",            # Que corte donde vea la palabra Regla
            "Sección", 
            "SECCIÓN",
            "PARTE", 
            "\n\n", 
            "\n"
        ]
    )
    
    # Ahora pasamos las 'paginas' ya limpias al splitter
    chunks = text_splitter.split_documents(paginas)
    
    for chunk in chunks:
        chunk.metadata["documento"] = nombre_doc
        chunk.metadata["prioridad"] = 1 if "CODIGO" in nombre_doc.upper() else 2
    
    vector_db.add_documents(chunks)
    print(f"✅ {nombre_doc} indexado con {len(chunks)} pedazos.")

if __name__ == "__main__":
    # Usamos la ruta relativa subiendo un nivel desde la carpeta scripts
    indexar_biblia_maritima("../biblioteca_mia/CODIGO PBIP GMP_unlocked.pdf", "Código Internacional PBIP")
