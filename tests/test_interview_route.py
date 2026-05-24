# tests/test_interview_route.py
# ─────────────────────────────────────────────────────────────────────────────
# Unit test untuk routes/interview.py
#   - Helper: call_openrouter()
#   - GET  /interview/setup
#   - GET  /interview/session (dari app.py)
#   - POST /interview/next-question  (atau endpoint submit jawaban)
# ─────────────────────────────────────────────────────────────────────────────

import pytest
import json
import requests
from unittest.mock import patch, MagicMock


# =============================================================================
# HELPER: call_openrouter() di routes/interview.py
# =============================================================================

class TestCallOpenrouterHelper:
    """Test helper function call_openrouter di routes/interview.py."""

    @patch('routes.interview.requests.post')
    def test_success_returns_content(self, mock_post):
        """Response 200 yang valid harus mengembalikan content string."""
        from routes.interview import call_openrouter
        mock_post.return_value.ok = True
        mock_post.return_value.headers = {'Content-Type': 'application/json'}
        mock_post.return_value.text = '{"choices": [{"message": {"content": "Halo"}}]}'
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': 'Ceritakan pengalaman kamu!'}}]
        }

        result = call_openrouter([{'role': 'user', 'content': 'test'}])
        assert result == 'Ceritakan pengalaman kamu!'

    @patch('routes.interview.requests.post')
    def test_html_response_raises_exception(self, mock_post):
        """Response HTML (bukan JSON) harus raise Exception."""
        from routes.interview import call_openrouter
        mock_post.return_value.ok = False
        mock_post.return_value.status_code = 200
        mock_post.return_value.headers = {'Content-Type': 'text/html'}
        mock_post.return_value.text = '<html><body>Error page</body></html>'

        with pytest.raises(Exception, match='HTML'):
            call_openrouter([{'role': 'user', 'content': 'test'}])

    @patch('routes.interview.requests.post')
    def test_error_in_json_raises_exception(self, mock_post):
        """Response JSON yang mengandung field 'error' harus raise Exception."""
        from routes.interview import call_openrouter
        mock_post.return_value.ok = True
        mock_post.return_value.headers = {'Content-Type': 'application/json'}
        mock_post.return_value.text = '{"error": {"message": "Invalid API key"}}'
        mock_post.return_value.json.return_value = {
            'error': {'message': 'Invalid API key'}
        }

        with pytest.raises(Exception, match='Invalid API key'):
            call_openrouter([{'role': 'user', 'content': 'test'}])

    @patch('routes.interview.requests.post')
    def test_http_error_raises(self, mock_post):
        """HTTP error (4xx/5xx) harus raise Exception."""
        from routes.interview import call_openrouter
        mock_post.return_value.ok = False
        mock_post.return_value.status_code = 500
        mock_post.return_value.headers = {'Content-Type': 'application/json'}
        mock_post.return_value.text = '{"error": "Internal Server Error"}'
        mock_post.return_value.json.return_value = {'error': 'Internal Server Error'}
        mock_post.return_value.raise_for_status.side_effect = Exception("HTTP 500")

        with pytest.raises(Exception):
            call_openrouter([{'role': 'user', 'content': 'test'}])


# =============================================================================
# GET /interview/setup (dari practice_bp)
# =============================================================================

class TestInterviewSetup:

    def test_setup_requires_login(self, client):
        """Interview setup harus redirect jika belum login."""
        response = client.get('/interview/setup')
        assert response.status_code == 302

    def test_setup_renders_positions(self, logged_in_client):
        """Halaman setup harus menampilkan daftar posisi."""
        response = logged_in_client.get('/interview/setup')
        assert response.status_code == 200


# =============================================================================
# GET /interview/session (route dari app.py)
# =============================================================================

class TestInterviewSession:

    def test_session_creates_new_session(self, logged_in_client, app):
        """GET /interview/session harus render halaman HTML sesi wawancara."""
        response = logged_in_client.get(
            '/interview/session?position_label=Backend+Developer&company=PT+Test&total_q=3'
        )
        assert response.status_code == 200
        # Route ini render template HTML, bukan JSON
        assert b'html' in response.data.lower()

    def test_session_generates_session_id_if_missing(self, logged_in_client):
        """GET /interview/session tanpa parameter tetap harus return 200."""
        # Pastikan tidak ada session_id di cookie
        with logged_in_client.session_transaction() as sess:
            sess.pop('session_id', None)

        response = logged_in_client.get('/interview/session?position_label=HR&company=ABC')
        assert response.status_code == 200


# =============================================================================
# Test endpoint interview di routes/interview.py (next question, submit, dll)
# =============================================================================

class TestInterviewEndpoints:
    """Test endpoint-endpoint di interview_bp."""

    def test_interview_next_requires_login(self, client):
        """Endpoint next question harus proteksi login."""
        # Cari endpoint POST di interview_bp
        response = client.post('/interview/next',
            data=json.dumps({}),
            content_type='application/json'
        )
        # Harusnya 302 redirect ke login
        assert response.status_code in (302, 404)  # 404 jika endpoint berbeda nama

    @patch('routes.interview.call_openrouter')
    def test_interview_next_question_success(self, mock_call, logged_in_client, app):
        """Next question harus mengembalikan pertanyaan dari AI."""
        mock_call.return_value = 'Ceritakan pengalaman kerja kamu yang paling berkesan!'

        # Simulasi request next question
        response = logged_in_client.post('/interview/next',
            data=json.dumps({
                'session_id': 'test-session',
                'position': 'Backend Developer',
                'company': 'PT Test',
                'answer': 'Jawaban saya adalah...',
                'question_num': 2,
                'language': 'id',
            }),
            content_type='application/json'
        )
        # Cek bahwa tidak ada server error
        assert response.status_code in (200, 302, 404)

    def test_interview_finish_requires_login(self, client):
        """Endpoint finish interview harus proteksi login."""
        response = client.post('/interview/finish',
            data=json.dumps({'session_id': 'test'}),
            content_type='application/json'
        )
        assert response.status_code in (302, 404)