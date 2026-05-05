# IASW Solution Design Document

## 1. Executive Summary

The Intelligent Account Servicing Workflow (IASW) is an AI-powered prototype that automates document verification for banking account servicing while maintaining strict human oversight. This solution demonstrates how banks can leverage AI to improve operational efficiency without compromising on accuracy, security, or regulatory compliance.

### Key Capabilities
- **Gemini Vision OCR**: Extracts handwriting, multilingual text, seals, signatures, and QR codes from document images in a single API call
- **LLM-Assisted Name Verification**: Marriage certificates do not contain the bride's new name — the system infers plausibility from the bride's old name and the groom's name using structural heuristics and Gemini LLM judgment
- **Integrity Analysis**: Error Level Analysis (ELA), EXIF metadata inspection, and QR/barcode decoding for forgery detection
- **Real-Time Pipeline Visibility**: Frontend polls every 2–3s and shows a live pipeline stepper as agents process the request
- **Human-in-the-Loop (HITL)**: Mandatory human checker approval before any core banking update; cryptographic token enforcement

## 2. Problem Statement

Banks process thousands of name change requests annually. Each request requires:
1. Manual document verification
2. Cross-referencing with existing records
3. Multiple approval levels
4. Core banking updates

This manual process is:
- Time-consuming (5–10 days average)
- Error-prone (human fatigue, transcription errors)
- Inconsistent (different reviewers apply different standards)
- Expensive (high labor costs)

## 3. Solution Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js 14)                       │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐   │
│  │ Intake Form  │  │ Checker Dashboard │  │  Dashboard/Stats  │   │
│  │              │  │ + PipelineProgress│  │                    │   │
│  │              │  │ + DocumentViewer  │  │                    │   │
│  └──────────────┘  └──────────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐   │
│  │ /intake/*    │  │ /checker/*       │  │ /status/*          │   │
│  └──────────────┘  └──────────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AI ORCHESTRATION (LangGraph)                     │
│  ┌───────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │Validation │─▶│  Document    │─▶│ Scoring  │─▶│  Summary     │  │
│  │  Agent    │  │  Processor   │  │  Agent   │  │  Generator   │  │
│  │           │  │(Gemini Vision│  │(LLM name │  │(Gemini LLM)  │  │
│  │           │  │ + ELA + EXIF)│  │ scoring) │  │              │  │
│  └───────────┘  └──────────────┘  └──────────┘  └──────────────┘  │
│       ↑ status_callback emits VALIDATING→PROCESSING→SCORING to DB  │
└─────────────────────────────────────────────────────────────────────┘
                    ┌───────────┴───────────┐
                    ▼                       ▼
┌──────────────────────────┐  ┌──────────────────────────────────────┐
│    RPS (Mock Banking)    │  │      FileNet (Document Store)        │
└──────────────────────────┘  └──────────────────────────────────────┘
```

### 3.2 Component Details

#### Frontend Layer
- **Technology**: Next.js 14.2.x with TypeScript (requires Node.js 18.x)
- **Styling**: Tailwind CSS
- **State Management**: React hooks + axios polling
- **Real-time Updates**: 3s polling for pending list, 2s polling for selected request while processing
- **New Components**: `PipelineProgress` (live stepper), `DocumentViewer` (inline doc + color-coded annotations + download button), `ValidationErrorBanner`

#### API Layer
- **Framework**: FastAPI (Python 3.10+ in conda env `iasw`)
- **Documentation**: Auto-generated OpenAPI/Swagger at `/docs`

#### AI Orchestration Layer
- **Framework**: LangGraph (stateful DAG with status callback)
- **LLM Primary**: Gemini 2.0 Flash Lite via `google-genai` SDK (new, not deprecated `google-generativeai`)
- **LLM Fallback**: Gemini 2.5 Flash (auto-triggered on 429 rate limit)
- **LLM Optional**: Groq LLaMA 3.3 70B (enabled by setting `GROQ_API_KEY`)
- **OCR Primary**: Gemini Vision (handles handwriting, multilingual, seal/QR/signature detection)
- **OCR Fallback**: Tesseract + regex (when `OCR_PROVIDER=tesseract`)

#### Data Layer
- **Database**: SQLite (dev) / PostgreSQL (prod) via SQLAlchemy
- **Document Storage**: Local filesystem
- **New Column**: `validation_errors JSON` on `pending_requests` table

## 4. AI Pipeline Design

### 4.1 Pipeline Flow

```
Input: Request + Document
         │
         ▼
┌─────────────────────┐
│ 1. VALIDATION       │ ─── Customer exists in RPS?
│    AGENT            │ ─── old_name matches RPS record?
│    emit: VALIDATING │ ─── Account status: Active?
└─────────────────────┘ ─── Store validation_errors to DB
         │
         ▼
┌─────────────────────┐
│ 2. DOCUMENT         │ ─── Gemini Vision: full image extraction
│    PROCESSOR        │     (handwriting, multilingual, seal/QR/sig)
│    emit: PROCESSING │ ─── ELA forgery detection (PIL ImageChops)
│    _DOCUMENTS       │ ─── EXIF metadata check (editing software)
└─────────────────────┘ ─── pyzbar QR/barcode decoding
         │
         ▼
┌─────────────────────┐
│ 3. CONFIDENCE       │ ─── Identity: old_name vs bride_name (fuzzy)
│    SCORER           │ ─── Plausibility: new_name given old+groom
│    emit: SCORING    │     (structural heuristic + Gemini LLM)
└─────────────────────┘ ─── Authenticity: seal/QR/reg.no/quality
         │
         ▼
┌─────────────────────┐
│ 4. SUMMARY          │ ─── Gemini LLM generates summary
│    GENERATOR        │ ─── Template fallback if LLM fails
└─────────────────────┘
         │
         ▼
Output: Verification Result + Recommendation
```

### 4.2 Name-Change Confidence Scoring

Marriage certificates **do not contain the bride's new married name**. The scorer uses a two-component approach:

```
name_score = weighted_average(
    identity_score   = fuzzy(old_name, bride_name_from_cert),  # weight 0.5
    plausibility     = 0.5 × heuristic + 0.5 × llm_judgment,  # weight 0.5
)

heuristic_plausibility:
  - First name preserved?     (old_name[0] ≈ new_name[0])       weight 0.4
  - New surname in groom?     (new_name[-1] ≈ any groom token)  weight 0.5
  - Name length reasonable?                                      weight 0.1

llm_judgment: ask Gemini "Is '{new_name}' a plausible married name
  for '{old_name}' who married '{groom_name}'?" → float 0.0–1.0
  (Returns None on failure; system uses heuristic at full weight)

Overall Score = name_score × 0.5 + authenticity × 0.3 + forgery_score × 0.2

Thresholds:
  ≥ 0.90 → APPROVE
  ≥ 0.70 → MANUAL_REVIEW
  < 0.70 → REJECT
  forgery == FAIL → REJECT (override)
```

### 4.3 Forgery & Integrity Detection

| Method | How | Detects |
|--------|-----|---------|
| **ELA (Error Level Analysis)** | PIL `ImageChops.difference(resaved_jpeg, original)` | Pixel-level editing in JPEG files |
| **EXIF Metadata** | `PIL.ExifData` software field | Photoshop, GIMP, screenshot editors |
| **pyzbar** | Barcode/QR decode | Missing/invalid QR that should be present |
| **Gemini Vision** | Prompt-level flags | `tampering_indicators` in response |

### 4.4 Gemini Vision Prompt Strategy

A single Gemini Vision call extracts all required information:
```
"Analyze this marriage certificate image and extract:
 bride_name, groom_name, marriage_date, registration_number,
 place_of_marriage, officiating_authority, document_language,
 has_official_seal (bool), has_signature (bool),
 has_qr_or_barcode (bool), document_quality (good/fair/poor),
 tampering_indicators (list)
Return JSON."
```
This replaces the old two-step Tesseract OCR → LLM text extraction pipeline.

## 5. Human-in-the-Loop Design

### 5.1 HITL Enforcement Mechanism

```
┌──────────────────────────────────────────────────────────────┐
│                      APPROVAL FLOW                           │
│                                                              │
│  1. AI generates recommendation                             │
│                    ↓                                        │
│  2. Status: AI_VERIFIED_PENDING_HUMAN                       │
│                    ↓                                        │
│  3. Checker reviews in dashboard                            │
│     - See validation error banner (if any)                  │
│     - View document inline with color-coded annotations     │
│     - Review confidence score breakdown                     │
│                    ↓                                        │
│  4. Checker clicks APPROVE                                  │
│                    ↓                                        │
│  5. System generates APPROVAL_TOKEN                         │
│     (cryptographically secure, single-use)                  │
│                    ↓                                        │
│  6. Token registered with RPS Gateway                       │
│                    ↓                                        │
│  7. RPS validates token before accepting update             │
│                    ↓                                        │
│  8. Token marked as USED (prevents replay)                  │
│                    ↓                                        │
│  9. Customer record updated                                 │
│                    ↓                                        │
│  10. Audit log records all actions                          │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Why AI Cannot Bypass the Checker

| Bypass Attempt | Prevention Mechanism |
|----------------|----------------------|
| AI generates fake token | Only Checker action triggers token generation |
| AI calls RPS directly | RPS endpoint validates token; no token = no update |
| AI modifies status to APPROVED | Status → APPROVED only after RPS update with valid token |
| AI reuses old token | Token marked USED; reuse rejected |

## 6. Data Models

### 6.1 PendingRequest (updated schema)

```python
class PendingRequest:
    id: int
    request_id: str              # "REQ-XXXXXXXX"
    customer_id: str
    old_name: str
    new_name: str
    request_type: str            # "LEGAL_NAME_CHANGE"
    document_path: str           # Local filesystem path
    status: RequestStatusEnum

    ai_summary: str
    ai_recommendation: str       # "APPROVE" | "REJECT" | "MANUAL_REVIEW"
    confidence_scores: JSON      # {name_match, authenticity, forgery_check, overall, details}
    extracted_fields: JSON       # {bride_name, groom_name, marriage_date, has_official_seal, ...}
    validation_errors: JSON      # {errors[], warnings[], customer_exists, name_matches, account_active}

    checker_id: str
    checker_notes: str
    approval_token: str          # Partial token for audit

    created_at: datetime
    updated_at: datetime
    completed_at: datetime
```

### 6.2 Extracted Fields Structure

```json
{
    "bride_name": "Priya Sharma",
    "groom_name": "Rahul Mehta",
    "marriage_date": "15th January 2024",
    "registration_number": "MC-2024-001234",
    "place_of_marriage": "New Delhi",
    "officiating_authority": "Registrar of Marriages",
    "document_language": "English",
    "has_official_seal": true,
    "has_signature": true,
    "has_qr_or_barcode": true,
    "document_quality": "good",
    "tampering_indicators": [],
    "ocr_provider": "gemini_vision"
}
```

Note: `married_name` is **not extracted** — marriage certificates do not contain the bride's new name. Plausibility is inferred from `groom_name`.

### 6.3 Confidence Scores Structure

```json
{
    "name_match": 0.91,
    "authenticity": 0.87,
    "forgery_check": "PASS",
    "overall": 0.88,
    "details": {
        "name_details": {
            "identity_score": 0.98,
            "heuristic_relationship": 0.85,
            "llm_relationship": 0.90,
            "combined_relationship": 0.875,
            "extracted_bride": "Priya Sharma",
            "extracted_groom": "Rahul Mehta"
        },
        "extraction_confidence": 0.87,
        "forgery_indicator_count": 0,
        "thresholds": {"auto_approve": 0.90, "manual_review": 0.70, "auto_reject": 0.40}
    }
}
```

## 7. Security Considerations

### 7.1 Data Protection
- Gemini Vision sends document images to Google APIs — suitable for non-production/demo use
- For production with sensitive documents, use `OCR_PROVIDER=tesseract` for local processing
- API keys stored as environment variables, never hardcoded in production

### 7.2 Access Control
- Checker actions require `checker_id` (placeholder; production should use SSO)
- Approval tokens are cryptographically generated (`secrets.token_urlsafe(32)`)
- All actions logged with actor identity in append-only JSONL audit trail

### 7.3 HITL Enforcement
- AI **never** writes directly to RPS
- Every RPS update is gated by a single-use token generated only by checker action
- Status machine prevents skipping human review stage

## 8. Scalability Considerations

### 8.1 Current Limitations (Prototype)
- SQLite single-writer bottleneck
- In-memory state management
- Gemini free tier: 1500 requests/day

### 8.2 Production Scaling

| Component | Current | Production |
|-----------|---------|------------|
| Database | SQLite | PostgreSQL + read replicas |
| LLM/OCR | Gemini free tier | Gemini enterprise or self-hosted Vision LM |
| Document Store | Local FS | S3 / Azure Blob |
| Queue | Background tasks | Celery + RabbitMQ |
| Notifications | Polling | WebSockets / SSE |

## 9. Monitoring & Observability

- **Audit log**: `logs/audit.jsonl` — append-only, JSONL format, all actions
- **Application logs**: Python `logging` module, per-agent INFO/WARNING/ERROR messages
- **Pipeline tracing**: `request_id` propagated through all agents and logs
- **Agent timing**: Each node logs start/end implicitly via LangGraph state transitions

## 10. Future Enhancements

### Already Implemented (vs. original design)
- [x] Gemini Vision OCR (handwriting, multilingual, seal/QR detection)
- [x] LLM-based name-change plausibility scoring
- [x] ELA + EXIF + QR forgery detection
- [x] Real-time pipeline progress UI
- [x] Validation error banner in checker UI
- [x] Inline document viewer with download option
- [x] Gemini model fallback on 429 rate limit

### Phase 2
- [ ] Multi-document support (Court Order + ID cross-verification)
- [ ] Batch processing
- [ ] Email / push notifications to checker
- [ ] Groq LLaMA 3.3 70B as primary for text tasks (separate from vision)

### Phase 3
- [ ] Production LLM (Gemini Enterprise or Claude API)
- [ ] Advanced forgery: CNN-based image forensics, watermark verification
- [ ] Integration with real core banking (RPS via enterprise service bus)
- [ ] Customer self-service portal

## 11. Compliance Considerations

### 11.1 Regulatory Alignment
- **GDPR**: Data minimization; AI decisions stored with full confidence breakdown for right-to-explanation
- **Banking Regulations**: Human approval enforced by token mechanism — AI cannot bypass
- **Audit Requirements**: Complete append-only trail of all agent decisions and human actions

### 11.2 Explainability
- AI recommendations include full confidence score breakdown visible to checkers
- Name matching details expandable in the checker UI
- Extracted fields with color-coded score impact annotations in DocumentViewer

## 12. Conclusion

IASW demonstrates that AI can significantly improve banking operations while maintaining the human oversight required by regulations and best practices. The key innovations are:

1. **Gemini Vision as unified OCR + field extractor**: Handles handwriting, multilingual, and integrity signals in one API call — replacing the fragile OCR → LLM chain
2. **Semantically-aware name scoring**: Correctly models the marriage certificate domain (no married name → infer plausibility from groom)
3. **Defense-in-depth forgery detection**: ELA + EXIF + QR + Gemini Vision flags
4. **Real-time observability**: Pipeline stepper gives checkers live visibility into AI processing
5. **Token-Based HITL**: Cryptographically enforced human approval gate

This prototype provides a foundation for production implementation with clear upgrade paths for each component.
