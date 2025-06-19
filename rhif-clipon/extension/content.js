function getLatestChatTurns() {
  const msgs = document.querySelectorAll('.text-base');
  const arr = Array.from(msgs).slice(-2);
  return { userText: arr[0]?.innerText || '', assistantText: arr[1]?.innerText || '' };
}

function insertAtCursor(text) {
  const ta = document.querySelector('textarea');
  if (ta) {
    ta.value += text;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

window.rhifContent = { getLatestChatTurns, insertAtCursor };
