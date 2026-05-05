# IASW - Intelligent Account Servicing Workflow

A production-grade prototype demonstrating AI-powered document verification with Human-in-the-Loop (HITL) approval for banking account servicing workflows.

## Overview

IASW automates the legal name change process for bank customers by:
1. Accepting document uploads (marriage certificates, court orders)
2. Using Gemini Vision AI to extract text, detect seals, signatures, QR codes, and handwriting
3. Calculating confidence scores — including LLM-based name-change plausibility analysis
4. Showing pipeline progress in real time while agents are processing
5. Requiring human checker approval before any core banking update

## Demo Flow

```
1. Staff submits request:
   - Customer ID: C001
   - Old Name: Priya Sharma
   - New Name: Priya Mehta
   - Document: Marriage Certificate (image or PDF)

2. AI Pipeline (LangGraph):
   SUBMITTED → VALIDATING → PROCESSING_DOCUMENTS → SCORING
   - Validates customer exists in RPS (mock core banking)
   - Gemini Vision extracts all fields from the document (including handwriting)
   - Detects official seal, signature, QR/barcode presence
   - Runs ELA forgery detection + EXIF metadata analysis
   - Scores: old_name vs bride_name (identity) + new_name plausibility vs groom_name
   - LLM (Gemini) assesses whether new name is a valid married name
   - Generates human-readable AI summary

3. Status: AI_VERIFIED_PENDING_HUMAN (or AI_FLAGGED_PENDING_HUMAN)

4. Checker Dashboard:
   - Reviews AI summary, confidence scores, and validation error banner
   - Sees pipeline progress in real time (stepper UI)
   - Views document inline with color-coded field annotations
   - Downloads document if needed
   - Approves or Rejects

5. On Approval:
   - System generates approval token
   - RPS validates token (HITL enforcement)
   - Customer record updated
   - Status: APPROVED
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14.2.x + TypeScript + Tailwind CSS |
| Backend | FastAPI (Python 3.10+) |
| Orchestration | LangGraph |
| LLM (primary) | Gemini 2.0 Flash Lite / 2.5 Flash fallback (Google Gemini free tier) |
| LLM (optional) | Groq — LLaMA 3.3 70B (free tier, requires `GROQ_API_KEY`) |
| OCR (primary) | Gemini Vision — handles handwriting, multilingual, seal/QR detection |
| OCR (fallback) | Tesseract + pdf2image |
| Forgery Detection | ELA (Pillow), EXIF metadata analysis, pyzbar QR decoding |
| Database | SQLite (SQLAlchemy) |
| Document Store | Local filesystem |
| Runtime | Conda environment (`iasw`) |

## Prerequisites

- **Conda** (Miniconda or Anaconda)
- **Node.js 18.x** (Next.js 14 requires Node ≥ 18; do NOT use Node 20+ without also upgrading Next.js)
- **Gemini API key** — free tier at https://aistudio.google.com/app/apikey (1500 req/day)
- **Tesseract** (optional — only needed if `OCR_PROVIDER=tesseract`)
- **libzbar0** (optional — only needed for QR barcode decoding)

### Install system dependencies (Ubuntu/Debian)

```bash
# Tesseract (OCR fallback)
sudo apt install tesseract-ocr poppler-utils

# QR/barcode decoding
sudo apt install libzbar0
```

## Quick Start

### 1. Create and activate conda environment

```bash
conda create -n iasw python=3.10 -y
conda activate iasw
```

### 2. Clone / navigate to project

```bash
cd /home/anish/Downloads/Assesment_v2/Assessment2
```

### 3. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 4. Set API key (required)

```bash
export GEMINI_API_KEY="your_api_key_here"
# Optional: for Groq LLaMA 3.3 70B
export GROQ_API_KEY="your_groq_key_here"
```

Or permanently in the conda env:
```bash
conda activate iasw
conda env config vars set GEMINI_API_KEY="your_api_key_here"
conda deactivate && conda activate iasw
```

### 5. Start the backend

```bash
conda activate iasw
cd /home/anish/Downloads/Assesment_v2/Assessment2
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Backend: http://localhost:8000  
API docs: http://localhost:8000/docs

### 6. Setup and start the frontend

```bash
cd /home/anish/Downloads/Assesment_v2/Assessment2/frontend
npm install
npm run dev
```

Frontend: http://localhost:3000

### 7. Generate Sample Certificate (Optional)

```bash
conda activate iasw
cd /home/anish/Downloads/Assesment_v2/Assessment2
python -m backend.scripts.generate_mock_certificate
```

## Project Structure

```
Assessment2/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # All config: API keys, models, thresholds
│   ├── models/
│   │   ├── database.py            # SQLAlchemy models (includes validation_errors JSON column)
│   │   └── schemas.py             # Pydantic request/response schemas
│   ├── services/
│   │   ├── llm_service.py         # Gemini + Groq providers (google-genai new SDK)
│   │   ├── rps_mock.py            # Mock core banking system
│   │   ├── filenet_mock.py        # Mock document store
│   │   └── audit_service.py       # Audit logging (JSONL)
│   ├── agents/
│   │   ├── orchestrator.py        # LangGraph DAG + status callback emitter
│   │   ├── validation_agent.py    # Customer/account validation against RPS
│   │   ├── document_processor.py  # Gemini Vision OCR + ELA + EXIF + QR
│   │   ├── confidence_scorer.py   # Name identity + plausibility + forgery scoring
│   │   └── summary_generator.py   # LLM-generated human-readable summary
│   └── routers/
│       ├── intake.py              # Request submission + async status callback
│       ├── checker.py             # HITL approval + document serving endpoint
│       └── status.py              # Request/customer status queries
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Dashboard (stats + recent requests)
│   │   ├── intake/page.tsx        # Staff intake form with document upload
│   │   └── checker/page.tsx       # Checker dashboard (Suspense-wrapped)
│   └── components/
│       ├── PipelineProgress.tsx   # Real-time pipeline stepper (polls every 2-3s)
│       ├── DocumentViewer.tsx     # Inline doc viewer + color-coded field annotations
│       ├── IntakeForm.tsx
│       ├── CheckerReview.tsx
│       ├── ConfidenceCard.tsx
│       └── StatusBadge.tsx
├── data/uploads/                   # Uploaded documents
├── logs/audit.jsonl               # Append-only audit trail
├── iasw.db                        # SQLite database
├── requirements.txt
└── README.md
```

## API Endpoints

### Intake
- `POST /api/v1/intake/submit` — Submit request with document upload (multipart)
- `POST /api/v1/intake/submit-json` — Submit without document (JSON, for testing)

### Checker
- `GET /api/v1/checker/pending` — List pending requests
- `GET /api/v1/checker/request/{id}` — Get request details
- `POST /api/v1/checker/request/{id}/action` — Approve or Reject
- `GET /api/v1/checker/stats` — Dashboard statistics
- `GET /api/v1/checker/document/{id}` — Serve the uploaded document inline (image/PDF)

### Status
- `GET /api/v1/status/request/{id}` — Request status
- `GET /api/v1/status/customer/{id}` — All requests for a customer
- `GET /api/v1/status/audit/{id}` — Audit trail for a request
- `GET /api/v1/status/all` — All requests (with optional limit)

## Environment Variables

```bash
# Gemini (required — primary LLM + OCR)
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash-lite        # Primary model (1500 req/day free)
GEMINI_FALLBACK_MODEL=gemini-2.5-flash    # Auto-fallback on 429 rate limit

# Groq (optional — LLaMA 3.3 70B, leave empty to disable)
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile

# OCR provider
OCR_PROVIDER=gemini_vision   # "gemini_vision" (default) or "tesseract"
TESSERACT_LANG=eng           # Used only when OCR_PROVIDER=tesseract

# Storage
DATABASE_URL=sqlite:///./iasw.db
UPLOAD_DIR=./data/uploads
LOG_DIR=./logs
```

## Test Data

The mock RPS contains these test customers:

| Customer ID | Name | Status |
|-------------|------|--------|
| C001 | Priya Sharma | Active |
| C002 | Rahul Kumar | Active |
| C003 | Anita Desai | Active |
| C004 | Vikram Singh | Dormant |

## Request Status Flow

```
SUBMITTED
    ↓
VALIDATING          ← validation_errors stored to DB (shown as banner in UI)
    ↓
PROCESSING_DOCUMENTS  ← Gemini Vision OCR + ELA + EXIF + QR detection
    ↓
SCORING             ← Name identity + plausibility + authenticity scoring
    ↓
AI_VERIFIED_PENDING_HUMAN  or  AI_FLAGGED_PENDING_HUMAN
    ↓                              ↓
    └──────────────────────────────┘
                ↓
        (Human Checker Review)
                ↓
    APPROVED  or  REJECTED
```

## Key Features

### 1. Gemini Vision OCR
- Handles handwritten documents (not just typed text)
- Multilingual extraction (Hindi, Tamil, English, etc.)
- Detects official seal, signature, and QR/barcode in a single API call
- No separate PDF conversion needed — Gemini accepts images directly
- Falls back to Tesseract + regex if Gemini is unavailable

### 2. Name-Change Confidence Scoring
Marriage certificates do **not** contain the bride's new married name. The scorer uses a two-component approach:
- **Identity (50%)**: fuzzy match `old_name` vs extracted `bride_name`
- **Plausibility (50%)**: heuristic structural check (first name preserved + new surname from groom) combined with LLM semantic judgment
- Falls back to heuristic-only if LLM call fails

### 3. Forgery & Integrity Detection
- **ELA (Error Level Analysis)**: detects JPEG pixel-level editing via PIL `ImageChops.difference()`
- **EXIF metadata**: flags documents edited in Photoshop, GIMP, or other software
- **pyzbar**: decodes QR codes and barcodes (graceful fallback if `libzbar0` not installed)

### 4. Real-Time Pipeline Progress
Status callback emits stage transitions to the database; frontend polls every 2–3s and renders a horizontal stepper (Submitted → Validating → Reading Document → AI Scoring → Human Review).

### 5. Human-in-the-Loop
- All changes require human checker approval
- Approval tokens prevent AI from writing directly to RPS
- Complete append-only audit trail in JSONL format

## Troubleshooting

### Backend won't start
- Check conda env is active: `conda activate iasw`
- Check port: `lsof -ti:8000` to see if port is in use
- Verify API key: `echo $GEMINI_API_KEY`

### Frontend freezes or hangs
- Confirm Node.js version is 18.x: `node --version`
- Do NOT use Node.js 20+ without also upgrading Next.js
- Kill stale processes: `kill $(lsof -ti:3000)` then restart

### Gemini 429 Rate Limit
- The system automatically falls back to `gemini-2.5-flash`
- Free tier: 1500 requests/day per model
- If both models are exhausted, wait for quota reset or switch to `GROQ_API_KEY`

### QR detection not working
- Install system library: `sudo apt install libzbar0`
- The system falls back gracefully — Gemini Vision still reports `has_qr_or_barcode` via image analysis

### Tesseract not found
- Default OCR is `gemini_vision` — Tesseract is only needed if `OCR_PROVIDER=tesseract`
- Install if needed: `sudo apt install tesseract-ocr`
