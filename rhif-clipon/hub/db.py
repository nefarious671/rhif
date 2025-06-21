"""Database helpers for storing and querying RHIF packets.

Schema overview
----------------
Tables:
  - ``rsp``: main packet store.
  - ``rsp_fts``: FTS5 virtual table (text, summary) linked to ``rsp``.
  - ``rsp_index``: flattened metadata for fast filtering.
  - ``keyword_set``/``keyword_set_fts`` and ``rsp_keyword_xref``: deduplicated
    keyword lists with FTS search.
  - ``dim_value``: lookup table for dimension text values.

Important indices are created on the FK columns.
"""

import json
import sqlite3
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from rhif_utils import canonical_json, rsp_hash, flatten_meta, canonical_keyword_list

from flask import current_app

_MEM_CONN: sqlite3.Connection | None = None


def ensure_schema() -> None:
    """Create required tables and indices if they do not already exist."""
    with get_db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS dim_value (
              id        INTEGER PRIMARY KEY,
              dimension TEXT NOT NULL,
              value     TEXT NOT NULL,
              UNIQUE(dimension,value)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rsp (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              hash TEXT UNIQUE,
              conv_id TEXT,
              turn INTEGER,
              role TEXT,
              date TEXT,
              text TEXT,
              summary TEXT,
              keywords TEXT,
              tags TEXT,
              tokens INTEGER,
              meta TEXT,
              children TEXT,
              novelty INTEGER,
              domain_id INT,
              topic_id INT,
              convtype_id INT,
              emotion_id INT
            )"""
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS rsp_fts USING fts5(text, summary, tokenize='trigram', content='rsp', content_rowid='id')"
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rsp_index (
              hash TEXT,
              dimension TEXT,
              value TEXT,
              dimension_hash TEXT,
              context_path TEXT,
              UNIQUE(hash, dimension, value)
            )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS rsp_domain_idx ON rsp(domain_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS rsp_topic_idx ON rsp(topic_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS rsp_convtype_idx ON rsp(convtype_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS rsp_emotion_idx ON rsp(emotion_id)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS keyword_set(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              kw_hash TEXT UNIQUE,
              keywords_json TEXT
            )"""
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS keyword_set_fts USING fts5(keywords_json, tokenize='trigram')"
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rsp_keyword_xref(
              rsp_id INT,
              keyword_set_id INT,
              PRIMARY KEY(rsp_id, keyword_set_id)
            )"""
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_keyword_set_hash ON keyword_set(kw_hash)"
        )
        conn.commit()


def get_db() -> sqlite3.Connection:
    """Return a connection to the configured SQLite database."""
    db_path = Path(current_app.config.get('DB_PATH', './rhif.sqlite'))
    if str(db_path) == ':memory:':
        global _MEM_CONN
        if _MEM_CONN is None:
            _MEM_CONN = sqlite3.connect(':memory:')
            _MEM_CONN.row_factory = sqlite3.Row
        return _MEM_CONN
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def execute(sql: str, *params) -> List[sqlite3.Row]:
    """Execute an SQL statement and return all fetched rows."""
    with get_db() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.fetchall()


def _dim_id(cur: sqlite3.Cursor, dim: str, val: str | None) -> Optional[int]:
    """Return ID for *val* in ``dim_value`` inserting if needed."""
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


def insert_rsp(row: Dict[str, Any]) -> int:
    """Insert a response packet and create all related index entries."""
    base_fields = [
        'conv_id', 'turn', 'role', 'date', 'text',
        'summary', 'keywords', 'tags', 'tokens',
        'meta', 'children', 'domain_id', 'topic_id',
        'convtype_id', 'emotion_id', 'novelty', 'hash'
    ]
    row = {k: row.get(k) for k in base_fields + ['domain','topic','conversation_type','emotion']}

    if row.get('date'):
        row['date'] = str(row['date']).strip('"\'')[:10]

    if row.get('novelty') is not None:
        row['novelty'] = round(float(row['novelty']), 2)

    kw_list = canonical_keyword_list(json.loads(row.get('keywords') or '[]'))
    kw_json = canonical_json(kw_list)
    kw_hash = hashlib.sha256(kw_json.encode()).hexdigest()
    row['keywords'] = None  # legacy field stored as NULL

    # build meta pairs from hot axes if meta not provided
    meta_pairs: List[Dict[str, Any]] = []
    for axis in ['domain', 'topic', 'conversation_type', 'emotion', 'novelty']:
        if row.get(axis):
            meta_pairs.append({'dimension': axis, 'value': row[axis]})
    if row.get('meta'):
        meta_pairs.extend(json.loads(row['meta']))
    row['meta'] = json.dumps(meta_pairs)

    row['hash'] = row.get('hash') or rsp_hash(
        row.get('text', ''), meta_pairs, json.loads(row.get('children', '[]') or '[]')
    )

    placeholders = ','.join('?' for _ in base_fields)
    sql = f"""
    INSERT OR IGNORE INTO rsp ({', '.join(base_fields)})
    VALUES ({', '.join(['?'] * len(base_fields))})
    """
    with get_db() as conn:
        cur = conn.cursor()
        row['domain_id'] = _dim_id(cur, 'domain', row.pop('domain', None))
        row['topic_id'] = _dim_id(cur, 'topic', row.pop('topic', None))
        row['convtype_id'] = _dim_id(cur, 'conversation_type', row.pop('conversation_type', None))
        row['emotion_id'] = _dim_id(cur, 'emotion', row.pop('emotion', None))

        # keyword set handling
        cur = conn.execute("SELECT id FROM keyword_set WHERE kw_hash=?", (kw_hash,))
        row_kw = cur.fetchone()
        if row_kw:
            kw_id = row_kw['id']
        else:
            try:
                cur = conn.execute(
                    "INSERT INTO keyword_set(kw_hash, keywords_json) VALUES (?,?)",
                    (kw_hash, kw_json)
                )
                kw_id = cur.lastrowid
                conn.execute(
                    "INSERT INTO keyword_set_fts(rowid, keywords_json) VALUES (?,?)",
                    (kw_id, kw_json)
                )
            except sqlite3.IntegrityError:
                kw_id = conn.execute(
                    "SELECT id FROM keyword_set WHERE kw_hash=?", (kw_hash,)
                ).fetchone()[0]

        cur = conn.execute(sql, [row[k] for k in base_fields])
        rowid = cur.lastrowid
        if rowid is None:
            raise RuntimeError("Failed to insert RSP row: lastrowid is None")
        conn.execute(
            "INSERT INTO rsp_fts(rowid, text, summary) VALUES (?,?,?)",
            (rowid, row['text'], row['summary'])
        )
        conn.execute(
            "INSERT OR IGNORE INTO rsp_keyword_xref(rsp_id, keyword_set_id) VALUES (?, ?)",
            (rowid, kw_id)
        )
        # index meta
        meta_rows = [
            (idx['hash'], idx['dimension'], idx['value'], idx['dimension_hash'], idx['context_path'])
            for idx in flatten_meta(row['hash'], meta_pairs, json.loads(row.get('children', '[]') or '[]'))
            if idx['dimension'] != 'word'
        ]
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO rsp_index(hash,dimension,value,dimension_hash,context_path) VALUES (?,?,?,?,?)",
                meta_rows
            )
        except sqlite3.IntegrityError:
            pass
        conn.commit()
    return rowid


def search_rsps(
    query: str,
    tags: Optional[List[str]] = None,
    limit: int = 10,
    domain: Optional[str] = None,
    topic: Optional[str] = None,
    keywords: Optional[str] = None,
    conv_id: Optional[str] = None,
    emotion: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    slow: bool = False,
) -> List[Dict[str, Any]]:
    """Search stored packets using FTS5 MATCH with optional filters."""
    if not query.strip():
        return []

    sql = (
        "SELECT rsp.id, rsp.conv_id, rsp.turn, rsp.role, rsp.date, rsp.text, "
        "rsp.summary, rsp.keywords, rsp.tags, rsp.tokens, "
        "d1.value AS domain, d2.value AS topic, "
        "d3.value AS conversation_type, d4.value AS emotion, rsp.novelty "
        "FROM (SELECT rowid, bm25(rsp_fts) AS rank FROM rsp_fts WHERE rsp_fts MATCH ? ORDER BY rank) f "
        "JOIN rsp ON rsp.id = f.rowid "
    )

    params: List[Any] = [query]
    if keywords:
        sql += (
            "JOIN rsp_keyword_xref rx ON rx.rsp_id = rsp.id "
            "JOIN keyword_set_fts ON keyword_set_fts.rowid = rx.keyword_set_id "
        )

    sql += (
        "LEFT JOIN dim_value d1 ON d1.id = rsp.domain_id "
        "LEFT JOIN dim_value d2 ON d2.id = rsp.topic_id "
        "LEFT JOIN dim_value d3 ON d3.id = rsp.convtype_id "
        "LEFT JOIN dim_value d4 ON d4.id = rsp.emotion_id "
        "WHERE 1=1 "
    )

    if keywords:
        sql += "AND keyword_set_fts MATCH ? "
        params.append(keywords)
    if tags:
        placeholders = " AND ".join(
            ["EXISTS (SELECT 1 FROM json_each(rsp.tags) WHERE value = ?)"] * len(tags)
        )
        sql += f"AND {placeholders} "
        params.extend(tags)
    if domain:
        sql += "AND d1.value = ? "
        params.append(domain)
    if topic:
        sql += "AND d2.value = ? "
        params.append(topic)
    if conv_id:
        sql += "AND rsp.conv_id = ? "
        params.append(conv_id)
    if emotion:
        sql += "AND d4.value = ? "
        params.append(emotion)
    if start:
        sql += "AND rsp.date >= ? "
        params.append(start)
    if end:
        sql += "AND rsp.date <= ? "
        params.append(end)

    sql += "ORDER BY f.rank, rsp.id DESC LIMIT ?"
    params.append(limit)

    rows = execute(sql, *params)
    return [dict(r) for r in rows]


def fetch_conversation(conv_id: str) -> List[Dict[str, Any]]:
    """Return all packets for a conversation ordered by turn."""
    rows = execute(
        "SELECT * FROM rsp WHERE conv_id = ? ORDER BY turn",
        conv_id,
    )
    return [dict(r) for r in rows]
