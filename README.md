# RHIF

RHIF (Recursive Hash Index Feed) is a lightweight self-hosted archive for
ChatGPT conversations. The project couples a Flask based **hub** with a
Chromium browser **extension** to capture, summarise and search past
messages on your local machine.

The repository tree contains the following modules:

* **rhif-clipon/hub** – ingestion API and metadata store.
* **rhif-clipon/extension** – Chrome/Edge extension for interacting with the hub.
* **rhif-clipon/tools** – import helpers for historical ChatGPT exports.
* **rhif-clipon/tests** – unit tests for hub utilities.

Run tests by executing `pytest` from within `rhif-clipon`.

## Program overview

1. **Hub** – `hub/hub.py`
   - Flask application exposing REST endpoints.
   - Summarises text using an Ollama model and persists data in SQLite.
   - Provides simple search and code snippet extraction.
2. **Extension** – `extension/`
   - Injects a small panel into chatgpt.com to search or insert past messages.
   - Uses a background worker to relay requests to the hub.
3. **Tools** – `tools/ingest_export.py`
   - CLI utility for importing legacy `conversations.json` archives.

## Programming specification

### Configuration

Environment variables control the hub (defaults shown):

```
OLLAMA_MODEL=llama3:8b-q5
HUB_PORT=8765
DB_PATH=./rhif.sqlite
WORKSPACE_DIR=./workspace
SUMMARY_TOKENS=120
KEYWORD_COUNT=8
```

### Hub API

| Endpoint      | Method | Description                                                     |
|---------------|-------|-----------------------------------------------------------------|
| `/summarise`  | POST  | Return summary, keywords and meta for provided text.            |
| `/ingest`     | POST  | Store a conversation turn and its metadata.                     |
| `/search`     | GET   | Full‑text search with optional tag/domain/topic filters.        |
| `/conversation` | GET   | Retrieve all turns for a conversation by ID. |
| `/savecode`   | POST  | Persist code blocks from markdown into the workspace directory. |
| `/health`     | GET   | Liveness probe used by tests and the extension.                 |

All POST endpoints accept/return JSON.

Date filters (`start`/`end` query params) expect ISO strings in `YYYY-MM-DD` format.

`/ingest` normalises supplied dates to that format, removing quotes or time components.

### Database schema

`db.py` manages the following tables:

* `rsp` – primary packet store.
* `rsp_fts` – FTS5 mirror for text and summary.
* `rsp_index` – flattened metadata pairs for filtering.
* `keyword_set` & `keyword_set_fts` – deduplicated keyword lists.
* `rsp_keyword_xref` – association table between responses and keyword sets.

Indexes exist on the `domain` and `topic` columns for quick lookup.

### Hashing and indexing

`rhif_utils.py` provides helpers for:

* Generating SHA‑256 hashes for packets and dimension/value pairs.
* Producing canonical JSON for deterministic hashing.
* Flattening metadata structures into index rows.

### Summarisation

`ollama_helpers.py` integrates with the local Ollama API. It prompts the
model to produce a short summary, a set number of keywords and basic meta
information (domain, topic, conversation type, emotion and a novelty
score). Long messages are chunked to respect the maximum prompt size.

### Code extraction

`code_utils.py` parses markdown code fences and saves each block to the
configured workspace directory. The `savecode` API uses these helpers.

### Browser extension

The extension runs on chatgpt.com and exposes two utilities through a
floating panel:

* Search the archive and copy or insert past messages.
* Toggle light/dark mode of the panel.

Communication with the hub happens via `background.js` using Chrome's
messaging API. `content.js` injects the panel, and `panel.js` performs
searches using the `utils.js` helper to call the hub.

## Usage

1. Install dependencies as described in `rhif-clipon/README.md`.
2. Run the hub with `python hub/hub.py`.
3. Load `extension/` as an unpacked extension in Chrome/Edge.
4. Import previous conversations using `tools/ingest_export.py` if desired.

