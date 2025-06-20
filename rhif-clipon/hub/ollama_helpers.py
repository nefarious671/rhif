"""Integration helpers for summarisation using the Ollama API."""

import json
import os
import logging
import regex as re
from typing import Dict, List, Tuple

import ollama


MAX_PROMPT_CHARS = int(os.getenv("OLLAMA_MAX_PROMPT", "32000"))

# error logger for failed ollama JSON responses
logger = logging.getLogger("ollama")
if not logger.handlers:
    handler = logging.FileHandler(
        "ollama_errors.log", encoding="utf-8", errors="replace"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)


_JSON_DECODER = json.JSONDecoder()
_JSON_REGEX = re.compile(r'\{(?:[^{}]|(?R))*\}', re.S)  # recursive brace matcher


def _extract_json(text: str) -> Dict:
    """Try hard to return a JSON object from *text*."""

    import ast

    def _clean_fences(t: str) -> str:
        t = t.strip()
        if t.startswith("```"):
            t = t.strip("` \n")
            if t.lower().startswith("json"):
                t = t[4:].lstrip()
        return t

    cleaned = _clean_fences(text)

    # 1) direct decode
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2) find first {...}
    m = _JSON_REGEX.search(cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            cleaned = m.group(0)

    # 3) best-effort fixes
    fixes = (
        cleaned
        .replace("“", '"').replace("”", '"')
        .replace("’", "'")
        .replace("\n", " ")
    )
    try:
        return json.loads(fixes)
    except Exception:
        try:
            return ast.literal_eval(fixes)
        except Exception:
            raise ValueError("No valid JSON object found")


def _summarise_once(
    text: str,
    model: str,
    kw_count: int,
    summary_tokens: int,
) -> Tuple[str, List[str], Dict[str, str]]:
    """Call Ollama once and return summary, keywords and meta data."""

    system_prompt = "You are an API that must return JSON only."
    user_prompt = (
        f"Summarize the message below in <= {summary_tokens} words.\n"
        f"Return exactly {kw_count} lowercase single-word keywords.\n"
        "Provide: domain, topic, conversation_type, emotion, novelty (0-1).\n"
        "Respond ONLY with JSON in this format:\n"
        '{"summary":"...","keywords":["kw1","kw2"],"domain":"...","topic":"...",'
        '"conversation_type":"...","emotion":"...","novelty":1}\n'
        'MESSAGE:\n"""' + text + '"""'
    )

    response = ollama.generate(
        model=model,
        prompt=user_prompt,
        system=system_prompt,
        # ➊ keep temperature 0 for deterministic output
        # ➋ use Ollama's JSON mode to avoid extra text
        format="json",
        options={"temperature": 0},
        stream=False
    )


    raw_resp = response.response if hasattr(response, "response") else response
    if isinstance(raw_resp, dict):
        raw_resp = raw_resp.get('response', '')
    if not isinstance(raw_resp, str):
        raw_resp = str(raw_resp)

    try:
        data = _extract_json(raw_resp)
    except Exception as e:
        logger.error(
            "JSON parse failure: %s\nPrompt: %r\nResponse: %r",
            e,
            user_prompt[:500],  
            raw_resp[:500],
        )
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
    """Summarise ``text`` using Ollama, splitting into chunks if needed."""
    if len(text) <= MAX_PROMPT_CHARS:
        return _summarise_once(text, model, kw_count, summary_tokens)

    chunk_size = MAX_PROMPT_CHARS - 1000
    chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    partial_summaries = [
        _summarise_once(c, model, kw_count, summary_tokens)[0] for c in chunks
    ]
    combined = "\n".join(partial_summaries)
    return _summarise_once(combined, model, kw_count, summary_tokens)
