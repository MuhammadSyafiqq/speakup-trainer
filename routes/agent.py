from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import requests
import os
import json

agent_bp = Blueprint('agent', __name__)

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_MODEL   = 'google/gemini-2.5-flash-lite'


def call_openrouter(messages: list) -> str:
    """Helper: kirim messages ke OpenRouter dan kembalikan teks response."""
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://speakup.app',  # dianjurkan OpenRouter
        'X-Title': 'SpeakUp',
    }
    payload = {
        'model': OPENROUTER_MODEL,
        'messages': messages,
        'max_tokens': 4096,
    }
    response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)

    if not response.ok:
        # Cetak body error agar mudah debug di terminal
        print(f"OpenRouter error {response.status_code}: {response.text}")
        response.raise_for_status()

    data = response.json()

    # Tangani error yang dikembalikan di dalam JSON (bukan HTTP error)
    if 'error' in data:
        raise Exception(f"OpenRouter API error: {data['error']}")

    return data['choices'][0]['message']['content']


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
# ENDPOINT: KIRIM PESAN KE AI AGENT
# ============================================
@agent_bp.route('/agent/chat', methods=['POST'])
@login_required
def chat():
    try:
        data     = request.get_json()
        history  = data.get('messages', [])
        user_msg = data.get('message', '').strip()

        if not user_msg:
            return jsonify({'error': 'Pesan tidak boleh kosong'}), 400

        if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.startswith('sk-or-xxx'):
            return jsonify({'error': 'OPENROUTER_API_KEY belum dikonfigurasi'}), 500

        # ── Bangun isi percakapan multi-turn ──
        # System prompt sebagai pesan pertama dengan role 'system'
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]

        # Tambahkan history (maks 10 pesan terakhir)
        for msg in history[-10:]:
            role = 'user' if msg['role'] == 'user' else 'assistant'
            messages.append({'role': role, 'content': msg['content']})

        # Tambahkan pesan user baru
        full_user_msg = f"Pesan dari pengguna ({current_user.username}):\n{user_msg}"
        messages.append({'role': 'user', 'content': full_user_msg})

        reply = call_openrouter(messages)

        return jsonify({'success': True, 'reply': reply, 'role': 'assistant'})

    except Exception as e:
        print(f"Agent chat error: {str(e)}")
        return jsonify({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}), 500


# ============================================
# ENDPOINT: QUICK PROMPT KATEGORI
# ============================================
@agent_bp.route('/agent/quick-prompt/<category>', methods=['GET'])
@login_required
def get_quick_prompt(category):
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

        prompt = f"""Tolong buatkan naskah {cat_label} dengan spesifikasi berikut:

TOPIK   : {topic}
DURASI  : {duration}
AUDIENS : {audience}
CATATAN : {notes if notes else 'Tidak ada catatan khusus'}

Buat naskah yang lengkap, menarik, dan siap untuk langsung dibacakan."""

        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user',   'content': prompt},
        ]
        naskah = call_openrouter(messages)

        return jsonify({'success': True, 'naskah': naskah, 'category': cat_label, 'topic': topic})

    except Exception as e:
        print(f"Generate naskah error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500