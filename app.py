# app.py
from flask import Flask, session, request, jsonify, render_template
from dotenv import load_dotenv
import os, uuid

load_dotenv()

app = Flask(__name__)

# ── Konfigurasi ────────────────────────────────────────────────
app.config['SECRET_KEY']                  = os.getenv('SECRET_KEY', 'dev-secret-key-ganti-ini')
app.config['SQLALCHEMY_DATABASE_URI']     = os.getenv('DATABASE_URL', 'sqlite:///speaking_trainer.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER']               = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH']          = 50 * 1024 * 1024  # 50MB

# ── Konfigurasi Flask-Mail ─────────────────────────────────────
app.config['MAIL_SERVER']         = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT']           = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS']        = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USE_SSL']        = os.getenv('MAIL_USE_SSL', 'False') == 'True'
app.config['MAIL_USERNAME']       = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD']       = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'SpeakUp <noreply@speakup.app>')
app.config['MAIL_SUPPRESS_SEND']  = os.getenv('MAIL_SUPPRESS_SEND', 'False') == 'True'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ── Inisialisasi Extensions ────────────────────────────────────
# Semua object (db, login, mail, migrate) didefinisikan di extensions.py
from extensions import db, login, mail, migrate

db.init_app(app)
login.init_app(app)
mail.init_app(app)
migrate.init_app(app, db)

# ── Daftarkan Blueprint ────────────────────────────────────────
from routes.auth      import auth_bp
from routes.practice  import practice_bp
from routes.history   import history_bp
from routes.agent     import agent_bp
from routes.interview import interview_bp

app.register_blueprint(auth_bp)
app.register_blueprint(practice_bp)
app.register_blueprint(history_bp)
app.register_blueprint(agent_bp)
app.register_blueprint(interview_bp)



# ── Import Models (wajib agar Flask-Migrate mendeteksi tabel) ──
from models.user               import User            # noqa: F401
from models.session            import PracticeSession # noqa: F401
from models.interview_session  import InterviewSession# noqa: F401
from models.email_verification import EmailVerificationToken # noqa: F401

# ── Services ───────────────────────────────────────────────────
from services.interview_service import InterviewService

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
interview_service  = InterviewService(OPENROUTER_API_KEY)


# Tambahkan kode ini di app.py setelah register_blueprint, sebelum db.create_all()

@app.after_request
def add_no_cache_headers(response):
    """
    Paksa browser tidak cache halaman yang memerlukan login.
    Ini mencegah user menekan tombol Back dan masih melihat halaman
    setelah logout.
    """
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma']        = 'no-cache'
    response.headers['Expires']       = '0'
    return response

# ── Route: Setup wawancara ─────────────────────────────────────
@app.route('/setup')
def setup():
    positions = [
        {'id': 'fresh_graduate', 'label': 'Fresh Graduate Umum', 'icon': '🎓'},
        {'id': 'frontend',       'label': 'Frontend Developer',  'icon': '💻'},
        {'id': 'backend',        'label': 'Backend Developer',   'icon': '🖥️'},
        {'id': 'custom',         'label': 'Custom',              'icon': '✏️'},
    ]
    return render_template('setup.html', positions=positions)

@app.route('/interview/session')
def interview_session():
    position_label = request.args.get('position_label')
    company        = request.args.get('company', '')
    total_q        = int(request.args.get('total_q', 5))
    language       = request.args.get('language', 'id')

    session_id = session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id

    session_obj = interview_service.get_or_create_session(
        session_id=session_id,
        position_label=position_label,
        company=company,
        total_q=total_q,
        language=language,
        user_id=None
    )
    return jsonify(session_obj.to_dict())

# ── Buat semua tabel jika belum ada ───────────────────────────
with app.app_context():
    db.create_all()
    print("✅ Database berhasil dibuat/diperbarui!")

if __name__ == '__main__':
    app.run(debug=True, port=10000)