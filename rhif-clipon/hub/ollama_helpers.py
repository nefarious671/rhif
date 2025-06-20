import json
from typing import Dict, List, Tuple

import ollama


def summarise_and_keywords(
    text: str,
    model: str,
    kw_count: int,
    summary_tokens: int
) -> Tuple[str, List[str], Dict[str, str]]:
    prompt = (
        "You are a summarization assistant.\n"
        f"TASK A – Summarize the message below in at most {summary_tokens} words.\n"
        f"TASK B – Output exactly {kw_count} lowercase, single-word keywords, comma-separated.\n"
        "TASK C – Provide metadata fields: domain, topic, conversation_type, emotion, novelty (0 to 1).\n"
        "Respond only in valid JSON:\n"
        '{ "summary": "...", "keywords": ["kw1","kw2"], "domain": "...", "topic": "...", '
        '"conversation_type": "...", "emotion": "...", "novelty": 1 }\n'
        'MESSAGE:\n"""' + text + '"""'
    )

    response = ollama.generate(
        model=model,
        prompt=prompt,
        options={"temperature": 0.3},
        stream=False
    )

    raw_resp = response.response if hasattr(response, "response") else response
    if isinstance(raw_resp, dict):
        raw_resp = raw_resp.get('response', '')
    if not isinstance(raw_resp, str):
        raw_resp = str(raw_resp)

    try:
        data = json.loads(raw_resp)
    except json.JSONDecodeError:
        return "", [], {}

    summary = data.get('summary', '').strip()
    keywords = data.get('keywords', [])
    if isinstance(keywords, str):
        keywords = [k.strip().lower() for k in keywords.split(',') if k.strip()]
    else:
        keywords = [k.lower() for k in keywords if isinstance(k, str)]

    meta = {
        'domain': data.get('domain', '').strip().lower(),
        'topic': data.get('topic', '').strip().lower(),
        'conversation_type': data.get('conversation_type', '').strip().lower(),
        'emotion': data.get('emotion', '').strip().lower(),
        'novelty': float(data.get('novelty', 0))
    }

    return summary, keywords, meta
