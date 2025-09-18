import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import psycopg

app = FastAPI()
DSN = os.getenv("DATABASE_URL","postgresql://pulpo:pulpo@localhost:5432/pulpo")

class SearchReq(BaseModel):
    top_k: int = 5
    vector_mode: str = "unit"   # "unit" (e₁) o "zeros" (solo test)

@app.post("/rag/search")
def rag_search(req: SearchReq, x_workspace_id: str = Header(...)):
    with psycopg.connect(DSN) as con, con.cursor() as cur:
        cur.execute("SELECT pulpo.set_ws_context(%s);", (x_workspace_id,))
        vec_sql = "(ARRAY[1.0::float4] || ARRAY(SELECT 0.0::float4 FROM generate_series(2,1024)))::vector" \
                  if req.vector_mode=="unit" else "ARRAY(SELECT 0.0::float4 FROM generate_series(1,1024))::vector"
        cur.execute(f"""
          WITH q AS (SELECT {vec_sql} AS v)
          SELECT ce.document_id::text, ce.chunk_id::text,
                 1 - (ce.embedding <=> (SELECT v FROM q)) AS cos_score,
                 left(c.text,160) AS preview
            FROM pulpo.chunk_embeddings ce
            JOIN pulpo.chunks c ON c.id=ce.chunk_id AND c.workspace_id=ce.workspace_id
           WHERE ce.workspace_id=current_setting('app.workspace_id')::uuid
           ORDER BY ce.embedding <-> (SELECT v FROM q)
           LIMIT %s;""", (req.top_k,))
        rows = cur.fetchall()
    return {"results":[{"doc_id":r[0], "chunk_id":r[1], "score":float(r[2]) if r[2] else None, "preview":r[3]} for r in rows]}