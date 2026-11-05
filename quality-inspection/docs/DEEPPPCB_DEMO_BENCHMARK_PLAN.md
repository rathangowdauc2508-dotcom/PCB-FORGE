# DeepPCB Demo Scenario + Benchmark Plan

## 1) Goal

Prove that the orchestration backend works with real Gemini API calls on DeepPCB pairs (template/test + GT boxes), not only toy data.

## 2) Demo Scenario (single-case live demo)

1. Input `error_log` (auto-generated from defect class template)
2. Agent1 extracts suspect circuit parts from the error code
3. Parallel branch:
   - Agent2A does spec precheck watch-list from spec text
   - Agent2B maps suspect parts on CAD/template image
4. Agent3 verifies defect on tested image using mapped regions + crop evidence
5. Agent4 validates against spec and outputs final root cause + resolution

Display in UI:
- Left: inputs (error/spec/template/tested)
- Center: agent trace with handoff
- Right: red-boxed defect + final resolution checklist

## 3) Input Mapping

### Error code generation

Use class-driven templates tied to DeepPCB class labels:
- open -> continuity break log
- short -> conductive bridge log
- mousebite -> edge copper loss log
- spur -> protrusion clearance risk log
- spurious copper -> residue bridge risk log
- pin-hole -> local copper void risk log

### Spec input

Use `data/specs/deeppcb_demo_spec_v1.md` as demo spec pack:
- reference families: IPC-2221, IPC-A-600, IPC-6012
- include defect-oriented rule blocks keyed by class terms

### CAD / tested image

- CAD input: `_temp.jpg`
- tested input: `_test.jpg`
- GT: `*_not/*.txt` (x1 y1 x2 y2 class_id)

## 4) Benchmark Protocol

Dataset:
- DeepPCB (paired template/test + bbox + class)

Sampling:
- default `per_class=1` and `max_cases=6` for fast live benchmark
- optional larger run for offline validation (`max_cases=24` etc.)

Execution:
- run full orchestration per case with real API calls
- each case stores model used, latency, trace completeness

Metrics (IoU threshold = 0.33):
- localization precision / recall / F1
- class-aware precision / recall / F1
- success rate and average latency
- model usage distribution and key-pool status

## 5) Commands

```bash
source .venv/bin/activate
PYTHONPATH=. python tools/benchmark_deeppcb_orchestration.py --max-cases 6 --per-class 1
```

Optional larger run:

```bash
PYTHONPATH=. python tools/benchmark_deeppcb_orchestration.py --max-cases 24 --per-class 2
```

## 6) Output Artifacts

- JSON report: `data/benchmarks/deeppcb_orchestration_*.json`
- Summary markdown: `data/benchmarks/deeppcb_orchestration_*.md`

Use these artifacts directly in hackathon submission evidence.
