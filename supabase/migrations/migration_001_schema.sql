-- migration_001_schema.sql
-- Phase 0.4 — Supabase schema for insurance-agent
-- Apply via: Supabase Dashboard → SQL Editor → paste → Run
-- Or: psql "$SUPABASE_DB_URL" -f supabase/migrations/migration_001_schema.sql

-- ══════════════════════════════════════════════════════════════════
-- EXTENSION
-- ══════════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS vector;

-- ══════════════════════════════════════════════════════════════════
-- 1. insurers — reference table seeded from uin_lifecycle.json
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE insurers (
    id          SERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,       -- 'ICI', 'SHA', 'NIA' etc.
    name        TEXT NOT NULL,              -- 'ICICI Lombard General Insurance'
    folder_name TEXT,                       -- '04_ICICI_Lombard'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 2. products — UIN base level (e.g. 'ICIHLIP')
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE products (
    id              SERIAL PRIMARY KEY,
    uin_base        TEXT UNIQUE NOT NULL,
    insurer_id      INTEGER NOT NULL REFERENCES insurers(id),
    product_name    TEXT NOT NULL,
    line_of_business TEXT,                  -- 'health', 'motor', 'travel' etc.
    product_type    TEXT,                   -- 'individual', 'group', 'top_up', 'addon'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 3. product_versions — individual UIN filings
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE product_versions (
    id                   SERIAL PRIMARY KEY,
    product_id           INTEGER NOT NULL REFERENCES products(id),
    uin                  TEXT UNIQUE NOT NULL,   -- 'ICIHLIP12345V012020'
    version              INTEGER NOT NULL,
    status               TEXT NOT NULL CHECK (status IN ('active', 'superseded', 'withdrawn')),
    irdai_source_path    TEXT,                   -- relative path to IRDAI copy
    website_source_path  TEXT,                   -- relative path to website copy
    is_canonical         BOOLEAN NOT NULL DEFAULT FALSE,
    page_count           INTEGER,
    file_size_bytes      BIGINT,
    features_extracted   BOOLEAN NOT NULL DEFAULT FALSE,
    chunks_generated     BOOLEAN NOT NULL DEFAULT FALSE,
    extraction_job_id    TEXT,
    extraction_priority  INTEGER NOT NULL DEFAULT 0,
    metadata             JSONB DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 4. policy_features — structured extraction output (60+ fields)
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE policy_features (
    id                       SERIAL PRIMARY KEY,
    product_version_id       INTEGER NOT NULL REFERENCES product_versions(id) ON DELETE CASCADE,
    features                 JSONB NOT NULL,
    extraction_model         TEXT NOT NULL,          -- 'gemini-2.5-flash'
    extraction_prompt_version TEXT NOT NULL,          -- 'v1.0', 'v2.0' etc.
    is_current               BOOLEAN NOT NULL DEFAULT TRUE,
    confidence_scores        JSONB,
    raw_extraction_text      TEXT,
    extraction_job_id        TEXT,
    warnings                 JSONB DEFAULT '[]'::jsonb,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 5. policy_chunks — RAG chunks with embeddings
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE policy_chunks (
    id                  SERIAL PRIMARY KEY,
    product_version_id  INTEGER NOT NULL REFERENCES product_versions(id) ON DELETE CASCADE,
    chunk_index         INTEGER NOT NULL,
    chunk_text          TEXT NOT NULL,
    section_title       TEXT,
    page_number         INTEGER,
    embedding           VECTOR(1024),
    chunking_config_id  INTEGER,
    metadata            JSONB DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 6. chunking_configs — reproducible chunking parameters
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE chunking_configs (
    id          SERIAL PRIMARY KEY,
    strategy    TEXT NOT NULL,           -- 'recursive', 'semantic' etc.
    chunk_size  INTEGER NOT NULL,
    overlap     INTEGER NOT NULL,
    model       TEXT,                    -- for semantic chunking
    metadata    JSONB DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 7. circulars — IRDAI circular metadata
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE circulars (
    id              SERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    circular_number TEXT,
    circular_date   DATE,
    category        TEXT,               -- 'circular', 'regulation', 'guideline'
    irdai_source    TEXT,
    pdf_path        TEXT,
    file_size_bytes BIGINT,
    page_count      INTEGER,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 8. circular_chunks — IRDAI circular RAG chunks
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE circular_chunks (
    id              SERIAL PRIMARY KEY,
    circular_id     INTEGER REFERENCES circulars(id),
    title           TEXT,
    circular_number TEXT,
    circular_date   DATE,
    irdai_source    TEXT,
    chunk_index     INTEGER NOT NULL,
    chunk_text      TEXT NOT NULL,
    section_title   TEXT,
    related_uins    JSONB DEFAULT '[]'::jsonb,
    embedding       VECTOR(1024),
    chunking_config_id  INTEGER,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 9. irdai_historical — structured IRDAI annual report data
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE irdai_historical (
    id          SERIAL PRIMARY KEY,
    year        INTEGER NOT NULL,
    category    TEXT NOT NULL,      -- 'market_share', 'premium', 'claims', 'complaints'
    data        JSONB NOT NULL,
    source_file TEXT,
    metadata    JSONB DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 10. conversations — chat sessions
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT,                 -- anonymous session identifier for MVP
    title       TEXT NOT NULL DEFAULT 'New Conversation',
    metadata    JSONB DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 11. messages — individual chat messages
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content         TEXT NOT NULL,
    tool_calls      JSONB,
    tool_results    JSONB,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    model_used      TEXT,
    latency_ms      INTEGER,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- 12. search_logs — analytics for what users search
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE search_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text      TEXT NOT NULL,
    query_type      TEXT NOT NULL,       -- 'semantic', 'structured', 'hybrid'
    result_count    INTEGER,
    results         JSONB,
    latency_ms      INTEGER,
    model_used      TEXT,
    session_id      TEXT,
    feedback_score  INTEGER CHECK (feedback_score IS NULL OR (feedback_score >= 1 AND feedback_score <= 5)),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- INDEXES
-- ══════════════════════════════════════════════════════════════════

-- Foreign key indexes
CREATE INDEX idx_products_insurer_id ON products(insurer_id);
CREATE INDEX idx_product_versions_product_id ON product_versions(product_id);
CREATE INDEX idx_policy_features_product_version ON policy_features(product_version_id);
CREATE INDEX idx_policy_chunks_product_version ON policy_chunks(product_version_id);
CREATE INDEX idx_circular_chunks_circular_id ON circular_chunks(circular_id);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_conversations_session ON conversations(session_id);

-- Status & extraction queue indexes
CREATE INDEX idx_product_versions_status ON product_versions(status);
CREATE INDEX idx_product_versions_extraction_queue ON product_versions(extraction_priority, features_extracted)
    WHERE features_extracted = FALSE;

-- JSONB query indexes (jsonb_path_ops is faster for containment @> and existence ? operators)
CREATE INDEX idx_policy_features_features_gin ON policy_features USING GIN(features jsonb_path_ops);
CREATE INDEX idx_irdai_historical_data_gin ON irdai_historical USING GIN(data jsonb_path_ops);

-- Current features lookup
CREATE INDEX idx_policy_features_current ON policy_features(product_version_id, is_current)
    WHERE is_current = TRUE;

-- Time-series lookups
CREATE INDEX idx_search_logs_created ON search_logs(created_at DESC);
CREATE INDEX idx_irdai_historical_year ON irdai_historical(year);

-- ══════════════════════════════════════════════════════════════════
-- VECTOR INDEXES (IVFFlat for cosine similarity)
-- lists = sqrt(expected_rows) — tune after data is loaded
-- ══════════════════════════════════════════════════════════════════
CREATE INDEX idx_policy_chunks_embedding ON policy_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_circular_chunks_embedding ON circular_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ══════════════════════════════════════════════════════════════════
-- FULL-TEXT SEARCH
-- ══════════════════════════════════════════════════════════════════
ALTER TABLE products ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english'::regconfig, COALESCE(product_name, ''))) STORED;

ALTER TABLE product_versions ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english'::regconfig, COALESCE(uin, ''))) STORED;

ALTER TABLE circulars ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (
        to_tsvector('english'::regconfig,
            COALESCE(title, '') || ' ' || COALESCE(circular_number, '')
        )
    ) STORED;

CREATE INDEX idx_products_search ON products USING GIN(search_vector);
CREATE INDEX idx_product_versions_search ON product_versions USING GIN(search_vector);
CREATE INDEX idx_circulars_search ON circulars USING GIN(search_vector);

-- ══════════════════════════════════════════════════════════════════
-- UPDATED_AT TRIGGER
-- ══════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_product_versions_updated_at
    BEFORE UPDATE ON product_versions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ══════════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY
-- Public read on reference data, service_role for writes
-- ══════════════════════════════════════════════════════════════════
ALTER TABLE insurers ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_features ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE circulars ENABLE ROW LEVEL SECURITY;
ALTER TABLE circular_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE irdai_historical ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_logs ENABLE ROW LEVEL SECURITY;

-- Public read policies
CREATE POLICY "Public read insurers" ON insurers FOR SELECT USING (true);
CREATE POLICY "Public read products" ON products FOR SELECT USING (true);
CREATE POLICY "Public read product_versions" ON product_versions FOR SELECT USING (true);
CREATE POLICY "Public read policy_features" ON policy_features FOR SELECT USING (true);
CREATE POLICY "Public read policy_chunks" ON policy_chunks FOR SELECT USING (true);
CREATE POLICY "Public read circulars" ON circulars FOR SELECT USING (true);
CREATE POLICY "Public read circular_chunks" ON circular_chunks FOR SELECT USING (true);
CREATE POLICY "Public read irdai_historical" ON irdai_historical FOR SELECT USING (true);

-- Conversations: anon users can CRUD their own session
CREATE POLICY "Session read conversations" ON conversations
    FOR SELECT USING (session_id = current_setting('request.session_id', true) OR session_id IS NULL);
CREATE POLICY "Session insert conversations" ON conversations
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Session update conversations" ON conversations
    FOR UPDATE USING (session_id = current_setting('request.session_id', true));

-- Messages: anon can CRUD in their session's conversations
CREATE POLICY "Session read messages" ON messages
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM conversations c WHERE c.id = messages.conversation_id
                AND (c.session_id = current_setting('request.session_id', true) OR c.session_id IS NULL))
    );
CREATE POLICY "Session insert messages" ON messages
    FOR INSERT WITH CHECK (true);

-- Search logs: anon can insert
CREATE POLICY "Anon insert search_logs" ON search_logs
    FOR INSERT WITH CHECK (true);
