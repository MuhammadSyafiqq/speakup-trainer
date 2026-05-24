# tests/conftest.py
import pytest
from app import app as flask_app
from extensions import db as _db
from models.user import User
from models.session import PracticeSession
from models.interview_session import InterviewSession
from models.email_verification import EmailVerificationToken


@pytest.fixture(scope='session')
def app():
    flask_app.config['TESTING']                   = True
    flask_app.config['SQLALCHEMY_DATABASE_URI']   = 'sqlite:///:memory:'
    flask_app.config['WTF_CSRF_ENABLED']          = False
    flask_app.config['MAIL_SUPPRESS_SEND']        = True
    flask_app.config['SERVER_NAME']               = 'localhost'
    flask_app.config['LOGIN_DISABLED']            = False

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    """Test client baru setiap test — tidak ada state dari test sebelumnya."""
    return app.test_client()


@pytest.fixture(autouse=True)
def logout_after_each_test(app):
    """
    Paksa logout setelah setiap test agar session login tidak bocor.
    autouse=True → otomatis berlaku untuk semua test tanpa perlu ditulis.
    """
    yield
    with app.test_client() as c:
        c.get('/logout', follow_redirects=True)


@pytest.fixture
def db(app):
    """Bersihkan semua data setelah setiap test."""
    yield _db
    _db.session.query(EmailVerificationToken).delete()
    _db.session.query(InterviewSession).delete()
    _db.session.query(PracticeSession).delete()
    _db.session.query(User).delete()
    _db.session.commit()


@pytest.fixture
def verified_user(db):
    u = User(username='testuser', email='test@example.com', is_verified=True)
    u.set_password('password123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def unverified_user(db):
    u = User(username='unverifieduser', email='unverified@example.com', is_verified=False)
    u.set_password('password123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def second_user(db):
    u = User(username='otheruser', email='other@example.com', is_verified=True)
    u.set_password('password123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def logged_in_client(client, verified_user):
    """Client yang sudah login sebagai verified_user."""
    client.post('/login', data={
        'username': 'testuser',
        'password': 'password123'
    }, follow_redirects=True)
    return client


@pytest.fixture
def practice_session(db, verified_user):
    s = PracticeSession(
        user_id=verified_user.id,
        category='pidato',
        title='Pidato Perpisahan',
        status='completed',
        score_total=80.0,
        score_clarity=80.0,
        score_structure=75.0,
        score_confidence=85.0,
        score_relevance=78.0,
        score_vocabulary=82.0,
        score_fluency=80.0,
    )
    _db.session.add(s)
    _db.session.commit()
    return s


@pytest.fixture
def multiple_sessions(db, verified_user):
    sessions = []
    scores = [60.0, 75.0, 90.0]
    for i, score in enumerate(scores):
        s = PracticeSession(
            user_id=verified_user.id,
            category='pidato',
            title=f'Sesi {i+1}',
            status='completed',
            score_total=score,
            score_clarity=score,
            score_structure=score,
            score_confidence=score,
            score_relevance=score,
            score_vocabulary=score,
            score_fluency=score,
        )
        _db.session.add(s)
        sessions.append(s)
    _db.session.commit()
    return sessions