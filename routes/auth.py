# routes/auth.py
# ─────────────────────────────────────────────────────────────
# Blueprint autentikasi SpeakUp:
#   • Google OAuth 2.0
#   • Register dengan verifikasi email
#   • Login biasa (username + password)
#   • Verifikasi email via token
#   • Kirim ulang email verifikasi
#   • Logout
# ─────────────────────────────────────────────────────────────

from flask          import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login    import login_user, logout_user, login_required, current_user
from urllib.parse   import urlencode          # ← lebih aman dari join manual
from models.user    import User
from models.email_verification import EmailVerificationToken
from extensions     import db
from utils.email    import send_verification_email, send_welcome_email
import hashlib, os, requests as http_req

auth_bp = Blueprint('auth', __name__)

# ── Konstanta Google OAuth ─────────────────────────────────────
# Simpan di .env — jangan hardcode di sini untuk keamanan
GOOGLE_CLIENT_ID     = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
GOOGLE_AUTH_URL      = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL     = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL  = 'https://www.googleapis.com/oauth2/v2/userinfo'


def get_redirect_uri() -> str:
    from flask import request as req
    # Gunakan HTTP untuk semua localhost, HTTPS untuk production
    is_local = req.host.startswith('localhost') or req.host.startswith('127.0.0.1')
    scheme = 'http' if is_local else 'https'
    return f"{scheme}://{req.host}/google/callback"


# ══════════════════════════════════════════════════════════════
# GOOGLE OAUTH — Step 1: Redirect ke Google
# ══════════════════════════════════════════════════════════════
@auth_bp.route('/google/login')
def google_login():
    """Redirect user ke halaman consent Google."""
    redirect_uri = get_redirect_uri()
    print(f"DEBUG redirect_uri: {redirect_uri}")

    # Simpan state anti-CSRF di session
    state = hashlib.sha256(os.urandom(32)).hexdigest()
    session['oauth_state'] = state

    params = {
        'client_id'    : GOOGLE_CLIENT_ID,
        'redirect_uri' : redirect_uri,
        'response_type': 'code',
        'scope'        : 'openid email profile',
        'state'        : state,
        'access_type'  : 'online',
        'prompt'       : 'select_account',
    }

    return redirect(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


# ══════════════════════════════════════════════════════════════
# GOOGLE OAUTH — Step 2: Callback dari Google
# ══════════════════════════════════════════════════════════════
@auth_bp.route('/google/callback')
def google_callback():
    """
    Terima authorization code dari Google, tukar dengan access token,
    ambil info user, lalu login atau buat akun baru.
    User Google otomatis terverifikasi (Google sudah validasi email).
    """

    # ── Cek error dari Google ──────────────────────────────────
    error = request.args.get('error')
    if error:
        flash(f'Login Google dibatalkan: {error}', 'warning')
        return redirect(url_for('auth.login'))

    # ── Verifikasi state anti-CSRF ─────────────────────────────
    state_returned = request.args.get('state', '')
    state_saved    = session.pop('oauth_state', '')
    if not state_returned or state_returned != state_saved:
        flash('Permintaan login tidak valid (state mismatch). Coba lagi.', 'danger')
        return redirect(url_for('auth.login'))

    # ── Ambil authorization code ───────────────────────────────
    code = request.args.get('code')
    if not code:
        flash('Tidak menerima kode dari Google. Coba lagi.', 'danger')
        return redirect(url_for('auth.login'))

    redirect_uri = get_redirect_uri()

    # ── Tukar code → access token ──────────────────────────────
    try:
        token_resp = http_req.post(GOOGLE_TOKEN_URL, data={
            'code'         : code,
            'client_id'    : GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri' : redirect_uri,
            'grant_type'   : 'authorization_code',
        }, timeout=10)
        token_resp.raise_for_status()
        access_token = token_resp.json().get('access_token')
    except Exception as e:
        print(f'❌ Token exchange error: {e}')
        flash('Gagal mendapatkan token dari Google. Coba lagi.', 'danger')
        return redirect(url_for('auth.login'))

    if not access_token:
        flash('Token Google tidak valid. Coba lagi.', 'danger')
        return redirect(url_for('auth.login'))

    # ── Ambil info profil user ─────────────────────────────────
    try:
        userinfo_resp = http_req.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        userinfo_resp.raise_for_status()
        info = userinfo_resp.json()
    except Exception as e:
        print(f'❌ Userinfo error: {e}')
        flash('Gagal mengambil info akun Google. Coba lagi.', 'danger')
        return redirect(url_for('auth.login'))

    email = info.get('email')
    name  = info.get('name', '')

    if not email:
        flash('Email tidak ditemukan di akun Google kamu.', 'danger')
        return redirect(url_for('auth.login'))

    # ── Cari atau buat user ────────────────────────────────────
    user = User.query.filter_by(email=email).first()
    if not user:
        base_username = email.split('@')[0]
        username      = base_username
        counter       = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(username=username, email=email)
        # Password random — user Google tidak perlu password manual
        user.password_hash = hashlib.sha256(os.urandom(32)).hexdigest()
        # ↓ Google sudah verifikasi email — langsung verified
        user.is_verified   = True
        db.session.add(user)
        db.session.commit()
        flash(f'Akun baru dibuat! Selamat datang, {username}! 🎤', 'success')
    else:
        # Jika user ada tapi belum verified (daftar manual sebelumnya),
        # mark verified sekarang karena Google sudah konfirmasi email
        if not user.is_verified:
            user.is_verified = True
            db.session.commit()
        flash(f'Selamat datang kembali, {user.username}! 🎤', 'success')

    # ── Login ──────────────────────────────────────────────────
    login_user(user, remember=True)

    next_page = session.pop('next_after_login', None)
    return redirect(next_page or url_for('practice.dashboard'))


# ══════════════════════════════════════════════════════════════
# HALAMAN UTAMA
# ══════════════════════════════════════════════════════════════
@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('practice.dashboard'))
    return render_template('index.html')


# ══════════════════════════════════════════════════════════════
# REGISTER
# ══════════════════════════════════════════════════════════════
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('practice.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email',    '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        # ── Validasi input ─────────────────────────────────────
        errors = []
        if not username or not email or not password:
            errors.append('Semua field harus diisi!')
        if len(username) < 3:
            errors.append('Username minimal 3 karakter!')
        if password != confirm:
            errors.append('Password tidak cocok!')
        if len(password) < 6:
            errors.append('Password minimal 6 karakter!')
        if User.query.filter_by(username=username).first():
            errors.append('Username sudah digunakan!')
        if User.query.filter_by(email=email).first():
            errors.append('Email sudah terdaftar!')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('auth/register.html',
                                   username=username, email=email)

        # ── Buat user baru ─────────────────────────────────────
        user = User(username=username, email=email, is_verified=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # ── Kirim email verifikasi ─────────────────────────────
        token = EmailVerificationToken.generate(user.id)
        ok    = send_verification_email(user, token)

        if ok:
            flash(
                f'Registrasi berhasil! Kami sudah kirim email verifikasi ke '
                f'<strong>{email}</strong>. Cek inbox (dan folder Spam). 📧',
                'success'
            )
        else:
            # Email gagal kirim — beri tahu user tapi akun tetap dibuat
            flash(
                'Akun berhasil dibuat, tapi email verifikasi gagal dikirim. '
                'Gunakan menu "Kirim Ulang Verifikasi" di halaman login.',
                'warning'
            )

        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


# ══════════════════════════════════════════════════════════════
# VERIFIKASI EMAIL via link
# ══════════════════════════════════════════════════════════════
@auth_bp.route('/verify-email/<token>')
def verify_email(token: str):
    """
    User mengklik link dari email.
    Validasi token → tandai user sebagai verified → redirect ke login.
    """
    record = EmailVerificationToken.query.filter_by(token=token).first()

    if not record:
        flash('Link verifikasi tidak ditemukan. Mungkin sudah kadaluarsa.', 'danger')
        return redirect(url_for('auth.resend_verification'))

    if record.used:
        flash('Link verifikasi ini sudah pernah digunakan. Silakan login.', 'info')
        return redirect(url_for('auth.login'))

    if record.is_expired:
        flash(
            'Link verifikasi sudah kadaluarsa (berlaku 24 jam). '
            'Minta link baru di bawah ini.',
            'warning'
        )
        return redirect(url_for('auth.resend_verification'))

    # ── Verifikasi berhasil ────────────────────────────────────
    record.user.is_verified = True
    record.used             = True
    db.session.commit()

    # Kirim email selamat datang (best-effort, tidak blok flow)
    send_welcome_email(record.user)

    flash('🎉 Email berhasil diverifikasi! Silakan login sekarang.', 'success')
    return redirect(url_for('auth.login'))


# ══════════════════════════════════════════════════════════════
# KIRIM ULANG VERIFIKASI
# ══════════════════════════════════════════════════════════════
@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """
    Form untuk meminta kiriman ulang email verifikasi.
    Selalu tampilkan pesan generik untuk mencegah user enumeration.
    """
    if current_user.is_authenticated:
        if current_user.is_verified:
            return redirect(url_for('practice.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        # Proses hanya jika user ada dan belum verified
        user = User.query.filter_by(email=email).first()
        if user and not user.is_verified:
            token = EmailVerificationToken.generate(user.id)
            send_verification_email(user, token)

        # Pesan sama regardless — hindari user enumeration
        flash(
            'Jika email terdaftar dan belum diverifikasi, '
            'kami sudah kirim ulang link verifikasinya. Cek inbox kamu. 📧',
            'info'
        )
        return redirect(url_for('auth.login'))

    return render_template('auth/resend_verification.html')


# ══════════════════════════════════════════════════════════════
# LOGIN BIASA
# ══════════════════════════════════════════════════════════════
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('practice.dashboard'))

    # Simpan halaman tujuan jika ada
    next_page = request.args.get('next')
    if next_page:
        session['next_after_login'] = next_page

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash('Username atau password salah!', 'danger')
            return render_template('auth/login.html', username=username)

        # ── Cek apakah email sudah diverifikasi ───────────────
        if not user.is_verified:
            flash(
                'Email kamu belum diverifikasi. Cek inbox atau '
                'kirim ulang link verifikasi.',
                'warning'
            )
            return render_template('auth/login.html', username=username)

        # ── Login berhasil ────────────────────────────────────
        login_user(user, remember=bool(remember))
        dest = session.pop('next_after_login', None)
        flash(f'Selamat datang kembali, {user.username}! 🎤', 'success')
        return redirect(dest or url_for('practice.dashboard'))

    return render_template('auth/login.html')


# ══════════════════════════════════════════════════════════════
# LOGOUT
# ══════════════════════════════════════════════════════════════
@auth_bp.route('/logout', methods=['GET', 'POST'])  # ← tambah POST
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Berhasil logout. Sampai jumpa! 👋', 'info')
    response = redirect(url_for('auth.login'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma']        = 'no-cache'
    response.headers['Expires']       = '0'
    response.delete_cookie('session')
    response.delete_cookie('remember_token')
    return response