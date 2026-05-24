# tests/test_interview_service.py
# ─────────────────────────────────────────────────────────────────────────────
# Unit test untuk services/interview_service.py
#   - InterviewService._call_openrouter()
#   - InterviewService.get_or_create_session()
# ─────────────────────────────────────────────────────────────────────────────

import pytest
import json
import time
from unittest.mock import patch, MagicMock, call
from services.interview_service import InterviewService


# =============================================================================
# FIXTURE
# =============================================================================

@pytest.fixture
def service():
    """Instance InterviewService dengan API key dummy untuk testing."""
    return InterviewService(openrouter_api_key='sk-test-key-dummy')


# =============================================================================
# _call_openrouter()
# =============================================================================

class TestCallOpenrouter:

    @patch('services.interview_service.requests.post')
    def test_success_returns_question_list(self, mock_post, service):
        """Response 200 JSON valid harus mengembalikan list pertanyaan."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.headers = {'Content-Type': 'application/json'}
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': 'Pertanyaan 1\nPertanyaan 2\nPertanyaan 3\nPertanyaan 4\nPertanyaan 5'}}]
        }
        result = service._call_openrouter('Test prompt', 5)
        assert len(result) == 5
        assert result[0] == 'Pertanyaan 1'
        assert result[4] == 'Pertanyaan 5'

    @patch('services.interview_service.requests.post')
    def test_strips_blank_lines(self, mock_post, service):
        """Baris kosong dalam response harus difilter."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.headers = {'Content-Type': 'application/json'}
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': 'Q1\n\nQ2\n\nQ3\n\nQ4\nQ5'}}]
        }
        result = service._call_openrouter('prompt', 5)
        assert len(result) == 5
        assert '' not in result

    @patch('services.interview_service.requests.post')
    def test_pads_if_fewer_questions_returned(self, mock_post, service):
        """Jika API mengembalikan < total_q pertanyaan, harus dilengkapi dengan fallback."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.headers = {'Content-Type': 'application/json'}
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': 'Hanya 2 pertanyaan\nIni pertanyaan kedua'}}]
        }
        result = service._call_openrouter('prompt', 5)
        assert len(result) == 5
        # Pertanyaan ke-3, 4, 5 adalah fallback
        assert result[2] == 'Pertanyaan 3'
        assert result[3] == 'Pertanyaan 4'
        assert result[4] == 'Pertanyaan 5'

    @patch('services.interview_service.requests.post')
    def test_truncates_if_more_questions_returned(self, mock_post, service):
        """Jika API mengembalikan lebih dari total_q, harus dipotong."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.headers = {'Content-Type': 'application/json'}
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': 'Q1\nQ2\nQ3\nQ4\nQ5\nQ6\nQ7'}}]
        }
        result = service._call_openrouter('prompt', 5)
        assert len(result) == 5

    @patch('services.interview_service.time.sleep')
    @patch('services.interview_service.requests.post')
    def test_rate_limit_429_waits_and_retries(self, mock_post, mock_sleep, service):
        """Status 429 harus menunggu sesuai Retry-After lalu retry."""
        mock_post.return_value.status_code = 429
        mock_post.return_value.headers = {'Retry-After': '5'}

        service._call_openrouter('prompt', 3)

        # Harus dipanggil sleep dengan nilai dari Retry-After
        mock_sleep.assert_called_with(5)

    @patch('services.interview_service.time.sleep')
    @patch('services.interview_service.requests.post')
    def test_html_response_on_200_retries(self, mock_post, mock_sleep, service):
        """Response 200 tapi isinya HTML harus retry dan akhirnya return fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Error</body></html>'
        mock_post.return_value = mock_response

        result = service._call_openrouter('prompt', 3)

        # Harus return fallback questions
        assert len(result) == 3
        assert all('gagal dimuat' in q for q in result)

    @patch('services.interview_service.time.sleep')
    @patch('services.interview_service.requests.post')
    def test_json_parse_error_retries_and_returns_fallback(self, mock_post, mock_sleep, service):
        """Jika response bukan JSON valid, harus retry lalu return fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = 'BUKAN JSON VALID <<<'
        mock_response.json.side_effect = ValueError("JSON decode error")
        mock_post.return_value = mock_response

        result = service._call_openrouter('prompt', 3)
        assert len(result) == 3
        assert all('gagal dimuat' in q for q in result)

    @patch('services.interview_service.requests.post')
    def test_error_in_json_response_returns_fallback(self, mock_post, service):
        """JSON yang mengandung field 'error' harus return fallback."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.headers = {'Content-Type': 'application/json'}
        mock_post.return_value.json.return_value = {
            'error': {'message': 'Model overloaded'}
        }
        result = service._call_openrouter('prompt', 3)
        assert len(result) == 3
        assert all('gagal dimuat' in q for q in result)

    @patch('services.interview_service.time.sleep')
    @patch('services.interview_service.requests.post')
    def test_server_error_500_retries_then_raises(self, mock_post, mock_sleep, service):
        """Status 500 harus retry sebanyak max_retries dan akhirnya raise."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = 'Internal Server Error'
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        mock_post.return_value = mock_response

        with pytest.raises(Exception):
            service._call_openrouter('prompt', 3, max_retries=2)

        # Harus sleep antar retry
        assert mock_sleep.called

    @patch('services.interview_service.requests.post')
    def test_returns_exactly_total_q_items(self, mock_post, service):
        """Hasil _call_openrouter harus selalu berjumlah tepat total_q."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.headers = {'Content-Type': 'application/json'}
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': 'Q1\nQ2\nQ3'}}]
        }
        for total_q in [1, 3, 5, 7]:
            result = service._call_openrouter('prompt', total_q)
            assert len(result) == total_q, f"Expected {total_q} questions, got {len(result)}"


# =============================================================================
# get_or_create_session()
# =============================================================================

class TestGetOrCreateSession:

    @patch('services.interview_service.InterviewSession')
    def test_returns_existing_session_without_api_call(self, mock_model, service, app):
        """Jika sesi sudah ada, harus langsung dikembalikan tanpa panggil API."""
        with app.app_context():
            existing = MagicMock()
            mock_model.query.filter_by.return_value.first.return_value = existing

            with patch.object(service, '_call_openrouter') as mock_call:
                result = service.get_or_create_session(
                    session_id='existing-id',
                    position_label='Backend Developer',
                    company='PT Test',
                    total_q=5,
                )
            # API tidak boleh dipanggil karena sesi sudah ada
            mock_call.assert_not_called()
            assert result is existing

    @patch('services.interview_service.db')
    @patch('services.interview_service.InterviewSession')
    def test_creates_new_session_when_not_found(self, mock_model, mock_db, service, app):
        """Jika sesi belum ada, harus generate pertanyaan dan simpan ke DB."""
        with app.app_context():
            mock_model.query.filter_by.return_value.first.return_value = None
            new_session = MagicMock()
            mock_model.return_value = new_session

            with patch.object(service, '_call_openrouter') as mock_call:
                mock_call.return_value = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']

                service.get_or_create_session(
                    session_id='new-id',
                    position_label='Frontend Developer',
                    company='PT ABC',
                    total_q=5,
                    language='id',
                    user_id=1,
                )

            # API harus dipanggil sekali
            mock_call.assert_called_once()
            # set_questions harus dipanggil dengan hasil API
            new_session.set_questions.assert_called_once_with(['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
            # Sesi harus di-add dan di-commit ke DB
            mock_db.session.add.assert_called_once_with(new_session)
            mock_db.session.commit.assert_called_once()

    @patch('services.interview_service.db')
    @patch('services.interview_service.InterviewSession')
    def test_new_session_uses_fallback_on_api_error(self, mock_model, mock_db, service, app):
        """Jika API error, sesi tetap dibuat dengan pertanyaan fallback."""
        with app.app_context():
            mock_model.query.filter_by.return_value.first.return_value = None
            new_session = MagicMock()
            mock_model.return_value = new_session

            with patch.object(service, '_call_openrouter') as mock_call:
                # Simulasi API error → _call_openrouter return fallback questions
                mock_call.return_value = [
                    'Pertanyaan 1 gagal dimuat',
                    'Pertanyaan 2 gagal dimuat',
                    'Pertanyaan 3 gagal dimuat',
                ]

                service.get_or_create_session(
                    session_id='fallback-id',
                    position_label='HR Manager',
                    company='',
                    total_q=3,
                )

            # Sesi harus tetap dibuat meskipun dengan fallback questions
            mock_db.session.add.assert_called_once()
            mock_db.session.commit.assert_called_once()
            new_session.set_questions.assert_called_once()

    @patch('services.interview_service.db')
    @patch('services.interview_service.InterviewSession')
    def test_new_session_prompt_includes_position_and_company(
        self, mock_model, mock_db, service, app
    ):
        """Prompt yang dikirim ke API harus menyertakan position dan company."""
        with app.app_context():
            mock_model.query.filter_by.return_value.first.return_value = None
            mock_model.return_value = MagicMock()

            with patch.object(service, '_call_openrouter') as mock_call:
                mock_call.return_value = ['Q1', 'Q2', 'Q3']

                service.get_or_create_session(
                    session_id='prompt-test',
                    position_label='Data Engineer',
                    company='PT Data Corp',
                    total_q=3,
                )

            called_prompt = mock_call.call_args[0][0]
            assert 'Data Engineer' in called_prompt
            assert 'PT Data Corp' in called_prompt