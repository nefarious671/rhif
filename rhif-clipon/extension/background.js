chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({ HUB_BASE: 'http://127.0.0.1:8765' });
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  fetch(msg.url, msg.options)
    .then(async (r) => {
      const ct = r.headers.get('Content-Type') || '';
      if (!ct.includes('application/json')) {
        const text = await r.text();
        throw new Error(`Non-JSON response: ${text.slice(0, 200)}`);
      }
      return r.json();
    })
    .then(sendResponse)
    .catch((err) => sendResponse({ error: err.toString() }));
  return true;
});
