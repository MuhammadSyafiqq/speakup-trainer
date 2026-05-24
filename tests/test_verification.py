# tests/test_verification.py
from datetime import datetime, timedelta
from models.email_verification import EmailVerificationToken
from models.user import User
from extensions import db


def test_UT_AUTH_16_valid_token(client, db, unverified_user):
    """Token valid mengaktifkan akun."""
    token = EmailVerificationToken.generate(unverified_user.id)
    r = client.get(f'/verify-email/{token.token}', follow_redirects=True)
    assert unverified_user.is_verified == True
    assert token.used == True


def test_UT_AUTH_17_expired_token(client, db, unverified_user):
    """Token kadaluarsa ditolak."""
    token = EmailVerificationToken.generate(unverified_user.id)
    token.expires_at = datetime.utcnow() - timedelta(hours=1)
    db.session.commit()

    r = client.get(f'/verify-email/{token.token}', follow_redirects=True)
    assert 'kadaluarsa' in r.data.decode().lower()
    assert unverified_user.is_verified == False


def test_UT_AUTH_18_used_token(client, db, unverified_user):
    """Token sudah dipakai ditolak."""
    token = EmailVerificationToken.generate(unverified_user.id)
    token.used = True
    db.session.commit()

    r = client.get(f'/verify-email/{token.token}', follow_redirects=True)
    assert 'sudah pernah digunakan' in r.data.decode().lower()


def test_UT_AUTH_19_invalid_token(client, db):
    """Token tidak ada di DB ditolak."""
    r = client.get('/verify-email/tokenpalsuyangtidakada', follow_redirects=True)
    assert 'tidak ditemukan' in r.data.decode().lower()


def test_UT_AUTH_20_resend_unverified(client, db, unverified_user):
    """Kirim ulang token untuk user belum terverifikasi."""
    r = client.post('/resend-verification',
                    data={'email': 'unverified@example.com'},
                    follow_redirects=True)
    tokens = EmailVerificationToken.query.filter_by(
        user_id=unverified_user.id, used=False
    ).count()
    assert tokens >= 1


def test_UT_AUTH_21_resend_verified(client, db, verified_user):
    """Kirim ulang untuk user sudah verified — tidak buat token baru."""
    before = EmailVerificationToken.query.filter_by(
        user_id=verified_user.id, used=False
    ).count()
    client.post('/resend-verification',
                data={'email': 'test@example.com'},
                follow_redirects=True)
    after = EmailVerificationToken.query.filter_by(
        user_id=verified_user.id, used=False
    ).count()
    assert after == before  # tidak bertambah


def test_UT_AUTH_22_resend_nonexistent(client, db):
    """Email tidak ada — pesan generik, tidak error."""
    r = client.post('/resend-verification',
                    data={'email': 'tidakada@example.com'},
                    follow_redirects=True)
    assert r.status_code == 200
    # Pesan tetap muncul (anti user enumeration)
    assert 'kami sudah kirim' in r.data.decode().lower()