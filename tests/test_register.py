# tests/test_register.py
from models.user import User
from models.email_verification import EmailVerificationToken


def post_register(client, **kwargs):
    data = {
        'username': 'newuser',
        'email': 'new@example.com',
        'password': 'password123',
        'confirm_password': 'password123',
        **kwargs
    }
    return client.post('/register', data=data, follow_redirects=True)


def test_UT_AUTH_01_username_empty(client, db):
    """Username kosong ditolak."""
    r = post_register(client, username='')
    assert 'Semua field harus diisi' in r.data.decode()


def test_UT_AUTH_02_username_short(client, db):
    """Username < 3 karakter ditolak."""
    r = post_register(client, username='ab')
    assert 'minimal 3 karakter' in r.data.decode()


def test_UT_AUTH_03_email_empty(client, db):
    """Email kosong ditolak."""
    r = post_register(client, email='')
    assert 'Semua field harus diisi' in r.data.decode()


def test_UT_AUTH_04_password_short(client, db):
    """Password < 6 karakter ditolak."""
    r = post_register(client, password='abc', confirm_password='abc')
    assert 'minimal 6 karakter' in r.data.decode()


def test_UT_AUTH_05_password_mismatch(client, db):
    """Konfirmasi password tidak cocok ditolak."""
    r = post_register(client, password='abc123', confirm_password='abc124')
    assert 'tidak cocok' in r.data.decode()


def test_UT_AUTH_06_username_duplicate(client, db, verified_user):
    """Username duplikat ditolak."""
    r = post_register(client, username='testuser', email='other@example.com')
    assert 'sudah digunakan' in r.data.decode()


def test_UT_AUTH_07_email_duplicate(client, db, verified_user):
    """Email duplikat ditolak."""
    r = post_register(client, username='otherone', email='test@example.com')
    assert 'sudah terdaftar' in r.data.decode()


def test_UT_AUTH_08_register_success(client, db):
    """User baru berhasil dibuat."""
    post_register(client)
    user = User.query.filter_by(email='new@example.com').first()
    assert user is not None
    assert user.is_verified == False


def test_UT_AUTH_09_verification_token_created(client, db):
    """Token verifikasi dibuat setelah register."""
    post_register(client)
    user = User.query.filter_by(email='new@example.com').first()
    token = EmailVerificationToken.query.filter_by(user_id=user.id).first()
    assert token is not None
    assert token.used == False


def test_UT_AUTH_10_email_fail_graceful(client, db, monkeypatch):
    """Akun tetap dibuat meski email gagal kirim."""
    def mock_send(*a, **kw):
        raise Exception('SMTP error')
    monkeypatch.setattr('utils.email.mail.send', mock_send)

    r = post_register(client)
    user = User.query.filter_by(email='new@example.com').first()
    assert user is not None  # akun tetap ada