"""Extracted file processing helpers formerly in main.py.

Contains the inline Pydantic models for uploaded file handling and all
helper functions for text/PDF extraction, spec navigation bundle building,
and grouped-case index pairing.
"""
from __future__ import annotations

import base64
import json
import re
from io import BytesIO

from pydantic import BaseModel, Field
from pypdf import PdfReader

from .schemas import GroupedCasePreview, ImageInput, OrchestrationOptions
from .spec_parser import build_spec_navigation_report, select_relevant_spec_excerpt


# ---------------------------------------------------------------------------
# Pydantic models (previously inline in main.py)
# ---------------------------------------------------------------------------

class DemoRunOptions(BaseModel):
    model: str | None = None
    include_raw_agent_payloads: bool = True


class VisionProbeOptions(BaseModel):
    candidate_models: list[str] | None = None
    image_path: str | None = "data/assets/tested_board.png"


class ErrorCodeGenerateInput(BaseModel):
    symptom: str
    interface: str = "I2C"
    context: str | None = None
    model: str | None = None


class SpecResolveInput(BaseModel):
    error_log: str
    spec_excerpt: str | None = None
    spec_document_path: str | None = None


class VisionDiffInput(BaseModel):
    design_image: ImageInput
    tested_image: ImageInput


class UploadedFileInput(BaseModel):
    file_name: str | None = None
    mime_type: str
    base64_data: str


class UploadedOrchestrationInput(BaseModel):
    error_log_file: UploadedFileInput
    design_image_file: UploadedFileInput
    tested_image_file: UploadedFileInput
    spec_files: list[UploadedFileInput] = Field(default_factory=list)
    design_reference_files: list[UploadedFileInput] = Field(default_factory=list)
    spec_file: UploadedFileInput | None = None
    background_context: str | None = None
    todo_context: str | None = None
    example_context: str | None = None


class UploadedOrchestrationRequest(BaseModel):
    input: UploadedOrchestrationInput
    options: OrchestrationOptions = Field(default_factory=OrchestrationOptions)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _pick_index(items: list, idx: int, *, strict: bool, name: str) -> tuple[object, int]:
    if not items:
        raise ValueError(f"{name} is empty")
    if idx < len(items):
        return items[idx], idx
    if strict:
        raise ValueError(f"{name}[{idx}] is missing in strict_index_pairing mode")
    return items[-1], len(items) - 1


def _build_grouped_case_mappings(
    *,
    error_logs: list[str],
    design_images: list[ImageInput],
    tested_images: list[ImageInput],
    spec_excerpts: list[str],
    spec_document_paths: list[str],
    strict: bool,
) -> list[GroupedCasePreview]:
    case_count = max(
        len(error_logs),
        len(design_images),
        len(tested_images),
        len(spec_excerpts) if spec_excerpts else 1,
        len(spec_document_paths) if spec_document_paths else 1,
    )

    mappings: list[GroupedCasePreview] = []
    for idx in range(case_count):
        _, error_idx = _pick_index(error_logs, idx, strict=strict, name="error_logs")
        _, design_idx = _pick_index(design_images, idx, strict=strict, name="design_images")
        _, tested_idx = _pick_index(tested_images, idx, strict=strict, name="tested_images")

        spec_type = "spec_excerpt"
        spec_idx = 0
        if spec_excerpts:
            _, spec_idx = _pick_index(spec_excerpts, idx, strict=strict, name="spec_excerpts")
            spec_type = "spec_excerpt"
        elif spec_document_paths:
            _, spec_idx = _pick_index(
                spec_document_paths,
                idx,
                strict=strict,
                name="spec_document_paths",
            )
            spec_type = "spec_document_path"
        else:
            raise ValueError("Either spec_excerpts or spec_document_paths must be provided")

        mappings.append(
            GroupedCasePreview(
                case_index=idx,
                error_log_index=error_idx,
                design_image_index=design_idx,
                tested_image_index=tested_idx,
                spec_source_type=spec_type,
                spec_source_index=spec_idx,
            )
        )
    return mappings


def _decode_uploaded_text(file_input: UploadedFileInput) -> str:
    raw = base64.b64decode(file_input.base64_data)
    return raw.decode("utf-8", errors="ignore")


def _uploaded_file_is_pdf(file_input: UploadedFileInput) -> bool:
    file_name = (file_input.file_name or "").lower()
    return file_input.mime_type.lower() == "application/pdf" or file_name.endswith(".pdf")


def _extract_text_from_uploaded_file(file_input: UploadedFileInput) -> str:
    raw = base64.b64decode(file_input.base64_data)

    if _uploaded_file_is_pdf(file_input):
        try:
            reader = PdfReader(BytesIO(raw))
            return "\f".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return raw.decode("utf-8", errors="ignore")

    return raw.decode("utf-8", errors="ignore")


def _normalize_file_label(file_input: UploadedFileInput) -> str:
    return (file_input.file_name or "").lower().strip()


def _is_datasheet_candidate(file_input: UploadedFileInput) -> bool:
    file_name = _normalize_file_label(file_input)
    return file_name.endswith(".pdf") and "datasheet" in file_name


def _select_datasheet_inputs(file_inputs: list[UploadedFileInput]) -> list[UploadedFileInput]:
    datasheet_inputs = [f for f in file_inputs if _is_datasheet_candidate(f)]
    if datasheet_inputs:
        return datasheet_inputs
    return file_inputs


def _contains_toc_marker(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(r"\b(table of contents|contents|content|toc)\b", lowered)
    )


def _extract_spec_text_for_focus(file_input: UploadedFileInput) -> str:
    raw = base64.b64decode(file_input.base64_data)
    if not _is_datasheet_candidate(file_input):
        return _extract_text_from_uploaded_file(file_input)

    try:
        reader = PdfReader(BytesIO(raw))
        pages: list[str] = []
        toc_pages: list[str] = []
        for page in reader.pages:
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue
            pages.append(page_text)
            if _contains_toc_marker(page_text):
                toc_pages.append(page_text)

        if toc_pages:
            return "\f".join(toc_pages)
        if pages:
            return pages[0]
        return ""
    except Exception:
        return _extract_text_from_uploaded_file(file_input)


def _render_pdf_to_image_parts(file_input: UploadedFileInput, max_pages: int = 2) -> list[tuple[bytes, str]]:
    if not _uploaded_file_is_pdf(file_input):
        return []

    raw = base64.b64decode(file_input.base64_data)

    try:
        import pypdfium2
    except Exception:
        return []

    try:
        constructors = [
            lambda: pypdfium2.PdfDocument(stream=raw),
            lambda: pypdfium2.PdfDocument(BytesIO(raw)),
            lambda: pypdfium2.PdfDocument(raw),
        ]
        document = None
        for maker in constructors:
            try:
                document = maker()
                break
            except Exception:
                continue
        if document is None:
            return []

        parts: list[tuple[bytes, str]] = []
        page_count = min(len(document), max_pages) if hasattr(document, "__len__") else max_pages
        for page_idx in range(page_count):
            page = None
            try:
                page = document.get_page(page_idx)
            except Exception:
                try:
                    page = document[page_idx]
                except Exception:
                    continue

            if page is None:
                continue

            try:
                rendered = page.render(scale=2)
                pil_image = rendered.to_pil()
            except Exception:
                try:
                    bitmap = page.render().get_bitmap()
                    pil_image = bitmap.to_pil()
                except Exception:
                    continue

            buf = BytesIO()
            pil_image.save(buf, format="PNG")
            parts.append((buf.getvalue(), "image/png"))
        return parts
    except Exception:
        return []


def _format_spec_plan_file_report(source: str, plan: dict, *, max_toc: int = 16, max_excerpt: int = 5) -> str:
    toc_lines = plan.get("toc", [])
    selected = plan.get("selected_sections", [])
    selected_excerpts = plan.get("selected_section_excerpts", [])

    toc_preview = toc_lines[:max_toc]
    excerpt_preview = selected_excerpts[:max_excerpt]

    return "\n".join(
        [
            f"## {source}",
            "",
            f"toc_candidates: {len(toc_lines)}",
            f"top_selected_sections: {selected[:3]}",
            "selected_excerpt_blocks:",
            *(f"{block}" for block in excerpt_preview),
            "toc_preview:",
            *(f"{entry['id']}. {entry['title']}" for entry in toc_preview),
        ]
    )


def _tokenize_error_terms(error_log: str) -> list[str]:
    return sorted({
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_\-]{3,}", error_log)
        if not token.isdigit()
    })


def _build_spec_navigation_bundle(
    file_inputs: list[UploadedFileInput],
    *,
    error_log: str,
) -> tuple[str, str, list[tuple[bytes, str]]]:
    if not file_inputs:
        raise ValueError("At least one spec file must be provided.")

    excerpts: list[str] = []
    focus_sections: list[str] = []
    toc_reports: list[dict] = []
    source_reports: list[str] = []
    image_parts: list[tuple[bytes, str]] = []

    filtered_inputs = _select_datasheet_inputs(file_inputs)

    for idx, file_input in enumerate(filtered_inputs):
        source = (file_input.file_name or f"spec_{idx + 1}").strip()
        full_text = _extract_spec_text_for_focus(file_input)
        if not full_text.strip():
            continue

        plan = build_spec_navigation_report(full_text, error_log=error_log, max_sections=6)
        plan_excerpt = select_relevant_spec_excerpt(full_text, error_log=error_log, max_chars=1200)
        if not plan_excerpt.strip():
            continue

        excerpts.append(f"--- {source} ---\n{plan_excerpt}")
        source_reports.append(_format_spec_plan_file_report(source, plan))

        for section in plan.get("selected_sections", []):
            normalized = section.strip()
            if normalized:
                focus_sections.append(normalized)
        toc_reports.append({"source": source, "toc": plan.get("toc", []), "selected_sections": plan.get("selected_sections", [])})
        image_parts.extend(_render_pdf_to_image_parts(file_input, max_pages=1))

    if not excerpts:
        raise ValueError("Uploaded spec files were empty or could not be parsed.")

    spec_excerpt = "\n\n".join(excerpts)
    spec_focus_payload = {
        "error_log_terms": sorted(_tokenize_error_terms(error_log)),
        "top_focus_sections": list(dict.fromkeys(focus_sections)),
        "source_reports": source_reports,
        "toc_reports": toc_reports,
    }
    return spec_excerpt, json.dumps(spec_focus_payload, ensure_ascii=False), image_parts


def _plain_excerpts_from_uploaded_files(file_inputs: list[UploadedFileInput]) -> str:
    excerpts: list[str] = []
    for idx, file_input in enumerate(file_inputs):
        text = _extract_text_from_uploaded_file(file_input).strip()
        if not text:
            continue
        source = (file_input.file_name or f"document_{idx + 1}").strip()
        excerpts.append(f"--- {source} ---\n{text}")
    return "\n\n".join(excerpts)
