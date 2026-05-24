// ── State ──
let chatOpen   = false;
let isTyping   = false;

// Key di sessionStorage per user (username diambil dari DOM)
function storageKey() {
    const el = document.querySelector('[data-username]');
    const user = el ? el.dataset.username : 'guest';
    return `speakup_chat_${user}`;
}

// Load history dari sessionStorage
function loadHistory() {
    try {
        const raw = sessionStorage.getItem(storageKey());
        return raw ? JSON.parse(raw) : [];
    } catch { return []; }
}

// Simpan history ke sessionStorage
function saveHistory(history) {
    try {
        // Simpan maks 40 pesan agar tidak membengkak
        const trimmed = history.slice(-40);
        sessionStorage.setItem(storageKey(), JSON.stringify(trimmed));
    } catch { /* storage full — abaikan */ }
}

// Hapus history (dipanggil saat logout)
function clearHistoryStorage() {
    try { sessionStorage.removeItem(storageKey()); } catch {}
}

// Expose ke global agar bisa dipanggil dari logout handler
window.clearAgentHistory = clearHistoryStorage;

let chatHistory = loadHistory();

// ============================================
// TOGGLE BUKA / TUTUP CHAT
// ============================================
function toggleAgentChat() {
    const chat = document.getElementById('agent-chat');
    const fab  = document.querySelector('.agent-fab');
    chatOpen = !chatOpen;

    if (chatOpen) {
        chat.classList.add('open');
        fab?.classList.add('active');
        document.getElementById('fab-icon').textContent = '✕';
        hideFabNotif();

        // Render ulang history jika ada, lalu scroll ke bawah
        restoreChat();
        setTimeout(scrollToBottom, 80);
        setTimeout(() => document.getElementById('ac-input')?.focus(), 200);
    } else {
        chat.classList.remove('open');
        fab?.classList.remove('active');
        document.getElementById('fab-icon').textContent = '✍️';
    }
}

// ============================================
// RESTORE CHAT DARI HISTORY
// ============================================
function restoreChat() {
    const container = document.getElementById('ac-messages');
    if (!container) return;

    // Jika history kosong, biarkan welcome message tetap ada
    if (chatHistory.length === 0) return;

    // Cek apakah sudah di-render (tandai dengan data-restored)
    if (container.dataset.restored === '1') return;
    container.dataset.restored = '1';

    // Kosongkan welcome message awal lalu render semua history
    container.innerHTML = '';
    chatHistory.forEach(msg => {
        appendMessageDOM(msg.role, msg.content, msg.time || '');
    });
}

// ============================================
// QUICK PROMPT — Klik chip kategori
// ============================================
async function quickPrompt(category) {
    document.getElementById('ac-chips').style.display = 'none';

    const labels = {
        pidato       : '🎤 Pidato Formal',
        wawancara    : '💼 Wawancara Kerja',
        presentasi   : '📊 Presentasi',
        debat        : '⚖️ Debat',
        mc           : '🎭 Master of Ceremony',
        storytelling : '📖 Storytelling',
    };

    const userMsg = `Halo! Saya ingin membuat naskah untuk kategori ${labels[category]}. Tolong bantu saya!`;
    appendMessageDOM('user', userMsg);
    pushHistory('user', userMsg);
    await sendToAgent(userMsg);
}

// ============================================
// HANDLE ENTER KEY
// ============================================
function handleEnter(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// ============================================
// KIRIM PESAN USER
// ============================================
async function sendMessage() {
    const input = document.getElementById('ac-input');
    const msg   = input.value.trim();
    if (!msg || isTyping) return;

    input.value = '';
    input.style.height = 'auto';

    document.getElementById('ac-chips').style.display = 'none';

    appendMessageDOM('user', msg);
    pushHistory('user', msg);
    await sendToAgent(msg);
}

// ============================================
// KIRIM KE BACKEND AGENT
// ============================================
async function sendToAgent(userMsg) {
    if (isTyping) return;
    isTyping = true;

    const typingId = showTyping();

    try {
        const res = await fetch('/agent/chat', {
            method  : 'POST',
            headers : { 'Content-Type': 'application/json' },
            body    : JSON.stringify({
                message  : userMsg,
                messages : chatHistory.slice(-10),
            }),
        });

        const data = await res.json();
        removeTyping(typingId);

        if (data.success && data.reply) {
            appendMessageDOM('assistant', data.reply);
            pushHistory('assistant', data.reply);
            if (!chatOpen) showFabNotif();
        } else {
            appendError(data.error || 'Terjadi kesalahan, coba lagi.');
        }
    } catch (err) {
        removeTyping(typingId);
        appendError('Koneksi gagal. Periksa internet kamu.');
        console.error('Agent error:', err);
    } finally {
        isTyping = false;
    }
}

// ============================================
// PUSH KE HISTORY & SIMPAN
// ============================================
function pushHistory(role, content) {
    const time = nowTime();
    chatHistory.push({ role, content, time });
    saveHistory(chatHistory);
}

function nowTime() {
    const d = new Date();
    return d.getHours().toString().padStart(2,'0') + ':' + d.getMinutes().toString().padStart(2,'0');
}

// ============================================
// TAMPILKAN PESAN DI CHAT (DOM only)
// ============================================
function appendMessageDOM(role, content, timeStr) {
    const container = document.getElementById('ac-messages');
    if (!container) return;

    const isBot = role === 'assistant';
    const time  = timeStr || nowTime();
    const div   = document.createElement('div');
    div.className = `ac-msg ${isBot ? 'bot' : 'user'}`;

    const formatted = formatMessage(content);

    div.innerHTML = isBot
        ? `<div class="msg-avatar">🤖</div>
           <div class="msg-bubble">
               ${formatted}
               <div class="msg-actions">
                   <button onclick="copyText(this)" class="msg-action-btn" title="Salin">📋 Salin</button>
                   <button onclick="downloadNaskah(this)" class="msg-action-btn" title="Unduh">⬇️ Unduh</button>
               </div>
               <div class="msg-time">${time}</div>
           </div>`
        : `<div class="msg-bubble user-bubble">
               ${formatted}
               <div class="msg-time">${time}</div>
           </div>
           <div class="msg-avatar user-av">👤</div>`;

    container.appendChild(div);
    setTimeout(() => div.classList.add('visible'), 10);
    scrollToBottom();
}

// Legacy alias agar tidak break kode lama
function appendMessage(role, content) { appendMessageDOM(role, content); }

// ============================================
// FORMAT PESAN (Markdown sederhana)
// ============================================
function formatMessage(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g,     '<em>$1</em>')
        .replace(/^### (.+)$/gm,  '<h4>$1</h4>')
        .replace(/^## (.+)$/gm,   '<h3>$1</h3>')
        .replace(/^# (.+)$/gm,    '<h2>$1</h2>')
        .replace(/^[\-\*] (.+)$/gm,'<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs,'<ul>$1</ul>')
        .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g,   '<br>')
        .replace(/^(.+)/,  '<p>$1')
        .replace(/(.+)$/, '$1</p>');
}

// ============================================
// TYPING INDICATOR
// ============================================
function showTyping() {
    const container = document.getElementById('ac-messages');
    const id  = 'typing-' + Date.now();
    const div = document.createElement('div');
    div.id        = id;
    div.className = 'ac-msg bot typing-msg';
    div.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-bubble typing-bubble">
            <div class="typing-dots"><span></span><span></span><span></span></div>
            <div class="typing-label">Gemini sedang menulis naskah...</div>
        </div>`;
    container.appendChild(div);
    setTimeout(() => div.classList.add('visible'), 10);
    scrollToBottom();
    return id;
}

function removeTyping(id) {
    document.getElementById(id)?.remove();
}

// ============================================
// PESAN ERROR
// ============================================
function appendError(msg) {
    const container = document.getElementById('ac-messages');
    const div = document.createElement('div');
    div.className = 'ac-msg bot';
    div.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-bubble error-bubble">
            <p>❌ ${msg}</p>
            <div class="msg-time">${nowTime()}</div>
        </div>`;
    container.appendChild(div);
    setTimeout(() => div.classList.add('visible'), 10);
    scrollToBottom();
}

// ============================================
// SALIN TEKS NASKAH
// ============================================
function copyText(btn) {
    const bubble = btn.closest('.msg-bubble');
    const clone  = bubble.cloneNode(true);
    clone.querySelectorAll('.msg-actions,.msg-time').forEach(el => el.remove());
    const text = clone.innerText.trim();

    navigator.clipboard.writeText(text).then(() => {
        btn.textContent = '✅ Disalin!';
        setTimeout(() => { btn.textContent = '📋 Salin'; }, 2000);
    }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        btn.textContent = '✅ Disalin!';
        setTimeout(() => { btn.textContent = '📋 Salin'; }, 2000);
    });
}

// ============================================
// UNDUH NASKAH SEBAGAI FILE TXT
// ============================================
function downloadNaskah(btn) {
    const bubble = btn.closest('.msg-bubble');
    const clone  = bubble.cloneNode(true);
    clone.querySelectorAll('.msg-actions,.msg-time').forEach(el => el.remove());
    const text = clone.innerText.trim();

    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = `naskah-speakup-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    btn.textContent = '✅ Diunduh!';
    setTimeout(() => { btn.textContent = '⬇️ Unduh'; }, 2000);
}

// ============================================
// BERSIHKAN CHAT (tombol 🗑️)
// ============================================
function clearChat() {
    if (!confirm('Hapus semua percakapan?')) return;

    chatHistory = [];
    saveHistory(chatHistory);

    const container = document.getElementById('ac-messages');
    container.dataset.restored = '0';
    container.innerHTML = `
        <div class="ac-msg bot visible">
            <div class="msg-avatar">🤖</div>
            <div class="msg-bubble">
                <p>Chat dibersihkan. Ada yang bisa saya bantu? 😊</p>
                <p>Pilih kategori atau ketik kebutuhanmu!</p>
                <div class="msg-time">${nowTime()}</div>
            </div>
        </div>`;

    document.getElementById('ac-chips').style.display = 'block';
}

// ============================================
// SCROLL KE BAWAH
// ============================================
function scrollToBottom() {
    const container = document.getElementById('ac-messages');
    if (container) {
        setTimeout(() => { container.scrollTop = container.scrollHeight; }, 80);
    }
}

// ============================================
// NOTIFIKASI FAB
// ============================================
function showFabNotif() {
    const notif = document.getElementById('fab-notif');
    if (notif) notif.style.display = 'flex';
}
function hideFabNotif() {
    const notif = document.getElementById('fab-notif');
    if (notif) notif.style.display = 'none';
}

// ============================================
// AUTO-RESIZE TEXTAREA
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    const textarea = document.getElementById('ac-input');
    if (textarea) {
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        });
    }

    // Tandai welcome msg agar tidak ikut dihapus jika history kosong
    const container = document.getElementById('ac-messages');
    if (container) container.dataset.restored = chatHistory.length > 0 ? '0' : '1';
});