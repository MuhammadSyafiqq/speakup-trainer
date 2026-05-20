from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from extensions import db
from flask_dance.contrib.google import make_google_blueprint, google


auth_bp = Blueprint('auth', __name__)

# --- Konfigurasi Google OAuth 2.0 ---
google_bp = make_google_blueprint(
    client_id="822893399626-tb3fmko3v6ue869kqkhd6f4ujfm6jndr.apps.googleusercontent.com",
    client_secret="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",
    scope=["profile", "email"],
    redirect_to="auth.google_authorized"
)
auth_bp.register_blueprint(google_bp, url_prefix="/login")

# --- Login menggunakan Google ---
@auth_bp.route('/google')
def google_login():
    if not google.authorized:
        return redirect(url_for("auth.google.login"))  # endpoint lengkap blueprint

    resp = google.get("/oauth2/v2/userinfo")
    if resp.ok:
        info = resp.json()
        email = info.get("email")

        # Cek user berdasarkan email
        user = User.query.filter_by(email=email).first()
        if not user:
            # Buat user baru otomatis
            user = User(username=email.split("@")[0], email=email)
            db.session.add(user)
            db.session.commit()

        login_user(user)
        flash(f'Selamat datang, {user.username}!', 'success')
        return redirect(url_for('practice.dashboard'))

    flash("Login Google gagal!", "danger")
    return redirect(url_for('auth.login'))

@auth_bp.route("/google/authorized")
def google_authorized():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if resp.ok:
        info = resp.json()
        email = info.get("email")

        # cek user
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(username=email.split("@")[0], email=email)
            db.session.add(user)
            db.session.commit()

        login_user(user)
        flash(f'Selamat datang, {user.username}!', 'success')
        return redirect(url_for('practice.dashboard'))

    flash("Login Google gagal!", "danger")
    return redirect(url_for('auth.login'))

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('practice.dashboard'))
    return render_template('index.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('practice.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validasi
        if not username or not email or not password:
            flash('Semua field harus diisi!', 'danger')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Password tidak cocok!', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password minimal 6 karakter!', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Username sudah digunakan!', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Email sudah terdaftar!', 'danger')
            return render_template('auth/register.html')

        # Buat user baru
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registrasi berhasil! Silakan login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('practice.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=bool(remember))
            next_page = request.args.get('next')
            flash(f'Selamat datang, {user.username}! 🎤', 'success')
            return redirect(next_page or url_for('practice.dashboard'))
        else:
            flash('Username atau password salah!', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Berhasil logout. Sampai jumpa!', 'info')
    return redirect(url_for('auth.index'))
