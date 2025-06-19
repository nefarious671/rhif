import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    fields = [
        'conv_id', 'turn', 'role', 'date', 'text',
        'summary', 'keywords', 'tags', 'tokens'
    ]
    row = {k: row.get(k) for k in fields}
    placeholders = ','.join('?' for _ in fields)
    sql = f"INSERT INTO rsp ({','.join(fields)}) VALUES ({placeholders})"
    with get_db() as conn:
        cur = conn.execute(sql, [row[k] for k in fields])
        rowid = cur.lastrowid
        conn.execute(
            "INSERT INTO rsp_fts(rowid, text, summary, keywords) VALUES (?,?,?,?)",
            (rowid, row['text'], row['summary'], row['keywords'])
        )
        conn.commit()
    return rowid


def search_rsps(query: str, tags: Optional[List[str]] = None, limit: int = 10) -> List[Dict[str, Any]]:
    sql = (
        "SELECT id, conv_id, turn, role, date, text, summary, keywords, tags, tokens "
        "FROM rsp_fts JOIN rsp ON rsp_fts.rowid = rsp.id "
        "WHERE rsp_fts MATCH ?"
    )
    params: List[Any] = [query]
    if tags:
        tag_clause = ' AND '.join(["json_extract(tags, '$') LIKE ?" for _ in tags])
        sql += f" AND {tag_clause}"
        params += [f'%{t}%' for t in tags]
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = execute(sql, *params)
    return [dict(r) for r in rows]
