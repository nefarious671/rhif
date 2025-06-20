import json
import sqlite3
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from rhif_utils import canonical_json, rsp_hash, flatten_meta, canonical_keyword_list

from flask import current_app

_MEM_CONN: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
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
    with get_db() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.fetchall()


def insert_rsp(row: Dict[str, Any]) -> int:
    """Insert an RSP row and its meta index."""
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
            (rowid, row['text'], row['summary'], row['keywords'])
        )
        conn.execute(
            "INSERT OR IGNORE INTO rsp_keyword_xref(rsp_id, keyword_set_id) VALUES (?, ?)",
            (rowid, kw_id)
        )
        # index meta
        for idx in flatten_meta(row['hash'], meta_pairs, json.loads(row.get('children', '[]') or '[]')):
            if idx['dimension'] == 'word':  # rely on FTS for word search
                continue
            try:
                conn.execute(
                    "INSERT INTO rsp_index(hash, dimension, value, dimension_hash, context_path) VALUES (?,?,?,?,?)",
                    (idx['hash'], idx['dimension'], idx['value'], idx['dimension_hash'], idx['context_path'])
                )
            except sqlite3.IntegrityError:
                # duplicate index row
                continue
        conn.commit()
    return rowid


def search_rsps(query: str,
                tags: Optional[List[str]] = None,
                limit: int = 10,
                domain: Optional[str] = None,
                topic: Optional[str] = None,
                keywords: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search RSPs using FTS with optional tag, keyword and axis filters."""
    sql = (
        "SELECT rsp.id, rsp.conv_id, rsp.turn, rsp.role, rsp.date, rsp.text, "
        "rsp.summary, rsp.keywords, rsp.tags, rsp.tokens, rsp.domain, rsp.topic "
        "FROM rsp_fts JOIN rsp ON rsp_fts.rowid = rsp.id "
    )
    if keywords:
        sql += (
            "JOIN rsp_keyword_xref rx ON rx.rsp_id = rsp.id "
            "JOIN keyword_set_fts ON keyword_set_fts.rowid = rx.keyword_set_id "
        )
    sql += "WHERE rsp_fts MATCH ?"
    params: List[Any] = [query]
    if keywords:
        sql += " AND (keyword_set_fts MATCH ?)"
        params.append(keywords)
    if tags:
        tag_clause = ' AND '.join(["json_extract(tags, '$') LIKE ?" for _ in tags])
        sql += f" AND {tag_clause}"
        params += [f'%{t}%' for t in tags]
    if domain:
        sql += " AND domain = ?"
        params.append(domain)
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = execute(sql, *params)
    return [dict(r) for r in rows]
