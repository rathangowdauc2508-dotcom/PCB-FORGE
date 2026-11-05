"""Extract REAL component data from a .kicad_pcb file.

Why this exists
---------------
The original BOM was synthesized from a fixed template using only the
component COUNT, so every board with >= 9 components produced an identical
parts list. That made the BOM look fake and, worse, it claimed synthetic
parts came from the user's board.

This module reads the actual `(footprint "...")` entries out of the KiCad
S-expression file, together with each footprint's Reference (R1, C2, U3) and
Value property when present. Different boards now produce different BOMs,
because the data genuinely comes from the file.

Nothing here is invented: if a footprint cannot be matched to the local parts
database, it is still listed, with its real reference designator and an
explicitly ESTIMATED cost derived from its package class.
"""
from __future__ import annotations

import re
from pathlib import Path

# (footprint "Library:Name" ...) or (footprint "Name" ...)
_FOOTPRINT_START_RE = re.compile(r'(?m)^\s*\(footprint\s+"([^"]+)"')
# KiCad 6/7/8: (property "Reference" "R1")   KiCad 5: (fp_text reference R1 ...)
_PROP_RE = re.compile(r'\(property\s+"(Reference|Value)"\s+"([^"]*)"')
_FP_TEXT_RE = re.compile(r'\(fp_text\s+(reference|value)\s+"?([^\s")]+)"?')


def _read_sexp_block(text: str, start: int) -> str:
    """Read one balanced S-expression while respecting quoted strings."""
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return text[start:]

def extract_components(file_path: str) -> list[dict]:
    """Return [{footprint, reference, value}] read from the actual PCB file.

    Returns [] when the file cannot be read or contains no footprints; the
    uploaded-board BOM path surfaces that as a clear analysis error.
    """
    try:
        text = Path(file_path).read_text(errors="ignore")
    except Exception:
        return []

    if "(kicad_pcb" not in text:
        return []

    components: list[dict] = []
    for match in _FOOTPRINT_START_RE.finditer(text):
        name = match.group(1)
        block = _read_sexp_block(text, match.start())

        reference, value = "", ""
        for prop, val in _PROP_RE.findall(block):
            if prop == "Reference":
                reference = val
            elif prop == "Value":
                value = val
        if not reference or not value:
            for kind, val in _FP_TEXT_RE.findall(block):
                if kind == "reference" and not reference:
                    reference = val
                elif kind == "value" and not value:
                    value = val

        # Strip "Library:" prefix if present.
        short = name.split(":")[-1]
        components.append({
            "footprint": short,
            "reference": reference,
            "value": value or short,
        })

    return components


# Rough package-class cost estimates (USD) for parts not in the local DB.
# Clearly ESTIMATES - surfaced as such in the BOM, never as a real quote.
_CLASS_COSTS = [
    (re.compile(r"^(R|R_)\d|resistor", re.I), 0.01, "Resistor"),
    (re.compile(r"^(C|C_)\d|capacitor", re.I), 0.02, "Capacitor"),
    (re.compile(r"^L_|inductor", re.I), 0.05, "Inductor"),
    (re.compile(r"LED", re.I), 0.08, "LED"),
    (re.compile(r"Diode|SOD", re.I), 0.06, "Diode"),
    (re.compile(r"USB", re.I), 0.85, "USB connector"),
    (re.compile(r"Crystal|XTAL|OSC", re.I), 0.45, "Crystal/oscillator"),
    (re.compile(r"Conn|Header|JST|Pin", re.I), 0.30, "Connector"),
    (re.compile(r"SOT|SOIC|QFN|QFP|BGA|TSSOP", re.I), 0.60, "Integrated circuit"),
]


def classify(footprint: str, value: str) -> tuple[float, str]:
    """Best-effort package classification -> (estimated unit cost, description)."""
    target = f"{footprint} {value}"
    for pattern, cost, label in _CLASS_COSTS:
        if pattern.search(target):
            return cost, f"{label} (cost estimated from package type)"
    return 0.25, "Unclassified part (cost estimated)"
