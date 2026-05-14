from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relasi ke sesi latihan
    sessions = db.relationship('PracticeSession', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_average_score(self):
        if not self.sessions:
            return 0
        scores = [s.score_total for s in self.sessions if s.score_total]
        return round(sum(scores) / len(scores), 1) if scores else 0

    def get_total_sessions(self):
        return len(self.sessions)

    def __repr__(self):
        return f'<User {self.username}>'
