from extensions import db
from datetime import datetime
import json

class InterviewSession(db.Model):
    __tablename__ = 'interview_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Info sesi
    session_id = db.Column(db.String(100), nullable=False, index=True)
    position_label = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), default='')
    language = db.Column(db.String(10), default='id')
    total_questions = db.Column(db.Integer, default=5)

    # Pertanyaan dan jawaban
    questions_json = db.Column(db.Text)      # simpan semua pertanyaan sebagai JSON
    audio_path = db.Column(db.String(500))   # path file audio jawaban user
    transcript = db.Column(db.Text)          # hasil voice-to-text

    # Skor per aspek
    score_total = db.Column(db.Float, default=0)
    score_clarity = db.Column(db.Float, default=0)
    score_structure = db.Column(db.Float, default=0)
    score_confidence = db.Column(db.Float, default=0)
    score_relevance = db.Column(db.Float, default=0)
    score_vocabulary = db.Column(db.Float, default=0)
    score_fluency = db.Column(db.Float, default=0)

    # Feedback & analisis
    feedback_json = db.Column(db.Text)
    suggestions = db.Column(db.Text)
    strengths = db.Column(db.Text)
    weaknesses = db.Column(db.Text)

    # Status proses
    status = db.Column(db.String(50), default='processing')  # processing, completed, error

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    duration_seconds = db.Column(db.Integer, default=0)       # durasi rekaman

    # --- Methods ---
    def set_feedback(self, feedback_dict):
        self.feedback_json = json.dumps(feedback_dict, ensure_ascii=False)

    def get_feedback(self):
        if self.feedback_json:
            return json.loads(self.feedback_json)
        return {}

    def set_questions(self, questions_list):
        self.questions_json = json.dumps(questions_list, ensure_ascii=False)

    def get_questions(self):
        if self.questions_json:
            return json.loads(self.questions_json)
        return []

    def calculate_total_score(self):
        scores = [
            self.score_clarity,
            self.score_structure,
            self.score_confidence,
            self.score_relevance,
            self.score_vocabulary,
            self.score_fluency
        ]
        valid = [s for s in scores if s and s > 0]
        self.score_total = round(sum(valid) / len(valid), 1) if valid else 0
        return self.score_total

    def get_grade(self):
        score = self.score_total or 0
        if score >= 90: return ('A', 'Luar Biasa! 🏆')
        elif score >= 80: return ('B', 'Sangat Baik! 🌟')
        elif score >= 70: return ('C', 'Baik 👍')
        elif score >= 60: return ('D', 'Cukup, terus berlatih! 💪')
        else: return ('E', 'Perlu banyak latihan 📚')

    def to_dict(self):
        grade, grade_text = self.get_grade()
        return {
            'id': self.id,
            'session_id': self.session_id,
            'position_label': self.position_label,
            'company': self.company,
            'language': self.language,
            'total_questions': self.total_questions,
            'questions': self.get_questions(),
            'audio_path': self.audio_path,
            'transcript': self.transcript,
            'score_total': self.score_total,
            'score_clarity': self.score_clarity,
            'score_structure': self.score_structure,
            'score_confidence': self.score_confidence,
            'score_relevance': self.score_relevance,
            'score_vocabulary': self.score_vocabulary,
            'score_fluency': self.score_fluency,
            'feedback': self.get_feedback(),
            'suggestions': self.suggestions,
            'strengths': self.strengths,
            'weaknesses': self.weaknesses,
            'grade': grade,
            'grade_text': grade_text,
            'status': self.status,
            'created_at': self.created_at.strftime('%d %B %Y, %H:%M'),
            'duration_seconds': self.duration_seconds
        }

    def __repr__(self):
        return f'<InterviewSession {self.id} - {self.position_label}>'