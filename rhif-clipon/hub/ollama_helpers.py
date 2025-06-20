from __future__ import annotations

import json
from typing import Dict, List, Tuple

import ollama


def summarise_and_keywords(text: str, model: str, kw_count: int, summary_tokens: int) -> Tuple[str, List[str], Dict[str, str]]:
    prompt = (
        "You are a summarization assistant.\n"
        f"TASK A \u2013 Summarise the message below in \u2264{summary_tokens} words.\n"
        f"TASK B \u2013 Output exactly {kw_count} lowercase single-word keywords, comma-separated.\n"
        'Respond *only* in JSON:\n'
        '{ "summary": "...", "keywords": ["kw1","kw2",...], "domain": "", "topic": "", "conversation_type": "", "emotion": "", "novelty": 1 }\n'
        'MESSAGE:\n"""' + text + '"""'
    )
    
    response = ollama.generate(
        model=model,
        prompt=prompt,
        options={"temperature": 0.3},
        stream=False
    )
    # If response is a GenerateResponse object, get the .response attribute
    if hasattr(response, "response"):
        data = json.loads(response.response)
    elif isinstance(response, dict):
        data = json.loads(response['response'])
    else:
        # Assume response is a GenerateResponse object and extract its 'response' attribute
        data = json.loads(getattr(response, "response", str(response)))
    summary = data.get('summary', '')
    keywords = data.get('keywords', [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(',') if k.strip()]
    meta = {
        'domain': data.get('domain', ''),
        'topic': data.get('topic', ''),
        'conversation_type': data.get('conversation_type', ''),
        'emotion': data.get('emotion', ''),
        'novelty': data.get('novelty', 0)
    }
    return summary, keywords, meta
