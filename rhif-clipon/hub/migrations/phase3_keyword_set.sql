-- Phase 3 migration for keyword_set deduplication
BEGIN;
CREATE TABLE IF NOT EXISTS keyword_set(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kw_hash TEXT UNIQUE,
  keywords_json TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS keyword_set_fts USING fts5(keywords_json);
CREATE TABLE IF NOT EXISTS rsp_keyword_xref(
  rsp_id INT,
  keyword_set_id INT,
  PRIMARY KEY(rsp_id, keyword_set_id)
);
--
-- Migrate existing keyword JSON into the new tables.
-- The kw_hash should be SHA-256 of the canonical keyword JSON
-- (lowercase, deduplicated and sorted).
-- Example Python logic:
--   kw_list = canonical_keyword_list(json.loads(rsp.keywords or "[]"))
--   kw_json = canonical_json(kw_list)
--   kw_hash = hashlib.sha256(kw_json.encode()).hexdigest()
--   INSERT OR IGNORE INTO keyword_set(kw_hash, keywords_json) VALUES(kw_hash, kw_json);
--   INSERT OR IGNORE INTO rsp_keyword_xref(rsp_id, (SELECT id FROM keyword_set WHERE kw_hash=kw_hash));
-- After migration clear legacy column:
UPDATE rsp SET keywords=NULL;
COMMIT;
