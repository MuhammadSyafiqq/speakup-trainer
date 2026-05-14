# 🎤 SpeakUp — Platform Latihan Public Speaking berbasis AI

## Struktur Folder Proyek

```
public_speaking_trainer/
├── app.py                          ← File utama (jalankan ini)
├── requirements.txt
├── .env                            ← API keys kamu
├── models/
│   ├── __init__.py
│   ├── user.py                     ← Model User
│   └── session.py                  ← Model Sesi Latihan
├── routes/
│   ├── __init__.py
│   ├── auth.py                     ← Login/Register/Logout
│   ├── practice.py                 ← Rekam & Analisis
│   └── history.py                  ← Riwayat & Chart
├── services/
│   ├── __init__.py
│   ├── whisper_service.py          ← Voice to Text (Whisper)
│   └── analysis_service.py        ← Analisis AI (Hugging Face)
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── uploads/                    ← File audio tersimpan di sini
└── templates/
    ├── base.html
    ├── index.html
    ├── dashboard.html
    ├── history.html
    ├── auth/
    │   ├── login.html
    │   └── register.html
    └── practice/
        ├── select_category.html
        ├── setup.html
        ├── record.html
        └── result.html
```

---

## ⚙️ Langkah Setup

### 1. Install Library

```bash
# Install torch dulu (sesuaikan dengan Python 3.13)
pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu

# Install requirements lainnya
pip install -r requirements.txt

# Install Whisper dari GitHub
pip install git+https://github.com/openai/whisper.git
```

### 2. Install FFmpeg (WAJIB untuk Whisper)

- **Windows**: Download dari https://www.gyan.dev/ffmpeg/builds/ lalu tambahkan ke PATH
- **Mac**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

Verifikasi: `ffmpeg -version`

### 3. Isi file `.env`

```
SECRET_KEY=buat-random-string-panjang-disini
HUGGINGFACE_API_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx
```

Daftar Hugging Face token gratis di: https://huggingface.co/settings/tokens

### 4. Jalankan Aplikasi

```bash
python app.py
```

Buka browser: http://localhost:5000

---

## 🤖 Model AI yang Digunakan

| Fungsi | Model | Keterangan |
|--------|-------|------------|
| Voice to Text | OpenAI Whisper (base) | Lokal, tidak perlu API key |
| Analisis Teks | Mistral-7B via HuggingFace | Gratis dengan HF token |

---

## 📊 Aspek yang Dinilai

1. **Kejelasan Bahasa** — Apakah mudah dipahami?
2. **Struktur Pidato** — Ada pembuka, isi, penutup?
3. **Kepercayaan Diri** — Terkesan mantap dan percaya diri?
4. **Relevansi Topik** — Sesuai dengan judul yang ditetapkan?
5. **Kosakata & Diksi** — Pilihan kata yang tepat dan bervariasi?
6. **Kelancaran Bicara** — Minim kata pengisi (em, eh, anu)?

---

## ⚠️ Catatan Penting

- Whisper model akan **otomatis download** (~150MB) saat pertama kali dijalankan
- Jika tidak ada Hugging Face token, sistem akan menggunakan **analisis fallback berbasis aturan**
- File audio disimpan di folder `static/uploads/`
- Database SQLite dibuat otomatis sebagai `speaking_trainer.db`
