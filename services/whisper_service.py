import whisper
import os
import subprocess
import tempfile

# Load model Whisper (gunakan 'base' untuk ringan, 'medium' untuk lebih akurat)
# Pilihan: tiny, base, small, medium, large
MODEL_SIZE = os.getenv('WHISPER_MODEL', 'medium')

_model = None

def get_model():
    """Load model sekali saja (singleton pattern)"""
    global _model
    if _model is None:
        print(f"🔄 Loading Whisper model '{MODEL_SIZE}'... (Pertama kali butuh download ~150MB)")
        _model = whisper.load_model(MODEL_SIZE)
        print(f"✅ Whisper model '{MODEL_SIZE}' berhasil dimuat!")
    return _model

def convert_to_wav(input_path: str) -> str:
    """Konversi audio ke WAV menggunakan ffmpeg"""
    output_path = input_path.replace('.webm', '.wav').replace('.mp4', '.wav').replace('.ogg', '.wav')

    if not output_path.endswith('.wav'):
        output_path = input_path + '.wav'

    try:
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-ar', '16000',       # Sample rate 16kHz (optimal untuk Whisper)
            '-ac', '1',           # Mono channel
            '-y',                 # Overwrite tanpa konfirmasi
            output_path
        ], check=True, capture_output=True)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"⚠️ ffmpeg error: {e.stderr.decode()}")
        return input_path  # Kembalikan path asli jika konversi gagal
    except FileNotFoundError:
        print("⚠️ ffmpeg tidak ditemukan, mencoba tanpa konversi...")
        return input_path

def transcribe_audio(audio_path: str) -> str:
    """
    Transkripsi audio ke teks menggunakan Whisper
    
    Args:
        audio_path: Path ke file audio
        
    Returns:
        String hasil transkripsi
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"File audio tidak ditemukan: {audio_path}")

    # Konversi ke WAV jika diperlukan
    wav_path = audio_path
    converted = False

    if not audio_path.endswith('.wav'):
        wav_path = convert_to_wav(audio_path)
        converted = True

    try:
        model = get_model()

        print(f"🎙️ Memulai transkripsi: {wav_path}")
        result = model.transcribe(
            wav_path,
            language='id',          # Bahasa Indonesia
            task='transcribe',
            fp16=False,             # Matikan fp16 untuk CPU
            verbose=False
        )

        transcript = result['text'].strip()
        print(f"✅ Transkripsi selesai ({len(transcript)} karakter)")

        return transcript

    finally:
        # Hapus file WAV hasil konversi (bukan file asli)
        if converted and os.path.exists(wav_path) and wav_path != audio_path:
            try:
                os.remove(wav_path)
            except:
                pass
