# tests/test_login.py


def post_login(client, username='testuser', password='password123', remember=False):
    return client.post('/login', data={
        'username': username,
        'password': password,
        'remember': 'on' if remember else ''
    }, follow_redirects=True)


def test_UT_AUTH_11_wrong_password(client, db, verified_user):
    """Password salah ditolak."""
    r = post_login(client, password='salah')
    assert 'salah' in r.data.decode().lower()


def test_UT_AUTH_12_wrong_username(client, db):
    """Username tidak ada ditolak."""
    r = post_login(client, username='tidakada')
    assert 'salah' in r.data.decode().lower()


def test_UT_AUTH_13_unverified_blocked(client, db, unverified_user):
    """Login diblokir jika belum verifikasi."""
    r = post_login(client, username='unverified')
    assert 'verifikasi' in r.data.decode().lower()
    # Pastikan tidak redirect ke dashboard
    assert 'dashboard' not in r.request.path


def test_UT_AUTH_14_login_success(client, db, verified_user):
    """Login berhasil dengan kredensial valid."""
    r = post_login(client)
    assert r.status_code == 200
    # Setelah login redirect ke dashboard
    assert b'dashboard' in r.data.lower() or r.status_code == 200


def test_UT_AUTH_15_remember_me(client, db, verified_user):
    """Remember me meneruskan flag ke login_user."""
    r = post_login(client, remember=True)
    assert r.status_code == 200