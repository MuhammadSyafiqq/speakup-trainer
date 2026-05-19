from flask import Flask, session, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv
import os, uuid


load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-ganti-ini')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///speaking_trainer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

from extensions import db, login_manager
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Silakan login terlebih dahulu.'
login_manager.login_message_category = 'warning'

# Import blueprint routes
from routes.auth import auth_bp
from routes.practice import practice_bp
from routes.history import history_bp
from routes.agent import agent_bp
from routes.interview import interview_bp

app.register_blueprint(interview_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(practice_bp)
app.register_blueprint(history_bp)
app.register_blueprint(agent_bp)

# Import models dan service
from models.user import User
from models.session import PracticeSession
from models.interview_session import InterviewSession
from services.interview_service import InterviewService

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()
    print("✅ Database berhasil dibuat!")

# --- Gemini API Service ---
GEMINI_API_URL = 'https://api.generativelanguage.googleapis.com/v1beta2/models/gemini-2.5-flash:generateContent'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'YOUR_API_KEY')

# Buat instance InterviewService
interview_service = InterviewService(GEMINI_API_KEY, GEMINI_API_URL)

# --- Routes setup wawancara ---
@app.route('/setup')
def setup():
    positions = [
        {'id': 'fresh_graduate', 'label': 'Fresh Graduate Umum', 'icon': '🎓'},
        {'id': 'frontend', 'label': 'Frontend Developer', 'icon': '💻'},
        {'id': 'backend', 'label': 'Backend Developer', 'icon': '🖥️'},
        {'id': 'custom', 'label': 'Custom', 'icon': '✏️'}
    ]
    return render_template('setup.html', positions=positions)

@app.route('/interview/session')
def interview_session():
    # Ambil parameter dari frontend
    position_label = request.args.get('position_label')
    company = request.args.get('company', '')
    total_q = int(request.args.get('total_q', 5))
    language = request.args.get('language', 'id')

    # session_id unik per user/session
    session_id = session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id

    user_id = None  # bisa diisi jika user login

    # Ambil atau buat session interview via InterviewService
    session_obj = interview_service.get_or_create_session(
        session_id=session_id,
        position_label=position_label,
        company=company,
        total_q=total_q,
        language=language,
        user_id=user_id
    )

    # Kembalikan JSON ke frontend
    return jsonify(session_obj.to_dict())




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)