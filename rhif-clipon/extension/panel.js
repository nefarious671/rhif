import { hubFetch } from './utils.js';

export function initPanel() {
  const panel = document.getElementById('rhif-panel');
  const header = document.getElementById('rhif-panel-header');
  const moveHandle = document.getElementById('rhif-move-handle');
  const searchInput = document.getElementById('rhif-search');
  const filterBtn = document.getElementById('rhif-filter-toggle');
  const filterPanel = document.getElementById('rhif-filter-panel');
  const results = document.getElementById('rhif-results');
  const separator = document.getElementById('rhif-separator');
  const preview = document.getElementById('rhif-preview');
  const controls = document.getElementById('rhif-preview-controls');
  const copyBtn = document.getElementById('rhif-copy');
  const prevBtn = document.getElementById('rhif-prev');
  const nextBtn = document.getElementById('rhif-next');
  const themeBtn = document.getElementById('rhif-theme-toggle');
  let dark = false;
  let rows = [];
  let current = -1;
  let convCache = {};
  let convRows = [];
  let convIndex = -1;

  makeDraggable(panel, { grid: 20, handle: moveHandle, storageKey: 'rhif-panel-pos' });
  makeResizable(panel, { storageKey: 'rhif-panel-size' });

  filterBtn.addEventListener('click', () => {
    filterPanel.classList.toggle('rhif-open');
  });

  themeBtn.addEventListener('click', () => {
    dark = !dark;
    panel.classList.toggle('rhif-dark', dark);
  });

  function mdToHtml(md) {
    let html = md
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>');
    return html.replace(/\n/g, '<br>');
  }

  async function ensureConversation(convId) {
    if (!convCache[convId]) {
      convCache[convId] = await hubFetch(`/conversation?conv_id=${encodeURIComponent(convId)}`, { headers: { Accept: 'application/json' } });
      convCache[convId].sort((a, b) => a.turn - b.turn);
    }
    convRows = convCache[convId];
  }

  function renderEntry(i) {
    if (i < 0 || i >= convRows.length) return;
    const row = convRows[i];
    convIndex = i;
    preview.innerHTML = mdToHtml(row.text || '');
    preview.scrollTop = 0;
    preview.classList.remove('rhif-hidden');
    controls.classList.remove('rhif-hidden');
    updateNav();
  }

  async function showPreview(idx) {
    if (idx < 0 || idx >= rows.length) return;
    const row = rows[idx];
    current = idx;
    try {
      await ensureConversation(row.conv_id);
      const i = convRows.findIndex(r => r.id === row.id);
      renderEntry(i === -1 ? 0 : i);
    } catch (err) {
      console.error('Preview failed:', err);
    }
  }

  function updateNav() {
    prevBtn.disabled = convIndex <= 0;
    nextBtn.disabled = convIndex === -1 || convIndex >= convRows.length - 1;
  }

  function moveIndex(dir) {
    const i = convIndex + dir;
    if (i >= 0 && i < convRows.length) return i;
    return -1;
  }

  prevBtn.addEventListener('click', () => {
    const i = moveIndex(-1);
    if (i !== -1) renderEntry(i);
  });
  nextBtn.addEventListener('click', () => {
    const i = moveIndex(1);
    if (i !== -1) renderEntry(i);
  });

  copyBtn.addEventListener('click', () => {
    if (convIndex === -1) return;
    const text = convRows[convIndex].text;
    navigator.clipboard.writeText(text).catch(() => {});
    window.postMessage({ type: 'RHIF_PASTE', payload: text }, '*');
  });

  async function runSearch() {
    const q = searchInput.value.trim();
    if (!q) return;
    const params = new URLSearchParams({ q, limit: '20' });
    const domain = document.getElementById('rhif-domain').value.trim();
    const topic = document.getElementById('rhif-topic').value.trim();
    const emotion = document.getElementById('rhif-emotion').value.trim();
    const convId = document.getElementById('rhif-conv-id').value.trim();
    const start = document.getElementById('rhif-date-start').value;
    const end = document.getElementById('rhif-date-end').value;
    const slow = document.getElementById('rhif-slow-search').checked;
    if (domain) params.append('domain', domain);
    if (topic) params.append('topic', topic);
    if (emotion) params.append('emotion', emotion);
    if (convId) params.append('conv_id', convId);
    if (start) params.append('start', start);
    if (end) params.append('end', end);
    if (slow) params.append('slow', '1');
    try {
      rows = await hubFetch(`/search?${params.toString()}`, { headers: { Accept: 'application/json' } });
    } catch (err) {
      console.error('Search failed:', err);
      return;
    }
    results.innerHTML = '';
    preview.classList.add('rhif-hidden');
    controls.classList.add('rhif-hidden');
    convCache = {};
    convRows = [];
    convIndex = -1;
    rows.forEach((r, idx) => {
      const li = document.createElement('li');
      li.className = 'rhif-row';
      const link = document.createElement('a');
      link.textContent = (r.summary || r.text).slice(0, 60);
      link.addEventListener('click', e => { e.preventDefault(); showPreview(idx); });
      li.appendChild(link);
      results.appendChild(li);
    });
  }

  searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') runSearch(); });

  // horizontal resize
  let resizeStart = 0;
  let startWidth = 0;
  const storedWidth = localStorage.getItem('rhif-results-width');
  if (storedWidth) results.style.width = storedWidth;
  separator.addEventListener('mousedown', e => {
    resizeStart = e.clientX;
    startWidth = results.offsetWidth;
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', onResize);
    window.addEventListener('mouseup', stopResize);
  });

  function onResize(e) {
    const dx = e.clientX - resizeStart;
    results.style.width = `${startWidth + dx}px`;
  }
  function stopResize() {
    window.removeEventListener('mousemove', onResize);
    window.removeEventListener('mouseup', stopResize);
    document.body.style.userSelect = '';
    localStorage.setItem('rhif-results-width', results.style.width);
  }
}

export function makeDraggable(el, opts = {}) {
  const grid = opts.grid || 1;
  const storageKey = opts.storageKey;
  const handle = opts.handle || el;
  if (storageKey) {
    const left = localStorage.getItem(`${storageKey}-left`);
    const top = localStorage.getItem(`${storageKey}-top`);
    if (left !== null && top !== null) {
      el.style.left = left;
      el.style.top = top;
      el.style.right = 'unset';
    }
  }
  function clampToViewport() {
    const maxLeft = window.innerWidth - el.offsetWidth;
    const maxTop = window.innerHeight - el.offsetHeight;
    let left = parseInt(el.style.left || '0', 10);
    let top = parseInt(el.style.top || '0', 10);
    if (isNaN(left)) left = 0;
    if (isNaN(top)) top = 0;
    left = Math.min(Math.max(left, 0), maxLeft);
    top = Math.min(Math.max(top, 0), maxTop);
    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
  }
  clampToViewport();
  let offsetX = 0, offsetY = 0, isDragging = false;

  handle.addEventListener('mousedown', (e) => {
    isDragging = true;
    offsetX = e.clientX - el.offsetLeft;
    offsetY = e.clientY - el.offsetTop;
    handle.style.cursor = 'grabbing';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    el.style.left = `${e.clientX - offsetX}px`;
    el.style.top = `${e.clientY - offsetY}px`;
    el.style.right = 'unset';
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
    clampToViewport();
    if (storageKey) {
      localStorage.setItem(`${storageKey}-left`, el.style.left);
      localStorage.setItem(`${storageKey}-top`, el.style.top);
    }
    handle.style.cursor = 'move';
  });
}

export function makeResizable(el, opts = {}) {
  const storageKey = opts.storageKey;
  const right = document.createElement('div');
  const bottom = document.createElement('div');
  right.className = 'rhif-resize-right';
  bottom.className = 'rhif-resize-bottom';
  el.appendChild(right);
  el.appendChild(bottom);

  if (storageKey) {
    const w = localStorage.getItem(`${storageKey}-width`);
    const h = localStorage.getItem(`${storageKey}-height`);
    if (w) el.style.width = w;
    if (h) el.style.height = h;
  }

  let startX = 0, startY = 0, startW = 0, startH = 0;

  right.addEventListener('mousedown', e => {
    startX = e.clientX;
    startW = el.offsetWidth;
    document.body.style.userSelect = 'none';
    function move(ev) {
      el.style.width = `${startW + (ev.clientX - startX)}px`;
    }
    function up() {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      document.body.style.userSelect = '';
      if (storageKey) localStorage.setItem(`${storageKey}-width`, el.style.width);
    }
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  });

  bottom.addEventListener('mousedown', e => {
    startY = e.clientY;
    startH = el.offsetHeight;
    document.body.style.userSelect = 'none';
    function move(ev) {
      el.style.height = `${startH + (ev.clientY - startY)}px`;
    }
    function up() {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      document.body.style.userSelect = '';
      if (storageKey) localStorage.setItem(`${storageKey}-height`, el.style.height);
    }
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  });
}
