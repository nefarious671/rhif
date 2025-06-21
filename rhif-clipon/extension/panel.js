import { hubFetch } from './utils.js';

export function initPanel() {
  const panel = document.getElementById('rhif-panel');
  const searchInput = document.getElementById('rhif-search');
  const results = document.getElementById('rhif-results');
  const themeBtn = document.getElementById('rhif-theme-toggle');
  let dark = false;

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
