
import time
import requests
from extensions import db
from models.interview_session import InterviewSession


class InterviewService:
    def __init__(self, gemini_api_key, gemini_api_url):
        self.gemini_api_key = gemini_api_key
        self.gemini_api_url = gemini_api_url

    def get_or_create_session(self, session_id, position_label, company, total_q=5, language='id', user_id=None):
        session_obj = InterviewSession.query.filter_by(session_id=session_id).first()
        if session_obj:
            return session_obj

        # generate pertanyaan
        prompt = f"Buat {total_q} pertanyaan wawancara untuk posisi {position_label} di perusahaan {company}. Bahasa: {language}."
        questions_list = self._call_gemini_api(prompt, total_q)

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

    def _call_gemini_api(self, prompt, total_q, max_retries=3):
        headers = {
            "Authorization": f"Bearer {self.gemini_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt,
            "temperature": 0.7,
            "candidate_count": total_q
        }

        for attempt in range(max_retries):
            response = requests.post(self.gemini_api_url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                return [c['content'][0]['text'] for c in data.get('candidates', [])]
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"Rate limit hit. Retrying in {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                response.raise_for_status()
        return [f"Pertanyaan {i+1} gagal dimuat" for i in range(total_q)]
    
