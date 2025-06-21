import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hub'))
from db import execute, insert_rsp, search_rsps
from rhif_utils import canonical_json
from flask import Flask


app = Flask(__name__)
app.config['DB_PATH'] = ':memory:'


with app.app_context():
    execute("""CREATE TABLE rsp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hash TEXT,
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
    )""")
    execute("CREATE VIRTUAL TABLE rsp_fts USING fts5(text, summary, keywords, content='rsp', content_rowid='id')")
    execute("""CREATE TABLE rsp_index(
        hash TEXT,
        dimension TEXT,
        value TEXT,
        dimension_hash TEXT,
        context_path TEXT,
        UNIQUE(hash, dimension, value)
    )""")
    execute("CREATE INDEX rsp_domain_idx ON rsp(domain)")
    execute("CREATE INDEX rsp_topic_idx ON rsp(topic)")
    execute("CREATE INDEX idx_keywords_json ON rsp(json_extract(keywords, '$'))")
    execute("CREATE TABLE keyword_set (id INTEGER PRIMARY KEY AUTOINCREMENT, kw_hash TEXT UNIQUE, keywords_json TEXT)")
    execute("CREATE VIRTUAL TABLE keyword_set_fts USING fts5(keywords_json)")
    execute("CREATE TABLE rsp_keyword_xref(rsp_id INT, keyword_set_id INT, PRIMARY KEY(rsp_id, keyword_set_id))")

def test_insert_and_search():
    with app.app_context():
        rowid = insert_rsp({'conv_id':'1','turn':1,'role':'user','date':'2024-01-01','text':'hello','summary':'hi','keywords':'["hi"]','tags':'[]','tokens':1,'domain':'test','topic':'unit'})
        res = search_rsps('hello', [], 10)
        assert len(res) == 1
        assert res[0]['id'] == rowid
        stored_kw = execute("SELECT keywords FROM rsp WHERE id=?", rowid)[0]['keywords']
        assert stored_kw is None

def test_keyword_canonicalisation_and_search():
    from rhif_utils import canonical_keyword_list
    with app.app_context():
        rowid = insert_rsp({'conv_id':'2','turn':1,'role':'user','date':'2024-01-01',
                             'text':'foo','summary':'bar','keywords':'["A","b","a"]',
                             'tags':'[]','tokens':1,'domain':'test','topic':'unit'})
        kw_row = execute("SELECT keyword_set_id FROM rsp_keyword_xref WHERE rsp_id=?", rowid)[0]
        kw_json = execute("SELECT keywords_json FROM keyword_set WHERE id=?", kw_row['keyword_set_id'])[0]['keywords_json']
        assert kw_json == canonical_json(canonical_keyword_list(['A','b','a']))
        res = search_rsps('foo', [], 10, keywords='a')
        assert any(r['id'] == rowid for r in res)


def test_search_date_range():
    with app.app_context():
        insert_rsp({'conv_id':'3','turn':1,'role':'user','date':'2024-01-02',
                    'text':'later','summary':'','keywords':'[]','tags':'[]','tokens':1,
                    'domain':'test','topic':'date'})
        insert_rsp({'conv_id':'3','turn':2,'role':'user','date':'2024-01-05',
                    'text':'latest','summary':'','keywords':'[]','tags':'[]','tokens':1,
                    'domain':'test','topic':'date'})
        res = search_rsps('late*', [], 10, start='2024-01-03', end='2024-01-06')
        assert len(res) == 1
        assert res[0]['text'] == 'latest'


def test_insert_strips_date_quotes():
    with app.app_context():
        rowid = insert_rsp({'conv_id':'4','turn':1,'role':'user',
                            'date':'"2024-02-02"',
                            'text':'quoted','summary':'','keywords':'[]',
                            'tags':'[]','tokens':1,
                            'domain':'test','topic':'quotes'})
        stored = execute("SELECT date FROM rsp WHERE id=?", rowid)[0]['date']
        assert stored == '2024-02-02'
        res = search_rsps('quoted', [], 10, start='2024-02-01', end='2024-02-03')
        assert len(res) == 1

