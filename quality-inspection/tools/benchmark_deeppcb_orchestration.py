from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.gemini_client import GeminiService
from app.orchestrator import OrchestrationEngine
from app.schemas import ImageInput, OrchestrationInput, OrchestrationOptions, OrchestrationRequest

CLASS_ID_TO_NAME = {
    1: "open",
    2: "short",
    3: "mousebite",
    4: "spur",
    5: "copper",
    6: "pin-hole",
}

ERROR_LOG_BY_CLASS = {
    1: "[ERROR] NET_OPEN_DETECTED - continuity break suspected on target trace path (open-circuit risk).",
    2: "[ERROR] NET_SHORT_DETECTED - adjacent nets show conductive bridge signature (short risk).",
    3: "[ERROR] EDGE_DAMAGE_MOUSEBITE - missing copper chunk on edge observed (mousebite risk).",
    4: "[ERROR] TRACE_SPUR_RISK - abnormal narrow protrusion may reduce clearance (spur risk).",
    5: "[ERROR] SPURIOUS_COPPER_RISK - residual copper fragment between intended traces detected.",
    6: "[ERROR] TRACE_PIN_HOLE_RISK - local copper void may degrade continuity/current path.",
}

KEYWORD_TO_CLASS = {
    "open": 1,
    "short": 2,
    "mousebite": 3,
    "mouse": 3,
    "spur": 4,
    "spurious": 5,
    "copper": 5,
    "pin-hole": 6,
    "pin hole": 6,
    "pinhole": 6,
}

REQUIRED_AGENT_IDS = ["agent_1", "agent_2a", "agent_2b", "agent_3", "agent_4"]


@dataclass
class BBox:
    x1: int
    y1: int
    x2: int
    y2: int
    class_id: int


@dataclass
class Case:
    case_id: str
    design_image_path: Path
    tested_image_path: Path
    gt_boxes: list[BBox]
    primary_class: int


def parse_annotation_file(path: Path) -> list[BBox]:
    boxes: list[BBox] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            continue
        x1, y1, x2, y2, class_id = map(int, parts)
        boxes.append(BBox(x1=x1, y1=y1, x2=x2, y2=y2, class_id=class_id))
    return boxes


def discover_cases(deeppcb_root: Path) -> list[Case]:
    cases: list[Case] = []
    for ann_path in deeppcb_root.glob("PCBData/*/*_not/*.txt"):
        base = ann_path.stem
        image_dir = ann_path.parent.parent / ann_path.parent.name.replace("_not", "")
        tested = image_dir / f"{base}_test.jpg"
        design = image_dir / f"{base}_temp.jpg"
        if not tested.exists() or not design.exists():
            continue

        gt_boxes = parse_annotation_file(ann_path)
        if not gt_boxes:
            continue

        primary_class = Counter([b.class_id for b in gt_boxes]).most_common(1)[0][0]
        cases.append(
            Case(
                case_id=base,
                design_image_path=design,
                tested_image_path=tested,
                gt_boxes=gt_boxes,
                primary_class=primary_class,
            )
        )
    return cases


def select_cases(cases: list[Case], *, per_class: int, seed: int, max_cases: int) -> list[Case]:
    rng = random.Random(seed)
    by_class: dict[int, list[Case]] = defaultdict(list)
    for case in cases:
        by_class[case.primary_class].append(case)

    selected: list[Case] = []
    for class_id in sorted(by_class.keys()):
        pool = by_class[class_id][:]
        rng.shuffle(pool)
        selected.extend(pool[:per_class])

    if len(selected) < max_cases:
        remaining = [c for c in cases if c not in selected]
        rng.shuffle(remaining)
        selected.extend(remaining[: max_cases - len(selected)])

    return selected[:max_cases]


def iou(a: dict[str, int], b: dict[str, int]) -> float:
    ix1 = max(a["x1"], b["x1"])
    iy1 = max(a["y1"], b["y1"])
    ix2 = min(a["x2"], b["x2"])
    iy2 = min(a["y2"], b["y2"])

    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    area_a = max(1, (a["x2"] - a["x1"]) * (a["y2"] - a["y1"]))
    area_b = max(1, (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]))
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def infer_class_id(text: str) -> int | None:
    lower = text.lower()
    for key, class_id in KEYWORD_TO_CLASS.items():
        if key in lower:
            return class_id
    return None


def match_metrics(
    gt_boxes: list[dict[str, int]],
    pred_boxes: list[dict[str, int | None]],
    *,
    iou_threshold: float,
    class_aware: bool,
) -> dict[str, int]:
    used_preds: set[int] = set()
    tp = 0

    for gt in gt_boxes:
        best_idx = None
        best_iou = 0.0
        for idx, pred in enumerate(pred_boxes):
            if idx in used_preds:
                continue
            if class_aware:
                pred_class = pred.get("class_id")
                if pred_class is None or pred_class != gt["class_id"]:
                    continue
            cur = iou(gt, pred)
            if cur >= iou_threshold and cur > best_iou:
                best_iou = cur
                best_idx = idx

        if best_idx is not None:
            tp += 1
            used_preds.add(best_idx)

    fp = len(pred_boxes) - tp
    fn = len(gt_boxes) - tp
    return {"tp": tp, "fp": fp, "fn": fn}


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp > 0 else 0.0
    recall = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def run_case(
    *,
    engine: OrchestrationEngine,
    case: Case,
    spec_path: Path,
    model: str | None,
    include_raw_agent_payloads: bool,
) -> dict[str, Any]:
    error_log = ERROR_LOG_BY_CLASS.get(case.primary_class, ERROR_LOG_BY_CLASS[2])

    request = OrchestrationRequest(
        input=OrchestrationInput(
            error_log=error_log,
            spec_document_path=str(spec_path),
            design_image=ImageInput(mime_type="image/jpeg", file_path=str(case.design_image_path)),
            tested_image=ImageInput(mime_type="image/jpeg", file_path=str(case.tested_image_path)),
        ),
        options=OrchestrationOptions(
            model=model,
            include_raw_agent_payloads=include_raw_agent_payloads,
        ),
    )

    response = engine.run(request)

    gt = [
        {"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2, "class_id": b.class_id}
        for b in case.gt_boxes
    ]

    inferred_from_root = infer_class_id(response.output.root_cause)
    preds = []
    for box in response.output.bounding_boxes:
        class_id = infer_class_id(box.label) or inferred_from_root
        preds.append(
            {
                "x1": box.x1,
                "y1": box.y1,
                "x2": box.x2,
                "y2": box.y2,
                "class_id": class_id,
            }
        )

    loc = match_metrics(gt, preds, iou_threshold=0.33, class_aware=False)
    cls = match_metrics(gt, preds, iou_threshold=0.33, class_aware=True)

    trace_ids = [row.agent_id for row in response.agent_trace]
    orchestration_ok = all(agent_id in trace_ids for agent_id in REQUIRED_AGENT_IDS)

    return {
        "case_id": case.case_id,
        "primary_class": case.primary_class,
        "primary_class_name": CLASS_ID_TO_NAME.get(case.primary_class, "unknown"),
        "gt_count": len(gt),
        "pred_count": len(preds),
        "model_used": response.model_used,
        "started_at": response.started_at.isoformat(),
        "ended_at": response.ended_at.isoformat(),
        "latency_sec": (response.ended_at - response.started_at).total_seconds(),
        "orchestration_trace_ids": trace_ids,
        "orchestration_ok": orchestration_ok,
        "localization": loc,
        "class_aware": cls,
        "root_cause": response.output.root_cause,
        "resolution": response.output.resolution,
    }


def write_markdown_summary(path: Path, payload: dict[str, Any]) -> None:
    lines = []
    lines.append(f"# DeepPCB Benchmark Summary ({payload['run_at_utc']})")
    lines.append("")
    lines.append(f"- Total cases: {payload['summary']['total_cases']}")
    lines.append(f"- Success cases: {payload['summary']['success_cases']}")
    lines.append(f"- Failed cases: {payload['summary']['failed_cases']}")
    lines.append(f"- Avg latency (sec): {payload['summary']['avg_latency_sec']:.2f}")
    lines.append(f"- Model usage: {payload['summary']['model_usage']}")
    lines.append("")
    loc = payload["summary"]["localization_prf"]
    cls = payload["summary"]["class_aware_prf"]
    lines.append("## Metrics (IoU >= 0.33)")
    lines.append("")
    lines.append(f"- Localization P/R/F1: {loc['precision']:.3f} / {loc['recall']:.3f} / {loc['f1']:.3f}")
    lines.append(f"- Class-aware P/R/F1: {cls['precision']:.3f} / {cls['recall']:.3f} / {cls['f1']:.3f}")
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    for row in payload["cases"]:
        if row.get("error"):
            lines.append(f"- {row['case_id']}: FAILED ({row['error']})")
            continue
        lines.append(
            f"- {row['case_id']} [{row['primary_class_name']}]: "
            f"model={row['model_used']} loc(tp/fp/fn)={row['localization']['tp']}/{row['localization']['fp']}/{row['localization']['fn']} "
            f"cls(tp/fp/fn)={row['class_aware']['tp']}/{row['class_aware']['fp']}/{row['class_aware']['fn']} "
            f"latency={row['latency_sec']:.2f}s"
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real Gemini orchestration benchmark on DeepPCB samples")
    parser.add_argument("--deeppcb-root", default="data/external/DeepPCB", help="Path to DeepPCB root")
    parser.add_argument("--spec-path", default="data/specs/deeppcb_demo_spec_v1.md", help="Spec document path")
    parser.add_argument("--max-cases", type=int, default=6)
    parser.add_argument("--per-class", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default=None, help="Force specific model. If omitted, orchestrator fallback policy is used")
    parser.add_argument("--include-raw-agent-payloads", action="store_true")
    args = parser.parse_args()

    deeppcb_root = Path(args.deeppcb_root).resolve()
    spec_path = Path(args.spec_path).resolve()

    if not deeppcb_root.exists():
        raise SystemExit(f"DeepPCB path not found: {deeppcb_root}")
    if not spec_path.exists():
        raise SystemExit(f"Spec path not found: {spec_path}")

    settings = get_settings()
    if not settings.gemini_api_keys:
        raise SystemExit("No Gemini API keys configured in .env")

    service = GeminiService(api_keys=settings.gemini_api_keys, request_timeout_sec=settings.request_timeout_sec)
    engine = OrchestrationEngine(settings=settings, gemini_service=service)

    all_cases = discover_cases(deeppcb_root)
    selected = select_cases(all_cases, per_class=args.per_class, seed=args.seed, max_cases=args.max_cases)

    run_at = datetime.now(tz=UTC)
    case_results: list[dict[str, Any]] = []

    for idx, case in enumerate(selected, start=1):
        print(f"[{idx}/{len(selected)}] Running case {case.case_id} ({CLASS_ID_TO_NAME.get(case.primary_class)})")
        try:
            result = run_case(
                engine=engine,
                case=case,
                spec_path=spec_path,
                model=args.model,
                include_raw_agent_payloads=args.include_raw_agent_payloads,
            )
            case_results.append(result)
        except Exception as exc:
            case_results.append(
                {
                    "case_id": case.case_id,
                    "primary_class": case.primary_class,
                    "primary_class_name": CLASS_ID_TO_NAME.get(case.primary_class, "unknown"),
                    "error": str(exc),
                }
            )

    success_rows = [row for row in case_results if not row.get("error")]
    failed_rows = [row for row in case_results if row.get("error")]

    loc_tp = sum(row["localization"]["tp"] for row in success_rows)
    loc_fp = sum(row["localization"]["fp"] for row in success_rows)
    loc_fn = sum(row["localization"]["fn"] for row in success_rows)

    cls_tp = sum(row["class_aware"]["tp"] for row in success_rows)
    cls_fp = sum(row["class_aware"]["fp"] for row in success_rows)
    cls_fn = sum(row["class_aware"]["fn"] for row in success_rows)

    model_usage = Counter(row["model_used"] for row in success_rows)
    avg_latency = sum(row["latency_sec"] for row in success_rows) / len(success_rows) if success_rows else 0.0

    payload = {
        "run_at_utc": run_at.isoformat(),
        "config": {
            "deeppcb_root": str(deeppcb_root),
            "spec_path": str(spec_path),
            "max_cases": args.max_cases,
            "per_class": args.per_class,
            "seed": args.seed,
            "forced_model": args.model,
            "iou_threshold": 0.33,
        },
        "summary": {
            "total_cases": len(case_results),
            "success_cases": len(success_rows),
            "failed_cases": len(failed_rows),
            "avg_latency_sec": avg_latency,
            "model_usage": dict(model_usage),
            "localization_prf": prf(loc_tp, loc_fp, loc_fn),
            "class_aware_prf": prf(cls_tp, cls_fp, cls_fn),
            "key_pool_status": service.key_pool_status(),
        },
        "cases": case_results,
    }

    out_json = Path("data/benchmarks") / f"deeppcb_orchestration_{run_at.strftime('%Y%m%d_%H%M%S')}.json"
    out_md = out_json.with_suffix(".md")

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown_summary(out_md, payload)

    print(f"Saved JSON: {out_json}")
    print(f"Saved MD:   {out_md}")
    print("Summary:")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
