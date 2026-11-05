from __future__ import annotations

from .utils import truncate_text

# ---------------------------------------------------------------------------
# PCB crop-level prompts (ported from pcb-analysis/backend/src/prompts.py)
# ---------------------------------------------------------------------------

CROP_CLASSIFICATION_PROMPT = """You are an expert electronics inspector specializing in Arduino Uno R3 boards.

You are given two images of the same cropped region:
1. The FIRST image is the raw crop from the test board.
2. The SECOND image is the same crop with a magenta/pink overlay highlighting pixels that differ from the known-good reference.

Use the highlighted image to understand WHERE the difference is, but describe the defect based on what you see in the RAW image. Do NOT mention the magenta overlay or highlighting in your description.

Classify the defect:

1. **defect_type**: MUST be exactly one of these four values: "missing_hole", "mouse_bite", "open_circuit", "short". No other values are allowed.
2. **description**: A brief description of the actual defect visible in the raw image.
3. **severity**: One of "low" (cosmetic, unlikely to affect function), "medium" (may affect reliability), or "high" (will cause board failure).

Return your analysis as structured JSON matching the provided schema."""

ANNOTATE_CROP_PROMPT = """You are an image editor. Draw a labeled bounding box on this cropped region of an Arduino Uno R3 board to mark the following defect.

Draw a clearly visible colored rectangle around the defect area within this crop. Place a text label just above the box with the defect type and severity. Use a bright color (e.g., red, cyan, magenta, yellow). Make the box 3 pixels thick. The label should have a filled background matching the box color with black text.

Defect to annotate:
- Type: {defect_type}
- Severity: {severity}
- Description: {description}

Return ONLY the edited image with the bounding box and label drawn. Do not alter the original image content — only add the annotation overlay."""


def base_context(background: str, todo: str, example: str) -> str:
    return (
        "You are part of a 4-agent hardware validation system for a hackathon demo.\n"
        "Flow is fixed: Agent1 -> (Agent2A Spec Precheck || Agent2B CAD Mapper) -> Agent3 -> Agent4.\n"
        "Be concise and evidence-driven. Avoid speculative narration.\n"
        "Always return schema-conformant JSON only.\n"
        "Stay concrete, avoid generic advice, and keep references tied to the provided evidence.\n\n"
        f"[HACKATHON BACKGROUND]\n{truncate_text(background, 2500)}\n\n"
        f"[PROJECT TODO / PITCH DIRECTION]\n{truncate_text(todo, 2000)}\n\n"
        f"[EXAMPLE DATA STRATEGY]\n{truncate_text(example, 2000)}"
    )


SYMPTOM_SCHEMA = {
    "type": "object",
    "properties": {
        "error_interpretation": {"type": "string"},
        "spec_navigation": {
            "type": "object",
            "properties": {
                "error_log_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "top_focus_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "toc_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["top_focus_sections", "toc_sections"],
        },
        "suspect_parts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_name": {"type": "string"},
                    "likely_fault_mode": {"type": "string"},
                    "why_related": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["part_name", "likely_fault_mode", "why_related", "confidence"],
            },
        },
        "handoff_message": {"type": "string"},
    },
    "required": ["error_interpretation", "spec_navigation", "suspect_parts", "handoff_message"],
}


SPEC_PRECHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "spec_watchlist": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "what_to_check": {"type": "string"},
                    "why_relevant": {"type": "string"},
                    "priority": {"type": "string"},
                },
                "required": ["rule_id", "what_to_check", "why_relevant", "priority"],
            },
        },
        "spec_risk_summary": {"type": "string"},
        "handoff_message": {"type": "string"},
    },
    "required": ["spec_watchlist", "spec_risk_summary", "handoff_message"],
}


DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "cad_mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_name": {"type": "string"},
                    "schematic_reference": {"type": "string"},
                    "reason": {"type": "string"},
                    "bbox": {
                        "type": "object",
                        "properties": {
                            "x1": {"type": "integer"},
                            "y1": {"type": "integer"},
                            "x2": {"type": "integer"},
                            "y2": {"type": "integer"},
                        },
                        "required": ["x1", "y1", "x2", "y2"],
                    },
                },
                "required": ["part_name", "schematic_reference", "reason", "bbox"],
            },
        },
        "handoff_message": {"type": "string"},
    },
    "required": ["cad_mappings", "handoff_message"],
}


PHYSICAL_SCHEMA = {
    "type": "object",
    "properties": {
        "defect_verification": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_name": {"type": "string"},
                    "defect_type": {"type": "string"},
                    "evidence": {"type": "string"},
                    "crop_note": {"type": "string"},
                    "confidence": {"type": "number"},
                    "bbox": {
                        "type": "object",
                        "properties": {
                            "x1": {"type": "integer"},
                            "y1": {"type": "integer"},
                            "x2": {"type": "integer"},
                            "y2": {"type": "integer"},
                        },
                        "required": ["x1", "y1", "x2", "y2"],
                    },
                },
                "required": ["part_name", "defect_type", "evidence", "crop_note", "confidence", "bbox"],
            },
        },
        "root_cause_candidate": {"type": "string"},
        "impact": {"type": "string"},
        "handoff_message": {"type": "string"},
    },
    "required": ["defect_verification", "root_cause_candidate", "impact", "handoff_message"],
}


SPEC_FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "spec_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "rule_text": {"type": "string"},
                    "compliance_status": {"type": "string"},
                    "gap": {"type": "string"},
                },
                "required": ["rule_id", "rule_text", "compliance_status", "gap"],
            },
        },
        "final_root_cause": {"type": "string"},
        "final_resolution": {
            "type": "array",
            "items": {"type": "string"},
        },
        "final_confidence": {"type": "number"},
    },
    "required": ["spec_checks", "final_root_cause", "final_resolution", "final_confidence"],
}


def symptom_prompt(*, context: str, error_log: str, spec_focus_plan: str | None = None) -> str:
    focus_block = ""
    if spec_focus_plan:
        focus_block = f"[SPEC_NAVIGATION_PLAN]\n{truncate_text(spec_focus_plan, 3000)}\n\n"

    return (
        f"{context}\n\n"
        "[ROLE]\n"
        "Agent1: Error Interpreter.\n"
        "From error code/log and structured spec TOC plan, identify likely circuit parts that can cause this error.\n\n"
        "[INPUT]\n"
        f"error_log:\n{error_log}\n\n"
        f"{focus_block}"
        "[TASK]\n"
        "1) Use error log + toc plan and emit `spec_navigation.top_focus_sections` (inspection priority based on TOC).\n"
        "2) Emit `spec_navigation.toc_sections` for at least 3 sections you will inspect first.\n"
        "3) Use provided TOC entry text and section excerpts as evidence when selecting parts.\n"
        "4) Map suspected parts/components with concrete hardware terms.\n"
        "5) Return suspect circuit parts and handoff as JSON-conformant text."
    )


def spec_precheck_prompt(*, context: str, spec_excerpt: str, symptom_result: dict) -> str:
    return (
        f"{context}\n\n"
        "[ROLE]\n"
        "Agent2A: Spec Precheck (parallel).\n"
        "Using spec text and Agent1 output, build a practical inspection watchlist.\n\n"
        "[INPUT]\n"
        f"symptom_result_json:\n{symptom_result}\n\n"
        f"spec_excerpt:\n{spec_excerpt}\n\n"
        "[TASK]\n"
        "Return concrete rule-based checks and priority for downstream physical verification."
    )


def design_prompt(*, context: str, symptom_result: dict, heuristic_bbox: dict | None, design_reference_text: str | None = None) -> str:
    input_sections = [
        f"symptom_result_json:\n{symptom_result}",
        f"heuristic_diff_bbox_hint:\n{heuristic_bbox}",
    ]
    if design_reference_text:
        input_sections.insert(
            0,
            f"[DESIGN_REFERENCE_TEXT]\n{truncate_text(design_reference_text, 2200)}",
        )

    joined_inputs = "\n\n".join(input_sections)

    return (
        f"{context}\n\n"
        "[ROLE]\n"
        "Agent2B: CAD Mapper (parallel).\n"
        "Map suspect parts to actual regions in CAD/schematic image.\n\n"
        "[INPUT]\n"
        f"{joined_inputs}\n\n"
        "[TASK]\n"
        "Return CAD part mappings with bounding boxes and handoff for physical verification."
    )


def physical_prompt(
    *,
    context: str,
    symptom_result: dict,
    spec_precheck_result: dict,
    design_result: dict,
    heuristic_bbox: dict | None,
) -> str:
    return (
        f"{context}\n\n"
        "[ROLE]\n"
        "Agent3: Physical Vision.\n"
        "Inspect tested-board image, zoom into CAD-mapped regions, and verify actual defects.\n\n"
        "[INPUT]\n"
        f"symptom_result_json:\n{symptom_result}\n\n"
        f"spec_precheck_result_json:\n{spec_precheck_result}\n\n"
        f"design_result_json:\n{design_result}\n\n"
        f"heuristic_diff_bbox_hint:\n{heuristic_bbox}\n\n"
        "[TASK]\n"
        "For each candidate area, verify defect type/evidence and provide root cause candidate + impact + handoff."
    )


def spec_final_prompt(
    *,
    context: str,
    spec_excerpt: str,
    physical_result: dict,
    design_result: dict,
    spec_precheck_result: dict,
    symptom_result: dict,
) -> str:
    return (
        f"{context}\n\n"
        "[ROLE]\n"
        "Agent4: Spec Resolver.\n"
        "Based on verified defect, produce spec-grounded final diagnosis and resolution.\n\n"
        "[INPUT]\n"
        f"symptom_result_json:\n{symptom_result}\n\n"
        f"spec_precheck_result_json:\n{spec_precheck_result}\n\n"
        f"design_result_json:\n{design_result}\n\n"
        f"physical_result_json:\n{physical_result}\n\n"
        f"spec_excerpt:\n{spec_excerpt}\n\n"
        "[TASK]\n"
        "Output spec checks, final root cause, and spec-grounded actionable fix list."
    )
