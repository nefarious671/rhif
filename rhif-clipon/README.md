# RHIF Clip-On

Local archiving hub and browser extension for ChatGPT conversations.

## Setup

```bash
# clone repo and enter
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r hub/requirements.txt
```

Pull the Ollama model:

```bash
ollama pull llama3:8b-q5
```

Create a `.env` to override defaults if needed.

## Running

```bash
python hub/hub.py
```

Load `extension/` as an unpacked extension in Chrome/Edge.

### Importing your legacy ChatGPT archive

```bash
python tools/ingest_export.py --export-dir ~/Downloads/chatgpt_export/
```

Run tests with:

```bash
pytest -q
```
