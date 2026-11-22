# 🌿 PARAS — Perempuan Aksi dan Tanggap Lintas Bencana

**PARAS** adalah platform web berbasis kecerdasan buatan (AI) yang dirancang untuk memberdayakan perempuan dan komunitas lokal (PKK / Dasawisma) dalam kesiapsiagaan, pelaporan, dan respons tanggap darurat bencana.

---

## 🌐 Live Deployment

* **Backend API (Railway):** [https://paras-app-production.up.railway.app](https://paras-app-production.up.railway.app)
* **API Documentation (Swagger UI):** [https://joyful-youthfulness-production-45055a8e.up.railway.app/docs](https://joyful-youthfulness-production-45055a8e.up.railway.app/docs)

---

## ✨ Fitur Utama

* **🌦️ Peringatan Dini Cuaca & Gempa (BMKG Intelligence):** Integrasi data real-time BMKG yang dirangkum oleh LLM menjadi informasi peringatan dini yang mudah dipahami dan relevan bagi masyarakat lokal.
* **💬 Chatbot Lapor Bencana (RAG-Powered):** Asisten pelaporan warga berbasis *Retrieval-Augmented Generation* (RAG) yang membantu warga melaporkan kejadian darurat sekaligus memberikan panduan mitigasi bencana yang akurat berdasarkan dokumen resmi.
* **🤝 Rekomendasi Aksi Komunitas:** Sistem rekomendasi berbasis AI yang menyarankan langkah aksi nyata dan terkoordinasi bagi pengurus PKK, Dasawisma, dan relawan lokal sesuai jenis ancaman bencana.
* **🛡️ Human-in-the-Loop Verification:** Alur peninjauan laporan untuk memastikan validitas informasi kebencanaan sebelum didiseminasikan ke komunitas.

---

## 🛠️ Tech Stack

### Frontend
* **Framework:** Next.js (App Router) & React
* **Styling & UI:** Tailwind CSS v4, shadcn/ui, Lucide React
* **Deployment:** Vercel

### Backend & AI
* **Framework:** Python, FastAPI, Uvicorn
* **Database & Auth:** Supabase (PostgreSQL, Google OAuth, `pgvector`)
* **AI & NLP:** Google Gemini API, Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`), PyMuPDF, scikit-learn
* **Deployment:** Railway (`paras-app-production.up.railway.app`)

---

## 🚀 Cara Menjalankan di Lokal

### Prasyarat
* Node.js (v20+)
* Python (3.10+)
* Akun & kredensial Supabase serta Google Gemini API Key

### 1. Clone Repository
```bash
git clone [https://github.com/PARAS-RK/paras-app.git](https://github.com/PARAS-RK/paras-app.git)
cd paras-app

```

### 2. Setup Frontend

```bash
cd frontend # sesuaikan jika folder frontend berada di root
npm install

```

Buat file `.env.local` dan isi variabel lingkungan yang diperlukan (gunakan URL Railway jika ingin langsung terhubung ke backend production, atau `http://localhost:8000` untuk backend lokal):

```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_API_URL=[https://paras-app-production.up.railway.app](https://paras-app-production.up.railway.app)

```

Jalankan server development frontend:

```bash
npm run dev

```

### 3. Setup Backend (Opsional untuk Development Lokal)

```bash
cd backend # sesuaikan dengan nama folder backend Anda
python -m venv venv

# Aktifkan virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

```

Buat file `.env` di folder backend:

```env
GEMINI_API_KEY=your_gemini_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

```

Jalankan server FastAPI:

```bash
uvicorn main:app --reload

```

---

## 👥 Tim Pengembang (Group 09 — Ruhana Kuddus)

Dikembangkan oleh tim **PARAS** sebagai bagian dari program **Perempuan Inovasi — GENerasi AI (AI Full Stack Web Development)**:

* **Annisa**
* **Bunga**
* **Diva**
* **Maharani**

---

## 📄 Lisensi

Proyek ini dikembangkan untuk tujuan edukasi, inovasi sosial, dan pemberdayaan komunitas tanggap bencana.
