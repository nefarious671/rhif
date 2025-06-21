async function hubFetch(path, options) {
  const { HUB_BASE } = await chrome.storage.sync.get({ HUB_BASE: 'http://127.0.0.1:8765' });
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), 5000);
  try {
    const res = await fetch(HUB_BASE + path, { ...options, signal: ctrl.signal });
    return await res.json();
  } finally {
    clearTimeout(id);
  }
}

document.getElementById('run-search').addEventListener('click', async () => {
  const q = document.getElementById('search').value;
  const rows = await hubFetch(`/search?q=${encodeURIComponent(q)}&limit=10`, {
    headers: { Accept: 'application/json' }
  });
  const ul = document.getElementById('results');
  ul.innerHTML = '';
  rows.forEach(r => {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.textContent = 'Insert';
    btn.addEventListener('click', () => {
      chrome.scripting.executeScript({
        target: { tabId: chrome.tabs.TAB_ID_CURRENT },
        func: (text) => {
          const ta = document.querySelector('textarea');
          ta.value += text;
          ta.dispatchEvent(new Event('input', { bubbles: true }));
        },
        args: [r.text]
      });
    });
    li.textContent = r.id + ' '; li.appendChild(btn);
    ul.appendChild(li);
  });
});

document.getElementById('save-turn').addEventListener('click', async () => {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tabId = tabs[0].id;
  const [userText, assistantText] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const msgs = document.querySelectorAll('.text-base');
      const latest = Array.from(msgs).slice(-2);
      return latest.map(n => n.innerText);
    }
  }).then(res => res[0].result);
  await hubFetch('/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conv_id: 'browser',
      turn: Date.now(),
      role: 'assistant',
      text: assistantText,
      tags: []
    })
  });
});

document.getElementById('save-code').addEventListener('click', async () => {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tabId = tabs[0].id;
  const assistantText = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const msgs = document.querySelectorAll('.text-base');
      const latest = msgs[msgs.length - 1];
      return latest.innerText;
    }
  }).then(res => res[0].result);
  const res = await hubFetch('/savecode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code_markdown: assistantText })
  });
  alert('Saved: ' + res.paths.join('\n'));
});
