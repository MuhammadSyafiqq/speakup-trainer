# tests/test_models.py
# ─────────────────────────────────────────────────────────────────────────────
# Unit test untuk semua Model:
#   - User
#   - PracticeSession
#   - InterviewSession
#   - EmailVerificationToken
# ─────────────────────────────────────────────────────────────────────────────

import pytest
import json
from datetime import datetime, timedelta
from models.user import User
from models.session import PracticeSession
from models.interview_session import InterviewSession
from models.email_verification import EmailVerificationToken
from extensions import db


# =============================================================================
# MODEL: User
# =============================================================================

class TestUserModel:

    def test_set_password_stores_hash(self, db, app):
        """set_password() harus menyimpan hash, bukan plain text."""
        with app.app_context():
            u = User(username='u1', email='u1@test.com')
            u.set_password('rahasia123')
            assert u.password_hash is not None
            assert u.password_hash != 'rahasia123'

    def test_check_password_correct(self, db, app):
        """check_password() harus return True untuk password yang benar."""
        with app.app_context():
            u = User(username='u2', email='u2@test.com')
            u.set_password('rahasia123')
            assert u.check_password('rahasia123') is True

    def test_check_password_wrong(self, db, app):
        """check_password() harus return False untuk password salah."""
        with app.app_context():
            u = User(username='u3', email='u3@test.com')
            u.set_password('rahasia123')
            assert u.check_password('salah') is False

    def test_check_password_no_hash(self, db, app):
        """check_password() harus return False jika password_hash kosong (akun Google OAuth)."""
        with app.app_context():
            u = User(username='u4', email='u4@test.com')
            u.password_hash = None
            assert u.check_password('apapun') is False

    def test_get_id_returns_string(self, db, app):
        """get_id() harus mengembalikan string (wajib untuk Flask-Login)."""
        with app.app_context():
            u = User(username='u5', email='u5@test.com', id=42)
            assert u.get_id() == '42'
            assert isinstance(u.get_id(), str)

    def test_get_average_score_no_sessions(self, db, app, verified_user):
        """get_average_score() harus return 0 jika tidak ada sesi."""
        with app.app_context():
            # verified_user tidak punya sesi
            user = db.session.get(User, verified_user.id)
            assert user.get_average_score() == 0

    def test_get_average_score_with_sessions(self, db, app, multiple_sessions, verified_user):
        """get_average_score() harus return rata-rata yang benar."""
        with app.app_context():
            user = db.session.get(User, verified_user.id)
            # skor: 60, 75, 90 → rata-rata 75
            avg = user.get_average_score()
            assert avg == 75

    def test_get_total_sessions(self, db, app, multiple_sessions, verified_user):
        """get_total_sessions() harus menghitung semua sesi milik user."""
        with app.app_context():
            user = db.session.get(User, verified_user.id)
            assert user.get_total_sessions() == 3

    def test_get_best_score(self, db, app, multiple_sessions, verified_user):
        """get_best_score() harus mengembalikan skor tertinggi."""
        with app.app_context():
            user = db.session.get(User, verified_user.id)
            assert user.get_best_score() == 90

    def test_repr(self, app):
        """__repr__ harus mengandung username."""
        with app.app_context():
            u = User(username='repr_user', email='repr@test.com')
            assert 'repr_user' in repr(u)


# =============================================================================
# MODEL: PracticeSession
# =============================================================================

class TestPracticeSessionModel:

    def test_calculate_total_score_all_valid(self, db, app, verified_user):
        """calculate_total_score() harus rata-ratakan 6 skor dengan benar."""
        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Test',
                score_clarity=80, score_structure=70,
                score_confidence=90, score_relevance=60,
                score_vocabulary=70, score_fluency=80,
            )
            result = s.calculate_total_score()
            assert result == round((80 + 70 + 90 + 60 + 70 + 80) / 6, 1)

    def test_calculate_total_score_some_zero(self, db, app, verified_user):
        """calculate_total_score() hanya rata-ratakan skor > 0."""
        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Test',
                score_clarity=80, score_structure=0,
                score_confidence=0, score_relevance=60,
                score_vocabulary=0, score_fluency=80,
            )
            result = s.calculate_total_score()
            # Hanya 80, 60, 80 yang valid → rata-rata 73.3
            assert result == round((80 + 60 + 80) / 3, 1)

    def test_calculate_total_score_all_zero(self, db, app, verified_user):
        """calculate_total_score() harus return 0 jika semua skor nol."""
        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Test',
                score_clarity=0, score_structure=0,
                score_confidence=0, score_relevance=0,
                score_vocabulary=0, score_fluency=0,
            )
            result = s.calculate_total_score()
            assert result == 0

    @pytest.mark.parametrize("score,expected_grade", [
        (95, 'A'),
        (85, 'B'),
        (75, 'C'),
        (65, 'D'),
        (50, 'E'),
    ])
    def test_get_grade(self, db, app, verified_user, score, expected_grade):
        """get_grade() harus mengembalikan grade yang sesuai rentang skor."""
        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Test',
                score_total=score,
            )
            grade, _ = s.get_grade()
            assert grade == expected_grade

    def test_set_and_get_feedback(self, db, app, verified_user):
        """set_feedback() dan get_feedback() harus bekerja bolak-balik (round-trip)."""
        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Test',
            )
            feedback = {'clarity': 'Baik', 'structure': 'Perlu diperbaiki'}
            s.set_feedback(feedback)
            assert s.get_feedback() == feedback

    def test_get_feedback_empty(self, db, app, verified_user):
        """get_feedback() harus return dict kosong jika feedback_json None."""
        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Test',
            )
            s.feedback_json = None
            assert s.get_feedback() == {}

    def test_to_dict_keys(self, db, app, verified_user):
        """to_dict() harus mengandung semua kunci yang diharapkan."""
        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Test Pidato',
                status='completed', score_total=80,
            )
            db.session.add(s)
            db.session.commit()
            d = s.to_dict()
            expected_keys = [
                'id', 'category', 'title', 'score_total',
                'score_clarity', 'score_structure', 'score_confidence',
                'score_relevance', 'score_vocabulary', 'score_fluency',
                'feedback', 'suggestions', 'strengths', 'weaknesses',
                'grade', 'grade_text', 'status', 'created_at', 'duration_seconds'
            ]
            for key in expected_keys:
                assert key in d, f"Key '{key}' tidak ditemukan di to_dict()"

    def test_repr(self, db, app, verified_user):
        """__repr__ harus mengandung judul sesi."""
        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Judul Repr'
            )
            assert 'Judul Repr' in repr(s)


# =============================================================================
# MODEL: InterviewSession
# =============================================================================

class TestInterviewSessionModel:

    def test_set_and_get_questions(self, db, app):
        """set_questions() / get_questions() harus bekerja round-trip."""
        with app.app_context():
            s = InterviewSession(
                session_id='abc123',
                position_label='Backend Developer',
            )
            questions = ['Ceritakan diri kamu?', 'Apa kelebihan kamu?', 'Kenapa ingin bergabung?']
            s.set_questions(questions)
            assert s.get_questions() == questions

    def test_get_questions_empty(self, db, app):
        """get_questions() harus return list kosong jika questions_json None."""
        with app.app_context():
            s = InterviewSession(
                session_id='abc456',
                position_label='Frontend Developer',
            )
            s.questions_json = None
            assert s.get_questions() == []

    def test_set_and_get_feedback(self, db, app):
        """set_feedback() / get_feedback() harus bekerja round-trip."""
        with app.app_context():
            s = InterviewSession(
                session_id='abc789',
                position_label='HR Manager',
            )
            fb = {'clarity': 'Sangat baik', 'structure': 'Terstruktur'}
            s.set_feedback(fb)
            assert s.get_feedback() == fb

    def test_calculate_total_score(self, db, app):
        """calculate_total_score() harus menghasilkan rata-rata 6 dimensi skor."""
        with app.app_context():
            s = InterviewSession(
                session_id='scr001',
                position_label='Test Position',
                score_clarity=70, score_structure=80,
                score_confidence=90, score_relevance=75,
                score_vocabulary=65, score_fluency=80,
            )
            result = s.calculate_total_score()
            expected = round((70 + 80 + 90 + 75 + 65 + 80) / 6, 1)
            assert result == expected

    @pytest.mark.parametrize("score,expected_grade", [
        (92, 'A'),
        (81, 'B'),
        (71, 'C'),
        (61, 'D'),
        (40, 'E'),
    ])
    def test_get_grade(self, score, expected_grade, app):
        """get_grade() harus mengembalikan grade yang tepat per rentang skor."""
        with app.app_context():
            s = InterviewSession(
                session_id=f'grade_{score}',
                position_label='Test',
                score_total=score,
            )
            grade, _ = s.get_grade()
            assert grade == expected_grade

    def test_to_dict_contains_questions(self, db, app):
        """to_dict() harus menyertakan field 'questions' hasil get_questions()."""
        with app.app_context():
            s = InterviewSession(
                session_id='dict001',
                position_label='Backend',
                company='PT Test',
                language='id',
                total_questions=3,
            )
            s.set_questions(['Q1', 'Q2', 'Q3'])
            db.session.add(s)
            db.session.commit()
            d = s.to_dict()
            assert d['questions'] == ['Q1', 'Q2', 'Q3']
            assert d['position_label'] == 'Backend'
            assert d['company'] == 'PT Test'

    def test_repr(self, app):
        """__repr__ harus mengandung position_label."""
        with app.app_context():
            s = InterviewSession(
                session_id='repr001',
                position_label='Data Scientist',
            )
            assert 'Data Scientist' in repr(s)


# =============================================================================
# MODEL: EmailVerificationToken
# =============================================================================

class TestEmailVerificationToken:

    def test_is_valid_fresh_token(self, db, app, verified_user):
        """Token baru yang belum dipakai dan belum kadaluarsa harus is_valid=True."""
        with app.app_context():
            token = EmailVerificationToken(
                user_id=verified_user.id,
                token='valid_token_abc',
                expires_at=datetime.utcnow() + timedelta(hours=24),
                used=False,
            )
            assert token.is_valid is True

    def test_is_valid_expired_token(self, db, app, verified_user):
        """Token yang sudah kadaluarsa harus is_valid=False."""
        with app.app_context():
            token = EmailVerificationToken(
                user_id=verified_user.id,
                token='expired_token',
                expires_at=datetime.utcnow() - timedelta(hours=1),
                used=False,
            )
            assert token.is_valid is False

    def test_is_valid_used_token(self, db, app, verified_user):
        """Token yang sudah dipakai harus is_valid=False meskipun belum kadaluarsa."""
        with app.app_context():
            token = EmailVerificationToken(
                user_id=verified_user.id,
                token='used_token',
                expires_at=datetime.utcnow() + timedelta(hours=24),
                used=True,
            )
            assert token.is_valid is False

    def test_is_expired(self, db, app, verified_user):
        """is_expired harus True jika expires_at sudah lewat."""
        with app.app_context():
            token = EmailVerificationToken(
                user_id=verified_user.id,
                token='exp_token',
                expires_at=datetime.utcnow() - timedelta(seconds=1),
                used=False,
            )
            assert token.is_expired is True

    def test_is_not_expired(self, db, app, verified_user):
        """is_expired harus False jika expires_at belum lewat."""
        with app.app_context():
            token = EmailVerificationToken(
                user_id=verified_user.id,
                token='not_exp_token',
                expires_at=datetime.utcnow() + timedelta(hours=10),
                used=False,
            )
            assert token.is_expired is False

    def test_generate_invalidates_old_tokens(self, db, app, verified_user):
        """generate() harus men-invalidate semua token lama yang masih aktif."""
        with app.app_context():
            user = db.session.get(User, verified_user.id)
            # Buat token lama
            old = EmailVerificationToken(
                user_id=user.id,
                token='old_token_xyz',
                expires_at=datetime.utcnow() + timedelta(hours=24),
                used=False,
            )
            db.session.add(old)
            db.session.commit()

            # Generate token baru — token lama harus di-mark used=True
            EmailVerificationToken.generate(user.id)

            old_refreshed = db.session.query(EmailVerificationToken).filter_by(
                token='old_token_xyz'
            ).first()
            assert old_refreshed.used is True

    def test_generate_creates_new_token(self, db, app, verified_user):
        """generate() harus membuat token baru dengan is_valid=True."""
        with app.app_context():
            user = db.session.get(User, verified_user.id)
            new_token = EmailVerificationToken.generate(user.id)
            assert new_token is not None
            assert new_token.is_valid is True
            assert len(new_token.token) > 0

    def test_repr(self, db, app, verified_user):
        """__repr__ harus mengandung user_id."""
        with app.app_context():
            token = EmailVerificationToken(
                user_id=verified_user.id,
                token='repr_test',
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            assert str(verified_user.id) in repr(token)