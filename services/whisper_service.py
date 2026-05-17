import os
import subprocess
from groq import Groq

# ============================================
# KONFIGURASI
# ============================================
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
MAX_FILE_SIZE_MB = 25  # Batas maksimal Groq Whisper API adalah 25MB

client = Groq(api_key=GROQ_API_KEY)


# ============================================
# KONVERSI AUDIO KE FORMAT YANG DIDUKUNG
# ============================================
def convert_to_mp3(input_path: str) -> tuple[str, bool]:
    """
    Konversi audio ke MP3 menggunakan ffmpeg.
    MP3 dipilih karena ukurannya kecil (penting karena batas 25MB OpenAI API).

    Returns:
        (output_path, converted) — converted=True jika file baru dibuat
    """
    # Jika sudah mp3, langsung kembalikan
    if input_path.endswith('.mp3'):
        return input_path, False

    output_path = os.path.splitext(input_path)[0] + '_converted.mp3'

    try:
        subprocess.run([
            'ffmpeg',
            '-i', input_path,
            '-ar', '16000',     # Sample rate 16kHz (optimal untuk speech)
            '-ac', '1',         # Mono channel
            '-b:a', '64k',      # Bitrate rendah agar file kecil
            '-y',               # Overwrite tanpa konfirmasi
            output_path
        ], check=True, capture_output=True)

        print(f"✅ Audio berhasil dikonversi ke MP3: {output_path}")
        return output_path, True

    except subprocess.CalledProcessError as e:
        print(f"⚠️ ffmpeg error saat konversi: {e.stderr.decode()}")
        return input_path, False

    except FileNotFoundError:
        print("⚠️ ffmpeg tidak ditemukan. Mencoba kirim file asli ke API...")
        return input_path, False


# ============================================
# CEK UKURAN FILE
# ============================================
def check_file_size(file_path: str) -> float:
    """Kembalikan ukuran file dalam MB"""
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)


# ============================================
# TRANSKRIPSI MENGGUNAKAN OPENAI WHISPER API
# ============================================
def transcribe_audio(audio_path: str) -> str:
    """
    Transkripsi audio ke teks menggunakan Groq Whisper API.

    Alur:
    1. Validasi file ada & API key tersedia
    2. Konversi ke MP3 (agar ukuran kecil & kompatibel)
    3. Cek ukuran file (maks 25MB)
    4. Kirim ke Groq Whisper API (whisper-large-v3)
    5. Kembalikan hasil teks

    Args:
        audio_path: Path ke file audio (webm, mp4, ogg, wav, mp3, dll)

    Returns:
        String hasil transkripsi dalam Bahasa Indonesia
    """

    # --- Validasi API Key ---
    if not GROQ_API_KEY or GROQ_API_KEY == 'gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
        raise ValueError(
            "GROQ_API_KEY belum diisi di file .env!\n"
            "Daftar gratis di: https://console.groq.com\n"
            "Buat API key di: https://console.groq.com/keys"
        )

    # --- Validasi file ada ---
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"File audio tidak ditemukan: {audio_path}")

    # --- Konversi ke MP3 ---
    print(f"🔄 Mempersiapkan audio: {audio_path}")
    mp3_path, was_converted = convert_to_mp3(audio_path)

    try:
        # --- Cek ukuran file ---
        file_size_mb = check_file_size(mp3_path)
        print(f"📦 Ukuran file: {file_size_mb:.2f} MB")

        if file_size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(
                f"File terlalu besar ({file_size_mb:.1f}MB). "
                f"Maksimal {MAX_FILE_SIZE_MB}MB. "
                f"Coba rekaman yang lebih pendek (maks ~30 menit)."
            )

        # --- Kirim ke Groq Whisper API ---
        print(f"🌐 Mengirim ke Groq Whisper API (whisper-large-v3)...")

        with open(mp3_path, 'rb') as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-large-v3",       # Model terbaik & gratis di Groq
                file=audio_file,
                language="id",                  # Bahasa Indonesia
                response_format="text",         # Kembalikan teks langsung
                prompt=(                        # Hint untuk akurasi lebih baik
                    "Ini adalah rekaman latihan public speaking dalam Bahasa Indonesia. "
                    "Transkripsi dengan tepat termasuk tanda baca yang sesuai."
                )
            )

        # response langsung berupa string karena response_format="text"
        transcript = response.strip() if isinstance(response, str) else str(response).strip()

        if not transcript:
            raise ValueError(
                "Transkripsi kosong — pastikan:\n"
                "1. Audio jelas dan tidak terlalu pelan\n"
                "2. Rekaman minimal 3-5 detik\n"
                "3. Mikrofon berfungsi dengan baik"
            )

        print(f"✅ Transkripsi selesai! ({len(transcript)} karakter)")
        return transcript

    finally:
        # Hapus file MP3 hasil konversi (bukan file asli)
        if was_converted and os.path.exists(mp3_path) and mp3_path != audio_path:
            try:
                os.remove(mp3_path)
                print(f"🧹 File sementara dihapus: {mp3_path}")
            except Exception:
                pass


# ============================================
# TEST MANUAL (jalankan: python whisper_service.py <file_audio>)
# ============================================
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("=" * 50)
        print("🎤 SpeakUp — Groq Whisper Service Test")
        print("=" * 50)
        print("Usage  : python whisper_service.py <path_ke_audio>")
        print("Contoh : python whisper_service.py test.webm")
        print("Contoh : python whisper_service.py rekaman.mp3")
        sys.exit(1)

    test_path = sys.argv[1]
    print(f"\n🎤 Testing Groq Whisper API")
    print(f"📁 File  : {test_path}")
    print(f"🤖 Model : whisper-large-v3")
    print("=" * 50)

    try:
        result = transcribe_audio(test_path)
        print("\n📝 HASIL TRANSKRIPSI:")
        print("=" * 50)
        print(result)
        print("=" * 50)
        print(f"✅ Total karakter: {len(result)}")
        print(f"✅ Total kata    : {len(result.split())}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")