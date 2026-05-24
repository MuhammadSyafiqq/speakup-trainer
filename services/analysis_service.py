import os
import requests
import json
import re
import time

HUGGINGFACE_API_TOKEN = os.getenv('HUGGINGFACE_API_TOKEN', '')

# Model LLM dari Hugging Face (gratis)
# Pilihan alternatif yang bisa digunakan:
# - "mistralai/Mistral-7B-Instruct-v0.3"
# - "meta-llama/Meta-Llama-3-8B-Instruct"  (butuh request akses)
# - "microsoft/Phi-3-mini-4k-instruct"
HF_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

ASPECT_DESCRIPTIONS = {
    'clarity': 'Kejelasan bahasa dan pengucapan',
    'structure': 'Struktur (pembuka, isi, penutup)',
    'confidence': 'Kepercayaan diri dan kelancaran',
    'relevance': 'Relevansi isi dengan judul/topik',
    'vocabulary': 'Kosakata dan diksi yang digunakan',
    'fluency': 'Kelancaran berbicara (minim kata pengisi)',
}

def build_prompt(transcript: str, title: str, category: str) -> str:
    """Buat prompt untuk analisis public speaking"""

    category_context = {
        'pidato': 'pidato formal',
        'wawancara': 'wawancara kerja',
        'presentasi': 'presentasi bisnis/akademik',
        'debat': 'debat dan argumentasi',
        'mc': 'Master of Ceremony (MC)',
        'storytelling': 'storytelling/bercerita',
    }

    ctx = category_context.get(category, 'public speaking')

    prompt = f"""Kamu adalah pelatih public speaking profesional. Analisis transkrip {ctx} berikut secara mendalam dan berikan feedback konstruktif dalam Bahasa Indonesia.

JUDUL/TOPIK: {title}
KATEGORI: {ctx}

TRANSKRIP:
{transcript}

Berikan analisis dalam format JSON dengan struktur TEPAT seperti ini (HANYA JSON, tidak ada teks lain):
{{
    "score_clarity": <angka 0-100>,
    "score_structure": <angka 0-100>,
    "score_confidence": <angka 0-100>,
    "score_relevance": <angka 0-100>,
    "score_vocabulary": <angka 0-100>,
    "score_fluency": <angka 0-100>,
    "strengths": "<kelebihan dalam 2-3 kalimat>",
    "weaknesses": "<kekurangan dalam 2-3 kalimat>",
    "suggestions": "<saran konkret untuk perbaikan dalam 3-5 poin>",
    "feedback_detail": {{
        "clarity": "<feedback spesifik tentang kejelasan bahasa>",
        "structure": "<feedback spesifik tentang struktur pembuka-isi-penutup>",
        "confidence": "<feedback spesifik tentang kepercayaan diri>",
        "relevance": "<feedback spesifik tentang relevansi dengan topik '{title}'>",
        "vocabulary": "<feedback spesifik tentang kosakata dan diksi>",
        "fluency": "<feedback spesifik tentang kelancaran dan kata pengisi>"
    }}
}}

Kriteria penilaian:
- score_clarity: Apakah bahasa yang digunakan jelas, mudah dipahami, dan pengucapan tertata?
- score_structure: Apakah ada pembuka yang menarik, isi yang terorganisir, dan penutup yang kuat?
- score_confidence: Apakah terlihat percaya diri, tidak ragu-ragu, dan mantap?
- score_relevance: Apakah isi sesuai dan menjelaskan topik '{title}' dengan baik?
- score_vocabulary: Apakah kosakata bervariasi, tepat, dan sesuai konteks {ctx}?
- score_fluency: Apakah bicara lancar? Berapa banyak kata pengisi (em, eh, anu, ya, gitu)?

Berikan penilaian yang jujur, konstruktif, dan memotivasi."""

    return prompt

def call_huggingface_api(prompt: str) -> str:
    """Panggil Hugging Face Inference API"""
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 1000,
            "temperature": 0.3,
            "return_full_text": False,
            "do_sample": True,
        }
    }

    response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=120)

    if response.status_code == 503:
        # Model sedang loading, coba lagi
        import time
        print("⏳ Model sedang loading, tunggu 20 detik...")
        time.sleep(20)
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=120)

    if response.status_code != 200:
        raise Exception(f"HuggingFace API Error {response.status_code}: {response.text}")

    result = response.json()

    if isinstance(result, list) and len(result) > 0:
        return result[0].get('generated_text', '')
    elif isinstance(result, dict):
        return result.get('generated_text', '')

    return str(result)

def extract_json_from_text(text: str) -> dict:
    """Ekstrak JSON dari teks response model"""
    # Coba parse langsung
    try:
        return json.loads(text.strip())
    except:
        pass

    # Cari JSON di dalam teks (antara { dan })
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except:
            pass

    # Jika tidak ada JSON valid, kembalikan default
    return None

def generate_fallback_analysis(transcript: str, title: str, category: str) -> dict:
    """
    Analisis sederhana berbasis aturan sebagai fallback
    jika API gagal atau token tidak tersedia
    """
    words = transcript.split() if transcript else []
    word_count = len(words)

    # Hitung kata pengisi (filler words)
    filler_words = ['em', 'eh', 'anu', 'ya', 'gitu', 'tuh', 'kan', 'hmm', 'uh', 'um']
    filler_count = sum(1 for w in words if w.lower() in filler_words)
    filler_ratio = (filler_count / word_count * 100) if word_count > 0 else 0

    # Cek relevansi: apakah kata dari judul muncul di transkrip
    title_words = [w.lower() for w in title.split() if len(w) > 3]
    transcript_lower = transcript.lower()
    relevance_hits = sum(1 for w in title_words if w in transcript_lower)
    relevance_ratio = (relevance_hits / len(title_words) * 100) if title_words else 50

    # Hitung skor dasar
    score_fluency = max(40, 100 - (filler_ratio * 3))
    score_relevance = min(95, 40 + relevance_ratio)
    score_clarity = 65 if word_count > 30 else 45
    score_structure = 60 if word_count > 50 else 40
    score_confidence = 65
    score_vocabulary = 60

    strengths_list = []
    weaknesses_list = []
    suggestions_list = []

    if word_count > 100:
        strengths_list.append("Panjang bicara sudah cukup baik")
    else:
        weaknesses_list.append("Perlu bicara lebih panjang dan detail")
        suggestions_list.append("Tambahkan lebih banyak poin dan penjelasan")

    if filler_ratio < 5:
        strengths_list.append("Penggunaan kata pengisi sangat minimal")
    elif filler_ratio < 15:
        weaknesses_list.append(f"Terdapat kata pengisi ({filler_count} kali)")
        suggestions_list.append("Kurangi kata pengisi seperti 'em', 'eh', 'anu'")
    else:
        weaknesses_list.append(f"Terlalu banyak kata pengisi ({filler_count} kali)")
        suggestions_list.append("Latih berbicara tanpa kata pengisi dengan rekaman rutin")

    if relevance_ratio > 60:
        strengths_list.append("Isi sudah cukup relevan dengan topik")
    else:
        weaknesses_list.append("Isi kurang sesuai dengan judul yang ditetapkan")
        suggestions_list.append(f"Pastikan setiap poin membahas topik '{title}' secara langsung")

    suggestions_list.extend([
        "Perkuat pembuka dengan kalimat pembuka yang menarik perhatian",
        "Akhiri dengan kesimpulan dan ajakan bertindak yang kuat"
    ])

    return {
        'score_clarity': round(score_clarity, 1),
        'score_structure': round(score_structure, 1),
        'score_confidence': round(score_confidence, 1),
        'score_relevance': round(score_relevance, 1),
        'score_vocabulary': round(score_vocabulary, 1),
        'score_fluency': round(score_fluency, 1),
        'strengths': ' | '.join(strengths_list) if strengths_list else 'Sudah berani mencoba berlatih',
        'weaknesses': ' | '.join(weaknesses_list) if weaknesses_list else 'Perlu lebih banyak latihan',
        'suggestions': '\n'.join([f"• {s}" for s in suggestions_list]),
        'feedback_detail': {
            'clarity': f"Panjang teks: {word_count} kata. Usahakan minimal 100-200 kata untuk pidato yang efektif.",
            'structure': "Pastikan ada pembuka (salam + pengantar), isi (2-3 poin utama), dan penutup (kesimpulan + penutup).",
            'confidence': "Berlatihlah lebih sering untuk meningkatkan kepercayaan diri.",
            'relevance': f"Relevansi dengan topik '{title}': {round(relevance_ratio)}% kata kunci terdeteksi.",
            'vocabulary': "Gunakan kata-kata yang bervariasi dan hindari pengulangan kata yang sama berulang kali.",
            'fluency': f"Kata pengisi terdeteksi: {filler_count} kali ({round(filler_ratio, 1)}% dari total kata)."
        }
    }

def analyze_speech(transcript: str, title: str, category: str) -> dict:
    """
    Fungsi utama analisis public speaking
    
    1. Coba gunakan Hugging Face API (LLM)
    2. Jika gagal, gunakan analisis fallback berbasis aturan
    """
    if not transcript or transcript.strip() == '':
        return generate_fallback_analysis('', title, category)

    # Coba gunakan HuggingFace API jika token tersedia
    if HUGGINGFACE_API_TOKEN and HUGGINGFACE_API_TOKEN != 'hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
        try:
            print("🤖 Menggunakan Hugging Face LLM untuk analisis...")
            prompt = build_prompt(transcript, title, category)
            raw_response = call_huggingface_api(prompt)

            analysis = extract_json_from_text(raw_response)

            if analysis and 'score_clarity' in analysis:
                # Pastikan semua skor dalam range 0-100
                for key in ['score_clarity', 'score_structure', 'score_confidence',
                           'score_relevance', 'score_vocabulary', 'score_fluency']:
                    if key in analysis:
                        analysis[key] = max(0, min(100, float(analysis.get(key, 50))))

                print("✅ Analisis LLM berhasil!")
                return analysis
            else:
                print("⚠️ Response LLM tidak valid, menggunakan analisis fallback...")

        except Exception as e:
            print(f"⚠️ HuggingFace API error: {str(e)}, menggunakan analisis fallback...")

    # Fallback: analisis berbasis aturan
    print("📊 Menggunakan analisis berbasis aturan (fallback)...")
    return generate_fallback_analysis(transcript, title, category)
