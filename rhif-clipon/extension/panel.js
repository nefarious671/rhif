import { hubFetch } from './utils.js';

export function initPanel() {
  const panel = document.getElementById('rhif-panel');
  const searchInput = document.getElementById('rhif-search');
  const results = document.getElementById('rhif-results');
  const preview = document.getElementById('rhif-preview');
  const themeBtn = document.getElementById('rhif-theme-toggle');
  let dark = false;
  makeDraggable(panel);

  themeBtn.addEventListener('click', () => {
    dark = !dark;
    panel.classList.toggle('rhif-dark', dark);
  });

  function showPreview(text) {
    preview.textContent = text;
    preview.classList.remove('rhif-hidden');
  }

  async function runSearch() {
    const q = searchInput.value.trim();
    if (!q) return;
    const rows = await hubFetch(`/search?q=${encodeURIComponent(q)}&limit=10`, {
      headers: { Accept: 'application/json' }
    });
    results.innerHTML = '';
    preview.classList.add('rhif-hidden');
    rows.forEach(r => {
      const li = document.createElement('li');
      li.className = 'rhif-item';

      const link = document.createElement('a');
      link.textContent = (r.summary || '').slice(0, 60);
      link.addEventListener('click', e => {
        e.preventDefault();
        showPreview(r.text);
      });

      const copy = document.createElement('button');
      copy.textContent = '📋';
      copy.addEventListener('click', () => {
        navigator.clipboard.writeText(r.text).catch(() => {});
      });

      li.appendChild(link);
      li.appendChild(copy);
      results.appendChild(li);
    });
  }

  searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') runSearch();
  });
}
export function makeDraggable(el, opts = {}) {
  const grid = opts.grid || 1;
  const storageKey = opts.storageKey;
  if (storageKey) {
    const left = localStorage.getItem(`${storageKey}-left`);
    const top = localStorage.getItem(`${storageKey}-top`);
    if (left !== null && top !== null) {
      el.style.left = left;
      el.style.top = top;
      el.style.right = 'unset';
    }
  }
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
    if (!isDragging) return;
    isDragging = false;
    if (grid > 1) {
      const snappedLeft = Math.round(el.offsetLeft / grid) * grid;
      const snappedTop = Math.round(el.offsetTop / grid) * grid;
      el.style.left = `${snappedLeft}px`;
      el.style.top = `${snappedTop}px`;
    }
    if (storageKey) {
      localStorage.setItem(`${storageKey}-left`, el.style.left);
      localStorage.setItem(`${storageKey}-top`, el.style.top);
    }
    el.style.cursor = 'move';
  });
}
