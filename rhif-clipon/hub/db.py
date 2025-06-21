"""Database helpers for storing and querying RHIF packets.

Schema overview
----------------
Tables:
  - ``rsp``: main packet store.
  - ``rsp_fts``: FTS5 virtual table (text, summary) linked to ``rsp``.
  - ``rsp_index``: flattened metadata for fast filtering.
  - ``keyword_set``/``keyword_set_fts`` and ``rsp_keyword_xref``: deduplicated
    keyword lists with FTS search.

Important indices are created on ``rsp.domain`` and ``rsp.topic``.
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
              domain TEXT,
              topic TEXT,
              conversation_type TEXT,
              emotion TEXT,
              novelty INTEGER
            )"""
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS rsp_fts USING fts5(text, summary, keywords, content='rsp', content_rowid='id')"
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
        conn.execute("CREATE INDEX IF NOT EXISTS rsp_domain_idx ON rsp(domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS rsp_topic_idx ON rsp(topic)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS keyword_set(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              kw_hash TEXT UNIQUE,
              keywords_json TEXT
            )"""
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS keyword_set_fts USING fts5(keywords_json)"
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


def insert_rsp(row: Dict[str, Any]) -> int:
    """Insert a response packet and create all related index entries."""
    base_fields = [
        'conv_id', 'turn', 'role', 'date', 'text',
        'summary', 'keywords', 'tags', 'tokens',
        'meta', 'children', 'domain', 'topic',
        'conversation_type', 'emotion', 'novelty', 'hash'
    ]
    row = {k: row.get(k) for k in base_fields}

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

    row['hash'] = row.get('hash') or rsp_hash(row.get('text', ''), meta_pairs, json.loads(row.get('children', '[]') or '[]'))

    placeholders = ','.join('?' for _ in base_fields)
    sql = f"""
    INSERT OR IGNORE INTO rsp ({', '.join(base_fields)})
    VALUES ({', '.join(['?'] * len(base_fields))})
    """
    with get_db() as conn:
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
            "INSERT INTO rsp_fts(rowid, text, summary, keywords) VALUES (?,?,?,?)",
            (rowid, row['text'], row['summary'], '')
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


def search_rsps(query: str,
                tags: Optional[List[str]] = None,
                limit: int = 10,
                domain: Optional[str] = None,
                topic: Optional[str] = None,
                keywords: Optional[str] = None,
                conv_id: Optional[str] = None,
                emotion: Optional[str] = None,
                start: Optional[str] = None,
                end: Optional[str] = None,
                slow: bool = False) -> List[Dict[str, Any]]:
    """Search stored packets using FTS and keyword/axis filters."""
    if not query.strip():
        return []
    base = (
        "SELECT rsp.id, rsp.conv_id, rsp.turn, rsp.role, rsp.date, rsp.text, "
        "rsp.summary, rsp.keywords, rsp.tags, rsp.tokens, rsp.domain, rsp.topic, "
    )
    if slow:
        sql = base + "0 AS rank FROM rsp "
    else:
        sql = base + "bm25(rsp_fts) AS rank FROM rsp_fts JOIN rsp ON rsp_fts.rowid = rsp.id "
    if keywords:
        sql += (
            "JOIN rsp_keyword_xref rx ON rx.rsp_id = rsp.id "
            "JOIN keyword_set_fts ON keyword_set_fts.rowid = rx.keyword_set_id "
        )
    if slow:
        sql += "WHERE rsp.text LIKE ?"
        params: List[Any] = [f"%{query}%"]
    else:
        sql += "WHERE rsp_fts MATCH ?"
        params: List[Any] = [query]
    if keywords:
        sql += " AND (keyword_set_fts MATCH ?)"
        params.append(keywords)
    if tags:
        placeholders = ' AND '.join([
            "EXISTS (SELECT 1 FROM json_each(rsp.tags) WHERE value = ?)" for _ in tags
        ])
        sql += f" AND {placeholders}"
        params.extend(tags)
    if domain:
        sql += " AND domain = ?"
        params.append(domain)
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    if conv_id:
        sql += " AND conv_id = ?"
        params.append(conv_id)
    if emotion:
        sql += " AND emotion = ?"
        params.append(emotion)
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    sql += " ORDER BY rank, rsp.id DESC LIMIT ?"
    params.append(limit)
    rows = execute(sql, *params)
    return [dict(r) for r in rows]
