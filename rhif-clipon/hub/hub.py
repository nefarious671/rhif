"""Flask application serving the RHIF ingestion hub.

This module exposes a small REST API used by the browser extension and
command-line tools. Endpoints provide summarisation of text via an Ollama
model, ingestion of conversation turns, lightweight search and a helper for
saving code blocks from assistant responses.
"""

from __future__ import annotations

import json
import os
from datetime import date
import sqlite3

from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from db import execute, insert_rsp, search_rsps, fetch_conversation
from ollama_helpers import summarise_and_keywords
from code_utils import extract_markdown_blocks, save_blocks


load_dotenv()

app = Flask(__name__, template_folder='templates')
app.url_map.strict_slashes = False  # allow optional trailing slashes
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
    """Return a short summary and keywords for the provided text."""
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
    """Ingest a conversation turn and store its summary and metadata."""
    data = request.get_json(force=True)
    if not data.get('text', '').strip():
        return jsonify({'ok': False, 'error': 'empty text'}), 400
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
    try:
        rowid = insert_rsp(row)
    except sqlite3.IntegrityError:
        return jsonify({'ok': False, 'dup': True}), 409
    return jsonify({'ok': True, 'id': rowid})


@app.route('/search', methods=['GET'])
def search_route():
    """Search the archive using FTS and optional filters."""
    query = request.args.get('q', '')
    tags = request.args.get('tags', '')
    limit = int(request.args.get('limit', 10))
    domain = request.args.get('domain')
    topic = request.args.get('topic')
    conv_id = request.args.get('conv_id')
    emotion = request.args.get('emotion')
    start = request.args.get('start')
    end = request.args.get('end')
    slow = request.args.get('slow') == '1'
    tag_list = [t.strip() for t in tags.split(',') if t.strip()]
    rows = search_rsps(query, tag_list, limit, domain, topic,
                       None, conv_id, emotion, start, end, slow)
    if request.headers.get('Accept') == 'application/json':
        return jsonify(rows)
    return render_template('search.html', rows=rows)


@app.route('/conversation', methods=['GET'])
def conversation_route():
    """Return all packets for a conversation."""
    conv_id = request.args.get('conv_id')
    if not conv_id:
        raise BadRequest('conv_id required')
    rows = fetch_conversation(conv_id)
    return jsonify(rows)


@app.route('/savecode', methods=['POST'])
def savecode_route():
    """Persist code blocks from markdown into the workspace directory."""
    data = request.get_json(force=True)
    code_md = data.get('code_markdown', '')
    base = data.get('base_filename')
    blocks = extract_markdown_blocks(code_md)
    paths = save_blocks(blocks, app.config['WORKSPACE_DIR'], base)
    return jsonify({'ok': True, 'paths': paths})


@app.route('/health')
def health_route():
    """Simple liveness probe used by tests and the extension."""
    return jsonify({'status': 'alive'})


if __name__ == '__main__':
    from db import ensure_schema
    with app.app_context():
        ensure_schema()
    port = app.config['HUB_PORT']
    app.run(host='127.0.0.1', port=port)
