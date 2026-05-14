from extensions import db
from datetime import datetime
import json

class PracticeSession(db.Model):
    __tablename__ = 'practice_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Info latihan
    category = db.Column(db.String(100), nullable=False)   # pidato, wawancara, presentasi, dll
    title = db.Column(db.String(200), nullable=False)       # judul topik

    # File & teks
    audio_path = db.Column(db.String(500))                  # path file audio
    transcript = db.Column(db.Text)                         # hasil voice to text

    # Skor per aspek (0-100)
    score_total = db.Column(db.Float, default=0)
    score_clarity = db.Column(db.Float, default=0)          # Kejelasan bahasa
    score_structure = db.Column(db.Float, default=0)        # Struktur (pembuka-isi-penutup)
    score_confidence = db.Column(db.Float, default=0)       # Kepercayaan diri
    score_relevance = db.Column(db.Float, default=0)        # Relevansi dengan judul
    score_vocabulary = db.Column(db.Float, default=0)       # Kosakata & diksi
    score_fluency = db.Column(db.Float, default=0)          # Kelancaran berbicara

    # Feedback & analisis (disimpan sebagai JSON string)
    feedback_json = db.Column(db.Text)                      # detail feedback per aspek
    suggestions = db.Column(db.Text)                        # saran perbaikan
    strengths = db.Column(db.Text)                          # kelebihan
    weaknesses = db.Column(db.Text)                         # kekurangan

    # Status proses
    status = db.Column(db.String(50), default='processing') # processing, completed, error

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    duration_seconds = db.Column(db.Integer, default=0)     # durasi rekaman

    def set_feedback(self, feedback_dict):
        self.feedback_json = json.dumps(feedback_dict, ensure_ascii=False)

    def get_feedback(self):
        if self.feedback_json:
            return json.loads(self.feedback_json)
        return {}

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
            'category': self.category,
            'title': self.title,
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
        return f'<Session {self.id} - {self.title}>'
