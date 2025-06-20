"""Helpers for extracting and persisting code snippets from markdown."""

import re
from pathlib import Path
from typing import Dict, List, Optional

CODE_BLOCK_RE = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)

EXT_MAP = {
    'python': '.py',
    'py': '.py',
    'javascript': '.js',
    'js': '.js',
    'html': '.html',
    'bash': '.sh',
    'sh': '.sh',
}


def extract_markdown_blocks(markdown: str) -> List[Dict[str, str]]:
    """Return a list of code blocks found in a markdown string."""
    blocks = []
    for match in CODE_BLOCK_RE.finditer(markdown):
        lang = (match.group(1) or '').strip().lower()
        code = match.group(2)
        ext = EXT_MAP.get(lang, '.txt')
        blocks.append({'lang': lang, 'ext': ext, 'code': code})
    return blocks


def save_blocks(blocks: List[Dict[str, str]], workspace_dir: str, base_filename: Optional[str] = None) -> List[str]:
    """Save each code block to ``workspace_dir`` and return the file paths."""
    paths = []
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)
    for i, blk in enumerate(blocks, 1):
        filename = base_filename or 'code'
        path = Path(workspace_dir) / f"{filename}_{i}{blk['ext']}"
        with open(path, 'w') as f:
            f.write(blk['code'])
        paths.append(str(path.resolve()))
    return paths
