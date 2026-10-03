-- BFDM non-Discord document archive index
-- Canonical source files live in source containers. This SQLite is a searchable index.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ingest_runs (
    ingest_run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    agent TEXT,
    source_scope TEXT,
    base_commit_sha TEXT,
    result_commit_sha TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS source_containers (
    corpus_id TEXT PRIMARY KEY,
    project TEXT,
    project_slug TEXT,
    title TEXT NOT NULL,
    source_role TEXT,
    source_kind TEXT,
    authorship_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    authorship_basis TEXT,
    partition_name TEXT,
    created_at TEXT,
    modified_at TEXT,
    normalized_path TEXT,
    primary_representation_path TEXT,
    normalized_sha256 TEXT,
    primary_representation_sha256 TEXT,
    document_family_id TEXT,
    ingest_run_id TEXT REFERENCES ingest_runs(ingest_run_id),
    CHECK (corpus_id GLOB 'BCS-[0-9][0-9][0-9][0-9][0-9][0-9]')
);

CREATE TABLE IF NOT EXISTS source_locators (
    locator_id INTEGER PRIMARY KEY,
    corpus_id TEXT NOT NULL REFERENCES source_containers(corpus_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    locator_type TEXT NOT NULL,
    native_id TEXT,
    url TEXT,
    library_file_id TEXT,
    project_file_id TEXT,
    project_name TEXT,
    source_path TEXT,
    version_id TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_locators_corpus
ON source_locators(corpus_id);

CREATE INDEX IF NOT EXISTS idx_source_locators_native
ON source_locators(provider, native_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_locators_provider_native
ON source_locators(provider, native_id)
WHERE native_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS source_representations (
    representation_id INTEGER PRIMARY KEY,
    corpus_id TEXT NOT NULL REFERENCES source_containers(corpus_id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    repo_path TEXT NOT NULL UNIQUE,
    mime_type TEXT,
    size_bytes INTEGER,
    sha256 TEXT NOT NULL,
    provider_revision_id TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_representations_corpus
ON source_representations(corpus_id);

CREATE INDEX IF NOT EXISTS idx_source_representations_sha
ON source_representations(sha256);

CREATE TABLE IF NOT EXISTS document_versions (
    corpus_id TEXT NOT NULL REFERENCES source_containers(corpus_id) ON DELETE CASCADE,
    provider_revision_id TEXT NOT NULL,
    modified_at TEXT,
    modifier_display_name TEXT,
    modifier_native_id TEXT,
    modifier_metadata_json TEXT,
    is_current INTEGER NOT NULL DEFAULT 0,
    body_capture_status TEXT NOT NULL,
    body_path TEXT,
    body_sha256 TEXT,
    body_text TEXT,
    export_mime_type TEXT,
    capture_error TEXT,
    PRIMARY KEY (corpus_id, provider_revision_id)
);

CREATE INDEX IF NOT EXISTS idx_document_versions_time
ON document_versions(corpus_id, modified_at);

CREATE TABLE IF NOT EXISTS comments (
    comment_key TEXT PRIMARY KEY,
    corpus_id TEXT NOT NULL REFERENCES source_containers(corpus_id) ON DELETE CASCADE,
    provider TEXT,
    native_comment_id TEXT,
    parent_comment_key TEXT REFERENCES comments(comment_key),
    author_display_name TEXT,
    author_native_id TEXT,
    author_is_self INTEGER,
    created_at TEXT,
    modified_at TEXT,
    resolved INTEGER,
    deleted INTEGER,
    quoted_context TEXT,
    content TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_comments_corpus
ON comments(corpus_id, created_at);

CREATE TABLE IF NOT EXISTS assets (
    asset_key TEXT PRIMARY KEY,
    corpus_id TEXT NOT NULL REFERENCES source_containers(corpus_id) ON DELETE CASCADE,
    provider_revision_id TEXT,
    filename TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    sha256 TEXT NOT NULL,
    repo_path TEXT NOT NULL,
    native_locator TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_assets_corpus
ON assets(corpus_id);

CREATE TABLE IF NOT EXISTS source_links (
    source_link_id INTEGER PRIMARY KEY,
    from_corpus_id TEXT NOT NULL REFERENCES source_containers(corpus_id) ON DELETE CASCADE,
    link_type TEXT NOT NULL,
    to_corpus_id TEXT REFERENCES source_containers(corpus_id) ON DELETE CASCADE,
    external_locator TEXT,
    basis TEXT,
    confidence TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_links_from
ON source_links(from_corpus_id);

CREATE TABLE IF NOT EXISTS ingest_warnings (
    warning_id INTEGER PRIMARY KEY,
    ingest_run_id TEXT REFERENCES ingest_runs(ingest_run_id),
    corpus_id TEXT REFERENCES source_containers(corpus_id),
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS source_fts USING fts5(
    corpus_id UNINDEXED,
    title,
    body
);

CREATE VIRTUAL TABLE IF NOT EXISTS revision_fts USING fts5(
    corpus_id UNINDEXED,
    provider_revision_id UNINDEXED,
    body
);

CREATE VIRTUAL TABLE IF NOT EXISTS comments_fts USING fts5(
    corpus_id UNINDEXED,
    comment_key UNINDEXED,
    content,
    quoted_context
);

-- Rebuild/populate FTS explicitly during ingestion from canonical tables.
-- Do not rely on FTS as the only surviving text representation.
--
-- Pre-merge validation must include:
--   PRAGMA integrity_check;
--   PRAGMA foreign_key_check;
