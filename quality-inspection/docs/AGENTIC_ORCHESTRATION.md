# Agentic Orchestration Design

## Pipeline

`Agent1 -> (Agent2A || Agent2B) -> Agent3 -> Agent4`

- Agent1 Symptom Analyzer
  - Input: `error_log`
  - Output: hypotheses + `handoff_message`
- Agent2A Spec Precheck (parallel)
  - Input: `spec_excerpt` + Agent1 output
  - Output: spec watch-list + `handoff_message`
- Agent2B CAD Mapper (parallel)
  - Input: design image + Agent1 output
  - Output: CAD part mapping with bounding boxes + `handoff_message`
- Agent3 Physical Defect Verifier
  - Input: tested image + Agent1/2A/2B outputs
  - Output: verified defect evidence, root-cause candidate, impact
- Agent4 Spec Compliance Resolver
  - Input: spec excerpt + Agent1/2A/2B/3 outputs
  - Output: final root cause + spec-grounded resolution actions

## Input/Output Separation

API response has strict separation:

- `input`: original runtime inputs used for orchestration
- `agent_trace`: each agent payload + handoff chain
- `output`: final user-facing diagnosis and actions

## Why this works for demo

- Real Gemini call path (no mock inference path required)
- Model auto-discovery via Gemini `models.list`
- Multi-key round-robin and key health tracking (`/keys/status`)
- Supports both static demo assets and real user-provided images
- Produces frontend-ready bounding box data

## Input Mapping Additions

- Error source:
  - `error_log` is direct input to Agent1
- Spec source:
  - `spec_excerpt` direct text path
  - `spec_document_path` PDF/TXT parsing path (keyword-based excerpt extraction)
- Vision source:
  - `design_image` + `tested_image` are passed to Gemini vision agents
  - image-diff heuristic computes `heuristic_diff_bbox` for red-box fallback
