import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hub'))
from db import execute, insert_rsp, search_rsps
from flask import Flask


app = Flask(__name__)
app.config['DB_PATH'] = ':memory:'


with app.app_context():
    execute("""CREATE TABLE rsp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conv_id TEXT,
        turn INTEGER,
        role TEXT,
        date TEXT,
        text TEXT,
        summary TEXT,
        keywords TEXT,
        tags TEXT,
        tokens INTEGER
    )""")
    execute("CREATE VIRTUAL TABLE rsp_fts USING fts5(text, summary, keywords, content='rsp', content_rowid='id')")

def test_insert_and_search():
    with app.app_context():
        rowid = insert_rsp({'conv_id':'1','turn':1,'role':'user','date':'2024-01-01','text':'hello','summary':'hi','keywords':'["hi"]','tags':'[]','tokens':1})
        res = search_rsps('hello', [], 10)
        assert len(res) == 1
        assert res[0]['id'] == rowid

