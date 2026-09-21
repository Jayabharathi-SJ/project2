# Virtual CFO Committee — Production Deployment & Operations Guide

## Architecture Overview

```
                          ┌────────────────────────┐
                          │   Vercel Frontend      │
                          │   (HTML5 / CSS / JS)   │
                          └───────────┬────────────┘
                                      │ HTTPS / REST
                                      ▼
                          ┌────────────────────────┐
                          │     Render Backend     │
                          │   FastAPI / Uvicorn    │
                          └───────┬───┬───┬────────┘
                                  │   │   │
        ┌─────────────────────────┘   │   └─────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────┐             ┌───────────────┐             ┌───────────────┐
│ PostgreSQL    │             │ Qdrant Cloud  │             │  NVIDIA NIM   │
│ Checkpointer  │             │ Vector Store  │             │  LLM Service  │
│ (State / RAG) │             │ (Legal RAG)   │             │ (Nemotron 30b)│
└───────────────┘             └───────────────┘             └───────────────┘
```

---

## 1. Backend Deployment (Render)

- **Repository**: `https://github.com/Jayabharathi-SJ/project2`
- **Branch**: `main`
- **Root Directory**: `.` (project root)
- **Environment**: Python 3
- **Plan**: Free Tier (512 MiB RAM)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`

### Required Environment Variables on Render:

| Variable | Description | Example / Default |
|---|---|---|
| `POSTGRES_URI` | Managed PostgreSQL connection string | `postgresql://user:password@hostname:5432/virtual_cfo_db` |
| `NVIDIA_API_KEY` | NVIDIA NIM API Key | `nvapi-...` |
| `NVIDIA_MODEL` | NVIDIA LLM model identifier | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| `NVIDIA_BASE_URL` | NVIDIA API base URL | `https://integrate.api.nvidia.com/v1` |
| `NVIDIA_TIMEOUT` | Request timeout in seconds | `15.0` |
| `QDRANT_URL` | Qdrant Cloud cluster endpoint | `https://<cluster-id>.<region>.cloud.qdrant.io:6333` |
| `QDRANT_API_KEY` | Qdrant Cloud cluster API key | `<your-qdrant-api-key>` |
| `QDRANT_COLLECTION_NAME` | Collection name | `legal_documents` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins | `https://your-app.vercel.app,http://localhost:8000` |
| `APP_ENV` | Application environment mode | `production` |
| `HF_HUB_OFFLINE` | Prevent eager network calls during startup | `0` |

> [!NOTE]
> The SentenceTransformer OOM fix (Commit `6673c84`) ensures FastAPI boots with lazy embedding loading, constraining PyTorch memory footprint to ~84.51 MB, well below Render's 512 MiB limit.

---

## 2. Frontend Deployment (Vercel)

The frontend is a zero-build static web application located in `frontend/`.

- **Platform**: Vercel
- **Repository**: Connect `Jayabharathi-SJ/project2`
- **Root Directory**: `.` (Vercel automatically detects `vercel.json`)
- **Output Directory**: `frontend` (configured in `vercel.json`)
- **Configuration**:
  - `vercel.json` routes all requests to `frontend/index.html`.
  - In `frontend/config.js`, uncomment and configure the production backend URL:
    ```javascript
    window.__API_BASE_URL__ = "https://<your-render-service>.onrender.com";
    ```
  - `frontend/app.js` automatically honors `window.__API_BASE_URL__` with fallbacks for co-hosted and local environments.

---

## 3. Database Services

### PostgreSQL Checkpointer
- Persistent LangGraph checkpointing for long-running financial research state.
- Automated table initialization via `setup_checkpointer()`.
- Thread-safe connection pooling and credential-redacting logging.

### Qdrant Cloud Vector Store
- Vector database hosting 10 seeded legal chunks from the official BNM Hire-Purchase (Amendment) Act 2026 guidelines.
- Cosine distance metric with 384-dimensional dense vectors (`all-MiniLM-L6-v2`).
- Integrated health check via `/health/ready`.

---

## 4. Operational Endpoints & Verification

| Method | Endpoint | Purpose | Expected Status |
|---|---|---|---|
| `GET` | `/` | Service identity & version | `200 OK` |
| `GET` | `/health` | Liveness probe (container orchestrator) | `200 OK` |
| `GET` | `/health/ready` | Readiness probe (PostgreSQL, Qdrant, NVIDIA) | `200 OK` |
| `POST` | `/analyze` | Multi-agent financial & legal analysis | `200 OK` (or `422` on validation error) |
| `POST` | `/analyze-document`| Multimodal PDF quote extraction | `200 OK` |
| `GET` | `/dashboard/` | Co-hosted frontend dashboard | `200 OK` |

---

## 5. Security Architecture

- **Credential Redaction**: Automatic masking of database URIs, NVIDIA API keys, and Qdrant credentials across all application logs.
- **Strict Input Validation**: Pydantic v2 validators enforce non-negative prices, tenure bounds (≤84 months for EV, ≤60 months standard), and sanitized 422 error structures.
- **MIME & Magic Byte Verification**: Uploaded procurement documents must begin with `%PDF-` header bytes before ingestion.
- **Deterministic Override**: Recommendation reasoning is grounded strictly in deterministic financial calculations; LLM hallucination cannot alter mathematical rankings.
