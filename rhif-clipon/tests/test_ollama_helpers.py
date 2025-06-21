import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hub.ollama_helpers import _extract_json


def test_extract_json_direct():
    txt = '{"summary":"ok","keywords":[],"domain":"a","topic":"b","conversation_type":"c","emotion":"d","novelty":0}'
    data = _extract_json(txt)
    assert data['summary'] == 'ok'


def test_extract_json_with_text():
    txt = '{"summary":"ok","keywords":[],"domain":"a","topic":"b","conversation_type":"c","emotion":"d","novelty":0}'
    resp = "Here is the summary:\n" + txt
    data = _extract_json(resp)
    assert data['topic'] == 'b'


def test_extract_json_code_fence():
    txt = '{"summary":"ok","keywords":[],"domain":"a","topic":"b","conversation_type":"c","emotion":"d","novelty":0}'
    resp = "Response:\n```json\n" + txt + "\n```"
    data = _extract_json(resp)
    assert data['novelty'] == 0
