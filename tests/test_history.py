# tests/test_history.py
# ─────────────────────────────────────────────────────────────────────────────
# Unit test untuk routes/history.py
#   - GET /history
#   - GET /history/chart-data
#   - POST /history/delete/<id>
# ─────────────────────────────────────────────────────────────────────────────

import pytest
import json
from unittest.mock import patch, MagicMock
from models.session import PracticeSession
from extensions import db


# =============================================================================
# GET /history
# =============================================================================

class TestHistoryPage:

    def test_history_requires_login(self, client):
        """Akses /history tanpa login harus redirect ke halaman login."""
        response = client.get('/history')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_history_renders_for_logged_in_user(self, logged_in_client, practice_session):
        """User yang sudah login harus bisa akses /history dengan status 200."""
        response = logged_in_client.get('/history')
        assert response.status_code == 200
        assert b'history' in response.data.lower()

    def test_history_empty_no_sessions(self, logged_in_client):
        """Halaman history harus tetap tampil meski user tidak punya sesi."""
        response = logged_in_client.get('/history')
        assert response.status_code == 200

    def test_history_with_category_filter(self, logged_in_client, app, verified_user):
        """Filter kategori harus diteruskan ke template sebagai context variable."""
        with app.app_context():
            # Tambah sesi dengan kategori spesifik
            s = PracticeSession(
                user_id=verified_user.id,
                category='presentasi', title='Test Presentasi',
                status='completed', score_total=70.0,
                score_clarity=70, score_structure=70, score_confidence=70,
                score_relevance=70, score_vocabulary=70, score_fluency=70,
            )
            db.session.add(s)
            db.session.commit()

        response = logged_in_client.get('/history?category=presentasi')
        assert response.status_code == 200

    def test_history_pagination(self, logged_in_client, app, verified_user):
        """Halaman 2 tidak boleh error meskipun data sedikit."""
        response = logged_in_client.get('/history?page=2')
        # Boleh 200 (halaman kosong) atau redirect, tidak boleh 500
        assert response.status_code in (200, 302)


# =============================================================================
# GET /history/chart-data
# =============================================================================

class TestChartData:

    def test_chart_data_requires_login(self, client, db):
        """Akses /history/chart-data tanpa login harus redirect."""
        response = client.get('/history/chart-data')
        assert response.status_code == 302

    def test_chart_data_empty_returns_zeros(self, logged_in_client):
        """Jika tidak ada sesi, semua stats harus bernilai 0."""
        response = logged_in_client.get('/history/chart-data')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['stats']['total_sessions'] == 0
        assert data['stats']['avg_score'] == 0
        assert data['stats']['best_score'] == 0
        assert data['stats']['latest_score'] == 0
        assert data['stats']['improvement'] == 0

    def test_chart_data_structure_keys(self, logged_in_client):
        """Response JSON harus mengandung semua kunci yang diharapkan."""
        response = logged_in_client.get('/history/chart-data')
        data = json.loads(response.data)
        expected_keys = [
            'labels', 'scores_total', 'scores_clarity', 'scores_structure',
            'scores_confidence', 'scores_relevance', 'scores_vocabulary',
            'scores_fluency', 'categories', 'titles', 'stats'
        ]
        for key in expected_keys:
            assert key in data, f"Key '{key}' tidak ada di response"

    def test_chart_data_with_single_session(self, logged_in_client, practice_session):
        """Dengan 1 sesi, improvement harus 0 dan stats terisi dengan benar."""
        response = logged_in_client.get('/history/chart-data')
        data = json.loads(response.data)
        assert data['stats']['total_sessions'] == 1
        assert data['stats']['avg_score'] == 80.0
        assert data['stats']['best_score'] == 80.0
        assert data['stats']['latest_score'] == 80.0
        assert data['stats']['improvement'] == 0  # butuh ≥ 2 sesi

    def test_chart_data_improvement_calculation(self, logged_in_client, multiple_sessions):
        """Improvement harus = skor_terakhir - skor_pertama (diurutkan ascending)."""
        response = logged_in_client.get('/history/chart-data')
        data = json.loads(response.data)
        # skor: 60, 75, 90 (ascending) → improvement = 90 - 60 = 30
        assert data['stats']['improvement'] == 30.0

    def test_chart_data_category_filter(self, logged_in_client, app, verified_user):
        """Filter kategori harus memfilter data yang dikembalikan."""
        with app.app_context():
            s1 = PracticeSession(
                user_id=verified_user.id, category='debat', title='Debat 1',
                status='completed', score_total=70.0,
                score_clarity=70, score_structure=70, score_confidence=70,
                score_relevance=70, score_vocabulary=70, score_fluency=70,
            )
            s2 = PracticeSession(
                user_id=verified_user.id, category='mc', title='MC 1',
                status='completed', score_total=85.0,
                score_clarity=85, score_structure=85, score_confidence=85,
                score_relevance=85, score_vocabulary=85, score_fluency=85,
            )
            db.session.add_all([s1, s2])
            db.session.commit()

        response = logged_in_client.get('/history/chart-data?category=debat')
        data = json.loads(response.data)
        # Semua categories yang dikembalikan harus 'debat'
        for cat in data['categories']:
            assert cat == 'debat'

    def test_chart_data_labels_format(self, logged_in_client, practice_session):
        """Label tanggal harus dalam format DD/MM/YYYY."""
        response = logged_in_client.get('/history/chart-data')
        data = json.loads(response.data)
        if data['labels']:
            label = data['labels'][0]
            parts = label.split('/')
            assert len(parts) == 3, f"Format tanggal tidak valid: {label}"
            assert len(parts[2]) == 4, "Tahun harus 4 digit"


# =============================================================================
# POST /history/delete/<id>
# =============================================================================

class TestDeleteSession:

    def test_delete_requires_login(self, client,db, practice_session):
        """Delete tanpa login harus redirect."""
        response = client.post(f'/history/delete/{practice_session.id}')
        assert response.status_code == 302

    def test_delete_own_session_success(self, logged_in_client, practice_session, app):
        """User bisa menghapus sesi miliknya sendiri."""
        response = logged_in_client.post(f'/history/delete/{practice_session.id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

        # Pastikan sesi benar-benar terhapus dari DB
        with app.app_context():
            deleted = db.session.get(PracticeSession, practice_session.id)
            assert deleted is None

    def test_delete_other_users_session_returns_403(
        self, logged_in_client, app, second_user
    ):
        """User tidak boleh menghapus sesi milik user lain — harus 403."""
        with app.app_context():
            other_session = PracticeSession(
                user_id=second_user.id,
                category='pidato', title='Sesi Orang Lain',
                status='completed', score_total=70.0,
                score_clarity=70, score_structure=70, score_confidence=70,
                score_relevance=70, score_vocabulary=70, score_fluency=70,
            )
            db.session.add(other_session)
            db.session.commit()
            session_id = other_session.id

        response = logged_in_client.post(f'/history/delete/{session_id}')
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Akses ditolak' in data['error']

    def test_delete_nonexistent_session_returns_404(self, logged_in_client):
        """Menghapus sesi yang tidak ada harus return 404."""
        response = logged_in_client.post('/history/delete/99999')
        assert response.status_code == 404

    def test_delete_removes_audio_file(self, logged_in_client, app, verified_user, tmp_path):
        """Menghapus sesi harus ikut menghapus file audio jika ada."""
        # Buat file audio sementara
        audio_file = tmp_path / 'test_audio.webm'
        audio_file.write_bytes(b'fake audio data')

        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Sesi Dengan Audio',
                status='completed', score_total=70.0,
                score_clarity=70, score_structure=70, score_confidence=70,
                score_relevance=70, score_vocabulary=70, score_fluency=70,
                audio_path=str(audio_file),
            )
            db.session.add(s)
            db.session.commit()
            session_id = s.id

        response = logged_in_client.post(f'/history/delete/{session_id}')
        assert response.status_code == 200
        assert not audio_file.exists(), "File audio harus ikut terhapus"

    def test_delete_session_without_audio(self, logged_in_client, app, verified_user):
        """Menghapus sesi yang tidak punya audio_path tidak boleh error."""
        with app.app_context():
            s = PracticeSession(
                user_id=verified_user.id,
                category='pidato', title='Sesi Tanpa Audio',
                status='completed', score_total=70.0,
                score_clarity=70, score_structure=70, score_confidence=70,
                score_relevance=70, score_vocabulary=70, score_fluency=70,
                audio_path=None,
            )
            db.session.add(s)
            db.session.commit()
            session_id = s.id

        response = logged_in_client.post(f'/history/delete/{session_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True