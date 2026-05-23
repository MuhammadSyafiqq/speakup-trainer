# utils/email.py
# ─────────────────────────────────────────────────────────────
# Helper untuk mengirim email transaksional:
#   • Verifikasi email saat register
#   • Kirim ulang verifikasi
# Semua email dalam format HTML + plain-text fallback.
# ─────────────────────────────────────────────────────────────

from flask        import url_for, current_app
from flask_mail   import Message
from extensions   import mail
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# INTERNAL HELPER
# ═══════════════════════════════════════════════════════════════

def _send(msg: Message) -> bool:
    """
    Kirim email dan tangani exception.
    Return True jika berhasil, False jika gagal.
    """
    try:
        mail.send(msg)
        return True
    except Exception as exc:
        logger.error(f'[Email] Gagal kirim ke {msg.recipients}: {exc}')
        return False


def _base_html(title: str, body_html: str) -> str:
    """Wrapper HTML email yang konsisten dan responsive."""
    return f"""
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#0f0f1a;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="min-height:100vh;background:linear-gradient(135deg,#0f0f1a 0%,#1a1a2e 50%,#16213e 100%)">
    <tr>
      <td align="center" style="padding:48px 16px">

        <!-- Card -->
        <table width="520" cellpadding="0" cellspacing="0"
               style="max-width:520px;width:100%;background:#1e1e35;border-radius:20px;
                      border:1px solid rgba(99,102,241,0.25);overflow:hidden">

          <!-- Header strip -->
          <tr>
            <td style="background:linear-gradient(90deg,#6366f1,#8b5cf6);
                       padding:6px 0;text-align:center;font-size:11px;
                       color:rgba(255,255,255,0.9);letter-spacing:3px;
                       text-transform:uppercase">
              SpeakUp — Platform Latihan Public Speaking
            </td>
          </tr>

          <!-- Logo area -->
          <tr>
            <td align="center" style="padding:40px 40px 24px">
              <div style="width:72px;height:72px;border-radius:50%;
                          background:linear-gradient(135deg,#6366f1,#8b5cf6);
                          display:inline-flex;align-items:center;justify-content:center;
                          font-size:32px;line-height:72px;text-align:center">
                🎤
              </div>
              <h1 style="margin:20px 0 8px;color:#fff;font-size:26px;
                         font-weight:700;letter-spacing:-0.5px">{title}</h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:0 40px 40px;color:#c4c4d4;font-size:15px;line-height:1.7">
              {body_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#16162a;padding:20px 40px;
                       border-top:1px solid rgba(255,255,255,0.07)">
              <p style="margin:0;color:#6b6b8a;font-size:12px;text-align:center;line-height:1.6">
                Email ini dikirim otomatis oleh sistem SpeakUp.<br>
                Jika kamu tidak merasa mendaftar, abaikan email ini.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════
# PUBLIC FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def send_verification_email(user, token) -> bool:
    """
    Kirim email verifikasi ke user yang baru daftar.

    Args:
        user  : instance User
        token : instance EmailVerificationToken
    Returns:
        True jika berhasil dikirim
    """
    verify_url = url_for('auth.verify_email', token=token.token, _external=True)

    html_body = f"""
      <p>Halo, <strong style="color:#a5b4fc">{user.username}</strong>! 👋</p>
      <p>Terima kasih sudah mendaftar di <strong>SpeakUp</strong>.
         Satu langkah lagi sebelum kamu bisa mulai latihan — verifikasi alamat emailmu.</p>

      <!-- CTA Button -->
      <table cellpadding="0" cellspacing="0" width="100%" style="margin:32px 0">
        <tr>
          <td align="center">
            <a href="{verify_url}"
               style="display:inline-block;padding:14px 36px;
                      background:linear-gradient(135deg,#6366f1,#8b5cf6);
                      color:#fff;border-radius:12px;text-decoration:none;
                      font-size:15px;font-weight:600;letter-spacing:0.3px;
                      box-shadow:0 8px 24px rgba(99,102,241,0.4)">
              ✅ &nbsp; Verifikasi Email Saya
            </a>
          </td>
        </tr>
      </table>

      <p style="color:#9090a8;font-size:13px">
        ⏰ Link berlaku selama <strong style="color:#c4c4d4">24 jam</strong> sejak email ini dikirim.
      </p>

      <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:24px 0">

      <p style="font-size:12px;color:#6b6b8a">
        Jika tombol tidak bisa diklik, salin URL berikut ke browser:<br>
        <a href="{verify_url}" style="color:#818cf8;word-break:break-all">{verify_url}</a>
      </p>
    """

    plain_body = (
        f"Halo {user.username},\n\n"
        f"Verifikasi email SpeakUp kamu:\n{verify_url}\n\n"
        f"Link berlaku 24 jam.\n\n"
        f"Jika kamu tidak mendaftar, abaikan email ini."
    )

    msg = Message(
        subject    = '✅ Verifikasi Email SpeakUp Kamu',
        recipients = [user.email],
        html       = _base_html('Verifikasi Email', html_body),
        body       = plain_body,
    )
    return _send(msg)


def send_welcome_email(user) -> bool:
    """
    Kirim email selamat datang setelah verifikasi berhasil.

    Args:
        user : instance User
    Returns:
        True jika berhasil dikirim
    """
    dashboard_url = url_for('practice.dashboard', _external=True)

    html_body = f"""
      <p>Hei, <strong style="color:#a5b4fc">{user.username}</strong>! 🎉</p>
      <p>Email kamu sudah diverifikasi. Selamat datang di <strong>SpeakUp</strong> —
         platform latihan public speaking yang akan membantumu tampil percaya diri
         di depan siapa pun.</p>

      <div style="background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);
                  border-radius:12px;padding:20px 24px;margin:24px 0">
        <p style="margin:0 0 8px;color:#a5b4fc;font-weight:600;font-size:14px">
          🚀 Apa yang bisa kamu lakukan sekarang?
        </p>
        <ul style="margin:0;padding-left:20px;color:#c4c4d4;font-size:14px;line-height:1.9">
          <li>Mulai sesi latihan berbicara pertamamu</li>
          <li>Rekam dan dengar kembali latihanmu</li>
          <li>Lihat progress dan statistik perkembanganmu</li>
        </ul>
      </div>

      <table cellpadding="0" cellspacing="0" width="100%" style="margin:8px 0 24px">
        <tr>
          <td align="center">
            <a href="{dashboard_url}"
               style="display:inline-block;padding:14px 36px;
                      background:linear-gradient(135deg,#6366f1,#8b5cf6);
                      color:#fff;border-radius:12px;text-decoration:none;
                      font-size:15px;font-weight:600;
                      box-shadow:0 8px 24px rgba(99,102,241,0.4)">
              🎤 &nbsp; Mulai Latihan Sekarang
            </a>
          </td>
        </tr>
      </table>
    """

    plain_body = (
        f"Hei {user.username},\n\n"
        f"Email kamu sudah diverifikasi. Selamat datang di SpeakUp!\n\n"
        f"Mulai latihan: {dashboard_url}"
    )

    msg = Message(
        subject    = '🎤 Selamat Datang di SpeakUp!',
        recipients = [user.email],
        html       = _base_html('Selamat Datang! 🎉', html_body),
        body       = plain_body,
    )
    return _send(msg)