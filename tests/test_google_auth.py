# tests/test_google_oauth.py
# ─────────────────────────────────────────────────────────────
# Unit Test — Google OAuth 2.0 Flow
# UT-AUTH-23 s/d UT-AUTH-27
#
# Semua request ke Google API (token exchange & userinfo)
# di-mock menggunakan unittest.mock sehingga test tidak
# memerlukan koneksi internet atau kredensial nyata.
# ─────────────────────────────────────────────────────────────

import pytest
from unittest.mock import patch, MagicMock
from models.user import User
from models.email_verification import EmailVerificationToken
from extensions import db as _db


# ══════════════════════════════════════════════════════════════
# HELPER — Mock Response Google API
# ══════════════════════════════════════════════════════════════

def make_token_response(access_token='fake-access-token-xyz'):
    """
    Mock respons dari GOOGLE_TOKEN_URL.
    Mengembalikan objek yang meniru requests.Response.
    """
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        'access_token': access_token,
        'token_type': 'Bearer',
        'expires_in': 3599,
        'scope': 'openid email profile',
    }
    mock.raise_for_status.return_value = None
    return mock


def make_userinfo_response(email='googleuser@gmail.com', name='Google User'):
    """
    Mock respons dari GOOGLE_USERINFO_URL.
    Mengembalikan profil user Google.
    """
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        'id'           : '123456789',
        'email'        : email,
        'name'         : name,
        'given_name'   : name.split()[0],
        'picture'      : 'https://example.com/photo.jpg',
        'verified_email': True,
    }
    mock.raise_for_status.return_value = None
    return mock


def make_error_response(status_code=400):
    """Mock respons error dari Google."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status.side_effect = Exception(f'HTTP {status_code}')
    return mock


# ══════════════════════════════════════════════════════════════
# HELPER — Simulasi State CSRF di Session
# ══════════════════════════════════════════════════════════════

def get_valid_state(client):
    """
    Kunjungi /google/login untuk mendapatkan state CSRF
    yang tersimpan di session, lalu kembalikan nilainya.
    """
    with client.session_transaction() as sess:
        sess['oauth_state'] = 'valid-state-123'
    return 'valid-state-123'


def callback_url(state, code='auth-code-abc'):
    """Buat URL callback Google dengan parameter yang benar."""
    return f'/google/callback?state={state}&code={code}'


# ══════════════════════════════════════════════════════════════
# UT-AUTH-23 — State CSRF Mismatch
# ══════════════════════════════════════════════════════════════

class TestCSRFState:

    def test_UT_AUTH_23_state_mismatch(self, client, db):
        """
        State yang dikembalikan Google berbeda dari yang tersimpan
        di session → harus ditolak dengan flash danger.
        """
        # Set state di session
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'state-yang-benar'

        # Callback dengan state yang berbeda (serangan CSRF)
        r = client.get(
            '/google/callback?state=state-palsu&code=somecode',
            follow_redirects=True
        )

        assert r.status_code == 200
        body = r.data.decode('utf-8')
        # Harus ada pesan error state mismatch
        assert any(keyword in body.lower() for keyword in [
            'state mismatch', 'tidak valid', 'coba lagi'
        ])
        # User tidak boleh ter-login (tidak redirect ke dashboard)
        assert '/dashboard' not in r.request.path

    def test_UT_AUTH_23b_empty_state(self, client, db):
        """State kosong juga harus ditolak."""
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'state-yang-benar'

        r = client.get(
            '/google/callback?code=somecode',
            follow_redirects=True
        )
        body = r.data.decode('utf-8')
        assert any(keyword in body.lower() for keyword in [
            'state mismatch', 'tidak valid', 'coba lagi'
        ])

    def test_UT_AUTH_23c_no_session_state(self, client, db):
        """Tidak ada state di session sama sekali."""
        # Jangan set session state — simulasi session expired
        r = client.get(
            '/google/callback?state=somestate&code=somecode',
            follow_redirects=True
        )
        body = r.data.decode('utf-8')
        assert any(keyword in body.lower() for keyword in [
            'state mismatch', 'tidak valid', 'coba lagi'
        ])


# ══════════════════════════════════════════════════════════════
# UT-AUTH-24 — Error dari Google
# ══════════════════════════════════════════════════════════════

class TestGoogleError:

    def test_UT_AUTH_24_access_denied(self, client, db):
        """
        User menolak consent di Google (error=access_denied)
        → flash warning, redirect ke login.
        """
        r = client.get(
            '/google/callback?error=access_denied',
            follow_redirects=True
        )
        assert r.status_code == 200
        body = r.data.decode('utf-8')
        assert any(keyword in body.lower() for keyword in [
            'dibatalkan', 'access_denied', 'coba lagi', 'login'
        ])

    def test_UT_AUTH_24b_other_error(self, client, db):
        """Error lain dari Google juga ditangani."""
        r = client.get(
            '/google/callback?error=temporarily_unavailable',
            follow_redirects=True
        )
        assert r.status_code == 200
        body = r.data.decode('utf-8')
        assert any(keyword in body.lower() for keyword in [
            'dibatalkan', 'temporarily_unavailable', 'coba lagi'
        ])

    def test_UT_AUTH_24c_no_code(self, client, db):
        """Callback tanpa authorization code ditolak."""
        state = get_valid_state(client)
        r = client.get(
            f'/google/callback?state={state}',  # tidak ada code
            follow_redirects=True
        )
        body = r.data.decode('utf-8')
        assert any(keyword in body.lower() for keyword in [
            'kode', 'code', 'coba lagi'
        ])

    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_24d_token_exchange_fails(self, mock_post, client, db):
        """Token exchange gagal (SMTP/network error)."""
        mock_post.return_value = make_error_response(400)

        state = get_valid_state(client)
        r = client.get(callback_url(state), follow_redirects=True)

        body = r.data.decode('utf-8')
        assert any(keyword in body.lower() for keyword in [
            'gagal', 'token', 'coba lagi'
        ])

    @patch('routes.auth.http_req.get')
    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_24e_userinfo_fails(self, mock_post, mock_get, client, db):
        """Token exchange berhasil tapi userinfo gagal."""
        mock_post.return_value = make_token_response()
        mock_get.return_value  = make_error_response(401)

        state = get_valid_state(client)
        r = client.get(callback_url(state), follow_redirects=True)

        body = r.data.decode('utf-8')
        assert any(keyword in body.lower() for keyword in [
            'gagal', 'info', 'coba lagi'
        ])


# ══════════════════════════════════════════════════════════════
# UT-AUTH-25 — User Baru dari Google
# ══════════════════════════════════════════════════════════════

class TestGoogleNewUser:

    @patch('routes.auth.http_req.get')
    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_25_new_user_created(self, mock_post, mock_get, client, db):
        """
        Email Google belum ada di DB → buat user baru,
        is_verified=True, langsung login.
        """
        mock_post.return_value = make_token_response()
        mock_get.return_value  = make_userinfo_response(
            email='brandnew@gmail.com', name='Brand New'
        )

        state = get_valid_state(client)
        r = client.get(callback_url(state), follow_redirects=True)

        # User harus ada di DB
        user = User.query.filter_by(email='brandnew@gmail.com').first()
        assert user is not None, 'User baru tidak dibuat di DB'

        # Google user langsung verified
        assert user.is_verified == True, 'is_verified harus True untuk Google user'

        # Harus redirect ke dashboard (login berhasil)
        assert r.status_code == 200

    @patch('routes.auth.http_req.get')
    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_25b_username_generated_from_email(
            self, mock_post, mock_get, client, db):
        """Username di-generate dari bagian lokal email."""
        mock_post.return_value = make_token_response()
        mock_get.return_value  = make_userinfo_response(
            email='johndoe@gmail.com'
        )

        state = get_valid_state(client)
        client.get(callback_url(state), follow_redirects=True)

        user = User.query.filter_by(email='johndoe@gmail.com').first()
        assert user is not None
        assert 'johndoe' in user.username

    @patch('routes.auth.http_req.get')
    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_25c_username_conflict_auto_numbered(
            self, mock_post, mock_get, client, db, verified_user):
        """
        Jika username dari email sudah dipakai,
        sistem tambahkan angka (testuser1, testuser2, dst).
        verified_user fixture pakai username='testuser', email='test@example.com'.
        Google user pakai email 'testuser@gmail.com' → username harusnya 'testuser1'.
        """
        mock_post.return_value = make_token_response()
        mock_get.return_value  = make_userinfo_response(
            email='testuser@gmail.com'  # local part = 'testuser' → konflik
        )

        state = get_valid_state(client)
        client.get(callback_url(state), follow_redirects=True)

        user = User.query.filter_by(email='testuser@gmail.com').first()
        assert user is not None
        # Username tidak boleh sama persis dengan yang sudah ada
        assert user.username != 'testuser'
        # Harus ada suffix angka
        assert user.username.startswith('testuser')

    @patch('routes.auth.http_req.get')
    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_25d_no_email_in_userinfo(
            self, mock_post, mock_get, client, db):
        """Google tidak mengembalikan email → tolak dengan flash danger."""
        mock_post.return_value = make_token_response()
        # Userinfo tanpa email
        mock_no_email = MagicMock()
        mock_no_email.status_code = 200
        mock_no_email.json.return_value = {'name': 'No Email User'}
        mock_no_email.raise_for_status.return_value = None
        mock_get.return_value = mock_no_email

        state = get_valid_state(client)
        r = client.get(callback_url(state), follow_redirects=True)

        body = r.data.decode('utf-8')
        assert any(keyword in body.lower() for keyword in [
            'email', 'tidak ditemukan', 'coba lagi'
        ])
        # Tidak ada user baru yang dibuat
        count = User.query.filter_by(email='').count()
        assert count == 0


# ══════════════════════════════════════════════════════════════
# UT-AUTH-26 — User Lama Login via Google
# ══════════════════════════════════════════════════════════════

class TestGoogleExistingUser:

    @patch('routes.auth.http_req.get')
    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_26_existing_user_login(
            self, mock_post, mock_get, client, db, verified_user):
        """
        Email Google sudah ada di DB → login user lama,
        tidak buat user baru.
        """
        mock_post.return_value = make_token_response()
        mock_get.return_value  = make_userinfo_response(
            email='test@example.com'  # email verified_user
        )

        count_before = User.query.count()

        state = get_valid_state(client)
        r = client.get(callback_url(state), follow_redirects=True)

        count_after = User.query.count()

        # Tidak boleh ada user baru
        assert count_after == count_before, \
            f'User baru dibuat padahal email sudah ada ({count_before} → {count_after})'
        assert r.status_code == 200

    @patch('routes.auth.http_req.get')
    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_26b_welcome_back_flash(
            self, mock_post, mock_get, client, db, verified_user):
        """Flash 'selamat datang kembali' muncul untuk user lama."""
        mock_post.return_value = make_token_response()
        mock_get.return_value  = make_userinfo_response(
            email='test@example.com'
        )

        state = get_valid_state(client)
        r = client.get(callback_url(state), follow_redirects=True)

        body = r.data.decode('utf-8')
        assert any(keyword in body.lower() for keyword in [
            'kembali', 'welcome', 'selamat datang'
        ])


# ══════════════════════════════════════════════════════════════
# UT-AUTH-27 — Auto-Verify User Lama via Google
# ══════════════════════════════════════════════════════════════

class TestGoogleAutoVerify:

    @patch('routes.auth.http_req.get')
    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_27_auto_verify_unverified_user(
            self, mock_post, mock_get, client, db, unverified_user):
        """
        User daftar manual tapi belum verifikasi email,
        lalu login via Google dengan email yang sama.
        → is_verified harus di-set True otomatis.
        """
        mock_post.return_value = make_token_response()
        mock_get.return_value  = make_userinfo_response(
            email='unverified@example.com'  # email unverified_user
        )

        # Pastikan awalnya belum verified
        assert unverified_user.is_verified == False

        state = get_valid_state(client)
        r = client.get(callback_url(state), follow_redirects=True)

        # Refresh dari DB
        _db.session.refresh(unverified_user)

        assert unverified_user.is_verified == True, \
            'is_verified harus True setelah Google mengkonfirmasi email'
        assert r.status_code == 200

    @patch('routes.auth.http_req.get')
    @patch('routes.auth.http_req.post')
    def test_UT_AUTH_27b_auto_verify_allows_login(
            self, mock_post, mock_get, client, db, unverified_user):
        """
        Setelah auto-verify via Google, user langsung bisa masuk
        (tidak diblokir seperti login manual belum verified).
        """
        mock_post.return_value = make_token_response()
        mock_get.return_value  = make_userinfo_response(
            email='unverified@example.com'
        )

        state = get_valid_state(client)
        r = client.get(callback_url(state), follow_redirects=True)

        # Tidak boleh ada flash "belum verifikasi"
        body = r.data.decode('utf-8')
        assert 'belum diverifikasi' not in body.lower()
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════
# BONUS — Test /google/login Endpoint
# ══════════════════════════════════════════════════════════════

class TestGoogleLoginRedirect:

    def test_login_redirects_to_google(self, client, db):
        """
        GET /google/login harus redirect ke accounts.google.com
        dengan parameter yang benar.
        """
        r = client.get('/google/login', follow_redirects=False)

        assert r.status_code == 302
        location = r.headers.get('Location', '')
        assert 'accounts.google.com' in location
        assert 'response_type=code' in location
        assert 'scope' in location

    def test_login_sets_csrf_state_in_session(self, client, db):
        """State CSRF harus tersimpan di session setelah /google/login."""
        client.get('/google/login', follow_redirects=False)

        with client.session_transaction() as sess:
            assert 'oauth_state' in sess
            assert len(sess['oauth_state']) > 10

    def test_login_state_in_redirect_url(self, client, db):
        """State di URL redirect harus sama dengan yang di session."""
        r = client.get('/google/login', follow_redirects=False)

        with client.session_transaction() as sess:
            session_state = sess.get('oauth_state', '')

        location = r.headers.get('Location', '')
        assert session_state in location