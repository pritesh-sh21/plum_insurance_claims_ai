# Plum Health Insurance - AI Claims Processing System

An AI-powered multi-agent pipeline that automates health insurance claim review. Members upload documents, the system verifies them, extracts structured data via GPT-4o vision, applies policy rules, and produces explainable decisions with a full audit trail.

---

## System Overview

```
Member uploads claim + documents
        ↓
Agent 1: Document Verifier    - checks correct doc types, readability, patient match
        ↓
Agent 2: Document Parser      - GPT-4o vision extracts patient, diagnosis, amounts
        ↓
Agent 3: Policy Evaluator     - applies waiting periods, exclusions, limits, co-pay
        ↓
Agent 4: Fraud Detector       - flags unusual claim patterns
        ↓
Agent 5: Decision Synthesizer - produces APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW
        ↓
Full audit trace returned with every decision
```

---

## Project Structure

```
Medical_Insurance_Claim_AI_Agent/
├── backend/
│   ├── agents/
│   │   ├── verifier.py       # Agent 1 - document verification
│   │   ├── parser.py         # Agent 2 - GPT-4o vision extraction
│   │   ├── evaluator.py      # Agent 3 - policy rule engine
│   │   ├── fraud.py          # Agent 4 - fraud detection
│   │   ├── synthesizer.py    # Agent 5 - decision synthesis
│   │   └── pipeline.py       # LangGraph orchestration
│   ├── core/
│   │   ├── models.py         # Pydantic data models
│   │   ├── policy_engine.py  # Pure policy functions
│   │   ├── file_handler.py   # PDF→image conversion, base64 encoding
│   │   ├── config.py         # Settings from .env
│   │   └── policy_terms.json # Coverage rules, members, limits
│   ├── routers/
│   │   ├── claims.py         # POST /api/v1/claims (JSON test cases)
│   │   └── upload.py         # POST /api/v1/claims/upload (real files)
│   ├── tests/
│   │   ├── test_verifier.py  # TC001, TC002, TC003
│   │   ├── test_pipeline.py  # TC004-TC012
│   │   └── test_file_handler.py
│   ├── sample_docs/
│   │   ├── *.pdf / *.jpg     # 19 mock documents covering all test cases
│   ├── main.py
│   ├── generate_docs.py      # Run this to generate all sample documents
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example
├── data/
│   ├── assignment.md
│   ├── policy_terms.json
│   ├── test_cases.json
│   └── sample_documents_guide.md
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ClaimForm.jsx
│   │   │   ├── DecisionPanel.jsx
│   │   │   └── TraceViewer.jsx
│   │   ├── api/claims.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.10+ | |
| Node.js | 18+ | For frontend |
| OpenAI API key | - | GPT-4o access required |

No system-level dependencies. `pymupdf` handles PDF rendering in pure Python.

---

## Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env
# Open .env and add your OpenAI API key

# 5. Start the API
uvicorn main:app --reload
```

API will be available at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`
Health check at `http://localhost:8000/health`

---

## Frontend Setup

```bash
# In a second terminal
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend will be available at `http://localhost:5173` (or next available port)

---

## Environment Variables

Create `backend/.env` with:

```env
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_MODEL=gpt-4o
OPENAI_MINI_MODEL=gpt-4o-mini
POLICY_FILE_PATH=./core/policy_terms.json
LOG_LEVEL=INFO
```

---

## Running Tests

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_pipeline.py -v

# Run specific test case
pytest tests/test_pipeline.py::test_tc004_clean_consultation -v
```

Expected output: **29 passed** (all 12 test cases + file handler tests)

---

## Generating Sample Documents

```bash
cd backend
python generate_docs.py
```

Generates 19 files covering all test cases:
- 18 PDFs - one prescription + one bill per member for each test case
- 1 blurry JPG for TC002 unreadable document test

TC009 and TC011 do not need PDFs - test them via Swagger at http://localhost:8000/docs using POST /api/v1/claims with the JSON payloads from test_cases.json

---

## API Endpoints

### `POST /api/v1/claims`
Submit a claim with pre-structured content (for test cases and programmatic use).

```json
{
  "member_id": "EMP001",
  "policy_id": "PLUM_GHI_2024",
  "claim_category": "CONSULTATION",
  "treatment_date": "2024-11-01",
  "claimed_amount": 1500,
  "hospital_name": "City Clinic",
  "documents": [
    {
      "file_id": "F001",
      "actual_type": "PRESCRIPTION",
      "quality": "GOOD",
      "content": {
        "patient_name": "Rajesh Kumar",
        "diagnosis": "Viral Fever",
        "doctor_name": "Dr. Arun Sharma"
      }
    }
  ]
}
```

### `POST /api/v1/claims/upload`
Submit a claim with real file uploads (used by the UI).

```
Content-Type: multipart/form-data

Fields:
  member_id         string
  policy_id         string
  claim_category    string
  treatment_date    string (YYYY-MM-DD)
  claimed_amount    float
  hospital_name     string (optional)
  ytd_claims_amount float (optional)
  document_types    JSON array e.g. ["PRESCRIPTION", "HOSPITAL_BILL"]
  files             one or more PDF/image files
```

---

## Test Cases

| ID | Name | Expected Decision |
|---|---|---|
| TC001 | Wrong document uploaded | Error - specific message |
| TC002 | Unreadable document | Error - re-upload request |
| TC003 | Cross-patient documents | Error - names both patients |
| TC004 | Clean consultation | APPROVED ₹1,350 |
| TC005 | Diabetes waiting period | REJECTED |
| TC006 | Dental partial approval | PARTIAL ₹8,000 |
| TC007 | MRI without pre-auth | REJECTED |
| TC008 | Per-claim limit exceeded | REJECTED |
| TC009 | Fraud - same-day claims | MANUAL_REVIEW |
| TC010 | Apollo network discount | APPROVED ₹3,240 |
| TC011 | Component failure | APPROVED (low confidence) |
| TC012 | Excluded treatment | REJECTED |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Agent orchestration | LangGraph |
| AI / Vision | OpenAI GPT-4o |
| Data validation | Pydantic v2 |
| PDF processing | pymupdf (no system deps) |
| Image processing | Pillow |
| Frontend | React 19 + Vite |
| Tests | pytest |

---

## Testing via Swagger

TC009 and TC011 require claims history or failure simulation flags that cannot be set through the UI form. Use Swagger at `http://localhost:8000/docs` with `POST /api/v1/claims` and paste the JSON directly from `data/test_cases.json`.

TC003 works both ways - through the UI with real PDFs (GPT-4o extracts names and cross-checks post-parse) and through Swagger with `patient_name_on_doc` set on each document.

---

## Key Design Decisions

**Why LangGraph?**
Each agent is a graph node. If any node fails, the pipeline catches the exception, records the failure, and continues without crashing. This is what makes TC011 (graceful degradation) work.

**Why no LLM for policy decisions?**
Policy rules are deterministic. Using an LLM to decide whether a waiting period has elapsed would introduce hallucination risk. LLM is used only for what it is uniquely good at - reading messy documents. All decisions are pure Python.

**Why pymupdf?**
No system dependencies. Works on Windows, Mac, Linux, and any cloud platform without installing poppler or other native tools.

---

## Local Setup Summary

```bash
# Terminal 1 - Backend
cd backend && venv\Scripts\activate && uvicorn main:app --reload

# Terminal 2 - Frontend  
cd frontend && npm run dev

# Browser
open http://localhost:5173
```