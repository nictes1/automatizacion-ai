#!/usr/bin/env python3
"""
Script para generar embeddings de documentos existentes usando Ollama
"""
import psycopg2
import httpx
import sys
from psycopg2.extras import RealDictCursor

# Configuración
DB_URL = "postgresql://pulpo:pulpo@localhost:5432/pulpo"
OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"

def generate_embedding(text: str) -> list:
    """Genera embedding usando Ollama"""
    response = httpx.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=30.0
    )
    if response.status_code == 200:
        return response.json().get("embedding")
    else:
        raise Exception(f"Error generando embedding: {response.status_code}")

def main():
    print("🚀 Generando embeddings para documentos...")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Obtener chunks sin embeddings
    cur.execute("""
        SELECT dc.id, dc.content
        FROM pulpo.document_chunks dc
        LEFT JOIN pulpo.document_embeddings de ON de.chunk_id = dc.id
        WHERE de.id IS NULL
        ORDER BY dc.id
    """)

    chunks = cur.fetchall()
    total = len(chunks)

    if total == 0:
        print("✅ Todos los chunks ya tienen embeddings")
        cur.close()
        conn.close()
        return

    print(f"📝 Procesando {total} chunks...")

    for idx, chunk in enumerate(chunks, 1):
        chunk_id = chunk['id']
        content = chunk['content']

        print(f"  [{idx}/{total}] Generando embedding para chunk {chunk_id}...", end=" ")

        try:
            # Generar embedding
            embedding = generate_embedding(content)

            if not embedding:
                print("❌ Error: embedding vacío")
                continue

            # Convertir a formato pgvector
            embedding_str = f"[{','.join(map(str, embedding))}]"

            # Insertar embedding
            cur.execute("""
                INSERT INTO pulpo.document_embeddings (chunk_id, embedding, model, created_at)
                VALUES (%s, %s::vector, %s, NOW())
            """, (chunk_id, embedding_str, EMBEDDING_MODEL))

            conn.commit()
            print("✅")

        except Exception as e:
            print(f"❌ Error: {e}")
            conn.rollback()

    # Verificar resultados
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(de.id) as with_embeddings
        FROM pulpo.document_chunks dc
        LEFT JOIN pulpo.document_embeddings de ON de.chunk_id = dc.id
    """)
    stats = cur.fetchone()

    print(f"\n✅ Proceso completado:")
    print(f"  - Total chunks: {stats['total']}")
    print(f"  - Con embeddings: {stats['with_embeddings']}")
    print(f"  - Sin embeddings: {stats['total'] - stats['with_embeddings']}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
