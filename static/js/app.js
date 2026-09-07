// app.js — shared logic across all pages (sidebar status indicator)

async function checkEngineStatus() {
  const dot = document.getElementById('ollama-status-dot');
  const text = document.getElementById('ollama-status-text');
  if (!dot || !text) return;

  try {
    const res = await fetch('http://localhost:11434/api/tags', { signal: AbortSignal.timeout(2500) });
    if (res.ok) {
      dot.classList.add('online');
      dot.classList.remove('offline');
      text.textContent = 'Engine ready';
    } else {
      throw new Error('bad response');
    }
  } catch (e) {
    dot.classList.add('offline');
    dot.classList.remove('online');
    text.textContent = 'Engine offline — open Ollama';
  }
}

checkEngineStatus();
setInterval(checkEngineStatus, 15000);

window.addEventListener('online', () => window.location.reload());

// Auto-grow textareas
document.addEventListener('input', (e) => {
  if (e.target.tagName === 'TEXTAREA') {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px';
  }
});
