# tests/test_analysis_service.py
# ─────────────────────────────────────────────────────────────────────────────
# Unit test untuk services/analysis_service.py
#   - build_prompt()
#   - extract_json_from_text()
#   - generate_fallback_analysis()
#   - call_huggingface_api()
#   - analyze_speech()
# ─────────────────────────────────────────────────────────────────────────────

import pytest
import json
import time
from unittest.mock import patch, MagicMock
from services.analysis_service import (
    build_prompt,
    extract_json_from_text,
    generate_fallback_analysis,
    call_huggingface_api,
    analyze_speech,
)


# =============================================================================
# build_prompt()
# =============================================================================

class TestBuildPrompt:

    def test_prompt_contains_title(self):
        """Prompt harus menyertakan judul yang diberikan."""
        prompt = build_prompt('Ini transkrip', 'Pidato Kemerdekaan', 'pidato')
        assert 'Pidato Kemerdekaan' in prompt

    def test_prompt_contains_category_context(self):
        """Prompt harus menyertakan konteks kategori yang benar."""
        prompt = build_prompt('transkrip', 'Test', 'wawancara')
        assert 'wawancara kerja' in prompt.lower()

    @pytest.mark.parametrize("category,expected_context", [
        ('pidato',       'pidato formal'),
        ('wawancara',    'wawancara kerja'),
        ('presentasi',   'presentasi bisnis'),
        ('debat',        'debat dan argumentasi'),
        ('mc',           'master of ceremony'),
        ('storytelling', 'storytelling'),
    ])
    def test_prompt_category_context_mapping(self, category, expected_context):
        """Setiap kategori harus dipetakan ke konteks yang benar."""
        prompt = build_prompt('transkrip', 'Test', category).lower()
        assert expected_context in prompt

    def test_prompt_contains_transcript(self):
        """Prompt harus menyertakan transkrip yang diberikan."""
        transcript = 'Assalamualaikum hadirin yang terhormat'
        prompt = build_prompt(transcript, 'Pidato', 'pidato')
        assert transcript in prompt

    def test_prompt_requests_json_output(self):
        """Prompt harus meminta output dalam format JSON."""
        prompt = build_prompt('transkrip', 'Test', 'pidato')
        assert 'JSON' in prompt

    def test_prompt_unknown_category_uses_default(self):
        """Kategori yang tidak dikenal harus menggunakan konteks default."""
        prompt = build_prompt('transkrip', 'Test', 'kategori_baru')
        assert 'public speaking' in prompt.lower()


# =============================================================================
# extract_json_from_text()
# =============================================================================

class TestExtractJsonFromText:

    def test_extract_clean_json(self):
        """JSON yang bersih harus berhasil di-parse."""
        text = '{"score_clarity": 80, "score_structure": 75}'
        result = extract_json_from_text(text)
        assert result is not None
        assert result['score_clarity'] == 80

    def test_extract_json_embedded_in_text(self):
        """JSON yang tertanam dalam teks harus berhasil diekstrak."""
        text = 'Berikut hasilnya:\n{"score_clarity": 90}\nTerima kasih.'
        result = extract_json_from_text(text)
        assert result is not None
        assert result['score_clarity'] == 90

    def test_returns_none_for_invalid_text(self):
        """Teks tanpa JSON valid harus mengembalikan None."""
        result = extract_json_from_text('Ini bukan JSON sama sekali!')
        assert result is None

    def test_returns_none_for_empty_string(self):
        """String kosong harus mengembalikan None."""
        result = extract_json_from_text('')
        assert result is None

    def test_extract_json_with_nested_objects(self):
        """JSON dengan nested object harus berhasil di-parse."""
        text = json.dumps({
            'score_clarity': 75,
            'feedback_detail': {'clarity': 'Bagus', 'structure': 'Cukup'}
        })
        result = extract_json_from_text(text)
        assert result is not None
        assert result['feedback_detail']['clarity'] == 'Bagus'


# =============================================================================
# generate_fallback_analysis()
# =============================================================================

class TestGenerateFallbackAnalysis:

    REQUIRED_KEYS = [
        'score_clarity', 'score_structure', 'score_confidence',
        'score_relevance', 'score_vocabulary', 'score_fluency',
        'strengths', 'weaknesses', 'suggestions', 'feedback_detail'
    ]

    def test_returns_all_required_keys(self):
        """Fallback harus mengembalikan semua kunci yang dibutuhkan."""
        result = generate_fallback_analysis('Transkrip test', 'Test', 'pidato')
        for key in self.REQUIRED_KEYS:
            assert key in result, f"Key '{key}' tidak ada di fallback"

    def test_scores_are_in_valid_range(self):
        """Semua skor harus berada dalam rentang 0-100."""
        result = generate_fallback_analysis('Transkrip panjang ' * 20, 'Test', 'pidato')
        score_keys = [k for k in self.REQUIRED_KEYS if k.startswith('score_')]
        for key in score_keys:
            assert 0 <= result[key] <= 100, f"{key} = {result[key]} di luar rentang 0-100"

    def test_empty_transcript_handled(self):
        """Transkrip kosong tidak boleh menyebabkan error."""
        result = generate_fallback_analysis('', 'Test', 'pidato')
        assert result is not None
        for key in self.REQUIRED_KEYS:
            assert key in result

    def test_filler_words_reduce_fluency_score(self):
        """Banyak kata pengisi harus menurunkan score_fluency."""
        clean = generate_fallback_analysis('kata ' * 50, 'Test', 'pidato')
        filler_heavy = generate_fallback_analysis('eh em anu ' * 30, 'Test', 'pidato')
        # Skor fluency lebih rendah saat banyak kata pengisi
        assert filler_heavy['score_fluency'] <= clean['score_fluency']

    def test_title_keywords_affect_relevance(self):
        """Kata kunci dari judul yang muncul di transkrip harus meningkatkan relevansi."""
        title = 'Teknologi Kecerdasan Buatan'
        relevant = generate_fallback_analysis(
            'teknologi kecerdasan buatan sangat penting', title, 'presentasi'
        )
        irrelevant = generate_fallback_analysis(
            'hari ini cuaca cerah dan menyenangkan', title, 'presentasi'
        )
        assert relevant['score_relevance'] >= irrelevant['score_relevance']

    def test_all_categories_work(self):
        """Semua kategori harus berhasil diproses oleh fallback."""
        categories = ['pidato', 'wawancara', 'presentasi', 'debat', 'mc', 'storytelling']
        for cat in categories:
            result = generate_fallback_analysis('Transkrip test', 'Test', cat)
            assert result is not None, f"Kategori '{cat}' gagal diproses"


# =============================================================================
# call_huggingface_api()
# =============================================================================

class TestCallHuggingfaceApi:

    @patch('services.analysis_service.requests.post')
    def test_success_returns_generated_text(self, mock_post):
        """Response 200 harus mengembalikan teks dari generated_text."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = [
            {'generated_text': '{"score_clarity": 80}'}
        ]
        result = call_huggingface_api('Test prompt')
        assert '{"score_clarity": 80}' in result

    @patch('services.analysis_service.time.sleep')
    @patch('services.analysis_service.requests.post')
    def test_503_waits_and_retries(self, mock_post, mock_sleep):
        """Status 503 (model loading) harus menunggu 20 detik dan retry."""
        first_response = MagicMock()
        first_response.status_code = 503

        second_response = MagicMock()
        second_response.status_code = 200
        second_response.json.return_value = [{'generated_text': 'retry berhasil'}]

        mock_post.side_effect = [first_response, second_response]

        result = call_huggingface_api('Test prompt')

        mock_sleep.assert_called_with(20)
        assert 'retry berhasil' in result

    @patch('services.analysis_service.requests.post')
    def test_error_status_raises_exception(self, mock_post):
        """Status error (bukan 200/503) harus raise Exception."""
        mock_post.return_value.status_code = 401
        mock_post.return_value.text = 'Unauthorized'

        with pytest.raises(Exception, match='401'):
            call_huggingface_api('Test prompt')

    @patch('services.analysis_service.requests.post')
    def test_dict_response_handled(self, mock_post):
        """Response berupa dict (bukan list) harus tetap berhasil diproses."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'generated_text': 'hasil dict'}
        result = call_huggingface_api('Test prompt')
        assert 'hasil dict' in result


# =============================================================================
# analyze_speech()
# =============================================================================

class TestAnalyzeSpeech:

    REQUIRED_KEYS = [
        'score_clarity', 'score_structure', 'score_confidence',
        'score_relevance', 'score_vocabulary', 'score_fluency',
        'strengths', 'weaknesses', 'suggestions',
    ]

    def test_empty_transcript_uses_fallback(self):
        """Transkrip kosong harus langsung menggunakan fallback analysis."""
        result = analyze_speech('', 'Test', 'pidato')
        assert result is not None
        for key in self.REQUIRED_KEYS:
            assert key in result

    def test_whitespace_only_transcript_uses_fallback(self):
        """Transkrip yang hanya spasi harus menggunakan fallback."""
        result = analyze_speech('   \n\t  ', 'Test', 'pidato')
        assert result is not None

    @patch('services.analysis_service.HUGGINGFACE_API_TOKEN', '')
    def test_no_api_token_uses_fallback(self):
        """Tanpa API token, harus langsung gunakan fallback."""
        result = analyze_speech('Ini transkrip test lengkap', 'Test Pidato', 'pidato')
        assert result is not None
        for key in self.REQUIRED_KEYS:
            assert key in result

    @patch('services.analysis_service.HUGGINGFACE_API_TOKEN', 'hf_validtoken')
    @patch('services.analysis_service.call_huggingface_api')
    @patch('services.analysis_service.extract_json_from_text')
    def test_successful_llm_analysis_returns_scores(self, mock_extract, mock_hf):
        """Jika LLM berhasil, skor harus diambil dari response LLM."""
        mock_hf.return_value = '{"score_clarity": 85}'
        mock_extract.return_value = {
            'score_clarity': 85, 'score_structure': 80,
            'score_confidence': 90, 'score_relevance': 75,
            'score_vocabulary': 70, 'score_fluency': 85,
            'strengths': 'Baik', 'weaknesses': 'Perlu perbaikan',
            'suggestions': 'Latih lebih sering',
            'feedback_detail': {}
        }
        result = analyze_speech('Transkrip test', 'Test', 'pidato')
        assert result['score_clarity'] == 85

    @patch('services.analysis_service.HUGGINGFACE_API_TOKEN', 'hf_validtoken')
    @patch('services.analysis_service.call_huggingface_api')
    @patch('services.analysis_service.extract_json_from_text')
    def test_llm_invalid_json_falls_back(self, mock_extract, mock_hf):
        """Jika LLM mengembalikan JSON tidak valid, harus fallback ke rule-based."""
        mock_hf.return_value = 'BUKAN JSON'
        mock_extract.return_value = None  # gagal ekstrak

        result = analyze_speech('Transkrip test', 'Test', 'pidato')
        assert result is not None
        for key in self.REQUIRED_KEYS:
            assert key in result

    @patch('services.analysis_service.HUGGINGFACE_API_TOKEN', 'hf_validtoken')
    @patch('services.analysis_service.call_huggingface_api')
    def test_llm_api_error_falls_back(self, mock_hf):
        """Jika HuggingFace API error, harus fallback ke rule-based."""
        mock_hf.side_effect = Exception("API timeout")

        result = analyze_speech('Transkrip test panjang', 'Test', 'pidato')
        assert result is not None
        for key in self.REQUIRED_KEYS:
            assert key in result

    @patch('services.analysis_service.HUGGINGFACE_API_TOKEN', 'hf_validtoken')
    @patch('services.analysis_service.call_huggingface_api')
    @patch('services.analysis_service.extract_json_from_text')
    def test_scores_clamped_to_0_100(self, mock_extract, mock_hf):
        """Skor dari LLM harus di-clamp ke rentang 0-100."""
        mock_hf.return_value = '{}'
        mock_extract.return_value = {
            'score_clarity': 150,   # di atas 100
            'score_structure': -10, # di bawah 0
            'score_confidence': 90,
            'score_relevance': 75,
            'score_vocabulary': 70,
            'score_fluency': 85,
            'strengths': 'OK', 'weaknesses': 'OK', 'suggestions': 'OK',
            'feedback_detail': {}
        }

        result = analyze_speech('Transkrip', 'Test', 'pidato')
        assert result['score_clarity'] <= 100
        assert result['score_structure'] >= 0