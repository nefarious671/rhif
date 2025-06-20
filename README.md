# RHIF

Upgraded RHIF Clip-On with recursive packet hashing and metadata indexing.

This repository contains two main pieces:

* **Hub** – a small Flask service for ingesting and searching conversation
  packets. It summarises content using an Ollama model and stores metadata in
  SQLite.
* **Extension** – a Chrome/Edge extension that interacts with the hub to save
  ChatGPT conversations and insert past responses.

Run tests with `pytest` inside the `rhif-clipon` directory.
