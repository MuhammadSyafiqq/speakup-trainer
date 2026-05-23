# extensions.py
# ─────────────────────────────────────────────────────────────
# Inisialisasi semua extension Flask di sini agar tidak ada
# circular import. Import di app factory dan blueprint.
# ─────────────────────────────────────────────────────────────

from flask_sqlalchemy import SQLAlchemy
from flask_login      import LoginManager
from flask_mail       import Mail
from flask_migrate    import Migrate

db       = SQLAlchemy()
login    = LoginManager()
mail     = Mail()
migrate  = Migrate()

# ── Konfigurasi LoginManager ───────────────────────────────────
login.login_view        = 'auth.login'           # redirect ke sini jika belum login
login.login_message     = 'Silakan login dulu untuk mengakses halaman ini.'
login.login_message_category = 'warning'

@login.user_loader
def load_user(user_id: str):
    from models.user import User
    return User.query.get(int(user_id))