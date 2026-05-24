import time
import requests
from extensions import db
from models.interview_session import InterviewSession

OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_MODEL   = 'google/gemini-2.5-flash-lite'


class InterviewService:
    def __init__(self, openrouter_api_key, **kwargs):
        self.openrouter_api_key = openrouter_api_key

    def get_or_create_session(self, session_id, position_label, company, total_q=5, language='id', user_id=None):
        session_obj = InterviewSession.query.filter_by(session_id=session_id).first()
        if session_obj:
            return session_obj

        prompt = f"Buat {total_q} pertanyaan wawancara untuk posisi {position_label} di perusahaan {company}. Bahasa: {language}."
        questions_list = self._call_openrouter(prompt, total_q)

        session_obj = InterviewSession(
            user_id=user_id,
            session_id=session_id,
            position_label=position_label,
            company=company,
            language=language,
            total_questions=total_q
        )
        session_obj.set_questions(questions_list)
        db.session.add(session_obj)
        db.session.commit()
        return session_obj

    def _call_openrouter(self, prompt, total_q, max_retries=3):
        headers = {
            'Authorization': f'Bearer {self.openrouter_api_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': OPENROUTER_MODEL,
            'messages': [
                {
                    'role': 'user',
                    'content': (
                        f"{prompt}\n\n"
                        f"Berikan tepat {total_q} pertanyaan, satu per baris, tanpa penomoran."
                    )
                }
            ],
        }

        for attempt in range(max_retries):
            response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)

            if response.status_code == 200:
                # Cek HTML hanya dari Content-Type — JANGAN cek response.text
                # karena saat di-mock, response.text adalah MagicMock (selalu truthy)
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    print(f"OpenRouter mengembalikan HTML pada attempt {attempt+1}, "
                          f"status 200 tapi bukan JSON. Response awal: {response.text[:200]}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    break

                try:
                    data = response.json()
                except ValueError as e:
                    print(f"Gagal parse JSON OpenRouter: {e}. Response: {response.text[:200]}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    break

                if 'error' in data:
                    err = data['error']
                    if isinstance(err, dict):
                        err = err.get('message', str(err))
                    print(f"OpenRouter API error: {err}")
                    break

                text = data['choices'][0]['message']['content']
                questions = [q.strip() for q in text.strip().splitlines() if q.strip()]
                if len(questions) < total_q:
                    questions += [f"Pertanyaan {i+1}" for i in range(len(questions), total_q)]
                return questions[:total_q]

            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"Rate limit hit. Retrying in {retry_after} seconds...")
                time.sleep(retry_after)

            else:
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    print(f"OpenRouter error {response.status_code}: response berupa HTML")
                else:
                    print(f"OpenRouter error {response.status_code}: {response.text[:300]}")

                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    response.raise_for_status()

        return [f"Pertanyaan {i+1} gagal dimuat" for i in range(total_q)]