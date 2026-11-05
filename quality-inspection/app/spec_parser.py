from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


def extract_spec_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "") for page in reader.pages]
        # Keep page boundaries to help identify TOC pages near the front.
        return "\f".join(pages)

    return path.read_text(encoding="utf-8")


def _tokenize_terms(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_\-]{3,}", text)
        if not token.isdigit()
    }


def _looks_like_toc_page_marker(text: str) -> bool:
    lowered = text.lower().strip()
    return bool(
        re.match(
            r"^(table of contents|contents|content|toc)\b",
            lowered,
        )
    )


def _split_text_lines_with_pages(spec_text: str) -> tuple[list[str], list[int], int]:
    pages = spec_text.split("\f")
    lines: list[str] = []
    line_pages: list[int] = []

    for page_index, page_text in enumerate(pages):
        for raw in page_text.splitlines():
            text = raw.strip()
            if not text:
                continue
            lines.append(text)
            line_pages.append(page_index)

    if not lines:
        return [], [], len(pages) or 1

    return lines, line_pages, len(pages)


def _extract_toc_candidates(lines: list[str], line_pages: list[int] | None = None) -> list[tuple[int, str]]:
    if not lines:
        return []

    if line_pages is None or len(line_pages) != len(lines):
        line_pages = list(range(len(lines)))

    page_count = max(line_pages) + 1 if line_pages else 1
    max_toc_pages = max(1, min(page_count, 8))
    toc_header_indices = [
        idx
        for idx, line in enumerate(lines)
        if line_pages[idx] < max_toc_pages and _looks_like_toc_page_marker(line)
    ]

    if not toc_header_indices:
        # Fall back to legacy full-document section parsing.
        candidates: list[tuple[int, str]] = []
        for i, raw in enumerate(lines):
            line = raw.strip()
            if not line:
                continue
            if re.match(r"^\d+(?:\.\d+)*\s+.+$", line):
                title = re.sub(r"\s{2,}.*$", "", line).strip()
                candidates.append((i, title))
        return candidates

    toc_start = toc_header_indices[0]
    toc_pages = {line_pages[idx] for idx in toc_header_indices}
    scan_window = lines[toc_start : toc_start + 320]

    candidates: list[tuple[int, str]] = []
    for i, raw in enumerate(scan_window, start=toc_start):
        if line_pages[i] not in toc_pages:
            continue

        line = raw.strip()
        if not line:
            continue

        is_toc_line = bool(
            re.match(r"^\d+(?:\.\d+)*\s+.+$", line)
            or re.match(r"^[A-Z][A-Z0-9 \-\/]+\s+\.*\s*\d+\s*$", line)
            or re.match(r".+\.+\s*\d+\s*$", line)
            or (line.startswith("-") and len(line) > 8)
        )
        if not is_toc_line:
            continue

        title = re.sub(r"\.+\s*\d+\s*$", "", line).strip(" .-")
        if title and len(title) > 3:
            candidates.append((i, title))

    return candidates


def _extract_section_text_by_title(lines: list[str], title: str, max_neighbors: int = 25) -> str:
    lower_title = title.lower()
    for idx, line in enumerate(lines):
        if lower_title in line.lower():
            start = max(0, idx - 2)
            end = min(len(lines), idx + max_neighbors + 1)
            return "\n".join(lines[start:end]).strip()

    if not lines:
        return ""
    # fallback: nearest keyword hit
    title_terms = {t for t in _tokenize_terms(title)}
    scored: tuple[int, int] | None = None
    for idx, line in enumerate(lines):
        lowered = line.lower()
        score = sum(1 for term in title_terms if term in lowered)
        if score > 0 and (scored is None or score > scored[0]):
            scored = (score, idx)
    if scored is None:
        return ""
    idx = scored[1]
    start = max(0, idx - 2)
    end = min(len(lines), idx + max_neighbors + 1)
    return "\n".join(lines[start:end]).strip()


def build_spec_navigation_report(spec_text: str, error_log: str, max_sections: int = 5) -> dict:
    lines, line_pages, _ = _split_text_lines_with_pages(spec_text)
    if not lines:
        return {
            "toc": [],
            "selected_sections": [],
            "selected_section_excerpts": [],
            "error_terms": sorted(_tokenize_terms(error_log)),
        }

    toc_candidates = _extract_toc_candidates(lines, line_pages=line_pages)
    term_counter = Counter(
        term.lower()
        for title_idx, title in toc_candidates
        for term in _tokenize_terms(title)
    )
    error_terms = _tokenize_terms(error_log)

    # score TOC entries by overlap with error tokens and keep the best matches
    scored: list[tuple[int, int, str]] = []
    for idx, title in toc_candidates:
        title_terms = _tokenize_terms(title)
        overlap = len(error_terms.intersection(title_terms))
        freq_bonus = sum(term_counter.get(term, 0) for term in title_terms if term in error_terms)
        score = overlap * 4 + freq_bonus
        scored.append((score, idx, title))

    scored.sort(key=lambda row: (-row[0], row[1]))
    selected_sections = [title for _, _line_idx, title in scored[:max_sections] if title]
    if not selected_sections:
        # Hard fallback: include top error tokens as broad section hints
        selected_sections = [token for token in sorted(error_terms)[:max_sections]]

    selected_section_excerpts = []
    for title in selected_sections:
        section_text = _extract_section_text_by_title(lines, title)
        if section_text:
            selected_section_excerpts.append(f"--- {title} ---\n{section_text}")

    toc = [
        {"id": str(i + 1), "title": title, "line": idx}
        for i, (idx, title) in enumerate(toc_candidates)
    ]

    return {
        "toc": toc,
        "selected_sections": selected_sections,
        "selected_section_excerpts": selected_section_excerpts,
        "error_terms": sorted(error_terms),
    }


def select_relevant_spec_excerpt(spec_text: str, error_log: str, max_chars: int = 2800) -> str:
    if not spec_text.strip():
        raise ValueError("Spec text is empty")

    lines = [line.strip() for line in spec_text.splitlines() if line.strip()]
    if not lines:
        return spec_text[:max_chars]

    plan = build_spec_navigation_report(spec_text=spec_text, error_log=error_log, max_sections=6)
    excerpts = [entry for entry in plan["selected_section_excerpts"] if entry.strip()]

    if not excerpts:
        keywords = _tokenize_terms(error_log)
        scored: list[tuple[int, int, str]] = []
        for idx, line in enumerate(lines):
            lowered = line.lower()
            score = sum(1 for kw in keywords if kw in lowered)
            if score > 0:
                scored.append((score, idx, line))

        if not scored:
            return spec_text[:max_chars]

        scored.sort(key=lambda row: (-row[0], row[1]))
        selected: list[str] = []
        used_indices: set[int] = set()
        for _, idx, _ in scored:
            for neighbor in (idx - 1, idx, idx + 1):
                if 0 <= neighbor < len(lines) and neighbor not in used_indices:
                    selected.append(lines[neighbor])
                    used_indices.add(neighbor)
            joined = "\n".join(selected)
            if len(joined) >= max_chars:
                return joined[:max_chars]
        return "\n".join(selected)[:max_chars]

    merged = "\n\n".join(excerpts)
    return merged[:max_chars]


def resolve_spec_excerpt(
    *,
    spec_excerpt: str | None,
    spec_document_path: str | None,
    error_log: str,
    root_dir: Path,
) -> str:
    if spec_excerpt and spec_excerpt.strip():
        return spec_excerpt

    if not spec_document_path:
        raise ValueError("Either spec_excerpt or spec_document_path must be provided")

    path = Path(spec_document_path)
    if not path.is_absolute():
        path = (root_dir / path).resolve()

    if not path.exists():
        raise ValueError(f"Spec document not found: {path}")

    full_text = extract_spec_text(path)
    return select_relevant_spec_excerpt(full_text, error_log)
