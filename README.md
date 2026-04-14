# OmniDoc — Multi-Sector Document Intelligence

> Upload any PDF. Ask questions in natural language. Get cited answers — for Agriculture, Healthcare, Education, Military, Household, or IT.

Built with FastAPI · LangGraph · pgvector · Next.js 14 · Multi-LLM fallback · RTX 4050 GPU support · 100% free tools.

---

## What it does

OmniDoc lets users upload PDF documents into sector-specific workspaces and ask questions in plain language. The system:

1. **Classifies intent** — extractive (fact lookup), descriptive (explanation), or comparative (cross-document)
2. **Retrieves relevant chunks** — BM25 keyword + dense vector hybrid search, GPU-accelerated reranking
3. **Answers via multi-LLM fallback** — tries Ollama → Groq → Gemini → Cloudflare → HuggingFace in sequence
4. **Returns cited answers** — every answer includes the source document and page number

---

## Multi-LLM Fallback Chain

```
1. Ollama     (local GPU — dev, unlimited, offline)
      ↓ if unavailable
2. Groq       (cloud free — 14,400 req/day)
      ↓ if rate limited
3. Gemini     (cloud free — 1,500 req/day)
      ↓ if rate limited
4. Cloudflare (cloud free — 10,000 req/day)
      ↓ if unavailable
5. HuggingFace(cloud free — always-on fallback)
```

Combined: ~40,000 free requests/day. Zero downtime even if one provider goes down.

---

## 6 Sectors

| Sector | Persona | Example patterns |
|---|---|---|
| Agriculture | Farm advisor | MSP values, NDVI, rainfall |
| Healthcare | Clinical analyst | Dosage (mg/ml), BP, ICD codes |
| Education | Academic advisor | Marks, GPA, deadlines |
| Military | Defence analyst | Grid references, callsigns, frequencies |
| Household | Home assistant | Warranty periods, bills, policy numbers |
| IT | Senior engineer | Versions, SLAs, CVEs, ports |

Each sector has its own AI persona, extraction regex patterns, UI terminology, and suggested questions. **Adding a new sector = adding one Python dict to `backend/sectors/__init__.py`. Zero other changes.**

---

## Architecture

```
Browser
  └── Next.js 14 + TypeScript + Tailwind (Vercel)
        └── FastAPI + LangGraph (Render.com)
              ├── Multi-LLM Fallback Chain
              │     Ollama → Groq → Gemini → Cloudflare → HuggingFace
              ├── RAG Core
              │     pgvector (PostgreSQL) — no FAISS
              │     BM25 + dense hybrid retrieval
              │     GPU cross-encoder reranker (RTX 4050)
              │     OCR for scanned PDFs (pytesseract)
              │     Table extraction (pdfplumber)
              ├── LangGraph Coordinator
              │     intent classifier → retriever → agent → synthesizer
              └── Data Layer
                    PostgreSQL + pgvector (Neon.tech)
                    Redis (cache)
                    Cloudflare R2 (PDF storage)
```

---

## Project structure

```
omnidoc/
├── backend/
│   ├── sectors/        ← All 6 sector configs (one dict each)
│   ├── core/
│   │   ├── llm_chain.py    ← Multi-LLM fallback chain
│   │   ├── rag_engine.py   ← pgvector, OCR, table extraction, GPU reranker
│   │   └── embeddings.py   ← GPU-accelerated sentence-transformers
│   ├── agents/
│   │   └── coordinator.py  ← LangGraph StateGraph
│   ├── api/
│   │   ├── database.py     ← All SQLAlchemy models + VectorChunk
│   │   └── routes/         ← health, auth, sectors, workspaces, members, documents, query, admin
│   ├── tools/
│   │   ├── storage.py      ← Cloudflare R2 + local fallback
│   │   └── notifications.py← Resend email
│   ├── alembic/            ← Database migrations
│   ├── tests/              ← pytest test suite
│   ├── scripts/
│   │   ├── setup_windows.bat  ← One-click Windows 11 + RTX 4050 setup
│   │   └── init_pgvector.sql  ← pgvector extension init
│   ├── monitoring/         ← Prometheus + Grafana config
│   ├── main.py             ← FastAPI entry point
│   ├── requirements.txt
│   └── .env.example        ← All credentials documented
├── frontend/
│   ├── pages/
│   │   ├── index.tsx   ← Main dashboard (chat, history, team tabs)
│   │   └── login.tsx   ← Auth page
│   ├── hooks/
│   │   ├── useApi.ts   ← Complete API client
│   │   └── useSector.ts← Sector state + accent colours
│   └── styles/
├── docker-compose.yml  ← PostgreSQL + Redis + monitoring (infra only)
├── .github/workflows/  ← CI/CD (GitHub Actions)
└── README.md
```

---

## Setup — Windows 11 + RTX 4050

### Prerequisites
- Python 3.11+ · Node.js 20+ · Docker Desktop · Git
- [Ollama](https://ollama.com/download) (for local GPU inference)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (for scanned PDFs)

### Step 1 — Clone and setup

```bash
git clone https://github.com/YOUR_USERNAME/omnidoc
cd omnidoc/backend
scripts\setup_windows.bat
```

This installs PyTorch with CUDA 12.1, all Python dependencies, and pulls Ollama models.

### Step 2 — Get free API keys

You need **at least one** LLM key. Get all for maximum resilience:

| Service | URL | Free limit |
|---|---|---|
| **Groq** (recommended first) | https://console.groq.com | 14,400 req/day |
| Gemini | https://aistudio.google.com | 1,500 req/day |
| Cloudflare AI | https://dash.cloudflare.com → Workers AI | 10,000 req/day |
| HuggingFace | https://huggingface.co/settings/tokens | Rate limited |
| **Neon** (database) | https://neon.tech | 0.5 GB free |
| Resend (email, optional) | https://resend.com | 3,000/month |

### Step 3 — Configure

```bash
# Backend
cd backend
cp .env.example .env
# Open .env in VS Code and fill in your keys
# Minimum required: DATABASE_URL + SECRET_KEY + at least one LLM key

# Frontend
cd ../frontend
cp .env.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000  (already set)
```

### Step 4 — Start infrastructure

```bash
# From project root
docker-compose up -d
# Starts: PostgreSQL (with pgvector), Redis, Phoenix, Prometheus, Grafana
```

### Step 5 — Database setup

```bash
cd backend
venv\Scripts\activate
alembic upgrade head
```

### Step 6 — Start backend

```bash
# Still in backend/ with venv active
uvicorn main:app --reload --port 8000
```

Visit http://localhost:8000/docs to verify. Check `/api/v1/health` to see which LLM providers are active.

### Step 7 — Start frontend

```bash
# New terminal
cd frontend
npm install
npm run dev
```

Visit **http://localhost:3000**

---

## Deploying for users (Render + Vercel + Neon) — FREE

### Backend → Render.com

1. Push to GitHub
2. [render.com](https://render.com) → New Web Service → connect your repo
3. **Root directory:** `backend`
4. **Build command:** `pip install -r requirements.txt`
5. **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add all environment variables from `backend/.env.example`
   - `DATABASE_URL` → your Neon.tech connection string  ← **CREDENTIAL REQUIRED**
   - `SECRET_KEY` → generate with `python -c "import secrets; print(secrets.token_hex(32))"`  ← **CREDENTIAL REQUIRED**
   - `GROQ_API_KEY` → from console.groq.com  ← **CREDENTIAL REQUIRED**
   - `GEMINI_API_KEY` → from aistudio.google.com (optional but recommended)
   - `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` (optional)
   - `FRONTEND_URL` → your Vercel URL (add after deploying frontend)

### Database → Neon.tech

1. [neon.tech](https://neon.tech) → Sign up → New project
2. Copy connection string (format: `postgresql://user:pass@host/db?sslmode=require`)
3. Set as `DATABASE_URL` in Render
4. Run migrations: `alembic upgrade head` (run locally with production DATABASE_URL)

### Frontend → Vercel

```bash
cd frontend
npx vercel --prod
# When prompted, set:
# NEXT_PUBLIC_API_URL = https://your-app-name.onrender.com
```

Or connect GitHub repo to Vercel dashboard and set environment variable there.

### GitHub Actions (auto-deploy on push)

Add these secrets in GitHub → Settings → Secrets → Actions:

| Secret | Where to get it |
|---|---|
| `RENDER_API_KEY` | Render dashboard → Account → API Keys |
| `RENDER_BACKEND_SERVICE_ID` | Your Render service ID (srv-xxxx) |
| `VERCEL_TOKEN` | Vercel → Settings → Tokens |
| `VERCEL_ORG_ID` | Vercel → Settings → General |
| `VERCEL_PROJECT_ID` | Vercel project → Settings → General |
| `PROD_API_URL` | Your Render backend URL |

---

## Service URLs (local dev)

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| Health + LLM status | http://localhost:8000/api/v1/health |
| Phoenix traces | http://localhost:6006 |
| Grafana | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |

---

## Running tests

```bash
cd backend
venv\Scripts\activate
pytest tests/ -v
```

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI + Python 3.11 | Fast, async, excellent docs |
| Agent framework | LangGraph | Explicit state, observable routing |
| LLM | Multi-provider fallback | Zero downtime, zero cost |
| Vector DB | pgvector (PostgreSQL) | No data loss, proper DELETE, queryable |
| Retrieval | BM25 + dense hybrid | Keyword precision + semantic recall |
| Reranker | ms-marco-MiniLM (GPU) | Free, local, fast on RTX 4050 |
| PDF processing | PyMuPDF + pdfplumber + pytesseract | Text + tables + OCR |
| Frontend | Next.js 14 + TypeScript + Tailwind | Production-ready, Vercel-native |
| Database | PostgreSQL (Neon.tech) | Free, never pauses |
| Cache | Redis | Sessions, query cache |
| Storage | Cloudflare R2 | 10GB free, zero egress |
| Email | Resend | 3,000/month free |
| Tracing | Arize Phoenix | Free LangSmith replacement |
| CI/CD | GitHub Actions | Auto-deploy on push |
| Deployment | Render + Vercel | Free tier, production-ready |

---
