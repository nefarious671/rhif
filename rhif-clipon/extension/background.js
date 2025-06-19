chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({ HUB_BASE: 'http://127.0.0.1:8765' });
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  fetch(msg.url, msg.options).then(r => r.json()).then(sendResponse).catch(err => sendResponse({ error: err.toString() }));
  return true;
});
