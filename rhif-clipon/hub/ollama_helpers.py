import json
import os
from typing import Dict, List, Tuple

import ollama


MAX_PROMPT_CHARS = int(os.getenv("OLLAMA_MAX_PROMPT", "32000"))


def _summarise_once(
    text: str,
    model: str,
    kw_count: int,
    summary_tokens: int,
) -> Tuple[str, List[str], Dict[str, str]]:
    prompt = (
        "You are a summarization assistant.\n"
        f"TASK A – Summarize the message below in at most {summary_tokens} words.\n"
        f"TASK B – Output exactly {kw_count} lowercase, single-word keywords, comma-separated.\n"
        "TASK C – Provide metadata fields: domain, topic, conversation_type, emotion, novelty (0 to 1).\n"
        "Respond ONLY with valid JSON in this exact format:\n"
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
    except Exception as e:
        print(f"Warning: failed to parse ollama JSON: {e}")
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


def summarise_and_keywords(
    text: str,
    model: str,
    kw_count: int,
    summary_tokens: int,
) -> Tuple[str, List[str], Dict[str, str]]:
    if len(text) <= MAX_PROMPT_CHARS:
        return _summarise_once(text, model, kw_count, summary_tokens)

    chunk_size = MAX_PROMPT_CHARS - 1000
    chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    partial_summaries = [
        _summarise_once(c, model, kw_count, summary_tokens)[0] for c in chunks
    ]
    combined = "\n".join(partial_summaries)
    return _summarise_once(combined, model, kw_count, summary_tokens)
