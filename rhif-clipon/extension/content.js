function getLatestChatTurns() {
  const msgs = document.querySelectorAll('.text-base');
  const arr = Array.from(msgs).slice(-2);
  return { userText: arr[0]?.innerText || '', assistantText: arr[1]?.innerText || '' };
}

function insertAtCursor(text) {
  const ta = document.querySelector('#prompt-textarea, textarea');
  if (ta) {
    ta.value += text;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

window.rhifContent = { getLatestChatTurns, insertAtCursor };

(async function () {
  const html = await fetch(chrome.runtime.getURL('panel.html')).then(r => r.text());
  const template = document.createElement('div');
  template.innerHTML = html.trim();
  const panel = template.firstElementChild;
  document.body.appendChild(panel);

  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = chrome.runtime.getURL('panel.css');
  document.head.appendChild(link);

  const { initPanel, makeDraggable } = await import(chrome.runtime.getURL('panel.js'));
  await initPanel();

  const btn = document.createElement('div');
  btn.id = 'rhif-toggle-btn';
  btn.textContent = 'R';
  document.body.appendChild(btn);
  makeDraggable(btn, { grid: 20, handle: btn, storageKey: 'rhif-btn' });
  btn.addEventListener('click', () => {
    panel.style.display = panel.style.display === 'none' || !panel.style.display ? 'block' : 'none';
  });

  document.addEventListener('keydown', e => {
    if (e.altKey && e.key.toLowerCase() === 'r') btn.click();
  });

  window.addEventListener('message', e => {
    if (e.data && e.data.type === 'RHIF_PASTE') insertAtCursor(e.data.payload);
  });
})();
