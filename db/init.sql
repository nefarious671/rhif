-- Schema for RHIF v2

-- 1-A Lookup table for repeated axis values
CREATE TABLE IF NOT EXISTS dim_value (
  id        INTEGER PRIMARY KEY,
  dimension TEXT NOT NULL,
  value     TEXT NOT NULL,
  UNIQUE(dimension,value)
);

-- 1-B rsp table additions
ALTER TABLE rsp
  ADD COLUMN domain_id INT;
ALTER TABLE rsp
  ADD COLUMN topic_id INT;
ALTER TABLE rsp
  ADD COLUMN convtype_id INT;
ALTER TABLE rsp
  ADD COLUMN emotion_id INT;

-- 1-D Re-create FTS tables without keywords and using trigram tokenizer
DROP TABLE IF EXISTS rsp_fts;
CREATE VIRTUAL TABLE rsp_fts
  USING fts5(
    text,
    summary,
    tokenize = 'trigram',
    content = 'rsp',
    content_rowid = 'id'
  );

DROP TABLE IF EXISTS keyword_set_fts;
CREATE VIRTUAL TABLE keyword_set_fts
  USING fts5(keywords_json, tokenize='trigram');

-- Covering indices for dimensions
CREATE INDEX IF NOT EXISTS rsp_domain_idx    ON rsp(domain_id);
CREATE INDEX IF NOT EXISTS rsp_topic_idx     ON rsp(topic_id);
CREATE INDEX IF NOT EXISTS rsp_convtype_idx  ON rsp(convtype_id);
CREATE INDEX IF NOT EXISTS rsp_emotion_idx   ON rsp(emotion_id);
