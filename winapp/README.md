# RHIF Windows App

This directory contains a simple standalone desktop application that mirrors the features of the browser extension. It connects to the local `hub.py` server and provides search and preview of archived responses.

## Running

1. Install the required packages:
   ```bash
   pip install tkhtmlview requests
   ```
2. Make sure `hub.py` is running:
   ```bash
   python ../rhif-clipon/hub/hub.py
   ```
3. Launch the app:
   ```bash
   python app.py
   ```

The app opens a small floating "R" button. Clicking it toggles the main panel where you can search, preview and copy responses just like the extension.
