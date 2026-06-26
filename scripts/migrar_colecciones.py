"""
migrar_colecciones.py
Fusiona auditoria_pbip + legislacion_mexicana → mia_conocimiento
Preserva todo el metadata original + agrega campo 'dominio' para que el LLM sepa de dónde viene.
NO borra las colecciones originales — solo crea la nueva.
"""

import chromadb
import uuid

CHROMA_PATH = "/home/julian/Naviera-Registro/scripts/chroma_db"
COLECCION_DESTINO = "mia_conocimiento"

def migrar():
    c = chromadb.PersistentClient(path=CHROMA_PATH)

    # Verificar que no exista ya la colección destino
    existentes = [col.name for col in c.list_collections()]
    if COLECCION_DESTINO in existentes:
        print(f"⚠️  La colección '{COLECCION_DESTINO}' ya existe.")
        resp = input("¿Borrarla y recrear? (s/N): ").strip().lower()
        if resp == "s":
            c.delete_collection(COLECCION_DESTINO)
            print("🗑️  Colección anterior eliminada.")
        else:
            print("Abortado.")
            return

    destino = c.create_collection(
        name=COLECCION_DESTINO,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"✅ Colección '{COLECCION_DESTINO}' creada.")

    total_migrado = 0

    # ── 1. PBIP ──────────────────────────────────────────────────────────────
    print("\n📦 Migrando auditoria_pbip...")
    pbip = c.get_collection("auditoria_pbip")
    pbip_data = pbip.get(include=["documents", "metadatas", "embeddings"])

    pbip_ids        = []
    pbip_docs       = []
    pbip_metas      = []
    pbip_embeddings = []

    for i, (doc, meta, emb) in enumerate(zip(
        pbip_data["documents"],
        pbip_data["metadatas"],
        pbip_data["embeddings"]
    )):
        nueva_meta = dict(meta)
        nueva_meta["dominio"]  = "pbip"
        nueva_meta["fuente"]   = f"Código PBIP — Parte {meta.get('parte', '?')} | {meta.get('seccion', '')}"
        nueva_meta["tipo"]     = "normativa_internacional"

        pbip_ids.append(f"pbip_{i}_{uuid.uuid4().hex[:8]}")
        pbip_docs.append(doc)
        pbip_metas.append(nueva_meta)
        pbip_embeddings.append(emb)

    # Insertar en lotes de 100
    for inicio in range(0, len(pbip_ids), 100):
        fin = inicio + 100
        destino.add(
            ids=pbip_ids[inicio:fin],
            documents=pbip_docs[inicio:fin],
            metadatas=pbip_metas[inicio:fin],
            embeddings=pbip_embeddings[inicio:fin],
        )

    total_migrado += len(pbip_ids)
    print(f"   ✅ {len(pbip_ids)} chunks PBIP migrados.")

    # ── 2. LEGISLACIÓN ───────────────────────────────────────────────────────
    print("\n📦 Migrando legislacion_mexicana...")
    leg = c.get_collection("legislacion_mexicana")
    leg_data = leg.get(include=["documents", "metadatas", "embeddings"])

    leg_ids        = []
    leg_docs       = []
    leg_metas      = []
    leg_embeddings = []

    for i, (doc, meta, emb) in enumerate(zip(
        leg_data["documents"],
        leg_data["metadatas"],
        leg_data["embeddings"]
    )):
        nueva_meta = dict(meta)
        nueva_meta["dominio"] = "legislacion_mexicana"
        # fuente ya existe en esta colección, la conservamos

        leg_ids.append(f"leg_{i}_{uuid.uuid4().hex[:8]}")
        leg_docs.append(doc)
        leg_metas.append(nueva_meta)
        leg_embeddings.append(emb)

    for inicio in range(0, len(leg_ids), 100):
        fin = inicio + 100
        destino.add(
            ids=leg_ids[inicio:fin],
            documents=leg_docs[inicio:fin],
            metadatas=leg_metas[inicio:fin],
            embeddings=leg_embeddings[inicio:fin],
        )

    total_migrado += len(leg_ids)
    print(f"   ✅ {len(leg_ids)} chunks legislación migrados.")

    # ── RESUMEN ──────────────────────────────────────────────────────────────
    print(f"\n🎯 Migración completa: {total_migrado} chunks en '{COLECCION_DESTINO}'")
    print(f"   Colecciones originales intactas: auditoria_pbip ({pbip.count()}), legislacion_mexicana ({leg.count()})")

    # Verificación rápida
    verificacion = destino.get(limit=3, include=["metadatas"])
    print("\n🔍 Muestra de los primeros 3 chunks migrados:")
    for m in verificacion["metadatas"]:
        print(f"   dominio={m.get('dominio')} | fuente={m.get('fuente')} | tipo={m.get('tipo')}")

if __name__ == "__main__":
    migrar()