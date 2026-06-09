#!/usr/bin/env python3
import os
import re
import shutil
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

TXT_PATH = "biblioteca_mia/BOE-A-2004-15290_Codigo_PBIP.txt"
CHROMA_PATH = "scripts/chroma_db"
COLLECTION_NAME = "auditoria_pbip"

embeddings = OllamaEmbeddings(model="nomic-embed-text")

def limpiar_linea(linea):
    if 'https://www.boe.es' in linea:
        return None
    if re.match(r'^\s*\d+/\d+/\d+', linea):
        return None
    if re.match(r'^\s*\d+\s*$', linea):
        return None
    if 'BOE-A-2004-15290' in linea:
        return None
    if 'Página' in linea and 'BOE' in linea:
        return None
    return linea.strip()

print("📖 Leyendo TXT...")
with open(TXT_PATH, 'r', encoding='utf-8') as f:
    lineas_raw = f.readlines()

lineas_limpias = [limpiar_linea(l) for l in lineas_raw]
lineas_limpias = [l for l in lineas_limpias if l]
texto = '\n'.join(lineas_limpias)

# ========== ENCONTRAR EL ANEXO ==========
anexo_match = re.search(
    r'ANEXO\s+CÓDIGO\s+INTERNACIONAL.*',
    texto,
    re.DOTALL | re.IGNORECASE
)

if anexo_match:
    anexo_texto = anexo_match.group(0)
    print(f"✅ Anexo: {len(anexo_texto)} caracteres")
else:
    raise ValueError("No se encontró el anexo")

# ========== SEPARAR PREÁMBULO, PARTE A Y PARTE B ==========
# Buscar posiciones exactas de "Parte A" y "Parte B" como líneas independientes
# El preámbulo del anexo termina donde empieza "Parte A"

# Encontrar todas las ocurrencias de "Parte A" y "Parte B" como palabras completas en líneas
pos_parte_a = None
pos_parte_b = None

for m in re.finditer(r'^Parte\s+A\s*$', anexo_texto, re.MULTILINE | re.IGNORECASE):
    pos_parte_a = m.start()
    print(f"   'Parte A' encontrado en posición {pos_parte_a}")
    break  # Primera ocurrencia

for m in re.finditer(r'^Parte\s+B\s*$', anexo_texto, re.MULTILINE | re.IGNORECASE):
    pos_parte_b = m.start()
    print(f"   'Parte B' encontrado en posición {pos_parte_b}")
    break  # Primera ocurrencia

if pos_parte_a is None:
    raise ValueError("No se encontró 'Parte A' en el anexo")
if pos_parte_b is None:
    raise ValueError("No se encontró 'Parte B' en el anexo")

# Extraer partes
preambulo = anexo_texto[:pos_parte_a].strip()
parte_a = anexo_texto[pos_parte_a:pos_parte_b].strip()
parte_b = anexo_texto[pos_parte_b:].strip()

print(f"\n✅ Preámbulo del anexo: {len(preambulo)} caracteres")
print(f"✅ Parte A: {len(parte_a)} caracteres")
print(f"✅ Parte B: {len(parte_b)} caracteres")

partes = {'A': parte_a, 'B': parte_b}

# ========== PROCESAR CADA PARTE ==========
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=4000,
    chunk_overlap=500,
    separators=["\n\n", "\n", ". ", " ", ""],
    length_function=len,
)

chunks = []
chunk_global_id = 0

for parte_nombre, parte_texto in partes.items():
    print(f"\n📑 Procesando Parte {parte_nombre}...")
    
    # ========== LIMPIAR RESIDUOS DEL PREÁMBULO ==========
    # Buscar el inicio real de las secciones del código
    # Parte A: "1. Generalidades", Parte B: "1. Introducción"
    inicio_real = None
    
    for patron in [r'\n1\.\s+Generalidades', r'\n1\.\s+Introducción']:
        match = re.search(patron, parte_texto, re.IGNORECASE)
        if match:
            inicio_real = match
            print(f"   Inicio real encontrado: '{patron.strip()}'")
            break
    
    if inicio_real:
        parte_texto = parte_texto[inicio_real.start():]
        print(f"   Texto efectivo: {len(parte_texto)} caracteres")
    else:
        print(f"   ⚠️ No se encontró inicio de secciones, usando texto completo")
    
    # ========== DIVIDIR POR SECCIONES ==========
    secciones_raw = re.split(r'\n(?=\d+\.?\s+[A-ZÁÉÍÓÚÜÑ])', parte_texto)
    
    secciones = []
    for sec in secciones_raw:
        sec = sec.strip()
        if not sec or len(sec) < 50:
            continue
        # Filtro: descartar párrafos del preámbulo que escaparon
        primera_linea = sec.split('\n')[0]
        if re.match(r'^\d+\.?\s+(La\s|Tras\s|En\s|Las\s|Nada\s|Reconociendo|Habiendo|Considerando|Estimando)', primera_linea):
            continue
        secciones.append(sec)
    
    print(f"   Secciones reales: {len(secciones)}")
    
    for i, sec in enumerate(secciones):
        titulo = sec.split('\n')[0][:80]
        print(f"   [{i}] {titulo}... ({len(sec)} chars)")
        
        metadata_base = {
            "parte": parte_nombre,
            "seccion": titulo,
            "indice_parte": i,
            "es_fragmento": False
        }
        
        if len(sec) <= 4000:
            chunks.append(Document(
                page_content=sec,
                metadata={**metadata_base, "chunk_id": chunk_global_id, "chunk_total": None}
            ))
            chunk_global_id += 1
        else:
            doc_temp = Document(page_content=sec, metadata=metadata_base)
            sub_chunks = text_splitter.split_documents([doc_temp])
            for sub in sub_chunks:
                sub.metadata["chunk_id"] = chunk_global_id
                sub.metadata["chunk_total"] = None
                sub.metadata["es_fragmento"] = True
                chunks.append(sub)
                chunk_global_id += 1

for c in chunks:
    c.metadata["chunk_total"] = len(chunks)

print(f"\n🔨 Total chunks: {len(chunks)}")

# Verificaciones
secciones_3 = [c for c in chunks if re.search(r'\b3\b.*Ámbito|Ámbito.*\b3\b', c.metadata["seccion"], re.IGNORECASE)]
print(f"\n✅ Secciones '3 Ámbito': {len(secciones_3)}")

secciones_a = [c for c in chunks if c.metadata["parte"] == "A"]
secciones_b = [c for c in chunks if c.metadata["parte"] == "B"]
print(f"📊 Parte A: {len(secciones_a)} documentos/chunks")
print(f"📊 Parte B: {len(secciones_b)} documentos/chunks")

print("\n📋 Parte A - Secciones:")
for c in secciones_a:
    frag = " [FRAG]" if c.metadata["es_fragmento"] else ""
    print(f"   {c.metadata['chunk_id']}: {c.metadata['seccion'][:60]}{frag} ({len(c.page_content)} chars)")

print("\n📋 Parte B - Secciones:")
for c in secciones_b:
    frag = " [FRAG]" if c.metadata["es_fragmento"] else ""
    print(f"   {c.metadata['chunk_id']}: {c.metadata['seccion'][:60]}{frag} ({len(c.page_content)} chars)")

# Guardar en Chroma
if os.path.exists(CHROMA_PATH):
    print("\n🗑️ Eliminando base Chroma anterior...")
    shutil.rmtree(CHROMA_PATH)

print("💾 Indexando en Chroma...")
db = Chroma.from_documents(chunks, embeddings, persist_directory=CHROMA_PATH, collection_name=COLLECTION_NAME)
print(f"✅ Base creada con {db._collection.count()} vectores.")

# Pruebas
print("\n" + "="*60)
print("🔍 'buques de carga arqueo bruto 500'")
results = db.similarity_search("buques de carga arqueo bruto 500", k=3)
for i, r in enumerate(results):
    print(f"\n--- {i+1} | Parte {r.metadata['parte']} | Chunk {r.metadata['chunk_id']} ---")
    print(f"Sección: {r.metadata['seccion'][:60]}")
    print(r.page_content[:400])

print("\n" + "="*60)
print("🔍 'nivel de protección 3'")
results = db.similarity_search("nivel de protección 3", k=3)
for i, r in enumerate(results):
    print(f"\n--- {i+1} | Parte {r.metadata['parte']} | Chunk {r.metadata['chunk_id']} ---")
    print(f"Sección: {r.metadata['seccion'][:60]}")
    print(r.page_content[:400])