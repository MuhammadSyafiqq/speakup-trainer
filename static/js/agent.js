// ============================================
// SPEAKUP AI AGENT — CHATBOX JAVASCRIPT
// ============================================

// State
let chatOpen = false;
let isTyping = false;
let chatHistory = []; // [{role: 'user'|'assistant', content: '...'}]

// ============================================
// TOGGLE BUKA / TUTUP CHAT
// ============================================
function toggleAgentChat() {
  const chat = document.getElementById("agent-chat");
  const fab = document.querySelector(".agent-fab");
  chatOpen = !chatOpen;

  if (chatOpen) {
    chat.classList.add("open");
    fab.classList.add("active");
    document.getElementById("fab-icon").textContent = "✕";
    document.getElementById("ac-input").focus();
    hideFabNotif();
    // Scroll ke bawah
    scrollToBottom();
  } else {
    chat.classList.remove("open");
    fab.classList.remove("active");
    document.getElementById("fab-icon").textContent = "✍️";
  }
}

// ============================================
// QUICK PROMPT — Klik chip kategori
// ============================================
async function quickPrompt(category) {
  // Sembunyikan chips setelah dipilih
  document.getElementById("ac-chips").style.display = "none";

  const labels = {
    pidato: "🎤 Pidato Formal",
    wawancara: "💼 Wawancara Kerja",
    presentasi: "📊 Presentasi",
    debat: "⚖️ Debat",
    mc: "🎭 Master of Ceremony",
    storytelling: "📖 Storytelling",
  };

  const userMsg = `Halo! Saya ingin membuat naskah untuk kategori ${labels[category]}. Tolong bantu saya!`;
  appendMessage("user", userMsg);
  chatHistory.push({ role: "user", content: userMsg });
  await sendToAgent(userMsg);
}

// ============================================
// HANDLE ENTER KEY
// ============================================
function handleEnter(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

// ============================================
// KIRIM PESAN USER
// ============================================
async function sendMessage() {
  const input = document.getElementById("ac-input");
  const msg = input.value.trim();

  if (!msg || isTyping) return;

  // Reset input
  input.value = "";
  input.style.height = "auto";

  // Sembunyikan chips jika masih ada
  document.getElementById("ac-chips").style.display = "none";

  // Tampilkan pesan user
  appendMessage("user", msg);
  chatHistory.push({ role: "user", content: msg });

  // Kirim ke AI
  await sendToAgent(msg);
}

// ============================================
// KIRIM KE BACKEND AGENT
// ============================================
async function sendToAgent(userMsg) {
  if (isTyping) return;
  isTyping = true;

  // Tampilkan typing indicator
  const typingId = showTyping();

  try {
    const res = await fetch("/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: userMsg,
        messages: chatHistory.slice(-10), // kirim max 10 pesan terakhir
      }),
    });

    const data = await res.json();
    removeTyping(typingId);

    if (data.success && data.reply) {
      appendMessage("assistant", data.reply);
      chatHistory.push({ role: "assistant", content: data.reply });

      // Notif jika chat tertutup
      if (!chatOpen) showFabNotif();
    } else {
      appendError(data.error || "Terjadi kesalahan, coba lagi.");
    }
  } catch (err) {
    removeTyping(typingId);
    appendError("Koneksi gagal. Periksa internet kamu.");
    console.error("Agent error:", err);
  } finally {
    isTyping = false;
  }
}

// ============================================
// TAMPILKAN PESAN DI CHAT
// ============================================
function appendMessage(role, content) {
  const container = document.getElementById("ac-messages");
  const isBot = role === "assistant";

  const div = document.createElement("div");
  div.className = `ac-msg ${isBot ? "bot" : "user"}`;

  const now = new Date();
  const timeStr =
    now.getHours().toString().padStart(2, "0") +
    ":" +
    now.getMinutes().toString().padStart(2, "0");

  // Format markdown sederhana untuk naskah
  const formatted = formatMessage(content);

  div.innerHTML = isBot
    ? `<div class="msg-avatar">🤖</div>
           <div class="msg-bubble">
               ${formatted}
               <div class="msg-actions">
                   <button onclick="copyText(this)" class="msg-action-btn" title="Salin">📋 Salin</button>
                   <button onclick="downloadNaskah(this)" class="msg-action-btn" title="Unduh">⬇️ Unduh</button>
               </div>
               <div class="msg-time">${timeStr}</div>
           </div>`
    : `<div class="msg-bubble user-bubble">
               ${formatted}
               <div class="msg-time">${timeStr}</div>
           </div>
           <div class="msg-avatar user-av">👤</div>`;

  container.appendChild(div);

  // Animasi masuk
  setTimeout(() => div.classList.add("visible"), 10);

  scrollToBottom();
}

// ============================================
// FORMAT PESAN (Markdown sederhana)
// ============================================
function formatMessage(text) {
  return (
    text
      // Bold **text**
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      // Italic *text*
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      // Heading ### text
      .replace(/^### (.+)$/gm, "<h4>$1</h4>")
      .replace(/^## (.+)$/gm, "<h3>$1</h3>")
      .replace(/^# (.+)$/gm, "<h2>$1</h2>")
      // List - item
      .replace(/^[\-\*] (.+)$/gm, "<li>$1</li>")
      .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
      // Numbered list
      .replace(/^\d+\. (.+)$/gm, "<li>$1</li>")
      // Line breaks
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>")
      // Wrap in p
      .replace(/^(.+)/, "<p>$1")
      .replace(/(.+)$/, "$1</p>")
  );
}

// ============================================
// TYPING INDICATOR
// ============================================
function showTyping() {
  const container = document.getElementById("ac-messages");
  const id = "typing-" + Date.now();
  const div = document.createElement("div");
  div.id = id;
  div.className = "ac-msg bot typing-msg";
  div.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-bubble typing-bubble">
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>
            <div class="typing-label">Gemini sedang menulis naskah...</div>
        </div>`;
  container.appendChild(div);
  setTimeout(() => div.classList.add("visible"), 10);
  scrollToBottom();
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ============================================
// PESAN ERROR
// ============================================
function appendError(msg) {
  const container = document.getElementById("ac-messages");
  const div = document.createElement("div");
  div.className = "ac-msg bot";
  div.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-bubble error-bubble">
            <p>❌ ${msg}</p>
            <div class="msg-time">${new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}</div>
        </div>`;
  container.appendChild(div);
  setTimeout(() => div.classList.add("visible"), 10);
  scrollToBottom();
}

// ============================================
// SALIN TEKS NASKAH
// ============================================
function copyText(btn) {
  const bubble = btn.closest(".msg-bubble");
  // Ambil teks tanpa tombol actions dan waktu
  const clone = bubble.cloneNode(true);
  clone
    .querySelectorAll(".msg-actions, .msg-time")
    .forEach((el) => el.remove());
  const text = clone.innerText.trim();

  navigator.clipboard
    .writeText(text)
    .then(() => {
      btn.textContent = "✅ Disalin!";
      setTimeout(() => {
        btn.textContent = "📋 Salin";
      }, 2000);
    })
    .catch(() => {
      // Fallback untuk browser lama
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      btn.textContent = "✅ Disalin!";
      setTimeout(() => {
        btn.textContent = "📋 Salin";
      }, 2000);
    });
}

// ============================================
// UNDUH NASKAH SEBAGAI FILE TXT
// ============================================
function downloadNaskah(btn) {
  const bubble = btn.closest(".msg-bubble");
  const clone = bubble.cloneNode(true);
  clone
    .querySelectorAll(".msg-actions, .msg-time")
    .forEach((el) => el.remove());
  const text = clone.innerText.trim();

  const filename = `naskah-speakup-${Date.now()}.txt`;
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);

  btn.textContent = "✅ Diunduh!";
  setTimeout(() => {
    btn.textContent = "⬇️ Unduh";
  }, 2000);
}

// ============================================
// BERSIHKAN CHAT
// ============================================
function clearChat() {
  if (!confirm("Hapus semua percakapan?")) return;

  chatHistory = [];

  const container = document.getElementById("ac-messages");
  container.innerHTML = `
        <div class="ac-msg bot visible">
            <div class="msg-avatar">🤖</div>
            <div class="msg-bubble">
                <p>Chat dibersihkan. Ada yang bisa saya bantu? 😊</p>
                <p>Pilih kategori atau ketik kebutuhanmu!</p>
                <div class="msg-time">Sekarang</div>
            </div>
        </div>`;

  document.getElementById("ac-chips").style.display = "block";
}

// ============================================
// SCROLL KE BAWAH
// ============================================
function scrollToBottom() {
  const container = document.getElementById("ac-messages");
  if (container) {
    setTimeout(() => {
      container.scrollTop = container.scrollHeight;
    }, 100);
  }
}

// ============================================
// NOTIFIKASI FAB
// ============================================
function showFabNotif() {
  const notif = document.getElementById("fab-notif");
  if (notif) notif.style.display = "flex";
}

function hideFabNotif() {
  const notif = document.getElementById("fab-notif");
  if (notif) notif.style.display = "none";
}

// ============================================
// AUTO-RESIZE TEXTAREA
// ============================================
document.addEventListener("DOMContentLoaded", () => {
  const textarea = document.getElementById("ac-input");
  if (textarea) {
    textarea.addEventListener("input", () => {
      textarea.style.height = "auto";
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + "px";
    });
  }
});
