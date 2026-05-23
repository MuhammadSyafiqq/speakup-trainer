# models/email_verification.py
# ─────────────────────────────────────────────────────────────
# Model untuk menyimpan token verifikasi email.
# Setiap token berlaku 24 jam dan hanya bisa dipakai sekali.
# ─────────────────────────────────────────────────────────────

from extensions import db
from datetime import datetime, timedelta
import secrets


class EmailVerificationToken(db.Model):
    __tablename__ = 'email_verification_tokens'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token      = db.Column(db.String(86), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used       = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relasi ke User
    user = db.relationship('User', backref=db.backref(
        'verification_tokens',
        lazy='dynamic',
        cascade='all, delete-orphan'
    ))

    # ── Factory method ─────────────────────────────────────────
    @classmethod
    def generate(cls, user_id: int) -> 'EmailVerificationToken':
        """
        Buat token baru untuk user_id tertentu.
        Token lama yang belum dipakai akan di-invalidate otomatis
        (kita tidak hapus, cukup mark used=True supaya audit trail tetap ada).
        """
        # Invalidate token lama yang masih aktif
        old_tokens = cls.query.filter_by(user_id=user_id, used=False).all()
        for t in old_tokens:
            t.used = True
        db.session.flush()

        # Buat token baru
        token = cls(
            user_id    = user_id,
            token      = secrets.token_urlsafe(64),   # 86 karakter base64-url
            expires_at = datetime.utcnow() + timedelta(hours=24),
        )
        db.session.add(token)
        db.session.commit()
        return token

    # ── Property helper ────────────────────────────────────────
    @property
    def is_valid(self) -> bool:
        """Token masih bisa dipakai: belum digunakan & belum kadaluarsa."""
        return not self.used and datetime.utcnow() < self.expires_at

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    def __repr__(self):
        return f'<EmailVerificationToken user_id={self.user_id} valid={self.is_valid}>'