from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models.session import PracticeSession
from extensions import db
import requests
import base64
import os, json, re, uuid
from datetime import datetime
from services.gemini_service import convert_to_mp3

interview_bp = Blueprint('interview', __name__)

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_MODEL   = os.getenv('OPENROUTER_MODEL', 'google/gemini-2.5-flash-lite')

# ============================================
# HELPER — CALL OPENROUTER
# ============================================
def call_openrouter(messages: list, max_tokens: int = 4096) -> str:
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://speakup.app',
        'X-Title': 'SpeakUp',
    }
    payload = {
        'model': OPENROUTER_MODEL,
        'messages': messages,
        'max_tokens': max_tokens,
    }
    response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
    if not response.ok:
        print(f'OpenRouter error {response.status_code}: {response.text[:500]}')
        # Cek apakah response berupa HTML (bukan JSON) sebelum raise
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' in content_type or response.text.strip().startswith('<'):
            raise Exception(
                f"OpenRouter mengembalikan halaman HTML (status {response.status_code}). "
                f"Kemungkinan API key tidak valid, rate limit, atau layanan sedang gangguan."
            )
        # Coba parse JSON error dari OpenRouter
        try:
            err_data = response.json()
            err_msg  = err_data.get('error', {})
            if isinstance(err_msg, dict):
                err_msg = err_msg.get('message', str(err_data))
            raise Exception(f"OpenRouter API error ({response.status_code}): {err_msg}")
        except (ValueError, KeyError):
            response.raise_for_status()

    # Pastikan response adalah JSON sebelum parse
    content_type = response.headers.get('Content-Type', '')
    if 'text/html' in content_type or response.text.strip().startswith('<'):
        raise Exception(
            "OpenRouter mengembalikan HTML alih-alih JSON. "
            "Periksa OPENROUTER_API_KEY dan koneksi jaringan."
        )

    try:
        data = response.json()
    except ValueError as e:
        raise Exception(f"Gagal parse response OpenRouter sebagai JSON: {e}. "
                        f"Response awal: {response.text[:200]}")

    if 'error' in data:
        err = data['error']
        if isinstance(err, dict):
            err = err.get('message', str(err))
        raise Exception(f"OpenRouter API error: {err}")

    return data['choices'][0]['message']['content']


# ============================================
# POSISI WAWANCARA
# ============================================
INTERVIEW_POSITIONS = [
    {'id': 'fresh_graduate', 'label': 'Fresh Graduate Umum',   'icon': '🎓'},
    {'id': 'software_dev',   'label': 'Software Developer',     'icon': '💻'},
    {'id': 'marketing',      'label': 'Marketing / Sales',      'icon': '📢'},
    {'id': 'finance',        'label': 'Keuangan / Akuntansi',   'icon': '💰'},
    {'id': 'hr',             'label': 'Human Resources (HR)',    'icon': '👥'},
    {'id': 'manager',        'label': 'Manajer / Team Lead',    'icon': '🏆'},
    {'id': 'internship',     'label': 'Magang / Internship',    'icon': '📚'},
    {'id': 'custom',         'label': 'Posisi Lainnya (Custom)', 'icon': '✏️'},
]


# ============================================
# PROMPT BUILDERS
# ============================================
def build_interviewer_prompt(position: str, company: str, session_data: dict) -> str:
    """
    Bangun prompt untuk AI interviewer.
    Jawaban user bisa berupa teks atau placeholder '[audio direkam]'.
    Transkripsi audio dilakukan batch di akhir sesi untuk hemat kuota.
    AI cukup generate pertanyaan berurutan tanpa bergantung isi jawaban.
    """
    question_num   = session_data.get('question_num', 1)
    total_q        = session_data.get('total_questions', 7)
    answers_so_far = session_data.get('answers', [])

    context = '\n'.join([
        f"Q{i+1}: {a['question']}\nA{i+1}: {'[sudah dijawab via audio]' if not a.get('answer','').strip() or a.get('answer','') == '[audio direkam]' else a['answer']}"
        for i, a in enumerate(answers_so_far)
    ])

    return f"""Kamu adalah HRD profesional yang sedang melakukan wawancara kerja dalam Bahasa Indonesia.

KONTEKS WAWANCARA:
- Posisi    : {position}
- Perusahaan: {company if company else 'perusahaan kami'}
- Pertanyaan: {question_num} dari {total_q}

RIWAYAT WAWANCARA SEJAUH INI:
{context if context else '(Belum ada jawaban sebelumnya — ini pertanyaan pertama)'}

INSTRUKSI PENTING:
1. Berikan SATU pertanyaan wawancara yang relevan untuk posisi {position}
2. Pertanyaan harus natural seperti HRD sungguhan — tidak kaku
3. Sesuaikan pertanyaan dengan jawaban sebelumnya jika ada (follow-up alami)
4. Urutan pertanyaan yang ideal:
   - Q1: Perkenalan diri (tell me about yourself)
   - Q2-3: Pengalaman & latar belakang
   - Q4-5: Keahlian teknis / kompetensi spesifik posisi
   - Q6: Situasional / behavioral (STAR method)
   - Q7: Motivasi & pertanyaan penutup
5. Jika ini pertanyaan ke-{question_num}, ikuti urutan di atas
6. HANYA tulis pertanyaan saja — tanpa awalan "Pertanyaan:" atau nomor
7. Buat pertanyaan terasa hangat dan profesional

Tulis pertanyaan sekarang (1-2 kalimat saja):"""


def build_batch_transcribe_prompt(qa_pairs: list) -> str:
    """
    Prompt untuk transkripsi SEMUA jawaban audio sekaligus di akhir sesi.
    qa_pairs: list of { question_num, question, audio_filename }
    """
    questions_text = '\n'.join([
        f"Jawaban {p['question_num']}: untuk pertanyaan \"{p['question']}\""
        for p in qa_pairs
    ])

    return f"""Kamu adalah sistem transkripsi profesional untuk sesi wawancara kerja.

Kamu akan menerima beberapa file audio jawaban wawancara sekaligus.
Untuk setiap audio, transkripsi ke teks Bahasa Indonesia dengan akurat.

Daftar jawaban yang perlu ditranskripsikan:
{questions_text}

ATURAN TRANSKRIPSI:
- Pertahankan kata pengisi (em, eh, anu, um) apa adanya
- Tandai jeda panjang (>2 detik) dengan [JEDA]
- Tandai audio tidak jelas dengan [tidak jelas]
- Jika audio kosong/sunyi, tulis [tidak ada jawaban]
- Jangan tambahkan komentar atau penjelasan

Berikan hasil dalam format JSON persis seperti ini (HANYA JSON):
{{
    "transcripts": [
        {{
            "question_num": 1,
            "transcript": "<teks transkripsi jawaban 1>"
        }},
        {{
            "question_num": 2,
            "transcript": "<teks transkripsi jawaban 2>"
        }}
    ]
}}"""


def build_analysis_prompt(position: str, company: str, answers: list) -> str:
    """
    Prompt analisis akhir sesi.
    answers sudah berisi teks jawaban (hasil transkripsi audio atau teks langsung).
    """
    qa_text = '\n\n'.join([
        f"Pertanyaan {i+1}: {a['question']}\n"
        f"Jawaban     : {a['answer']}\n"
        f"Durasi      : {a.get('duration', 0)} detik"
        for i, a in enumerate(answers)
    ])

    return f"""Kamu adalah konsultan karir profesional. Analisis hasil wawancara kerja berikut secara mendalam.

POSISI    : {position}
PERUSAHAAN: {company if company else 'tidak disebutkan'}

REKAP SESI WAWANCARA:
{qa_text}

Berikan analisis LENGKAP dalam format JSON persis seperti ini (HANYA JSON, tidak ada teks lain):
{{
    "overall_score": <angka 0-100>,
    "score_communication": <angka 0-100>,
    "score_confidence": <angka 0-100>,
    "score_relevance": <angka 0-100>,
    "score_structure": <angka 0-100>,
    "score_vocabulary": <angka 0-100>,

    "grade": "<A/B/C/D/E>",
    "grade_text": "<teks penilaian singkat>",

    "summary": "<ringkasan performa secara keseluruhan dalam 3-4 kalimat>",

    "per_answer_feedback": [
        {{
            "question_num": 1,
            "question": "<pertanyaan>",
            "answer_summary": "<ringkasan singkat jawaban>",
            "score": <0-100>,
            "feedback": "<feedback spesifik untuk jawaban ini>",
            "highlight": "<kalimat terbaik dari jawaban ini jika ada>"
        }}
    ],

    "strengths": [
        "<kelebihan 1 spesifik>",
        "<kelebihan 2 spesifik>",
        "<kelebihan 3 spesifik>"
    ],
    "improvements": [
        "<area perbaikan 1 dengan saran konkret>",
        "<area perbaikan 2 dengan saran konkret>",
        "<area perbaikan 3 dengan saran konkret>"
    ],
    "tips": [
        "<tips praktis 1 untuk wawancara berikutnya>",
        "<tips praktis 2>",
        "<tips praktis 3>"
    ],

    "feedback_detail": {{
        "clarity"   : "<feedback spesifik aspek kejelasan komunikasi>",
        "structure" : "<feedback spesifik aspek struktur jawaban>",
        "confidence": "<feedback spesifik aspek kepercayaan diri>",
        "relevance" : "<feedback spesifik aspek relevansi jawaban>",
        "vocabulary": "<feedback spesifik aspek kosakata dan diksi>",
        "fluency"   : "<feedback spesifik aspek kelancaran bicara>"
    }},

    "hiring_recommendation": "<Sangat Direkomendasikan / Direkomendasikan / Dipertimbangkan / Belum Direkomendasikan>",
    "hiring_reason": "<alasan singkat rekomendasi hiring>"
}}

PENTING:
- Semua teks harus dalam Bahasa Indonesia
- JANGAN gunakan format markdown seperti **bold** atau *italic* di dalam nilai JSON
- Tulis teks biasa tanpa simbol formatting apapun
- Berikan penilaian yang JUJUR, KONSTRUKTIF, dan SPESIFIK berdasarkan setiap jawaban"""


# ============================================
# HELPERS — PEMBERSIH TEKS
# ============================================
def clean_markdown(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*',     r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'`{1,3}', '', text)
    return text.strip()


def safe_list_to_str(val, separator=' | ') -> str:
    if isinstance(val, list):
        return separator.join(clean_markdown(str(v)) for v in val if v)
    return clean_markdown(str(val)) if val else ''


def safe_tips_to_str(tips: list) -> str:
    if not isinstance(tips, list):
        return ''
    return '\n'.join(f"• {clean_markdown(str(t))}" for t in tips if t)


def parse_json_response(raw: str) -> dict | None:
    """Coba berbagai strategi parse JSON dari response LLM."""
    raw = re.sub(r'```json\s*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'```\s*', '', raw)
    raw = re.sub(r'//[^\n]*', '', raw)
    raw = raw.strip()

    for attempt in [
        raw,
        raw[raw.find('{'):raw.rfind('}')+1] if '{' in raw else '',
    ]:
        if not attempt:
            continue
        try:
            return json.loads(attempt)
        except Exception:
            pass
    return None


def save_audio_temp(audio_file, user_id: int) -> str:
    """Simpan file audio ke folder upload sementara, kembalikan path."""
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
    os.makedirs(upload_folder, exist_ok=True)
    ext      = os.path.splitext(audio_file.filename)[1] or '.webm'
    filename = f"interview_{user_id}_{uuid.uuid4().hex}{ext}"
    path     = os.path.join(upload_folder, filename)
    audio_file.save(path)
    return path


def cleanup_files(*paths):
    """Hapus file-file sementara."""
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


# ============================================
# HALAMAN SETUP WAWANCARA
# ============================================
@interview_bp.route('/interview/setup')
@login_required
def setup():
    return render_template('interview/setup.html', positions=INTERVIEW_POSITIONS)


# ============================================
# HALAMAN SESI WAWANCARA
# ============================================
@interview_bp.route('/interview/session')
@login_required
def session_page():
    position       = request.args.get('position', 'Fresh Graduate')
    company        = request.args.get('company', '')
    total_q        = int(request.args.get('total_q', 7))
    position_label = request.args.get('position_label', position)

    return render_template('interview/session.html',
                           position=position,
                           position_label=position_label,
                           company=company,
                           total_q=total_q)


# ============================================
# API: DAPATKAN PERTANYAAN BERIKUTNYA
# ============================================
# Alur baru:
#   1. Frontend rekam audio jawaban user → simpan di sisi client (IndexedDB / blob URL)
#   2. Frontend kirim teks jawaban (bisa kosong/"[audio disimpan]") ke endpoint ini
#      agar AI bisa generate pertanyaan follow-up
#   3. Audio BELUM dikirim ke server — disimpan di browser sampai sesi selesai
# ============================================
@interview_bp.route('/interview/get-question', methods=['POST'])
@login_required
def get_question():
    try:
        data         = request.get_json()
        position     = data.get('position', 'Fresh Graduate')
        company      = data.get('company', '')
        session_data = data.get('session_data', {})

        # session_data.answers[].answer bisa berisi teks ringkas dari user
        # (misalnya summary singkat yang user ketik) atau placeholder
        # "[audio direkam]" — AI tetap bisa generate pertanyaan kontekstual
        # jika ada jawaban sebelumnya, bahkan dari summary singkat sekalipun.

        prompt   = build_interviewer_prompt(position, company, session_data)
        question = call_openrouter(
            [{'role': 'user', 'content': prompt}],
            max_tokens=256  # pertanyaan pendek — hemat token
        ).strip()

        # Bersihkan prefix tidak perlu
        for prefix in ['Pertanyaan:', 'Q:', 'HRD:', 'Interviewer:']:
            if question.startswith(prefix):
                question = question[len(prefix):].strip()

        return jsonify({'success': True, 'question': question})

    except Exception as e:
        print(f'get_question error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# API: UPLOAD & SIMPAN AUDIO PER JAWABAN
# ============================================
# Endpoint ini HANYA menyimpan file audio ke server — tidak transkripsi.
# Dipanggil frontend setelah user selesai menjawab tiap pertanyaan.
# Audio disimpan dengan nama terstruktur agar mudah ditemukan saat analisis.
# ============================================
@interview_bp.route('/interview/save-audio', methods=['POST'])
@login_required
def save_audio():
    """
    Terima file audio satu jawaban, simpan ke disk.
    Kembalikan filename agar frontend bisa track daftar audio.
    TIDAK melakukan transkripsi — transkripsi dilakukan batch di akhir sesi.
    """
    try:
        if 'audio' not in request.files:
            return jsonify({'success': False, 'error': 'Tidak ada file audio'}), 400

        audio_file = request.files['audio']
        q_num      = request.form.get('q_num', '1')

        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
        os.makedirs(upload_folder, exist_ok=True)

        # Nama file terstruktur: interview_{user_id}_q{num}_{uuid}.webm
        ext      = os.path.splitext(audio_file.filename)[1] or '.webm'
        filename = f"interview_{current_user.id}_q{q_num}_{uuid.uuid4().hex}{ext}"
        path     = os.path.join(upload_folder, filename)
        audio_file.save(path)

        print(f'Audio Q{q_num} tersimpan: {filename}')
        return jsonify({'success': True, 'filename': filename, 'q_num': int(q_num)})

    except Exception as e:
        print(f'save_audio error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# API: TRANSKRIPSI BATCH + ANALISIS AKHIR
# ============================================
# Alur:
#   1. Terima daftar { question_num, question, filename, duration } dari frontend
#   2. Transkripsi semua audio sekaligus (satu panggilan AI per audio) secara loop
#   3. Gabungkan hasil transkripsi ke dalam answers
#   4. Jalankan analisis akhir dengan semua jawaban lengkap
#   5. Simpan ke database, kembalikan hasil
#   6. Hapus semua file audio sementara
# ============================================
@interview_bp.route('/interview/analyze', methods=['POST'])
@login_required
def analyze():
    """
    Endpoint analisis akhir sesi.
    Menerima JSON body:
    {
        "position"  : "Software Developer",
        "company"   : "PT Maju Bersama",
        "answers"   : [
            {
                "question_num" : 1,
                "question"     : "Ceritakan tentang diri kamu...",
                "filename"     : "interview_5_q1_abc123.webm",  // jika ada audio
                "answer"       : "",  // opsional: teks jawaban jika tidak ada audio
                "duration"     : 45
            },
            ...
        ]
    }
    """
    tmp_files = []  # track semua file sementara untuk cleanup

    try:
        data     = request.get_json()
        position = data.get('position', 'Fresh Graduate')
        company  = data.get('company', '')
        answers  = data.get('answers', [])

        if not answers:
            return jsonify({'success': False, 'error': 'Tidak ada jawaban'}), 400

        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')

        # ── LANGKAH 1: Transkripsi audio untuk setiap jawaban yang punya file audio ──
        print(f'Memulai transkripsi batch untuk {len(answers)} jawaban...')

        for ans in answers:
            filename = ans.get('filename', '')
            q_num    = ans.get('question_num', '?')

            # Jika jawaban sudah berisi teks (mode teks atau sudah diisi), lewati
            if ans.get('answer', '').strip() and ans['answer'] != '[audio direkam]':
                print(f'  Q{q_num}: sudah ada teks jawaban, skip transkripsi')
                continue

            # Jika tidak ada filename, set placeholder
            if not filename:
                ans['answer'] = '[Tidak ada jawaban]'
                continue

            audio_path = os.path.join(upload_folder, filename)
            if not os.path.exists(audio_path):
                print(f'  Q{q_num}: file audio tidak ditemukan ({filename})')
                ans['answer'] = '[File audio tidak ditemukan]'
                continue

            # Konversi ke MP3
            mp3_path, was_converted = convert_to_mp3(audio_path)
            if was_converted:
                tmp_files.append(mp3_path)
            tmp_files.append(audio_path)

            try:
                file_size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
                print(f'  Q{q_num}: transkripsi audio ({file_size_mb:.1f}MB)...')

                with open(mp3_path, 'rb') as f:
                    audio_b64 = base64.b64encode(f.read()).decode('utf-8')

                prompt_text = f"""Transkripsi jawaban audio wawancara kerja berikut ke teks Bahasa Indonesia.

Pertanyaan yang diajukan: "{ans.get('question', '')}"

Aturan:
- Tulis apa yang diucapkan persis apa adanya
- Pertahankan kata pengisi (em, eh, anu, um)
- Tandai jeda panjang dengan [JEDA]
- Jika audio kosong atau tidak jelas, tulis [tidak ada jawaban terdengar]
- HANYA tulis transkripsi, tanpa komentar apapun"""

                messages = [
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'image_url',
                                'image_url': {
                                    'url': f'data:audio/mp3;base64,{audio_b64}'
                                }
                            },
                            {
                                'type': 'text',
                                'text': prompt_text
                            }
                        ]
                    }
                ]

                transcript = call_openrouter(messages, max_tokens=1024).strip()
                if not transcript:
                    transcript = '[Jawaban tidak terdengar]'

                ans['answer'] = transcript
                print(f'  Q{q_num}: transkripsi selesai ({len(transcript)} karakter)')

            except Exception as e:
                print(f'  Q{q_num}: transkripsi gagal — {e}')
                ans['answer'] = '[Transkripsi gagal, silakan coba ulang]'

        # ── LANGKAH 2: Analisis semua jawaban sekaligus ──
        print('Memulai analisis akhir sesi...')
        prompt = build_analysis_prompt(position, company, answers)
        raw    = call_openrouter(
            [{'role': 'user', 'content': prompt}],
            max_tokens=4096
        )

        result = parse_json_response(raw)
        if not result:
            return jsonify({'success': False, 'error': 'Gagal parse hasil analisis'}), 500

        # ── LANGKAH 3: Bersihkan & normalisasi output ──
        summary     = clean_markdown(result.get('summary', ''))
        hire_rec    = clean_markdown(result.get('hiring_recommendation', ''))
        hire_reason = clean_markdown(result.get('hiring_reason', ''))
        strengths   = safe_list_to_str(result.get('strengths', []))
        weaknesses  = safe_list_to_str(result.get('improvements', []))
        suggestions = safe_tips_to_str(result.get('tips', []))

        raw_fd = result.get('feedback_detail', {})
        if not isinstance(raw_fd, dict):
            raw_fd = {}
        feedback_detail = {
            'clarity'   : clean_markdown(raw_fd.get('clarity',    'Tidak tersedia')),
            'structure' : clean_markdown(raw_fd.get('structure',  'Tidak tersedia')),
            'confidence': clean_markdown(raw_fd.get('confidence', 'Tidak tersedia')),
            'relevance' : clean_markdown(raw_fd.get('relevance',  'Tidak tersedia')),
            'vocabulary': clean_markdown(raw_fd.get('vocabulary', 'Tidak tersedia')),
            'fluency'   : clean_markdown(raw_fd.get('fluency',    'Tidak tersedia')),
        }

        per_ans_clean = []
        for item in result.get('per_answer_feedback', []):
            if isinstance(item, dict):
                per_ans_clean.append({
                    'question_num'  : item.get('question_num', 0),
                    'question'      : clean_markdown(item.get('question', '')),
                    'answer_summary': clean_markdown(item.get('answer_summary', '')),
                    'score'         : item.get('score', 0),
                    'feedback'      : clean_markdown(item.get('feedback', '')),
                    'highlight'     : clean_markdown(item.get('highlight', '')),
                })

        # ── LANGKAH 4: Simpan ke database ──
        transcript_full = '\n\n'.join([
            f"Q{a.get('question_num','')}: {a['question']}\nA: {a['answer']}"
            for a in answers
        ])

        session_obj = PracticeSession(
            user_id          = current_user.id,
            category         = 'wawancara',
            title            = f"Wawancara {position}" + (f" di {company}" if company else ''),
            transcript       = transcript_full,
            score_total      = float(result.get('overall_score', 0)),
            score_clarity    = float(result.get('score_communication', 0)),
            score_structure  = float(result.get('score_structure', 0)),
            score_confidence = float(result.get('score_confidence', 0)),
            score_relevance  = float(result.get('score_relevance', 0)),
            score_vocabulary = float(result.get('score_vocabulary', 0)),
            score_fluency    = float(result.get('score_communication', 0)),
            strengths        = strengths,
            weaknesses       = weaknesses,
            suggestions      = suggestions,
            status           = 'completed',
            duration_seconds = sum(a.get('duration', 0) for a in answers),
        )

        session_obj.set_feedback({
            'clarity'              : feedback_detail['clarity'],
            'structure'            : feedback_detail['structure'],
            'confidence'           : feedback_detail['confidence'],
            'relevance'            : feedback_detail['relevance'],
            'vocabulary'           : feedback_detail['vocabulary'],
            'fluency'              : feedback_detail['fluency'],
            'feedback_detail'      : feedback_detail,
            'per_answer_feedback'  : per_ans_clean,
            'hiring_recommendation': hire_rec,
            'hiring_reason'        : hire_reason,
            'summary'              : summary,
            'tips'                 : result.get('tips', []),
            'improvements'         : result.get('improvements', []),
            # Simpan transkripsi per jawaban untuk referensi
            'transcripts'          : [
                {
                    'question_num': a.get('question_num'),
                    'question'    : a.get('question'),
                    'transcript'  : a.get('answer'),
                    'duration'    : a.get('duration', 0),
                }
                for a in answers
            ],
        })

        db.session.add(session_obj)
        db.session.commit()
        print(f'Sesi wawancara #{session_obj.id} tersimpan')

        return jsonify({
            'success'   : True,
            'session_id': session_obj.id,
            'result'    : result,
            # Kembalikan juga transkripsi agar frontend bisa tampilkan
            'transcripts': [
                {
                    'question_num': a.get('question_num'),
                    'question'    : a.get('question'),
                    'transcript'  : a.get('answer'),
                }
                for a in answers
            ],
        })

    except Exception as e:
        print(f'analyze error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        # Hapus semua file audio sementara
        if tmp_files:
            print(f'Membersihkan {len(tmp_files)} file sementara...')
            cleanup_files(*tmp_files)


# ============================================
# HALAMAN HASIL WAWANCARA
# ============================================
@interview_bp.route('/interview/result/<int:session_id>')
@login_required
def result(session_id):
    session_obj = PracticeSession.query.get_or_404(session_id)
    if session_obj.user_id != current_user.id:
        return jsonify({'error': 'Akses ditolak'}), 403
    return render_template('interview/result.html', session=session_obj)