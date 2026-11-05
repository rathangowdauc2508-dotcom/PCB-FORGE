# PCB Forge — PCB Quality Inspection

The inspection screen runs PCB Forge's own six-class YOLOv8 detector after it has been trained on labeled PCB images. Its training process starts from a YAML architecture with random initialization; it does not use a downloaded pretrained checkpoint. See [docs/TRAIN_PCB_MODEL.md](docs/TRAIN_PCB_MODEL.md) for dataset preparation, the command, outputs, and current limits.

The inspection service also keeps a separate Gemma multi-evidence API for design/reference/specification diagnosis. The single-photo inspection screen is dedicated to PCB Forge's trained detector. No detections means “not detected,” not “passed.”

## Architecture

```
User Input (error log, images, specs)
        │
        ▼
  ┌─────────────────────┐
  │  Agent 1 — Symptom  │   Parse error log → suspect parts
  │     Analyzer        │
  └────────┬────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌──────────┐ ┌──────────┐
│ Agent 2A │ │ Agent 2B │   Parallel: spec precheck + CAD mapping
│ Spec     │ │ CAD      │
│ Precheck │ │ Mapper   │
└────┬─────┘ └────┬─────┘
     └─────┬──────┘
           ▼
  ┌─────────────────────┐
  │  Agent 3 — Physical │   Verify defects on tested board image
  │     Vision          │
  └────────┬────────────┘
           ▼
  ┌─────────────────────┐
  │  Agent 4 — Spec     │   Final diagnosis + resolution
  │     Resolver        │
  └─────────────────────┘
           │
           ▼
  Annotated image + diagnosis report
```

### Agent Roles

| Agent | Name | Role |
|-------|------|------|
| 1 | Symptom Analyzer | Parses error logs to identify suspect components and fault modes |
| 2A | Spec Precheck | Builds an inspection watchlist from specification documents (parallel) |
| 2B | CAD Mapper | Maps suspect parts to physical regions on the design image (parallel) |
| 3 | Physical Vision | Inspects the tested board image to verify actual defects |
| 4 | Spec Resolver | Produces spec-grounded root cause, compliance checks, and resolution steps |

## Tech Stack

**Backend:** Python 3.11+, FastAPI, Google Generative AI SDK serving Gemma 4, OpenCV, Pillow, Pydantic v2

**Frontend:** React 19, TypeScript, Vite, Zustand

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- One or more [Google AI Studio API keys](https://aistudio.google.com/apikey) with access to Gemma 4

### Backend

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set GEMINI_API_KEYS=key1,key2,...

uvicorn app.main:app --reload --port 8000
```

Swagger docs: http://127.0.0.1:8000/docs

### Frontend

```bash
cd front
npm install
npm run dev
```

The dev server starts at http://localhost:5173 and proxies `/api` requests to port 8000.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEYS` | Comma-separated Google AI Studio API keys used to call Gemma (round-robin pool) | *required* |
| `DEFAULT_MODEL` | Model override; set to `gemma-4-31b-it` for Gemma-only runs | `gemma-4-31b-it` (recommended) |
| `DEFAULT_TEMPERATURE` | LLM temperature | `0.2` |
| `MAX_OUTPUT_TOKENS` | Maximum response tokens | `1200` |
| `REQUEST_TIMEOUT_SEC` | Model request timeout (seconds) | `90` |

## API Endpoints

### Health & Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server status and key count |
| GET | `/models` | Available models + recommendation (UI shows only Gemma 4) |
| GET | `/keys/status` | API key pool health |

### Orchestration

| Method | Path | Description |
|--------|------|-------------|
| POST | `/orchestrate` | Run full 5-agent pipeline |
| POST | `/orchestrate/uploaded` | Run pipeline with uploaded files |
| POST | `/orchestrate/grouped` | Batch-process multiple cases |
| POST | `/orchestrate/grouped/preview` | Preview batch index mapping |
| POST | `/orchestrate/demo` | Run pipeline with built-in demo data |

### Preprocessing

| Method | Path | Description |
|--------|------|-------------|
| POST | `/preprocess/error-code/generate` | Generate sample error logs |
| POST | `/preprocess/spec/resolve` | Parse spec from document or text |
| POST | `/preprocess/vision/diff-box` | Compute image diff bounding box |
| POST | `/models/vision/probe` | Test vision model capabilities |
| GET | `/demo-case` | Fetch pre-built demo request |

### PCB Analysis (standalone)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analysis/template` | Upload reference template image |
| GET | `/analysis/template` | Retrieve stored template |
| POST | `/analysis/analyze` | Analyze test image against template |

## Request Shape (`POST /orchestrate`)

```json
{
  "input": {
    "error_log": "[ERROR] I2C Bus Arbitration Lost ...",
    "spec_excerpt": "IPC-2221B Section 6.1 ...",
    "design_image": { "mime_type": "image/png", "file_path": "data/assets/template_board.png" },
    "tested_image": { "mime_type": "image/png", "file_path": "data/assets/tested_board.png" }
  },
  "options": {
    "model": "gemma-4-31b-it",
    "include_raw_agent_payloads": true
  }
}
```

Either `spec_excerpt` (direct text) or `spec_document_path` (PDF/TXT path) should be provided.

## Key Features

- **Multi-Agent Pipeline** — Five specialized agents with parallel fan-out (agents 2A/2B run concurrently via ThreadPoolExecutor)
- **Multi-Key Pool** — Round-robin API key rotation with rate-limit backoff and health tracking
- **OpenCV Diff Engine** — Pixel-level template-vs-tested comparison with morphological noise filtering, contour detection, and region merging; highlighted diff crops are composited into the final annotated image
- **Gemma 4 Models** — All agents run on Gemma 4; the frontend model selector lists only Gemma 4 models
- **Spec Parsing** — Supports PDF and plain-text specification documents with TOC extraction and section focus planning
- **Frontend Visualization** — Side-by-side image comparison with interactive bounding box overlays, staged agent reveal animation, and a diagnosis dashboard

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI app, CORS, router includes
│   ├── orchestrator.py       # Multi-agent pipeline execution
│   ├── agents.py             # Agent runner (prompt → Gemma → parse)
│   ├── gemini_client.py      # Multi-key Google AI client (Gemma) with retry
│   ├── key_pool.py           # Round-robin API key management
│   ├── config.py             # Settings from environment
│   ├── schemas.py            # Pydantic models
│   ├── prompts.py            # Agent prompts and JSON schemas
│   ├── diff_engine.py        # OpenCV diff detection
│   ├── vision_diff.py        # Diff engine wrapper
│   ├── image_annotation.py   # Pillow bounding-box rendering
│   ├── image_utils.py        # Image helpers (draw, composite, b64)
│   ├── analyzer.py           # Standalone PCB analysis pipeline
│   ├── spec_parser.py        # PDF/text spec extraction
│   ├── file_processing.py    # Upload parsing helpers
│   ├── utils.py              # Shared utilities
│   └── routes/
│       ├── health.py         # /health, /models, /keys/status
│       ├── orchestration.py  # /orchestrate endpoints
│       ├── preprocess.py     # /preprocess + /demo-case
│       └── analysis.py       # /analysis endpoints
├── front/
│   └── src/
│       ├── App.tsx
│       ├── api/              # API client + demo data
│       ├── stores/           # Zustand state management
│       ├── types/            # TypeScript interfaces
│       └── components/
│           ├── input/        # File upload panel
│           ├── pipeline/     # Agent pipeline visualization
│           ├── viewer/       # Image comparison + bounding boxes
│           ├── diagnosis/    # Root cause + resolution dashboard
│           ├── crossref/     # Spec-defect cross-reference
│           └── layout/       # Header, page layout
├── data/
│   ├── demo_case.json        # Pre-built demo request
│   └── assets/               # Demo board images
├── tests/                    # pytest suite (53 tests)
├── requirements.txt
└── .env                      # API keys + runtime settings
```

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

## Demo Data

- **Context docs:** `background.md`, `todo.md`, `example.md` — injected into all agent prompts
- **Assets:** `data/assets/template_board.png`, `data/assets/tested_board.png`
- **Demo request:** `data/demo_case.json`

## Model Policy

This project is built for a hackathon that requires **Gemma** models only. The supported models are `gemma-4-31b-it` (default) and `gemma-4-26b-a4b-it`, and the frontend model selector filters to Gemma 4. If the selected model fails, the error is surfaced rather than silently falling back to another model family.
