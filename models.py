from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class SessionQuestion(db.Model):
    __tablename__ = 'session_questions'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String, nullable=False, index=True)
    question_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)