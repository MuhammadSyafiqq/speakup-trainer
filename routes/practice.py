from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from models.session import PracticeSession
from extensions import db
from services.whisper_service import transcribe_audio
from services.analysis_service import analyze_speech
import os
import uuid
from datetime import datetime

practice_bp = Blueprint('practice', __name__)

# Kategori latihan yang tersedia
CATEGORIES = [
    {
        'id': 'pidato',
        'name': 'Pidato Formal',
        'icon': '🎤',
        'description': 'Latihan pidato resmi untuk acara formal, upacara, atau presentasi publik',
        'tips': ['Gunakan bahasa formal', 'Perhatikan struktur pembuka-isi-penutup', 'Latih intonasi dan volume'],
        'color': '#4F46E5'
    },
    {
        'id': 'wawancara',
        'name': 'Wawancara Kerja',
        'icon': '💼',
        'description': 'Latihan menjawab pertanyaan wawancara kerja dengan percaya diri',
        'tips': ['Jawab dengan jelas dan terstruktur', 'Gunakan contoh nyata (metode STAR)', 'Hindari kata-kata pengisi berlebihan'],
        'color': '#059669'
    },
    {
        'id': 'presentasi',
        'name': 'Presentasi Bisnis',
        'icon': '📊',
        'description': 'Latihan menyampaikan presentasi bisnis atau akademik yang meyakinkan',
        'tips': ['Sampaikan poin utama dengan jelas', 'Gunakan data dan fakta pendukung', 'Ajak audiens berinteraksi'],
        'color': '#DC2626'
    },
    {
        'id': 'debat',
        'name': 'Debat & Argumentasi',
        'icon': '⚖️',
        'description': 'Latihan menyampaikan argumen yang logis dan persuasif dalam debat',
        'tips': ['Sampaikan posisi dengan tegas', 'Dukung dengan alasan kuat', 'Hormati lawan bicara'],
        'color': '#D97706'
    },
    {
        'id': 'mc',
        'name': 'Master of Ceremony (MC)',
        'icon': '🎭',
        'description': 'Latihan menjadi MC yang memandu acara dengan energi dan profesionalisme',
        'tips': ['Gunakan bahasa yang antusias', 'Atur tempo dan jeda dengan baik', 'Jaga energi sepanjang acara'],
        'color': '#7C3AED'
    },
    {
        'id': 'storytelling',
        'name': 'Storytelling',
        'icon': '📖',
        'description': 'Latihan bercerita dengan narasi yang menarik dan memukau pendengar',
        'tips': ['Bangun plot yang menarik', 'Gunakan deskripsi yang vivid', 'Sampaikan pesan moral dengan jelas'],
        'color': '#0891B2'
    },
]

@practice_bp.route('/dashboard')
@login_required
def dashboard():
    recent_sessions = PracticeSession.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).order_by(PracticeSession.created_at.desc()).limit(5).all()

    total_sessions = PracticeSession.query.filter_by(user_id=current_user.id).count()
    avg_score = current_user.get_average_score()

    return render_template('dashboard.html',
        categories=CATEGORIES,
        recent_sessions=recent_sessions,
        total_sessions=total_sessions,
        avg_score=avg_score
    )

@practice_bp.route('/practice/select-category')
@login_required
def select_category():
    return render_template('practice/select_category.html', categories=CATEGORIES)

@practice_bp.route('/practice/setup', methods=['GET', 'POST'])
@login_required
def setup_practice():
    category_id = request.args.get('category') or request.form.get('category')

    if not category_id:
        return redirect(url_for('practice.select_category'))

    category = next((c for c in CATEGORIES if c['id'] == category_id), None)
    if not category:
        flash('Kategori tidak ditemukan!', 'danger')
        return redirect(url_for('practice.select_category'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Judul latihan harus diisi!', 'danger')
            return render_template('practice/setup.html', category=category)

        return redirect(url_for('practice.record',
            category=category_id,
            title=title
        ))

    return render_template('practice/setup.html', category=category)

@practice_bp.route('/practice/record')
@login_required
def record():
    category_id = request.args.get('category')
    title = request.args.get('title')

    if not category_id or not title:
        return redirect(url_for('practice.select_category'))

    category = next((c for c in CATEGORIES if c['id'] == category_id), None)

    return render_template('practice/record.html',
        category=category,
        title=title
    )

@practice_bp.route('/practice/upload-audio', methods=['POST'])
@login_required
def upload_audio():
    """Endpoint untuk menerima file audio dari browser"""
    try:
        if 'audio' not in request.files:
            return jsonify({'success': False, 'error': 'File audio tidak ditemukan'}), 400

        audio_file = request.files['audio']
        category = request.form.get('category', 'pidato')
        title = request.form.get('title', 'Latihan')
        duration = request.form.get('duration', 0)

        if audio_file.filename == '':
            return jsonify({'success': False, 'error': 'Tidak ada file yang dipilih'}), 400

        # Generate nama file unik
        filename = f"{current_user.id}_{uuid.uuid4().hex}.webm"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(filepath)

        # Buat record session dulu dengan status processing
        session = PracticeSession(
            user_id=current_user.id,
            category=category,
            title=title,
            audio_path=filepath,
            status='processing',
            duration_seconds=int(float(duration)) if duration else 0
        )
        db.session.add(session)
        db.session.commit()

        return jsonify({
            'success': True,
            'session_id': session.id,
            'message': 'Audio berhasil diupload, sedang diproses...'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@practice_bp.route('/practice/process/<int:session_id>', methods=['POST'])
@login_required
def process_session(session_id):
    """Proses transkripsi dan analisis AI"""
    session = PracticeSession.query.get_or_404(session_id)

    if session.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Akses ditolak'}), 403

    try:
        # Step 1: Transkripsi dengan Whisper
        print(f"🎙️ Memulai transkripsi sesi {session_id}...")
        transcript = transcribe_audio(session.audio_path)

        if not transcript or transcript.strip() == '':
            session.status = 'error'
            db.session.commit()
            return jsonify({'success': False, 'error': 'Transkripsi gagal - audio mungkin tidak jelas'}), 500

        session.transcript = transcript
        db.session.commit()
        print(f"✅ Transkripsi selesai: {transcript[:100]}...")

        # Step 2: Analisis dengan AI
        print(f"🤖 Memulai analisis AI...")
        analysis = analyze_speech(
            transcript=transcript,
            title=session.title,
            category=session.category
        )

        # Step 3: Simpan hasil analisis
        session.score_clarity = analysis.get('score_clarity', 0)
        session.score_structure = analysis.get('score_structure', 0)
        session.score_confidence = analysis.get('score_confidence', 0)
        session.score_relevance = analysis.get('score_relevance', 0)
        session.score_vocabulary = analysis.get('score_vocabulary', 0)
        session.score_fluency = analysis.get('score_fluency', 0)
        session.calculate_total_score()

        session.suggestions = analysis.get('suggestions', '')
        session.strengths = analysis.get('strengths', '')
        session.weaknesses = analysis.get('weaknesses', '')
        session.set_feedback(analysis.get('feedback_detail', {}))
        session.status = 'completed'

        db.session.commit()
        print(f"✅ Analisis selesai! Skor total: {session.score_total}")

        return jsonify({
            'success': True,
            'session_id': session.id,
            'score_total': session.score_total,
            'message': 'Analisis selesai!'
        })

    except Exception as e:
        session.status = 'error'
        db.session.commit()
        print(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@practice_bp.route('/practice/result/<int:session_id>')
@login_required
def result(session_id):
    session = PracticeSession.query.get_or_404(session_id)

    if session.user_id != current_user.id:
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('practice.dashboard'))

    return render_template('practice/result.html', session=session)

@practice_bp.route('/practice/status/<int:session_id>')
@login_required
def check_status(session_id):
    """API untuk cek status processing"""
    session = PracticeSession.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        return jsonify({'error': 'Akses ditolak'}), 403

    return jsonify({
        'status': session.status,
        'session_id': session.id
    })
