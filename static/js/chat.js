// chat.js — handles the AI chat interface

const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatInner = document.getElementById('chat-inner');
const chatEmpty = document.getElementById('chat-empty');
const chatScroll = document.getElementById('chat-scroll');

function scrollToBottom() {
  chatScroll.scrollTop = chatScroll.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function addMessage(role, text, sources) {
  if (chatEmpty) chatEmpty.style.display = 'none';

  const msg = document.createElement('div');
  msg.className = `msg ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  if (role === 'bot') {
    avatar.innerHTML = `<svg viewBox="0 0 40 40" fill="none"><path d="M20 34C20 34 8 27.5 8 17.5C8 11 13 6 19 6C19.5 6 20 6.05 20 6.05C20 6.05 20.5 6 21 6C27 6 32 11 32 17.5C32 27.5 20 34 20 34Z" fill="#E8B04B"/></svg>`;
  } else {
    avatar.textContent = 'You';
  }

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = escapeHtml(text).replace(/\n/g, '<br>');

  if (sources && sources.length > 0) {
    const src = document.createElement('div');
    src.className = 'msg-sources';
    src.innerHTML = sources.map(s => `<span>${escapeHtml(s)}</span>`).join('');
    bubble.appendChild(src);
  }

  msg.appendChild(avatar);
  msg.appendChild(bubble);
  chatInner.appendChild(msg);
  scrollToBottom();
  return msg;
}

function addTypingIndicator() {
  const msg = document.createElement('div');
  msg.className = 'msg bot';
  msg.id = 'typing-msg';
  msg.innerHTML = `
    <div class="msg-avatar"><svg viewBox="0 0 40 40" fill="none"><path d="M20 34C20 34 8 27.5 8 17.5C8 11 13 6 19 6C19.5 6 20 6.05 20 6.05C20 6.05 20.5 6 21 6C27 6 32 11 32 17.5C32 27.5 20 34 20 34Z" fill="#E8B04B"/></svg></div>
    <div class="msg-bubble"><div class="typing-indicator"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>
  `;
  chatInner.appendChild(msg);
  scrollToBottom();
}

function removeTypingIndicator() {
  const el = document.getElementById('typing-msg');
  if (el) el.remove();
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  addMessage('user', text);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  sendBtn.disabled = true;
  addTypingIndicator();

  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    removeTypingIndicator();

    if (data.error) {
      addMessage('bot', `Something went wrong: ${data.error}`);
    } else {
      addMessage('bot', data.reply, data.sources);
    }
  } catch (err) {
    removeTypingIndicator();
    addMessage('bot', "I couldn't reach the local engine. Make sure Ollama is running, then try again.");
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

chatInput.focus();
