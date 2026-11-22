import os
import re

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

try:
    from recommendation.community_recommender import (
        format_recommendations,
        get_dynamic_recommendations,
    )
    from recommendation.generation import generate_answer, generate_community_draft
    from recommendation.knowledge_base import get_community_draft_fallback
    from recommendation.retrieval import retrieve_context
except ModuleNotFoundError:
    from src.recommendation.community_recommender import (
        format_recommendations,
        get_dynamic_recommendations,
    )
    from src.recommendation.generation import generate_answer, generate_community_draft
    from src.recommendation.knowledge_base import get_community_draft_fallback
    from src.recommendation.retrieval import retrieve_context


def get_allowed_origins() -> list[str]:
    raw_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]


app = FastAPI(
    title="PARAS Full API Documentation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., examples=["Apa yang harus dilakukan saat terjadi banjir?"])


class CommunityRecommendationRequest(BaseModel):
    report: str = Field(
        ...,
        examples=[
            "Kategori: Banjir\nLokasi: Kel. Pindrikan Kidul\nDetail: Genangan air setinggi 35 cm."
        ],
    )
    region_id: str | None = Field(default=None, examples=["3374080005"])
    top_k: int = Field(default=2, ge=1, le=5)


@app.get("/", tags=["FastAPI - AI Engine"])
def root():
    return {"service": "PARAS RAG & Aksi Komunitas API", "status": "running"}


@app.get("/health", tags=["FastAPI - AI Engine"])
def health():
    return {"status": "ok"}


@app.post("/chat", tags=["FastAPI - AI Engine"])
def chat(payload: ChatRequest):
    question = payload.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Pertanyaan tidak boleh kosong")
    try:
        contexts = retrieve_context(question)
        answer = generate_answer(question, contexts)
        sources = [
            {
                "title": item.get("title", item.get("source", "dokumen")),
                "page": item.get("page") if isinstance(item.get("page"), int) else None,
            }
            for item in contexts
        ]
        return {"answer": answer, "sources": sources}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal memproses chat: {exc}")


@app.post("/recommendations/community", tags=["FastAPI - AI Engine"])
def recommendations_community(payload: CommunityRecommendationRequest):
    report = payload.report.strip()
    if not report:
        raise HTTPException(status_code=400, detail="Laporan tidak boleh kosong")
    try:
        try:
            results = get_dynamic_recommendations(
                user_report=report,
                top_k=max(1, min(payload.top_k, 5)),
            )
        except Exception:
            results = []

        contexts = []
        for item in results:
            parts = []
            if item.get("problem"):
                parts.append(f"Masalah: {item['problem']}")
            langkah = item.get("langkah") or []
            if isinstance(langkah, list) and langkah:
                parts.append("Langkah: " + "; ".join(str(s) for s in langkah))
            elif langkah:
                parts.append(f"Langkah: {langkah}")
            if item.get("responsible"):
                parts.append(f"Penanggung jawab: {item['responsible']}")
            if item.get("indicator"):
                parts.append(f"Indikator: {item['indicator']}")

            contexts.append({
                "title": item.get("kegiatan", "Referensi komunitas"),
                "source": "knowledge_base_paras",
                "text": "\n".join(parts),
            })

        draft = generate_community_draft(report, contexts)

        return {
            "results": results,
            "text": format_recommendations(results) if results else "",
            "draft": draft,
        }
    except Exception:
        match = re.search(r"Kategori:\s*([^\n]+)", report or "", re.IGNORECASE)
        fallback = get_community_draft_fallback(match.group(1).strip() if match else "Lainnya")
        return {
            "results": [],
            "text": "",
            "draft": fallback,
        }


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="PARAS Full-Stack API Documentation",
        version="1.0.0",
        description=(
            "Dokumentasi terpadu **PARAS (Perempuan Aksi dan Tanggap Lintas Bencana)** "
            "yang menghubungkan **FastAPI AI Engine** (Railway) dengan **Next.js App Routes**.\n\n"
            "- **FastAPI AI Engine:** Direct endpoint Python (`/chat`, `/recommendations/community`)\n"
            "- **Next.js Public, User & Admin Endpoints:** Route aplikasi (`/api/*`, `/auth/*`)"
        ),
        routes=app.routes,
    )

    openapi_schema["servers"] = [
        {
            "url": "https://paras-app-production.up.railway.app",
            "description": "FastAPI AI Backend (Railway Production)",
        },
        {
            "url": "http://localhost:3000",
            "description": "Next.js Full-Stack App (Local)",
        },
    ]

    openapi_schema["tags"] = [
        {"name": "FastAPI - AI Engine", "description": "Endpoint langsung pada layanan FastAPI Python (Railway)"},
        {"name": "Public Endpoints", "description": "Endpoint publik Next.js tanpa autentikasi"},
        {"name": "User Endpoints", "description": "Endpoint pengguna terautentikasi (Auth Required: Ya)"},
        {"name": "BMKG Endpoints", "description": "Data cuaca, peringatan dini, dan gempa BMKG + AI summary"},
        {"name": "Auth & Account", "description": "Konfirmasi reset password, signout, dan hapus akun"},
        {"name": "Admin Endpoints", "description": "Endpoint manajemen wilayah & anggota (Auth Required: Admin)"},
    ]

    openapi_schema.setdefault("components", {})["securitySchemes"] = {
        "UserAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "sb-access-token",
            "description": "Sesi login Supabase Auth (User)",
        },
        "AdminAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "sb-access-token",
            "description": "Sesi login Supabase Auth (Admin / Ketua PKK)",
        },
    }

    unauth_401 = {
        "description": "Unauthorized / Belum login",
        "content": {
            "application/json": {
                "examples": {
                    "belum_login": {"value": {"error": "Belum login"}},
                    "unauthorized": {"value": {"error": "Unauthorized"}},
                }
            }
        },
    }

    nextjs_paths = {
        "/api/chat": {
            "post": {
                "tags": ["Public Endpoints"],
                "summary": "Menjawab pertanyaan FAQ PARAS dengan RAG",
                "description": "Auth Required: **Tidak**. Meneruskan pertanyaan FAQ ke layanan RAG.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["message"],
                                "properties": {
                                    "message": {"type": "string", "example": "Apa itu PARAS?"}
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Jawaban RAG berhasil dikembalikan"}},
            }
        },
        "/api/home": {
            "get": {
                "tags": ["User Endpoints"],
                "summary": "Mengambil data ringkasan beranda pengguna",
                "description": "Auth Required: **Ya**. Mengambil nama, wilayah, poin, aksi aktif, dan statistik laporan.",
                "security": [{"UserAuth": []}],
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "example": {
                                    "displayName": "Dewamah",
                                    "areaFull": "RT 002/RW 003, Kel. Pindrikan Kidul, Kota Semarang",
                                    "region": {
                                        "city": "Kota Semarang",
                                        "district": "Semarang Tengah",
                                        "province": "Jawa Tengah",
                                        "subdistrict": "Pindrikan Kidul",
                                    },
                                    "stats": {
                                        "points": 0,
                                        "completedCount": 0,
                                        "activeAction": None,
                                        "reportsTotal": 2,
                                        "reportsInProgress": 2,
                                    },
                                }
                            }
                        },
                    },
                    "401": unauth_401,
                },
            }
        },
        "/api/lapor": {
            "get": {
                "tags": ["User Endpoints"],
                "summary": "Mengambil data untuk form laporan",
                "description": "Auth Required: **Ya**. Mengambil profil pengguna (nama, status akun, wilayah) dan daftar kategori aktif.",
                "security": [{"UserAuth": []}],
                "responses": {
                    "200": {"description": "Data form laporan"},
                    "401": {
                        "description": "Unauthorized",
                        "content": {"application/json": {"example": {"error": "Unauthorized"}}},
                    },
                },
            },
            "post": {
                "tags": ["User Endpoints"],
                "summary": "Membuat laporan baru",
                "description": "Auth Required: **Ya**. Body multipart/form-data dengan field category, location, details, isAnonymous, dan file (satu gambar JPG/PNG/WebP). Sukses mengembalikan 201 dengan reportId dan ticketCode.",
                "security": [{"UserAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["category", "location", "details", "file"],
                                "properties": {
                                    "category": {"type": "string", "example": "Banjir"},
                                    "location": {"type": "string", "example": "RT 002/RW 003 Pindrikan Kidul"},
                                    "details": {"type": "string", "example": "Saluran air meluap ke jalan"},
                                    "isAnonymous": {"type": "boolean", "example": False},
                                    "file": {"type": "string", "format": "binary"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Laporan berhasil dibuat",
                        "content": {
                            "application/json": {
                                "example": {"reportId": "uuid-report", "ticketCode": "PRS-20261122-01"}
                            }
                        },
                    },
                    "401": unauth_401,
                },
            },
        },
        "/api/pantau": {
            "get": {
                "tags": ["User Endpoints"],
                "summary": "Daftar laporan terkirim, dan laporan lain",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Daftar laporan"}, "401": unauth_401},
            }
        },
        "/api/pantau/{id}": {
            "get": {
                "tags": ["User Endpoints"],
                "summary": "Detail laporan",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "Detail laporan"}, "401": unauth_401},
            }
        },
        "/api/pantau/{id}/vote": {
            "post": {
                "tags": ["User Endpoints"],
                "summary": "Mendukung laporan orang lain",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "Dukungan ditambahkan"}, "401": unauth_401},
            },
            "delete": {
                "tags": ["User Endpoints"],
                "summary": "Membatalkan dukungan",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "Dukungan dibatalkan"}, "401": unauth_401},
            },
        },
        "/api/notifications": {
            "get": {
                "tags": ["User Endpoints"],
                "summary": "Mengambil notifikasi terbaru",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Daftar notifikasi"}, "401": unauth_401},
            },
            "patch": {
                "tags": ["User Endpoints"],
                "summary": "Menandai dibaca",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Notifikasi ditandai dibaca"}, "401": unauth_401},
            },
            "delete": {
                "tags": ["User Endpoints"],
                "summary": "Menghapus notifikasi",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Notifikasi dihapus"}, "401": unauth_401},
            },
        },
        "/api/recommendations/community": {
            "post": {
                "tags": ["User Endpoints"],
                "summary": "Menerima laporan warga, meminta rekomendasi kegiatan dan panduan SOP ke layanan AI",
                "description": "Auth Required: **Ya**. Meneruskan laporan warga ke FastAPI `/recommendations/community`.",
                "security": [{"UserAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "report": {"type": "string"},
                                    "region_id": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Rekomendasi kegiatan & SOP"}, "401": unauth_401},
            }
        },
        "/auth/confirm": {
            "get": {
                "tags": ["Auth & Account"],
                "summary": "Memverifikasi tautan reset kata sandi dari email",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Tautan terverifikasi"}},
            }
        },
        "/auth/signout": {
            "post": {
                "tags": ["Auth & Account"],
                "summary": "Mengeluarkan pengguna dari sesi saat ini lalu mengarahkan ke halaman tujuan",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"302": {"description": "Redirect ke halaman tujuan"}},
            }
        },
        "/api/account": {
            "delete": {
                "tags": ["Auth & Account"],
                "summary": "Menghapus akun pengguna yang sedang login dari Supabase Auth",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Akun dihapus"}, "401": unauth_401},
            }
        },
        "/api/bmkg": {
            "get": {
                "tags": ["BMKG Endpoints"],
                "summary": "Semua data BMKG (cuaca, peringatan, gempa dirasakan, gempa besar) dalam sekali panggil",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "example": {
                                    "data": {
                                        "cuaca": {
                                            "data_type": "cuaca",
                                            "status": "normal",
                                            "payload": {
                                                "slots": [
                                                    {
                                                        "ikon": "https://api-apps.bmkg.go.id/storage/icon/cuaca/hujan ringan-pm.svg",
                                                        "suhu": 27,
                                                        "angin": 9.1,
                                                        "waktu": "2026-11-22 19:00:00",
                                                        "kondisi": "Hujan Ringan",
                                                        "arah_angin": "E",
                                                        "kelembapan": 89,
                                                    }
                                                ]
                                            },
                                            "summary_text": "Cuaca 24 jam ke depan umumnya cerah hingga cerah berawan dengan suhu berkisar 26-32°C, namun berpotensi hujan ringan di malam dan sore hari. Jangan lupa siapkan payung atau jas hujan jika hendak beraktivitas di luar rumah ya 🌧️",
                                            "summary_source": "ai",
                                            "source_issued_at": "2026-11-22T00:00:00+00:00",
                                            "fetched_at": "2026-11-22T11:07:24.917149+00:00",
                                            "expired_at": "2026-11-22T16:07:24.917149+00:00",
                                        },
                                        "peringatan": {
                                            "data_type": "peringatan",
                                            "status": "aman",
                                            "payload": {"items": []},
                                            "summary_text": "Saat ini tidak ada peringatan dini cuaca di wilayah Anda, sehingga kondisinya aman. Anda bisa beraktivitas seperti biasa dengan tenang dan nyaman ☀️",
                                            "summary_source": "ai",
                                        },
                                        "gempa_rasa": {
                                            "data_type": "gempa_rasa",
                                            "status": "aman",
                                            "payload": {"items": []},
                                            "summary_text": "Dalam 24 jam terakhir, tidak ada gempa yang dirasakan di wilayah Anda. Kondisi saat ini aman, jadi Anda bisa beraktivitas dengan tenang dan nyaman 😊",
                                            "summary_source": "ai",
                                        },
                                        "gempa_besar": {
                                            "data_type": "gempa_besar",
                                            "status": "normal",
                                            "payload": {
                                                "items": [
                                                    {
                                                        "waktu": "21 Nov 2026 16:42:11 WIB",
                                                        "sumber": "43 km BaratLaut MALUKUBRTDAYA",
                                                        "potensi": "Tidak berpotensi tsunami",
                                                        "dirasakan": None,
                                                        "kedalaman": "125 km",
                                                        "magnitudo": "7.2",
                                                    }
                                                ],
                                                "jumlah": 9,
                                                "terasa_di_wilayah": False,
                                            },
                                            "summary_text": "Dalam 7 hari terakhir ada 9 gempa besar di Indonesia dengan yang terkuat berkekuatan 7.2 di Maluku Barat Daya, tetapi tidak ada yang terasa di Kota Semarang. Meskipun begitu, tetaplah berhati-hati dan selalu pantau informasi resmi dari BMKG ya 🙏",
                                            "summary_source": "ai",
                                        },
                                    }
                                }
                            }
                        },
                    },
                    "401": {
                        "description": "Belum login",
                        "content": {"application/json": {"example": {"error": "Belum login"}}},
                    },
                },
            }
        },
        "/api/bmkg/cuaca": {
            "get": {
                "tags": ["BMKG Endpoints"],
                "summary": "Prakiraan cuaca dan ringkasan untuk kelurahan pengguna",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Data prakiraan cuaca"}, "401": unauth_401},
            }
        },
        "/api/bmkg/peringatan": {
            "get": {
                "tags": ["BMKG Endpoints"],
                "summary": "Peringatan dini cuaca dan ringkasan untuk wilayah pengguna",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Data peringatan dini cuaca"}, "401": unauth_401},
            }
        },
        "/api/bmkg/gempaBesar": {
            "get": {
                "tags": ["BMKG Endpoints"],
                "summary": "Gempa M5.0+ di Indonesia (7 hari terakhir) dan ringkasan",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Data gempa M5.0+"}, "401": unauth_401},
            }
        },
        "/api/bmkg/gempaKecil": {
            "get": {
                "tags": ["BMKG Endpoints"],
                "summary": "Gempa yang dirasakan di wilayah pengguna (24 jam terakhir) dan ringkasan",
                "description": "Auth Required: **Ya**.",
                "security": [{"UserAuth": []}],
                "responses": {"200": {"description": "Data gempa dirasakan"}, "401": unauth_401},
            }
        },
        "/api/admin/dashboard": {
            "get": {
                "tags": ["Admin Endpoints"],
                "summary": "Wilayah admin dan jumlah pengguna PKK dan warga",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "responses": {"200": {"description": "Data dashboard admin"}, "401": unauth_401},
            }
        },
        "/api/admin/counts": {
            "get": {
                "tags": ["Admin Endpoints"],
                "summary": "Jumlah pengguna PKK dan warga saja",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "responses": {"200": {"description": "Jumlah pengguna PKK dan warga"}, "401": unauth_401},
            }
        },
        "/api/admin/users": {
            "get": {
                "tags": ["Admin Endpoints"],
                "summary": "Daftar pengguna yang dikelola",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "responses": {"200": {"description": "Daftar pengguna"}, "401": unauth_401},
            }
        },
        "/api/admin/users/{userId}/actions": {
            "post": {
                "tags": ["Admin Endpoints"],
                "summary": "Menjalankan aksi manajemen pengguna",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "parameters": [{"name": "userId", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "Aksi berhasil dijalankan"}, "401": unauth_401},
            }
        },
        "/api/admin/profile": {
            "get": {
                "tags": ["Admin Endpoints"],
                "summary": "Profil admin",
                "description": "Auth Required: **Admin**. Nama, email, HP, RT/RW, wilayah, unit, peran, tanggal bergabung, jumlah anggota, avatar.",
                "security": [{"AdminAuth": []}],
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "example": {
                                    "name": "Siti Aminah",
                                    "email": "saminah12@gmail.com",
                                    "phone": "089511112222",
                                    "rt": "",
                                    "rw": "",
                                    "area": "Kelurahan Pindrikan Kidul, Kec. Semarang Tengah",
                                    "unit": "PKK Pindrikan Kidul",
                                    "role": "Ketua PKK",
                                    "joined": "19 Nov 2026",
                                    "memberCount": 5,
                                    "avatarUrl": None,
                                }
                            }
                        },
                    },
                    "401": unauth_401,
                },
            },
            "patch": {
                "tags": ["Admin Endpoints"],
                "summary": "Mengubah profil admin",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "responses": {"200": {"description": "Profil admin diperbarui"}, "401": unauth_401},
            },
        },
        "/api/admin/profile/email": {
            "post": {
                "tags": ["Admin Endpoints"],
                "summary": "Meminta pergantian email (butuh email baru dan kata sandi)",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["newEmail", "password"],
                                "properties": {
                                    "newEmail": {"type": "string"},
                                    "password": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Kode verifikasi dikirim"}, "401": unauth_401},
            }
        },
        "/api/admin/profile/email/verify": {
            "post": {
                "tags": ["Admin Endpoints"],
                "summary": "Memverifikasi pergantian email dengan dua kode (email baru dan email lama)",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["newEmailCode", "oldEmailCode"],
                                "properties": {
                                    "newEmailCode": {"type": "string"},
                                    "oldEmailCode": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Email berhasil diganti"}, "401": unauth_401},
            }
        },
        "/api/admin/password": {
            "post": {
                "tags": ["Admin Endpoints"],
                "summary": "Mengganti kata sandi (kata sandi lama dan baru)",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["oldPassword", "newPassword"],
                                "properties": {
                                    "oldPassword": {"type": "string"},
                                    "newPassword": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Kata sandi diganti"}, "401": unauth_401},
            }
        },
        "/api/admin/profile/candidates": {
            "get": {
                "tags": ["Admin Endpoints"],
                "summary": "Kandidat penerima jabatan Ketua",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "responses": {"200": {"description": "Daftar kandidat Ketua"}, "401": unauth_401},
            }
        },
        "/api/admin/transfer": {
            "post": {
                "tags": ["Admin Endpoints"],
                "summary": "Menyerahkan jabatan Ketua ke anggota lain",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "responses": {"200": {"description": "Jabatan Ketua diserahkan"}, "401": unauth_401},
            }
        },
        "/api/admin/emergency-contacts": {
            "get": {
                "tags": ["Admin Endpoints"],
                "summary": "Kontak darurat aktif di wilayah admin",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "responses": {"200": {"description": "Daftar kontak darurat"}, "401": unauth_401},
            }
        },
        "/api/admin/reports/media": {
            "get": {
                "tags": ["Admin Endpoints"],
                "summary": "URL foto bukti (berlaku 1 jam) untuk semua laporan di wilayah admin",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "responses": {"200": {"description": "Daftar signed URL foto bukti"}, "401": unauth_401},
            }
        },
        "/api/admin/recommendations": {
            "post": {
                "tags": ["Admin Endpoints"],
                "summary": "Meminta rekomendasi AI ke FastAPI",
                "description": "Auth Required: **Admin**.",
                "security": [{"AdminAuth": []}],
                "responses": {"200": {"description": "Rekomendasi AI dikembalikan"}, "401": unauth_401},
            }
        },
    }

    openapi_schema["paths"].update(nextjs_paths)
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi