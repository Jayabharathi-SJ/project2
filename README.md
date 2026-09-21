# Virtual CFO Committee

**Autonomous Multimodal Financial Research & Legal Compliance Agent**

An enterprise-grade autonomous Virtual CFO application designed for corporate asset procurement and capital financing decisions in Malaysia. The system evaluates Cash Purchase, Hire Purchase (HP), and Operating Lease options under the **Hire-Purchase (Amendment) Act 2026** guidelines issued by Bank Negara Malaysia (BNM).

---

## Key Capabilities

1. **Deterministic Financial Analysis**:
   - **Cash Purchase**: Net cash outflow, upfront capital impact, and vendor cash discounts.
   - **Hire Purchase**: Reducing balance interest calculation, amortisation schedule, down payment constraints, and true Effective Interest Rate (EIR).
   - **Operating Leasing**: Total lease liabilities, upfront fees, and monthly expense projections.
   - **Comparative Evaluation**: Side-by-side net cash flow differences and mathematical ranking.

2. **Regulatory & Legal Compliance Engine**:
   - Automated compliance verification against BNM 2026 guidelines.
   - Enforces statutory EIR ceilings (17% p.a. ≤ 5 years, 16% p.a. > 5 years).
   - Electric Vehicle (EV) tenure ceiling enforcement (maximum 7 years / 84 months).
   - Minimum 10% down payment verification.
   - Grounded RAG retrieval from BNM official consumer guidance documents via Qdrant Cloud.

3. **LangGraph Autonomous Workflow**:
   - Multi-agent committee workflow orchestrating Document Parsing, Financial Modeling, Legal Audit, and CFO Recommendation.
   - LangGraph PostgreSQL state checkpointer for audit trails and resilient resume capabilities.
   - NVIDIA NIM (Nemotron 30b) explanation synthesis guarded against hallucination or ranking overrides.

4. **Interactive Enterprise Dashboard**:
   - Modern, responsive web interface for instant financial parameter tuning.
   - Drag-and-drop multimodal PDF quote processing with magic-byte validation.
   - Pre-configured procurement scenarios (Sedan, EV, Industrial CNC Machinery).

---

## Technology Stack

- **Backend**: FastAPI, Uvicorn, Pydantic v2
- **Agent Orchestration**: LangGraph, LangGraph-Checkpoint-Postgres
- **RAG & Vector Storage**: Qdrant Client (dense embeddings with cosine distance), PyPDF
- **LLM**: NVIDIA NIM API (`nvidia/nemotron-3.5-lightning-30b-a3b`)
- **Database**: PostgreSQL (psycopg3 binary)
- **Frontend**: Vanilla JavaScript (ES6+), CSS3 Glassmorphism, HTML5
- **Hosting**: Render (Backend API), Vercel (Frontend Dashboard)

---

## Getting Started

### Local Development

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Jayabharathi-SJ/project2.git
   cd project2
   ```

2. **Set Up Python Virtual Environment**:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate   # Windows
   # source .venv/bin/activate # Linux/macOS
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

4. **Run Test Suite**:
   ```bash
   pytest tests/ -v
   ```

5. **Start Application Server**:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   Access the dashboard at `http://127.0.0.1:8000/dashboard/` and API docs at `http://127.0.0.1:8000/docs`.

---

## Deployment

Refer to [`DEPLOYMENT.md`](./DEPLOYMENT.md) for full deployment instructions on Render and Vercel.
