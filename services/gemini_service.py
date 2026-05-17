import os
import base64
import json
import re
import subprocess
import google.generativeai as genai

# ============================================
# KONFIGURASI
# ============================================
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
MAX_FILE_SIZE_MB = 20  # Batas aman untuk Gemini inline audio

# Inisialisasi Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')


# ============================================
# KONVERSI AUDIO KE MP3
# ============================================
def convert_to_mp3(input_path: str) -> tuple[str, bool]:
    """
    Konversi audio ke MP3 agar ukuran kecil & kompatibel dengan Gemini.

    Returns:
        (output_path, was_converted)
    """
    if input_path.endswith('.mp3'):
        return input_path, False

    output_path = os.path.splitext(input_path)[0] + '_converted.mp3'

    try:
        subprocess.run([
            'ffmpeg',
            '-i', input_path,
            '-ar', '16000',   # 16kHz optimal untuk speech
            '-ac', '1',       # Mono
            '-b:a', '64k',    # Bitrate kecil
            '-y',
            output_path
        ], check=True, capture_output=True)

        print(f"✅ Konversi MP3 berhasil: {output_path}")
        return output_path, True

    except subprocess.CalledProcessError as e:
        print(f"⚠️ ffmpeg error: {e.stderr.decode()}")
        return input_path, False

    except FileNotFoundError:
        print("⚠️ ffmpeg tidak ditemukan, kirim file asli...")
        return input_path, False


# ============================================
# BACA FILE AUDIO SEBAGAI BASE64
# ============================================
def read_audio_as_base64(file_path: str) -> str:
    """Baca file audio dan encode ke base64 untuk dikirim ke Gemini"""
    with open(file_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def get_mime_type(file_path: str) -> str:
    """Tentukan MIME type berdasarkan ekstensi file"""
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        '.mp3':  'audio/mp3',
        '.mp4':  'audio/mp4',
        '.wav':  'audio/wav',
        '.webm': 'audio/webm',
        '.ogg':  'audio/ogg',
        '.m4a':  'audio/mp4',
        '.flac': 'audio/flac',
    }
    return mime_map.get(ext, 'audio/mp3')


# ============================================
# BANGUN PROMPT ANALISIS
# ============================================
def build_analysis_prompt(title: str, category: str) -> str:
    """
    Buat prompt lengkap untuk Gemini agar menganalisis audio
    public speaking secara menyeluruh termasuk aspek non-verbal
    seperti jeda, filler words, intonasi, dll.
    """

    category_context = {
        'pidato':       'pidato formal',
        'wawancara':    'wawancara kerja',
        'presentasi':   'presentasi bisnis/akademik',
        'debat':        'debat dan argumentasi',
        'mc':           'Master of Ceremony (MC)',
        'storytelling': 'storytelling/bercerita',
    }
    ctx = category_context.get(category, 'public speaking')

    return f"""Kamu adalah pelatih public speaking profesional berpengalaman.
Dengarkan rekaman audio {ctx} berikut dengan sangat teliti.

JUDUL / TOPIK : "{title}"
KATEGORI      : {ctx}

INSTRUKSI ANALISIS:
Analisis rekaman audio ini secara menyeluruh dari dua sisi:

1. ISI & TEKS (apa yang dikatakan):
   - Apakah isi sesuai dan relevan dengan judul "{title}"?
   - Apakah struktur pidato jelas (pembuka, isi, penutup)?
   - Apakah kosakata dan diksi tepat untuk konteks {ctx}?

2. KUALITAS AUDIO & CARA BERBICARA (bagaimana cara mengatakannya):
   - Hitung dan catat SEMUA kata pengisi: "em", "eh", "anu", "um",
     "hmm", "ah", "ya", "gitu", "kan", "tuh", "oke", "jadi" berlebihan
   - Deteksi jeda diam yang tidak disengaja (>2 detik) — catat
     di mana dan berapa kali terjadi
   - Analisis intonasi: apakah monoton atau bervariasi?
   - Analisis kecepatan bicara: terlalu cepat, tepat, atau terlalu lambat?
   - Analisis volume: konsisten atau naik-turun tidak terkontrol?
   - Deteksi tanda keragu-raguan: suara terputus, pengulangan kata,
     koreksi diri sendiri (contoh: "saya akan... maksud saya...")
   - Apakah terdengar percaya diri atau gugup?

BUAT TRANSKRIPSI LENGKAP:
Tulis ulang apa yang diucapkan persis apa adanya, termasuk:
- Semua kata pengisi (em, eh, anu, dll)
- Tandai jeda panjang dengan [JEDA X detik]
- Tandai keragu-raguan dengan [RAGU]
Contoh format: "Saya akan [RAGU] em... membahas tentang [JEDA 3 detik] pentingnya..."

BERIKAN HASIL DALAM FORMAT JSON TEPAT SEPERTI INI
(HANYA JSON, tidak ada teks lain di luar JSON):
{{
    "transcript_bersih": "<transkripsi tanpa tanda kurung, teks bersih>",
    "transcript_detail": "<transkripsi lengkap dengan [JEDA], [RAGU], dan kata pengisi>",

    "score_clarity": <angka 0-100>,
    "score_structure": <angka 0-100>,
    "score_confidence": <angka 0-100>,
    "score_relevance": <angka 0-100>,
    "score_vocabulary": <angka 0-100>,
    "score_fluency": <angka 0-100>,

    "audio_analysis": {{
        "filler_words_count": <total jumlah kata pengisi>,
        "filler_words_detail": "<daftar kata pengisi yang terdeteksi dan frekuensinya>",
        "silent_pauses_count": <jumlah jeda diam tidak disengaja>,
        "silent_pauses_detail": "<deskripsi kapan dan di mana jeda terjadi>",
        "speaking_speed": "<terlalu cepat / tepat / terlalu lambat>",
        "intonation": "<monoton / cukup bervariasi / sangat ekspresif>",
        "volume_consistency": "<tidak konsisten / cukup konsisten / sangat konsisten>",
        "confidence_level": "<sangat gugup / gugup / cukup percaya diri / percaya diri / sangat percaya diri>",
        "hesitation_count": <jumlah tanda keragu-raguan>,
        "hesitation_detail": "<deskripsi momen keragu-raguan yang terdeteksi>"
    }},

    "strengths": "<2-3 kalimat kelebihan yang spesifik berdasarkan audio>",
    "weaknesses": "<2-3 kalimat kekurangan yang spesifik berdasarkan audio>",
    "suggestions": "<5 saran konkret dan spesifik berdasarkan hasil analisis audio>",

    "feedback_detail": {{
        "clarity": "<feedback spesifik tentang kejelasan bahasa dan pengucapan>",
        "structure": "<feedback spesifik tentang struktur pembuka-isi-penutup>",
        "confidence": "<feedback spesifik tentang kepercayaan diri berdasarkan suara>",
        "relevance": "<feedback spesifik tentang relevansi isi dengan topik '{title}'>",
        "vocabulary": "<feedback spesifik tentang kosakata dan diksi>",
        "fluency": "<feedback spesifik menyebutkan jumlah filler words dan jeda>"
    }}
}}

Kriteria penilaian skor (0-100):
- score_clarity   : Kejelasan pengucapan dan bahasa yang digunakan
- score_structure : Ada tidaknya pembuka menarik, isi terorganisir, penutup kuat
- score_confidence: Berdasarkan suara, intonasi, volume, dan ketegasan bicara
- score_relevance : Seberapa relevan isi dengan judul "{title}"
- score_vocabulary: Kekayaan dan ketepatan pilihan kata
- score_fluency   : Kelancaran — dikurangi untuk setiap filler word dan jeda berlebihan

Berikan penilaian yang JUJUR, SPESIFIK berdasarkan audio, dan KONSTRUKTIF."""


# ============================================
# NORMALISASI NILAI — pastikan tipe data benar
# ============================================
def safe_int(val, default=0) -> int:
    """Konversi nilai apapun ke int dengan aman"""
    try:
        if isinstance(val, list):
            val = val[0] if val else default
        return int(float(str(val).strip()))
    except Exception:
        return default

def safe_float(val, default=50.0) -> float:
    """Konversi nilai apapun ke float 0-100 dengan aman"""
    try:
        if isinstance(val, list):
            val = val[0] if val else default
        return max(0.0, min(100.0, float(str(val).strip())))
    except Exception:
        return default

def safe_str(val, default='-') -> str:
    """Konversi nilai apapun ke string dengan aman"""
    if val is None:
        return default
    if isinstance(val, list):
        # Jika list of string, gabung jadi satu teks
        return ' | '.join(str(v) for v in val if v) or default
    if isinstance(val, dict):
        return str(val)
    result = str(val).strip()
    return result if result else default

def safe_dict(val, default=None) -> dict:
    """Pastikan nilai adalah dict"""
    if isinstance(val, dict):
        return val
    if isinstance(val, list) and val and isinstance(val[0], dict):
        return val[0]
    return default or {}


# ============================================
# EKSTRAK & NORMALISASI JSON DARI GEMINI
# ============================================
def extract_and_normalize(raw_text: str, title: str) -> dict | None:
    """
    Ekstrak JSON dari response Gemini lalu normalisasi semua field
    agar tipe datanya konsisten — mengatasi variasi output Gemini
    yang kadang string, kadang list, kadang dict berbeda struktur.
    """

    # --- Step 1: Bersihkan teks dari markdown ---
    text = raw_text
    # Hapus berbagai bentuk code block
    text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*', '', text)
    # Hapus komentar Python/JS di dalam JSON (// ...)
    text = re.sub(r'//[^\n]*', '', text)
    text = text.strip()

    # --- Step 2: Coba berbagai strategi parse JSON ---
    parsed = None

    # Strategi 1: parse langsung
    try:
        parsed = json.loads(text)
    except Exception:
        pass

    # Strategi 2: cari blok { ... } terluar
    if not parsed:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
            except Exception:
                pass

    # Strategi 3: cari blok JSON dengan regex lebih agresif
    if not parsed:
        # Kadang Gemini membungkus dengan teks sebelum {
        start = text.find('{')
        end   = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start:end+1])
            except Exception:
                pass

    # Strategi 4: jika response adalah list, ambil elemen pertama yang dict
    if not parsed:
        try:
            maybe_list = json.loads(text)
            if isinstance(maybe_list, list):
                for item in maybe_list:
                    if isinstance(item, dict):
                        parsed = item
                        break
        except Exception:
            pass

    if not parsed or not isinstance(parsed, dict):
        print(f"⚠️ Semua strategi parse JSON gagal. Raw text (200 char): {raw_text[:200]}")
        return None

    print(f"✅ JSON berhasil di-parse ({len(parsed)} keys)")

    # --- Step 3: Normalisasi semua field ke tipe yang benar ---

    # Skor — pastikan angka 0-100
    normalized = {
        'transcript_bersih' : safe_str(parsed.get('transcript_bersih'), '[Transkripsi tidak tersedia]'),
        'transcript_detail'  : safe_str(parsed.get('transcript_detail'), '[Detail tidak tersedia]'),
        'score_clarity'      : safe_float(parsed.get('score_clarity'), 50),
        'score_structure'    : safe_float(parsed.get('score_structure'), 50),
        'score_confidence'   : safe_float(parsed.get('score_confidence'), 50),
        'score_relevance'    : safe_float(parsed.get('score_relevance'), 50),
        'score_vocabulary'   : safe_float(parsed.get('score_vocabulary'), 50),
        'score_fluency'      : safe_float(parsed.get('score_fluency'), 50),
        'strengths'          : safe_str(parsed.get('strengths'), 'Tidak tersedia'),
        'weaknesses'         : safe_str(parsed.get('weaknesses'), 'Tidak tersedia'),
        'suggestions'        : safe_str(parsed.get('suggestions'), 'Tidak tersedia'),
    }

    # Normalisasi audio_analysis — bisa datang sebagai dict atau nested
    raw_audio = safe_dict(parsed.get('audio_analysis'))
    normalized['audio_analysis'] = {
        'filler_words_count'  : safe_int(raw_audio.get('filler_words_count'), 0),
        'filler_words_detail' : safe_str(raw_audio.get('filler_words_detail'), 'Tidak terdeteksi'),
        'silent_pauses_count' : safe_int(raw_audio.get('silent_pauses_count'), 0),
        'silent_pauses_detail': safe_str(raw_audio.get('silent_pauses_detail'), 'Tidak terdeteksi'),
        'speaking_speed'      : safe_str(raw_audio.get('speaking_speed'), 'Tidak terdeteksi'),
        'intonation'          : safe_str(raw_audio.get('intonation'), 'Tidak terdeteksi'),
        'volume_consistency'  : safe_str(raw_audio.get('volume_consistency'), 'Tidak terdeteksi'),
        'confidence_level'    : safe_str(raw_audio.get('confidence_level'), 'Tidak terdeteksi'),
        'hesitation_count'    : safe_int(raw_audio.get('hesitation_count'), 0),
        'hesitation_detail'   : safe_str(raw_audio.get('hesitation_detail'), 'Tidak terdeteksi'),
    }

    # Normalisasi feedback_detail
    raw_fb = safe_dict(parsed.get('feedback_detail'))
    normalized['feedback_detail'] = {
        'clarity'   : safe_str(raw_fb.get('clarity'), 'Tidak tersedia'),
        'structure' : safe_str(raw_fb.get('structure'), 'Tidak tersedia'),
        'confidence': safe_str(raw_fb.get('confidence'), 'Tidak tersedia'),
        'relevance' : safe_str(raw_fb.get('relevance'), f"Tidak tersedia untuk topik '{title}'"),
        'vocabulary': safe_str(raw_fb.get('vocabulary'), 'Tidak tersedia'),
        'fluency'   : safe_str(raw_fb.get('fluency'), 'Tidak tersedia'),
    }

    # Normalisasi suggestions: jika masih list, ubah ke string dengan bullet
    raw_sug = parsed.get('suggestions')
    if isinstance(raw_sug, list):
        normalized['suggestions'] = '\n'.join(
            f"• {s}" for s in raw_sug if s
        )
    elif isinstance(raw_sug, str):
        normalized['suggestions'] = raw_sug

    # Normalisasi strengths/weaknesses: jika list, gabung
    for key in ['strengths', 'weaknesses']:
        raw_val = parsed.get(key)
        if isinstance(raw_val, list):
            normalized[key] = ' '.join(str(v) for v in raw_val if v)

    return normalized


# ============================================
# ANALISIS FALLBACK (jika Gemini gagal)
# ============================================
def fallback_analysis(title: str, category: str) -> dict:
    """Analisis sederhana berbasis aturan jika Gemini tidak tersedia"""
    return {
        'transcript_bersih': '[Transkripsi tidak tersedia — Gemini API error]',
        'transcript_detail': '[Transkripsi tidak tersedia — Gemini API error]',
        'score_clarity': 50,
        'score_structure': 50,
        'score_confidence': 50,
        'score_relevance': 50,
        'score_vocabulary': 50,
        'score_fluency': 50,
        'audio_analysis': {
            'filler_words_count': 0,
            'filler_words_detail': 'Tidak dapat dideteksi',
            'silent_pauses_count': 0,
            'silent_pauses_detail': 'Tidak dapat dideteksi',
            'speaking_speed': 'Tidak dapat dideteksi',
            'intonation': 'Tidak dapat dideteksi',
            'volume_consistency': 'Tidak dapat dideteksi',
            'confidence_level': 'Tidak dapat dideteksi',
            'hesitation_count': 0,
            'hesitation_detail': 'Tidak dapat dideteksi',
        },
        'strengths': 'Analisis tidak tersedia karena terjadi error pada Gemini API.',
        'weaknesses': 'Silakan coba lagi atau periksa koneksi internet kamu.',
        'suggestions': '• Pastikan GEMINI_API_KEY sudah diisi dengan benar di file .env\n• Pastikan koneksi internet stabil\n• Coba rekam ulang dan kirim kembali',
        'feedback_detail': {
            'clarity': 'Tidak tersedia',
            'structure': 'Tidak tersedia',
            'confidence': 'Tidak tersedia',
            'relevance': 'Tidak tersedia',
            'vocabulary': 'Tidak tersedia',
            'fluency': 'Tidak tersedia',
        }
    }


# ============================================
# FUNGSI UTAMA — ANALISIS AUDIO DENGAN GEMINI
# ============================================
def analyze_audio_with_gemini(audio_path: str, title: str, category: str) -> dict:
    """
    Fungsi utama: kirim audio langsung ke Gemini 1.5 Flash
    untuk transkripsi + analisis public speaking sekaligus.

    Args:
        audio_path : Path ke file audio hasil rekaman
        title      : Judul / topik yang dipilih pengguna
        category   : Kategori latihan (pidato, wawancara, dll)

    Returns:
        dict berisi transcript, skor semua aspek, dan feedback lengkap
    """

    # --- Validasi API Key ---
    if not GEMINI_API_KEY or GEMINI_API_KEY == 'AIzaSy_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
        raise ValueError(
            "GEMINI_API_KEY belum diisi di file .env!\n"
            "Daftar gratis di: https://aistudio.google.com/app/apikey"
        )

    # --- Validasi file ada ---
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"File audio tidak ditemukan: {audio_path}")

    # --- Konversi ke MP3 ---
    print(f"🔄 Mempersiapkan audio untuk Gemini...")
    mp3_path, was_converted = convert_to_mp3(audio_path)

    try:
        # --- Cek ukuran file ---
        file_size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
        print(f"📦 Ukuran file: {file_size_mb:.2f} MB")

        if file_size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(
                f"File audio terlalu besar ({file_size_mb:.1f}MB). "
                f"Maksimal {MAX_FILE_SIZE_MB}MB. "
                f"Coba rekam lebih pendek (maks ~20 menit)."
            )

        # --- Encode audio ke base64 ---
        print(f"📤 Menyiapkan audio untuk dikirim ke Gemini...")
        audio_b64 = read_audio_as_base64(mp3_path)
        mime_type = get_mime_type(mp3_path)

        # --- Bangun prompt ---
        prompt = build_analysis_prompt(title, category)

        # --- Kirim ke Gemini 1.5 Flash ---
        print(f"🤖 Mengirim audio ke Gemini 1.5 Flash untuk dianalisis...")
        print(f"   (Gemini akan mendengar audio + transkripsi + analisis sekaligus)")

        response = model.generate_content([
            {
                'inline_data': {
                    'mime_type': mime_type,
                    'data': audio_b64
                }
            },
            prompt
        ])

        raw_text = response.text
        print(f"✅ Response dari Gemini diterima ({len(raw_text)} karakter)")

        # --- Ekstrak & normalisasi JSON ---
        result = extract_and_normalize(raw_text, title)

        if not result:
            print("⚠️ Gagal parse JSON dari Gemini, menggunakan fallback...")
            return fallback_analysis(title, category)

        print(f"✅ Analisis Gemini berhasil!")
        print(f"   Skor: clarity={result['score_clarity']}, "
              f"structure={result['score_structure']}, "
              f"confidence={result['score_confidence']}")
        audio_info = result.get('audio_analysis', {})
        print(f"   Filler words: {audio_info.get('filler_words_count', 0)}x")
        print(f"   Jeda diam   : {audio_info.get('silent_pauses_count', 0)}x")

        return result

    finally:
        # Hapus file MP3 sementara
        if was_converted and os.path.exists(mp3_path) and mp3_path != audio_path:
            try:
                os.remove(mp3_path)
                print(f"🧹 File sementara dihapus: {mp3_path}")
            except Exception:
                pass


# ============================================
# TEST MANUAL
# ============================================
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 4:
        print("=" * 60)
        print("🎤 SpeakUp — Gemini Audio Analysis Test")
        print("=" * 60)
        print("Usage  : python gemini_service.py <audio> <judul> <kategori>")
        print("Contoh : python gemini_service.py rekaman.webm \"Pentingnya Pendidikan\" pidato")
        print("Kategori: pidato | wawancara | presentasi | debat | mc | storytelling")
        sys.exit(1)

    audio  = sys.argv[1]
    judul  = sys.argv[2]
    kat    = sys.argv[3]

    print(f"\n🎤 Testing Gemini 1.5 Flash Audio Analysis")
    print(f"📁 Audio    : {audio}")
    print(f"📝 Judul    : {judul}")
    print(f"🎯 Kategori : {kat}")
    print("=" * 60)

    try:
        result = analyze_audio_with_gemini(audio, judul, kat)

        print("\n📝 TRANSKRIPSI BERSIH:")
        print("-" * 60)
        print(result.get('transcript_bersih', '-'))

        print("\n📝 TRANSKRIPSI DETAIL (dengan filler & jeda):")
        print("-" * 60)
        print(result.get('transcript_detail', '-'))

        print("\n📊 SKOR:")
        print("-" * 60)
        print(f"  Kejelasan      : {result.get('score_clarity')}/100")
        print(f"  Struktur       : {result.get('score_structure')}/100")
        print(f"  Kepercayaan    : {result.get('score_confidence')}/100")
        print(f"  Relevansi      : {result.get('score_relevance')}/100")
        print(f"  Kosakata       : {result.get('score_vocabulary')}/100")
        print(f"  Kelancaran     : {result.get('score_fluency')}/100")

        audio_info = result.get('audio_analysis', {})
        print("\n🎙️ ANALISIS AUDIO:")
        print("-" * 60)
        print(f"  Filler words   : {audio_info.get('filler_words_count', 0)}x — {audio_info.get('filler_words_detail', '-')}")
        print(f"  Jeda diam      : {audio_info.get('silent_pauses_count', 0)}x — {audio_info.get('silent_pauses_detail', '-')}")
        print(f"  Kecepatan      : {audio_info.get('speaking_speed', '-')}")
        print(f"  Intonasi       : {audio_info.get('intonation', '-')}")
        print(f"  Volume         : {audio_info.get('volume_consistency', '-')}")
        print(f"  Kepercayaan    : {audio_info.get('confidence_level', '-')}")
        print(f"  Keragu-raguan  : {audio_info.get('hesitation_count', 0)}x — {audio_info.get('hesitation_detail', '-')}")

        print("\n✅ KELEBIHAN:")
        print(result.get('strengths', '-'))

        print("\n⚠️ KEKURANGAN:")
        print(result.get('weaknesses', '-'))

        print("\n💡 SARAN:")
        print(result.get('suggestions', '-'))

    except Exception as e:
        print(f"\n❌ ERROR: {e}")