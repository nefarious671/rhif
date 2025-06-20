import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from rhif_utils import canonical_json, rsp_hash, flatten_meta

from flask import current_app


def get_db() -> sqlite3.Connection:
    db_path = Path(current_app.config.get('DB_PATH', './rhif.sqlite'))
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
    sql = f"INSERT INTO rsp ({','.join(base_fields)}) VALUES ({placeholders})"
    with get_db() as conn:
        cur = conn.execute(sql, [row[k] for k in base_fields])
        rowid = cur.lastrowid
        conn.execute(
            "INSERT INTO rsp_fts(rowid, text, summary, keywords) VALUES (?,?,?,?)",
            (rowid, row['text'], row['summary'], row['keywords'])
        )
        # index meta
        for idx in flatten_meta(row['hash'], meta_pairs, json.loads(row.get('children', '[]') or '[]')):
            conn.execute(
                "INSERT INTO rsp_index(hash, dimension, value, dimension_hash, context_path) VALUES (?,?,?,?,?)",
                (idx['hash'], idx['dimension'], idx['value'], idx['dimension_hash'], idx['context_path'])
            )
        conn.commit()
    return rowid


def search_rsps(query: str,
                tags: Optional[List[str]] = None,
                limit: int = 10,
                domain: Optional[str] = None,
                topic: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search RSPs using FTS with optional tag and axis filters."""
    sql = (
        "SELECT rsp.id, rsp.conv_id, rsp.turn, rsp.role, rsp.date, "
        "rsp.text, rsp.summary, rsp.keywords, rsp.tags, rsp.tokens, "
        "rsp.domain, rsp.topic "
        "FROM rsp_fts JOIN rsp ON rsp_fts.rowid = rsp.id "
        "WHERE rsp_fts MATCH ?"
    )
    params: List[Any] = [query]
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
