from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
import google.generativeai as genai
import os
import json

agent_bp = Blueprint('agent', __name__)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ============================================
# SYSTEM PROMPT — Karakter AI Agent SpeakUp
# ============================================
SYSTEM_PROMPT = """Kamu adalah AI Agent SpeakUp — asisten khusus untuk membantu pengguna
membuat naskah public speaking berkualitas tinggi dalam Bahasa Indonesia.

KEMAMPUAN UTAMAMU:
1. Membuat naskah pidato formal (sambutan, wisuda, pernikahan, upacara, dll)
2. Membuat jawaban wawancara kerja yang terstruktur dan meyakinkan
3. Membuat skrip presentasi bisnis atau akademik
4. Membuat argumen debat (pro/kontra) yang logis dan persuasif
5. Membuat teks MC / pembawa acara yang energik dan profesional
6. Membuat naskah storytelling yang menarik dan memukau
7. Memperbaiki / mengedit naskah yang sudah ada
8. Memberikan tips dan saran public speaking

FORMAT NASKAH YANG KAMU BUAT:
- Selalu mulai dengan pembuka yang kuat dan menarik perhatian
- Isi yang terstruktur jelas (minimal 3 poin utama)
- Penutup yang berkesan dan memorable
- Sesuaikan gaya bahasa dengan konteks (formal/semi-formal/casual)
- Cantumkan estimasi durasi bicara
- Berikan catatan tips delivery di akhir naskah

ATURAN PENTING:
- Selalu gunakan Bahasa Indonesia yang baik dan benar
- Jika pengguna meminta kategori spesifik, fokus pada kategori tersebut
- Jika ada informasi yang kurang (topik, durasi, audiens), tanyakan dulu
- Berikan respons yang ramah, antusias, dan memotivasi
- Gunakan emoji secukupnya untuk membuat chat lebih hidup
- Jangan terlalu panjang dalam chat biasa, tapi naskah boleh lengkap

INGAT: Kamu bukan hanya generator naskah, tapi juga PELATIH public speaking
yang memberikan feedback, tips, dan motivasi kepada pengguna."""


# ============================================
# TEMPLATE QUICK PROMPT PER KATEGORI
# ============================================
QUICK_PROMPTS = {
    'pidato': {
        'label': 'Pidato Formal',
        'message': 'Halo! Saya ingin membuat naskah pidato. Bisa bantu saya? Tolong tanyakan informasi yang dibutuhkan seperti topik, durasi, dan konteks acaranya.',
    },
    'wawancara': {
        'label': 'Wawancara Kerja',
        'message': 'Halo! Saya butuh bantuan menyiapkan jawaban untuk wawancara kerja. Bisa bantu saya mempersiapkan jawaban yang baik? Tanyakan posisi dan pertanyaan yang ingin saya latih.',
    },
    'presentasi': {
        'label': 'Presentasi',
        'message': 'Halo! Saya ingin membuat skrip presentasi. Bisa bantu saya? Tanyakan topik, durasi, dan audiens presentasi saya.',
    },
    'debat': {
        'label': 'Debat',
        'message': 'Halo! Saya ingin menyiapkan argumen untuk debat. Bisa bantu saya membuat argumen yang kuat? Tanyakan mosi debat dan posisi saya (pro/kontra).',
    },
    'mc': {
        'label': 'Master of Ceremony',
        'message': 'Halo! Saya ingin membuat teks MC untuk sebuah acara. Bisa bantu saya? Tanyakan jenis acara, rundown, dan gaya yang diinginkan.',
    },
    'storytelling': {
        'label': 'Storytelling',
        'message': 'Halo! Saya ingin membuat naskah cerita yang menarik. Bisa bantu saya? Tanyakan tema, pesan yang ingin disampaikan, dan audiens targetnya.',
    },
}


# ============================================
# ENDPOINT: KIRIM PESAN KE AI AGENT (STREAMING)
# ============================================
@agent_bp.route('/agent/chat', methods=['POST'])
@login_required
def chat():
    """
    Endpoint utama chat dengan AI Agent.
    Mendukung streaming response agar terasa real-time.
    """
    try:
        data     = request.get_json()
        messages = data.get('messages', [])  # history chat
        user_msg = data.get('message', '').strip()

        if not user_msg:
            return jsonify({'error': 'Pesan tidak boleh kosong'}), 400

        if not GEMINI_API_KEY or GEMINI_API_KEY.startswith('AIzaSy_xxx'):
            return jsonify({'error': 'GEMINI_API_KEY belum dikonfigurasi'}), 500

        # Bangun history chat untuk Gemini (multi-turn conversation)
        chat_history = []
        for msg in messages:
            role    = 'user' if msg['role'] == 'user' else 'model'
            content = msg['content']
            chat_history.append({'role': role, 'parts': [content]})

        # Mulai chat session dengan history
        chat_session = model.start_chat(history=chat_history)

        # Kirim pesan dengan system prompt sebagai konteks
        full_prompt = f"{SYSTEM_PROMPT}\n\n---\n\nPesan dari pengguna ({current_user.username}):\n{user_msg}"

        # Generate response (non-streaming untuk simplicity & compatibility)
        response = chat_session.send_message(full_prompt)
        reply    = response.text

        return jsonify({
            'success': True,
            'reply'  : reply,
            'role'   : 'assistant'
        })

    except Exception as e:
        print(f"❌ Agent chat error: {str(e)}")
        return jsonify({
            'success': False,
            'error'  : f'Terjadi kesalahan: {str(e)}'
        }), 500


# ============================================
# ENDPOINT: QUICK PROMPT KATEGORI
# ============================================
@agent_bp.route('/agent/quick-prompt/<category>', methods=['GET'])
@login_required
def get_quick_prompt(category):
    """Ambil template pesan awal untuk tiap kategori"""
    prompt = QUICK_PROMPTS.get(category)
    if not prompt:
        return jsonify({'error': 'Kategori tidak ditemukan'}), 404
    return jsonify({'success': True, 'prompt': prompt})


# ============================================
# ENDPOINT: GENERATE NASKAH LANGSUNG
# ============================================
@agent_bp.route('/agent/generate', methods=['POST'])
@login_required
def generate_naskah():
    """
    Generate naskah langsung dengan parameter spesifik.
    Digunakan untuk quick generate tanpa percakapan panjang.
    """
    try:
        data     = request.get_json()
        category = data.get('category', 'pidato')
        topic    = data.get('topic', '')
        duration = data.get('duration', '5 menit')
        audience = data.get('audience', 'umum')
        notes    = data.get('notes', '')

        if not topic:
            return jsonify({'error': 'Topik harus diisi'}), 400

        category_labels = {
            'pidato'      : 'Pidato Formal',
            'wawancara'   : 'Wawancara Kerja',
            'presentasi'  : 'Presentasi',
            'debat'       : 'Debat',
            'mc'          : 'Master of Ceremony (MC)',
            'storytelling': 'Storytelling',
        }

        cat_label = category_labels.get(category, category)

        prompt = f"""{SYSTEM_PROMPT}

---

Tolong buatkan naskah {cat_label} dengan spesifikasi berikut:

📝 TOPIK     : {topic}
⏱️ DURASI    : {duration}
👥 AUDIENS   : {audience}
📌 CATATAN   : {notes if notes else 'Tidak ada catatan khusus'}

Buat naskah yang lengkap, menarik, dan siap untuk langsung dibacakan.
Sertakan:
1. Naskah lengkap dengan formatting yang jelas
2. Estimasi waktu per bagian
3. Tips delivery dan gestur yang disarankan
4. Kata kunci yang perlu ditekankan (bold/caps)"""

        response = model.generate_content(prompt)
        naskah   = response.text

        return jsonify({
            'success': True,
            'naskah' : naskah,
            'category': cat_label,
            'topic'  : topic,
        })

    except Exception as e:
        print(f"❌ Generate naskah error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500