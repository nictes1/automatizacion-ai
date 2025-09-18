SET search_path = public, pulpo;
DO $$BEGIN IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector') THEN CREATE EXTENSION vector; END IF; END$$;
CREATE TABLE IF NOT EXISTS pulpo.documents(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  title text, mime text, storage_url text, size_bytes bigint, hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, hash)
);
CREATE TABLE IF NOT EXISTS pulpo.chunks(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES pulpo.documents(id) ON DELETE CASCADE,
  pos int NOT NULL, text text NOT NULL, meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(workspace_id, document_id, pos)
);
CREATE TABLE IF NOT EXISTS pulpo.chunk_embeddings(
  chunk_id uuid PRIMARY KEY REFERENCES pulpo.chunks(id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL, document_id uuid NOT NULL, embedding vector(1024) NOT NULL
);
CREATE TABLE IF NOT EXISTS pulpo.ingest_jobs(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  document_id uuid REFERENCES pulpo.documents(id) ON DELETE CASCADE, status text NOT NULL CHECK (status IN ('queued','processing','success','failed')),
  error_message text, stats_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz
);
ALTER TABLE pulpo.documents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.chunks           ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.chunk_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.ingest_jobs      ENABLE ROW LEVEL SECURITY;
DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='ws_iso_documents') THEN
    CREATE POLICY ws_iso_documents ON pulpo.documents
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='ws_iso_chunks') THEN
    CREATE POLICY ws_iso_chunks ON pulpo.chunks
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='ws_iso_chunk_embeddings') THEN
    CREATE POLICY ws_iso_chunk_embeddings ON pulpo.chunk_embeddings
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='ws_iso_ingest_jobs') THEN
    CREATE POLICY ws_iso_ingest_jobs ON pulpo.ingest_jobs
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;
END$$;
DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='pulpo' AND indexname='ivf_chunk_embeddings') THEN
    CREATE INDEX ivf_chunk_embeddings ON pulpo.chunk_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
  END IF;
END$$;