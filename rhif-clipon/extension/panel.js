import { hubFetch } from './utils.js';

export function initPanel() {
  const panel = document.getElementById('rhif-panel');
  const searchInput = document.getElementById('rhif-search');
  const results = document.getElementById('rhif-results');
  const themeBtn = document.getElementById('rhif-theme-toggle');
  let dark = false;
  makeDraggable(panel);

  themeBtn.addEventListener('click', () => {
    dark = !dark;
    panel.classList.toggle('rhif-dark', dark);
  });

  async function runSearch() {
    const q = searchInput.value.trim();
    if (!q) return;
    const rows = await hubFetch(`/search?q=${encodeURIComponent(q)}&limit=10`, {
      headers: { Accept: 'application/json' }
    });
    results.innerHTML = '';
    rows.forEach(r => {
      const li = document.createElement('li');
      li.className = 'rhif-item';
      const meta = document.createElement('div');
      meta.textContent = `${r.topic || ''} ${r.emotion ? ' - ' + r.emotion : ''}`;
      const btn = document.createElement('button');
      btn.textContent = 'Insert';
      btn.addEventListener('click', () => {
        navigator.clipboard.writeText(r.text).catch(() => {});
        window.postMessage({ type: 'RHIF_PASTE', payload: r.text }, '*');
      });
      li.textContent = (r.summary || '').slice(0, 60) + ' ';
      li.appendChild(meta);
      li.appendChild(btn);
      results.appendChild(li);
    });
  }

  searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') runSearch();
  });
}
function makeDraggable(el) {
  let offsetX = 0, offsetY = 0, isDragging = false;

  el.addEventListener('mousedown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON') return; // Don't drag when interacting with controls
    isDragging = true;
    offsetX = e.clientX - el.offsetLeft;
    offsetY = e.clientY - el.offsetTop;
    el.style.cursor = 'grabbing';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    el.style.left = `${e.clientX - offsetX}px`;
    el.style.top = `${e.clientY - offsetY}px`;
    el.style.right = 'unset'; // override fixed right anchor
  });

  document.addEventListener('mouseup', () => {
    isDragging = false;
    el.style.cursor = 'move';
  });
}
