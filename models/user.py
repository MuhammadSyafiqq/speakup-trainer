# models/user.py
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True)
    is_verified   = db.Column(db.Boolean, default=False, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login    = db.Column(db.DateTime, nullable=True)

    # ── Password helpers ───────────────────────────────────────
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    # ── Stats helpers (dipakai di dashboard) ──────────────────
    def get_average_score(self) -> int:
        """Hitung rata-rata score_total dari semua sesi completed milik user."""
        from models.session import PracticeSession
        sessions = PracticeSession.query.filter_by(
            user_id=self.id,
            status='completed'
        ).all()
        if not sessions:
            return 0
        scores = [s.score_total for s in sessions if s.score_total is not None]
        if not scores:
            return 0
        return round(sum(scores) / len(scores))

    def get_total_sessions(self) -> int:
        """Hitung total sesi latihan user."""
        from models.session import PracticeSession
        return PracticeSession.query.filter_by(user_id=self.id).count()

    def get_best_score(self) -> int:
        """Ambil skor tertinggi user."""
        from models.session import PracticeSession
        from sqlalchemy import func
        result = db.session.query(func.max(PracticeSession.score_total)).filter_by(
            user_id=self.id,
            status='completed'
        ).scalar()
        return round(result) if result else 0

    # ── Flask-Login required ───────────────────────────────────
    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.username} verified={self.is_verified}>'