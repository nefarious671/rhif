from __future__ import annotations

import json
import os
from datetime import date

from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from db import execute, insert_rsp, search_rsps
from ollama_helpers import summarise_and_keywords
from code_utils import extract_markdown_blocks, save_blocks


load_dotenv()

app = Flask(__name__, template_folder='templates')
CORS(app, origins=['chrome-extension://*'])

app.config.update(
    OLLAMA_MODEL=os.getenv('OLLAMA_MODEL', 'llama3:8b-q5'),
    HUB_PORT=int(os.getenv('HUB_PORT', 8765)),
    DB_PATH=os.getenv('DB_PATH', './rhif.sqlite'),
    WORKSPACE_DIR=os.getenv('WORKSPACE_DIR', './workspace'),
    SUMMARY_TOKENS=int(os.getenv('SUMMARY_TOKENS', 120)),
    KEYWORD_COUNT=int(os.getenv('KEYWORD_COUNT', 8)),
)


@app.route('/summarise', methods=['POST'])
def summarise_route():
    data = request.get_json(force=True)
    summary, keywords, meta = summarise_and_keywords(
        data.get('text', ''),
        app.config['OLLAMA_MODEL'],
        app.config['KEYWORD_COUNT'],
        app.config['SUMMARY_TOKENS'],
    )
    return jsonify({'summary': summary, 'keywords': keywords, 'meta': meta})


@app.route('/ingest', methods=['POST'])
def ingest_route():
    data = request.get_json(force=True)
    tags = data.get('tags', ['#legacy'])
    row = {
        'conv_id': data['conv_id'],
        'turn': data['turn'],
        'role': data['role'],
        'date': data.get('date') or date.today().isoformat(),
        'text': data['text'],
        'tags': json.dumps(tags),
        'summary': None,
        'keywords': None,
        'tokens': len(data['text'].split()),
    }
    row['summary'], kw, meta = summarise_and_keywords(
        row['text'],
        app.config['OLLAMA_MODEL'],
        app.config['KEYWORD_COUNT'],
        app.config['SUMMARY_TOKENS'],
    )
    row['keywords'] = json.dumps(kw)
    row.update(meta)
    rowid = insert_rsp(row)
    return jsonify({'ok': True, 'id': rowid})


@app.route('/search', methods=['GET'])
def search_route():
    query = request.args.get('q', '')
    tags = request.args.get('tags', '')
    limit = int(request.args.get('limit', 10))
    domain = request.args.get('domain')
    topic = request.args.get('topic')
    tag_list = [t.strip() for t in tags.split(',') if t.strip()]
    rows = search_rsps(query, tag_list, limit, domain, topic)
    if request.headers.get('Accept') == 'application/json':
        return jsonify(rows)
    return render_template('search.html', rows=rows)


@app.route('/savecode', methods=['POST'])
def savecode_route():
    data = request.get_json(force=True)
    code_md = data.get('code_markdown', '')
    base = data.get('base_filename')
    blocks = extract_markdown_blocks(code_md)
    paths = save_blocks(blocks, app.config['WORKSPACE_DIR'], base)
    return jsonify({'ok': True, 'paths': paths})


@app.route('/health')
def health_route():
    return jsonify({'status': 'alive'})


if __name__ == '__main__':
    from pathlib import Path
    # ensure db exists
    db_path = Path(app.config['DB_PATH'])
    if not db_path.exists():
        with db_path.open('w'):
            pass
        execute(
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
        execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS rsp_fts USING fts5(text, summary, keywords, content='rsp', content_rowid='id')"
        )
        execute(
            """CREATE TABLE IF NOT EXISTS rsp_index (
              hash TEXT,
              dimension TEXT,
              value TEXT,
              dimension_hash TEXT,
              context_path TEXT
            )"""
        )
        execute("CREATE INDEX IF NOT EXISTS idx_keywords_json ON rsp(json_extract(keywords, '$'))")
        execute("CREATE INDEX IF NOT EXISTS idx_tags_json ON rsp(json_extract(tags, '$'))")
    port = app.config['HUB_PORT']
    app.run(host='127.0.0.1', port=port)
