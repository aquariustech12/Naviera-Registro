from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from rank_bm25 import BM25Okapi
import re

db = Chroma(
    persist_directory="scripts/chroma_db",
    embedding_function=OllamaEmbeddings(model="nomic-embed-text"),
    collection_name="auditoria_pbip"
)

# Cargar BM25
all_docs = db.get()
corpus_texts = all_docs['documents']
corpus_metadatas = all_docs['metadatas']

def tokenize(text):
    return re.findall(r'\b\w+\b', text.lower())

tokenized_corpus = [tokenize(doc) for doc in corpus_texts]
bm25 = BM25Okapi(tokenized_corpus)

# ========== BÚSQUEDA EN DOS ETAPAS ==========

def buscar_bm25_top(query, k_bm25=10, parte=None):
    """BM25 puro, devuelve top k documentos."""
    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)
    
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    
    results = []
    for idx, score in ranked:
        meta = corpus_metadatas[idx]
        if parte and meta.get('parte') != parte:
            continue
        results.append({
            'text': corpus_texts[idx],
            'metadata': meta,
            'bm25_score': score,
            'index': idx
        })
        if len(results) >= k_bm25:
            break
    
    return results

def buscar_semantico_rerank(query, candidatos, k_final=3):
    """Re-rankea los candidatos BM25 con embeddings semánticos."""
    # Extraer textos de los candidatos
    texts = [c['text'] for c in candidatos]
    
    # Calcular embeddings de query y candidatos
    from langchain_ollama import OllamaEmbeddings
    emb = OllamaEmbeddings(model="nomic-embed-text")
    
    query_embedding = emb.embed_query(query)
    doc_embeddings = emb.embed_documents(texts)
    
    # Similaridad coseno
    import numpy as np
    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    for i, cand in enumerate(candidatos):
        cand['semantic_score'] = cosine_similarity(query_embedding, doc_embeddings[i])
    
    # Combinar: 70% BM25 + 30% semántico (SOLO entre los top BM25)
    for cand in candidatos:
        # Normalizar BM25 localmente (entre los candidatos)
        max_bm25 = max(c['bm25_score'] for c in candidatos)
        bm25_norm = cand['bm25_score'] / max_bm25 if max_bm25 > 0 else 0
        
        cand['final_score'] = 0.7 * bm25_norm + 0.3 * cand['semantic_score']
    
    candidatos.sort(key=lambda x: x['final_score'], reverse=True)
    return candidatos[:k_final]

def buscar(query, k_final=3, parte=None, estrategia='auto'):
    """
    Estrategias:
    - 'bm25': solo BM25 (mejor para definiciones, números exactos)
    - 'semantico': solo semántico (mejor para conceptos vagos)
    - 'rerank': BM25 top 10 + re-ranqueo semántico (balanceado)
    - 'auto': detecta según query
    """
    
    # Detectar tipo de query
    query_lower = query.lower()
    es_definicion = any(w in query_lower for w in ['arqueo', 'tonelaje', '500', 'eslora', 'definición', 'ámbito', 'aplica', 'cuál', 'cuáles', 'qué es', 'tipos de'])
    es_procedimiento = any(w in query_lower for w in ['cómo', 'procedimiento', 'medida', 'paso', 'debe', 'deberá', 'obligación', 'nivel de protección', 'plan de protección'])
    
    if estrategia == 'auto':
        if es_definicion:
            estrategia = 'bm25'
        elif es_procedimiento:
            estrategia = 'rerank'
        else:
            estrategia = 'semantico'
    
    print(f"   Estrategia: {estrategia}")
    
    if estrategia == 'bm25':
        results = buscar_bm25_top(query, k_bm25=k_final, parte=parte)
        for r in results:
            r['final_score'] = r['bm25_score']  # No re-ranqueo
        return results
    
    elif estrategia == 'semantico':
        docs = db.similarity_search(query, k=k_final, filter={'parte': parte} if parte else None)
        results = []
        for doc in docs:
            results.append({
                'text': doc.page_content,
                'metadata': doc.metadata,
                'bm25_score': 0,
                'semantic_score': 0,  # No calculamos, Chroma ya lo hizo
                'final_score': 0
            })
        return results
    
    elif estrategia == 'rerank':
        candidatos = buscar_bm25_top(query, k_bm25=10, parte=parte)
        return buscar_semantico_rerank(query, candidatos, k_final=k_final)
    
    else:
        raise ValueError(f"Estrategia desconocida: {estrategia}")

# ========== PRUEBAS ==========

queries = [
    ("buques de carga arqueo bruto 500", 'bm25'),  # Definición exacta
    ("nivel de protección 3 medidas buque", 'rerank'),  # Procedimiento
    ("plan de protección del buque contenido mínimo", 'rerank'),  # Procedimiento
    ("qué es una declaración de protección marítima", 'bm25'),  # Definición
]

for query, estrategia_esperada in queries:
    print(f"\n{'='*60}")
    print(f"🔍 '{query}'")
    print(f"{'='*60}")
    
    # Auto-detectar
    print(f"\n--- AUTO ---")
    results = buscar(query, k_final=3, parte='A', estrategia='auto')
    for i, r in enumerate(results):
        print(f"{i+1}. Parte {r['metadata']['parte']} | {r['metadata']['seccion'][:50]} | score={r.get('final_score', 0):.3f}")
    
    # Forzar estrategia esperada
    print(f"\n--- {estrategia_esperada.upper()} ---")
    results = buscar(query, k_final=3, parte='A', estrategia=estrategia_esperada)
    for i, r in enumerate(results):
        if estrategia_esperada == 'bm25':
            print(f"{i+1}. Parte {r['metadata']['parte']} | {r['metadata']['seccion'][:50]} | BM25={r['bm25_score']:.3f}")
        else:
            print(f"{i+1}. Parte {r['metadata']['parte']} | {r['metadata']['seccion'][:50]} | final={r['final_score']:.3f}")