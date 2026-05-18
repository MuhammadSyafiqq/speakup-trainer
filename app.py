from flask import Flask
from dotenv import load_dotenv
import os

from extensions import db, login_manager

load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv(
    'SECRET_KEY',
    'dev-secret-key-ganti-ini'
)

app.config['SQLALCHEMY_DATABASE_URI'] = (
    'sqlite:///speaking_trainer.db'
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = os.path.join(
    'static',
    'uploads'
)

app.config['MAX_CONTENT_LENGTH'] = (
    50 * 1024 * 1024
)

# Buat folder uploads kalau belum ada
os.makedirs(
    app.config['UPLOAD_FOLDER'],
    exist_ok=True
)

# ============================================
# INIT EXTENSIONS
# ============================================

db.init_app(app)

login_manager.init_app(app)

login_manager.login_view = 'auth.login'

login_manager.login_message = (
    'Silakan login terlebih dahulu.'
)

login_manager.login_message_category = 'warning'

# ============================================
# IMPORT ROUTES
# ============================================

from routes.auth import auth_bp
from routes.practice import practice_bp
from routes.history import history_bp
from routes.agent import agent_bp

app.register_blueprint(auth_bp)
app.register_blueprint(practice_bp)
app.register_blueprint(history_bp)
app.register_blueprint(agent_bp)

# ============================================
# IMPORT MODELS
# ============================================

from models.user import User
from models.session import PracticeSession

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============================================
# CREATE DATABASE
# ============================================

with app.app_context():
    db.create_all()
    print('✅ Database berhasil dibuat!')

if __name__ == '__main__':
    app.run(debug=True, port=5000)