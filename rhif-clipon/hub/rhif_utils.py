import hashlib
import json
from typing import Iterable, Dict, Any, Generator


def canonical_json(data: Any) -> str:
    """Return canonical JSON with sorted keys and no whitespace."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def rsp_hash(text: str, meta: Iterable[Dict[str, Any]] | None = None, children: Iterable[str] | None = None) -> str:
    """Compute SHA-256 hash for an RSP packet."""
    obj = {
        "text": text,
        "meta": list(meta or []),
        "children": list(children or []),
    }
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()


def dimension_hash(dimension: str, value: str) -> str:
    """Return SHA-256 hash for a dimension/value pair."""
    return hashlib.sha256(f"{dimension}:{value}".encode()).hexdigest()


def flatten_meta(rsp_hash_value: str, meta: Iterable[Dict[str, Any]], context_path: Iterable[str] | None = None) -> Generator[Dict[str, Any], None, None]:
    """Yield flattened rows for the meta index."""
    path = list(context_path or [])
    for pair in meta:
        dim = pair.get("dimension") or ""
        val = pair.get("value") or ""
        yield {
            "hash": rsp_hash_value,
            "dimension": dim,
            "value": val,
            "dimension_hash": dimension_hash(dim, val),
            "context_path": json.dumps(path),
        }

def canonical_keyword_list(keywords: Iterable[str]) -> list[str]:
    """Return canonicalised keyword list: lowercase, unique and sorted."""
    cleaned = {str(k).strip().lower() for k in keywords if str(k).strip()}
    return sorted(cleaned)
