-- Catalog DDL: extensions, tables, indexes (apply as one script; order matters).

-- pgvector: semantic search on catalog_embeddings.embedding
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- catalog_resources
--
-- All skill fields are stored in payload JSONB.  The dedicated columns
-- (name, version, kind, is_latest, tenant_ids) cover every filter that the
-- application issues today.  New agentskills.io fields land in payload
-- automatically:
--
--   payload->>'license'           e.g. "IBM Internal"
--   payload->>'compatibility'     environment requirements string
--   payload->'allowed_tools'      JSON array of tool name strings
--   payload->'metadata'           object: title, category, products, tags,
--                                         author, instructions, …
--   payload->'metadata'->'tags'   JSON array of keyword/trigger strings
--   payload->'metadata'->'products' JSON array of IBM product names
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    official_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_latest BOOLEAN NOT NULL DEFAULT false,
    tenant_ids TEXT[],
    -- Raw source content (e.g. Markdown file).  NULL when not provided.
    -- Excluded from all standard SELECT queries; fetched only on explicit request
    -- via get_resource_content().
    content TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT catalog_resources_kind_name_version_unique UNIQUE (kind, name, version)
);

-- One is_latest row per (kind, name) — enforced at the DB level.
CREATE UNIQUE INDEX IF NOT EXISTS catalog_resources_one_is_latest_per_kind_name
    ON catalog_resources (kind, name)
    WHERE is_latest;

-- Fast lookup by kind + name (list, get, count).
CREATE INDEX IF NOT EXISTS catalog_resources_kind_name_idx
    ON catalog_resources (kind, name);

-- Tenant visibility filter: ANY(tenant_ids) queries.
CREATE INDEX IF NOT EXISTS catalog_resources_tenant_ids_gin
    ON catalog_resources USING gin (tenant_ids);

-- ---------------------------------------------------------------------------
-- Payload JSONB indexes — support future filtering on agentskills.io fields
-- without application-layer changes.
-- ---------------------------------------------------------------------------

-- Filter / search by license value  (e.g. WHERE payload->>'license' = 'IBM Internal').
CREATE INDEX IF NOT EXISTS catalog_resources_payload_license_idx
    ON catalog_resources ((payload->>'license'));

-- Containment queries on metadata.tags array
-- (e.g. WHERE payload->'metadata'->'tags' @> '["apm"]').
CREATE INDEX IF NOT EXISTS catalog_resources_payload_metadata_tags_gin
    ON catalog_resources USING gin ((payload->'metadata'->'tags'));

-- Containment queries on metadata.products array
-- (e.g. WHERE payload->'metadata'->'products' @> '["Instana"]').
CREATE INDEX IF NOT EXISTS catalog_resources_payload_metadata_products_gin
    ON catalog_resources USING gin ((payload->'metadata'->'products'));

-- Full-text search across name + description + metadata fields
-- (e.g. WHERE to_tsvector('english', payload->>'description') @@ plainto_tsquery('tracing')).
CREATE INDEX IF NOT EXISTS catalog_resources_payload_fts_idx
    ON catalog_resources
    USING gin (
        to_tsvector(
            'english',
            coalesce(payload->>'name', '') || ' ' ||
            coalesce(payload->>'description', '') || ' ' ||
            coalesce(payload->'metadata'->>'title', '') || ' ' ||
            coalesce(payload->'metadata'->>'category', '')
        )
    );

-- ---------------------------------------------------------------------------
-- catalog_resource_metadata
--
-- Private, non-public metadata for catalog resources (JSONB column ``data``).
-- Never serialised into API responses.  Linked to ``catalog_resources.id``
-- (same pattern as ``catalog_embeddings``).
--
-- One row per resource row (UUID).  ON DELETE CASCADE removes metadata when
-- the parent ``catalog_resources`` row is deleted.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_resource_metadata (
    resource_id UUID        PRIMARY KEY
        REFERENCES catalog_resources (id) ON DELETE CASCADE,
    data          JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Migration from legacy (kind, name, version) composite key + optional rename:
--   ALTER TABLE catalog_resource_metadata ADD COLUMN resource_id UUID;
--   UPDATE catalog_resource_metadata m
--      SET resource_id = r.id
--     FROM catalog_resources r
--    WHERE r.kind = m.kind AND r.name = m.name AND r.version = m.version;
--   ALTER TABLE catalog_resource_metadata DROP CONSTRAINT IF EXISTS fk_catalog_resource_metadata_resource;
--   ALTER TABLE catalog_resource_metadata DROP CONSTRAINT IF EXISTS catalog_resource_metadata_pkey;
--   ALTER TABLE catalog_resource_metadata ALTER COLUMN resource_id SET NOT NULL;
--   ALTER TABLE catalog_resource_metadata ADD PRIMARY KEY (resource_id);
--   ALTER TABLE catalog_resource_metadata ADD CONSTRAINT fk_catalog_resource_metadata_resource
--       FOREIGN KEY (resource_id) REFERENCES catalog_resources (id) ON DELETE CASCADE;
--   ALTER TABLE catalog_resource_metadata DROP COLUMN IF EXISTS kind;
--   ALTER TABLE catalog_resource_metadata DROP COLUMN IF EXISTS name;
--   ALTER TABLE catalog_resource_metadata DROP COLUMN IF EXISTS version;
-- If upgrading from private_meta: ALTER TABLE catalog_resource_metadata RENAME COLUMN private_meta TO data;

CREATE TABLE IF NOT EXISTS catalog_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id UUID NOT NULL REFERENCES catalog_resources (id) ON DELETE CASCADE,
    embedding vector(1536) NOT NULL,
    embedding_model TEXT NOT NULL,
    provider TEXT,
    model_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT catalog_embeddings_one_per_resource UNIQUE (resource_id)
);

CREATE INDEX IF NOT EXISTS catalog_embeddings_hnsw_cosine
    ON catalog_embeddings
    USING hnsw (embedding vector_cosine_ops);