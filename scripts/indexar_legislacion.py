#!/usr/bin/env python3
"""
INDEXADOR DE LEGISLACIÓN NACIONAL MEXICANA
- Procesa LNCM, LOAPF, Reglamento Interior SEMAR, Circular OMI 1074 y Guía de Protección Marítima.
- Divide cada documento en fragmentos por artículo/sección.
- Guarda en colección "legislacion_mexicana" en ChromaDB.
- NO TOCA el PBIP (ya indexado en "auditoria_pbip").
"""

import os
import re
import shutil
from pathlib import Path
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ============================================================
# CONFIGURACIÓN
# ============================================================
TXT_DIR = "biblioteca_mia"
CHROMA_PATH = "scripts/chroma_db"
COLLECTION_NAME = "legislacion_mexicana"  # Nueva colección
MAX_CHUNK_SIZE = 1500  # Reducido para evitar exceder el contexto de Ollama
OVERLAP = 200

embeddings = OllamaEmbeddings(model="nomic-embed-text")

# ============================================================
# DETECCIÓN DE TIPO DE DOCUMENTO POR NOMBRE DE ARCHIVO
# ============================================================
def detectar_tipo_documento(nombre_archivo: str) -> dict:
    """
    Devuelve un dict con:
        - tipo: str (ley, reglamento, circular, guia)
        - fuente: str (nombre para metadatos)
        - patron_division: str (expresión regular para separar artículos/secciones)
        - campo_metadato: str (nombre del campo donde guardar el número)
    """
    nombre = nombre_archivo.upper()
    
    if "LNCM" in nombre or "NAVEGACION" in nombre:
        return {
            "tipo": "ley",
            "fuente": "Ley de Navegación y Comercio Marítimos",
            "patron_division": r"(?=Artículo\s+\d+[\.\-]?\s*)",
            "campo_metadato": "articulo"
        }
    elif "LOAPF" in nombre or "ORGANICA" in nombre:
        return {
            "tipo": "ley",
            "fuente": "Ley Orgánica de la Administración Pública Federal",
            "patron_division": r"(?=Artículo\s+\d+[\.\-]?\s*)",
            "campo_metadato": "articulo"
        }
    elif "REGLAMENTO" in nombre or "RISEMAR" in nombre:
        return {
            "tipo": "reglamento",
            "fuente": "Reglamento Interior de la Secretaría de Marina",
            "patron_division": r"(?=Artículo\s+\d+[\.\-]?\s*)",
            "campo_metadato": "articulo"
        }
    elif "CIRCULAR" in nombre or "1074" in nombre:
        return {
            "tipo": "circular",
            "fuente": "MSC.1/Circ.1074 - Directrices para OPR",
            "patron_division": r"(?=\.\d+\s+|\d+\.\s+)",
            "campo_metadato": "seccion"
        }
    elif "GUIA" in nombre or "PROTECCION" in nombre or "PROTECCIÓN" in nombre:
        return {
            "tipo": "guia",
            "fuente": "Guía sobre Protección Marítima y el Código PBIP",
            "patron_division": r"(?=Sección\s+\d+[\.\-]?\s*)",
            "campo_metadato": "seccion"
        }
    else:
        return None

# ============================================================
# EXTRACCIÓN DE NÚMERO DE ARTÍCULO/SECCIÓN DESDE EL TEXTO
# ============================================================
def extraer_numero(texto: str, campo: str) -> str:
    """Extrae el número del artículo/sección de la primera línea del fragmento."""
    if campo == "articulo":
        match = re.search(r"Artículo\s+(\d+)", texto, re.IGNORECASE)
        return match.group(1) if match else "sin_numero"
    elif campo == "seccion":
        match = re.search(r"Sección\s+(\d+)", texto, re.IGNORECASE)
        return match.group(1) if match else "sin_numero"
    else:
        # Para circular, buscar números como "1.1" o "3.2"
        match = re.search(r"^\.?\s*(\d+\.\d+)\s+", texto)
        return match.group(1) if match else "sin_numero"

# ============================================================
# PROCESADOR PRINCIPAL
# ============================================================
def procesar_archivo(ruta: str) -> list:
    nombre_archivo = Path(ruta).name
    info = detectar_tipo_documento(nombre_archivo)
    if not info:
        print(f"⚠️  Tipo no reconocido: {nombre_archivo} - se usará división genérica")
        # División genérica por párrafos
        with open(ruta, 'r', encoding='utf-8') as f:
            texto = f.read()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=MAX_CHUNK_SIZE,
            chunk_overlap=OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        docs = splitter.split_documents([Document(page_content=texto, metadata={"fuente": nombre_archivo})])
        for d in docs:
            d.metadata["tipo"] = "generico"
            # Validar tamaño
            if len(d.page_content) > 3000:
                print(f"   ⚠️  Fragmento demasiado largo: {len(d.page_content)} chars, dividiendo")
        return docs

    with open(ruta, 'r', encoding='utf-8') as f:
        texto = f.read()

    # Dividir usando el patrón específico
    partes = re.split(info["patron_division"], texto)
    # El primer elemento puede ser basura (preámbulo), así que lo descartamos
    if partes and not re.match(r"Artículo|Sección|\.\d+", partes[0].strip()):
        partes = partes[1:]

    chunks = []
    for fragmento in partes:
        fragmento = fragmento.strip()
        if not fragmento or len(fragmento) < 20:
            continue
        
        # Extraer número de artículo/sección
        numero = extraer_numero(fragmento, info["campo_metadato"])
        
        # Crear documento
        doc = Document(
            page_content=fragmento,
            metadata={
                "fuente": info["fuente"],
                "tipo": info["tipo"],
                info["campo_metadato"]: numero,
                "archivo_original": nombre_archivo,
            }
        )
        chunks.append(doc)

    return chunks

# ============================================================
# MAIN
# ============================================================
def main():
    print("🚀 INICIANDO INDEXACIÓN DE LEGISLACIÓN NACIONAL")
    print("📂 Leyendo archivos desde:", TXT_DIR)

    todos_chunks = []
    archivos_procesados = []

    for archivo in os.listdir(TXT_DIR):
        if not archivo.endswith(".txt"):
            continue
        # Saltar el PBIP (ya indexado)
        if "BOE-A-2004-15290_Codigo_PBIP" in archivo:
            print(f"⏩ Saltando PBIP: {archivo}")
            continue

        ruta_completa = os.path.join(TXT_DIR, archivo)
        print(f"📄 Procesando: {archivo}")
        chunks = procesar_archivo(ruta_completa)
        # Filtrar fragmentos que aún superen el límite práctico (3000 caracteres)
        chunks_filtrados = []
        for chunk in chunks:
            if len(chunk.page_content) > 3000:
                print(f"   ⚠️  Fragmento de {len(chunk.page_content)} chars, subdividiendo...")
                # Subdividir con el splitter genérico
                sub_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=100,
                    separators=["\n\n", "\n", ". ", " ", ""]
                )
                subdocs = sub_splitter.split_documents([chunk])
                for sub in subdocs:
                    sub.metadata["es_subfragmento"] = True
                    chunks_filtrados.append(sub)
            else:
                chunks_filtrados.append(chunk)
        
        if chunks_filtrados:
            todos_chunks.extend(chunks_filtrados)
            archivos_procesados.append(archivo)
            print(f"   → {len(chunks_filtrados)} fragmentos generados")
        else:
            print(f"   ⚠️  No se generaron fragmentos")

    if not todos_chunks:
        print("❌ No se encontraron documentos para indexar.")
        return

    print(f"\n🧩 Total de fragmentos: {len(todos_chunks)}")

    # Eliminar colección anterior si existe para evitar duplicados
    collection_path = os.path.join(CHROMA_PATH, COLLECTION_NAME)
    if os.path.exists(collection_path):
        print(f"🗑️  Eliminando colección anterior: {COLLECTION_NAME}")
        shutil.rmtree(collection_path)

    print("💾 Guardando en ChromaDB...")
    db = Chroma.from_documents(
        todos_chunks,
        embeddings,
        persist_directory=CHROMA_PATH,
        collection_name=COLLECTION_NAME
    )
    print(f"✅ Indexación completada. {db._collection.count()} vectores guardados.")
    print(f"📚 Archivos indexados: {', '.join(archivos_procesados)}")

if __name__ == "__main__":
    main()