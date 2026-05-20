from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models.session import PracticeSession
from extensions import db
import google.generativeai as genai
import os, json, re, uuid
from datetime import datetime
from services.gemini_service import convert_to_mp3

interview_bp = Blueprint('interview', __name__)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ============================================
# POSISI WAWANCARA YANG TERSEDIA
# ============================================
INTERVIEW_POSITIONS = [
    {'id': 'fresh_graduate',  'label': 'Fresh Graduate Umum',      'icon': '🎓'},
    {'id': 'software_dev',    'label': 'Software Developer',        'icon': '💻'},
    {'id': 'marketing',       'label': 'Marketing / Sales',         'icon': '📢'},
    {'id': 'finance',         'label': 'Keuangan / Akuntansi',      'icon': '💰'},
    {'id': 'hr',              'label': 'Human Resources (HR)',       'icon': '👥'},
    {'id': 'manager',         'label': 'Manajer / Team Lead',       'icon': '🏆'},
    {'id': 'internship',      'label': 'Magang / Internship',       'icon': '📚'},
    {'id': 'custom',          'label': 'Posisi Lainnya (Custom)',    'icon': '✏️'},
]

# ============================================
# SYSTEM PROMPT INTERVIEWER AI
# ============================================
def build_interviewer_prompt(position: str, company: str, session_data: dict) -> str:
    question_num   = session_data.get('question_num', 1)
    total_q        = session_data.get('total_questions', 7)
    answers_so_far = session_data.get('answers', [])
    context        = '\n'.join([
        f"Q{i+1}: {a['question']}\nA{i+1}: {a['answer']}"
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
6. HANYA tulis pertanyaan saja — tanpa awalan seperti "Pertanyaan:" atau nomor
7. Buat pertanyaan terasa hangat dan profesional, bukan seperti robot

Tulis pertanyaan sekarang (1-2 kalimat saja):"""


def build_analysis_prompt(position: str, company: str, answers: list) -> str:
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

    "hiring_recommendation": "<Sangat Direkomendasikan / Direkomendasikan / Dipertimbangkan / Belum Direkomendasikan>",
    "hiring_reason": "<alasan singkat rekomendasi hiring>"
}}

Berikan penilaian yang JUJUR, KONSTRUKTIF, dan SPESIFIK berdasarkan setiap jawaban."""


# ============================================
# HALAMAN SETUP WAWANCARA
# ============================================
@interview_bp.route('/interview/setup')
@login_required
def setup():
    return render_template('interview/setup.html',
                           positions=INTERVIEW_POSITIONS)


# ============================================
# HALAMAN SESI WAWANCARA REAL-TIME
# ============================================
@interview_bp.route('/interview/session')
@login_required
def session_page():
    position     = request.args.get('position', 'Fresh Graduate')
    company      = request.args.get('company', '')
    total_q      = int(request.args.get('total_q', 7))
    position_label = request.args.get('position_label', position)

    return render_template('interview/session.html',
                           position=position,
                           position_label=position_label,
                           company=company,
                           total_q=total_q)


# ============================================
# API: DAPATKAN PERTANYAAN BERIKUTNYA
# ============================================
@interview_bp.route('/interview/get-question', methods=['POST'])
@login_required
def get_question():
    try:
        data         = request.get_json()
        position     = data.get('position', 'Fresh Graduate')
        company      = data.get('company', '')
        session_data = data.get('session_data', {})

        prompt   = build_interviewer_prompt(position, company, session_data)
        response = model.generate_content(prompt)
        question = response.text.strip()

        # Bersihkan prefix tidak perlu
        for prefix in ['Pertanyaan:', 'Q:', 'HRD:', 'Interviewer:']:
            if question.startswith(prefix):
                question = question[len(prefix):].strip()

        return jsonify({'success': True, 'question': question})

    except Exception as e:
        print(f'❌ get_question error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# API: TRANSKRIPSI JAWABAN AUDIO
# ============================================
@interview_bp.route('/interview/transcribe-answer', methods=['POST'])
@login_required
def transcribe_answer():
    """Terima audio jawaban → transkripsi dengan Gemini"""
    try:
        if 'audio' not in request.files:
            return jsonify({'success': False, 'error': 'Tidak ada file audio'}), 400

        audio_file = request.files['audio']
        question   = request.form.get('question', '')
        q_num      = request.form.get('q_num', '1')

        # Simpan file sementara
        from flask import current_app
        tmp_filename = f"interview_{current_user.id}_{uuid.uuid4().hex}.webm"
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
        os.makedirs(upload_folder, exist_ok=True)
        tmp_path = os.path.join(upload_folder, tmp_filename)
        audio_file.save(tmp_path)

        # Konversi ke MP3
        mp3_path, was_converted = convert_to_mp3(tmp_path)

        try:
            # Kirim ke Gemini untuk transkripsi + konteks pertanyaan
            import base64
            with open(mp3_path, 'rb') as f:
                audio_b64 = base64.b64encode(f.read()).decode('utf-8')

            prompt = f"""Kamu adalah sistem transkripsi untuk wawancara kerja.

Pertanyaan yang diajukan: "{question}"

Transkripsi jawaban audio berikut ke teks Bahasa Indonesia dengan akurat.
Pertahankan semua kata pengisi (em, eh, anu) dan jeda yang terdengar.
Jika audio tidak jelas atau kosong, tulis "[tidak ada jawaban terdengar]".

HANYA tulis transkripsi saja, tanpa komentar atau penjelasan tambahan."""

            response = model.generate_content([
                {'inline_data': {'mime_type': 'audio/mp3', 'data': audio_b64}},
                prompt
            ])

            transcript = response.text.strip()
            if not transcript:
                transcript = '[Jawaban tidak terdengar dengan jelas]'

        finally:
            # Hapus file temp
            for p in [tmp_path, mp3_path]:
                if p and os.path.exists(p) and p != tmp_path:
                    try: os.remove(p)
                    except: pass
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except: pass

        return jsonify({'success': True, 'transcript': transcript})

    except Exception as e:
        print(f'❌ transcribe_answer error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# API: ANALISIS AKHIR SESI
# ============================================
@interview_bp.route('/interview/analyze', methods=['POST'])
@login_required
def analyze():
    try:
        data     = request.get_json()
        position = data.get('position', 'Fresh Graduate')
        company  = data.get('company', '')
        answers  = data.get('answers', [])

        if not answers:
            return jsonify({'success': False, 'error': 'Tidak ada jawaban'}), 400

        prompt   = build_analysis_prompt(position, company, answers)
        response = model.generate_content(prompt)
        raw      = response.text

        # Bersihkan & parse JSON
        raw = re.sub(r'```json\s*', '', raw, flags=re.IGNORECASE)
        raw = re.sub(r'```\s*', '', raw)
        raw = raw.strip()

        result = None
        for attempt in [raw, raw[raw.find('{'):raw.rfind('}')+1]]:
            try:
                result = json.loads(attempt)
                break
            except Exception:
                pass

        if not result:
            return jsonify({'success': False, 'error': 'Gagal parse hasil analisis'}), 500

        # Simpan ke database sebagai PracticeSession
        session_obj = PracticeSession(
            user_id         = current_user.id,
            category        = 'wawancara',
            title           = f"Wawancara {position}" + (f" di {company}" if company else ''),
            transcript      = '\n\n'.join([
                f"Q: {a['question']}\nA: {a['answer']}" for a in answers
            ]),
            score_total     = float(result.get('overall_score', 0)),
            score_clarity   = float(result.get('score_communication', 0)),
            score_structure = float(result.get('score_structure', 0)),
            score_confidence= float(result.get('score_confidence', 0)),
            score_relevance = float(result.get('score_relevance', 0)),
            score_vocabulary= float(result.get('score_vocabulary', 0)),
            score_fluency   = float(result.get('score_relevance', 0)),
            strengths       = ' | '.join(result.get('strengths', [])),
            weaknesses      = ' | '.join(result.get('improvements', [])),
            suggestions     = '\n'.join(['• ' + t for t in result.get('tips', [])]),
            status          = 'completed',
            duration_seconds= sum(a.get('duration', 0) for a in answers),
        )
        session_obj.set_feedback({
            'per_answer_feedback'  : result.get('per_answer_feedback', []),
            'hiring_recommendation': result.get('hiring_recommendation', ''),
            'hiring_reason'        : result.get('hiring_reason', ''),
            'summary'              : result.get('summary', ''),
            'tips'                 : result.get('tips', []),
            'improvements'         : result.get('improvements', []),
        })

        db.session.add(session_obj)
        db.session.commit()

        return jsonify({
            'success'   : True,
            'session_id': session_obj.id,
            'result'    : result,
        })

    except Exception as e:
        print(f'❌ analyze error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


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