"""One-off migration to RHIF schema v2.

Steps:
 1. Apply schema changes (dim_value table, FK cols, new FTS tables).
 2. Populate FK columns from existing text values.
 3. Rebuild FTS tables and vacuum the database.

Run once:
    python migrate_v2.py ./rhif.sqlite
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from tqdm import tqdm


def _dim_id(cur: sqlite3.Cursor, dim: str, val: str | None) -> int | None:
    if not val:
        return None
    cur.execute(
        "INSERT OR IGNORE INTO dim_value(dimension,value) VALUES (?,?)",
        (dim, val),
    )
    return cur.execute(
        "SELECT id FROM dim_value WHERE dimension=? AND value=?",
        (dim, val),
    ).fetchone()[0]


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dim_value (
  id        INTEGER PRIMARY KEY,
  dimension TEXT NOT NULL,
  value     TEXT NOT NULL,
  UNIQUE(dimension,value)
);
"""


def migrate(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # basic table for dimension lookups
    cur.executescript(SCHEMA_SQL)

    # add new FK columns if they are missing
    cols = [r[1] for r in cur.execute("PRAGMA table_info(rsp)")]
    for col in ("domain_id", "topic_id", "convtype_id", "emotion_id"):
        if col not in cols:
            cur.execute(f"ALTER TABLE rsp ADD COLUMN {col} INT")

    # (re)create FTS tables and indices
    cur.execute("DROP TABLE IF EXISTS rsp_fts")
    cur.execute(
        """CREATE VIRTUAL TABLE rsp_fts USING fts5(
            text,
            summary,
            tokenize='trigram',
            content='rsp',
            content_rowid='id'
        )"""
    )
    cur.execute("DROP TABLE IF EXISTS keyword_set_fts")
    cur.execute(
        "CREATE VIRTUAL TABLE keyword_set_fts USING fts5(keywords_json, tokenize='trigram')"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS rsp_domain_idx ON rsp(domain_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS rsp_topic_idx ON rsp(topic_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS rsp_convtype_idx ON rsp(convtype_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS rsp_emotion_idx ON rsp(emotion_id)")

    rows = cur.execute(
        "SELECT id, domain, topic, conversation_type, emotion FROM rsp"
    ).fetchall()
    for r in tqdm(rows, desc="rsp"):
        d = _dim_id(cur, "domain", r[1])
        t = _dim_id(cur, "topic", r[2])
        c = _dim_id(cur, "conversation_type", r[3])
        e = _dim_id(cur, "emotion", r[4])
        cur.execute(
            "UPDATE rsp SET domain_id=?, topic_id=?, convtype_id=?, emotion_id=?,"
            " domain=NULL, topic=NULL, conversation_type=NULL, emotion=NULL WHERE id=?",
            (d, t, c, e, r[0]),
        )

    # rebuild FTS table from scratch
    for rid, text, summary in tqdm(
        cur.execute("SELECT id, text, summary FROM rsp"), desc="fts rebuild"
    ):
        cur.execute(
            "INSERT INTO rsp_fts(rowid, text, summary) VALUES (?,?,?)",
            (rid, text, summary),
        )

    conn.commit()
    cur.execute("VACUUM")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    db_file = Path(sys.argv[1] if len(sys.argv) > 1 else "./rhif.sqlite")
    migrate(db_file)
