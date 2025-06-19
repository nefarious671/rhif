import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hub'))
from code_utils import extract_markdown_blocks


def test_extract_blocks():
    md = """Here
```python
print('hi')
```
"""
    blocks = extract_markdown_blocks(md)
    assert len(blocks) == 1
    assert blocks[0]['lang'] == 'python'
    assert 'print' in blocks[0]['code']

