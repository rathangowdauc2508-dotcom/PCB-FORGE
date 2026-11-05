"""
PCB parsing tool.

Tries, in order:
  1. KiCad's `pcbnew` Python API (only available if KiCad is installed on the
     host and its python bindings are on PYTHONPATH). This is the "real"
     path and is used automatically when available.
  2. A lightweight regex/text fallback parser that reads the raw
     S-expression `.kicad_pcb` file and extracts as much real geometry as it
     can (board outline bbox, layer count, footprint/pad/via/track/zone
     counts, trace widths, drill sizes, clearances).
No demo metrics are substituted for an unreadable uploaded file. Unknown
measurements stay null so downstream checks can report that they were not run.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

DEMO_ANALYSIS = {
    "board_width_mm": 80.0,
    "board_height_mm": 50.0,
    "area_mm2": 4000.0,
    "layers": 4,
    "components": 42,
    "footprints": 42,
    "pads": 168,
    "vias": 85,
    "tracks": 120,
    "zones": 3,
    "min_trace_width_mm": 0.15,
    "min_clearance_mm": 0.12,
    "min_drill_diameter_mm": 0.25,
    "board_edge_clearance_mm": 0.3,
    "source": "demo_fixture",
}


def _try_pcbnew(file_path: str) -> Optional[dict]:
    try:
        import pcbnew  # type: ignore
    except ImportError:
        return None

    try:
        board = pcbnew.LoadBoard(file_path)
        bbox = board.GetBoardEdgesBoundingBox()
        to_mm = 1e-6  # KiCad internal units are nanometers
        width = bbox.GetWidth() * to_mm
        height = bbox.GetHeight() * to_mm
        width = round(width, 2) if width > 0 else None
        height = round(height, 2) if height > 0 else None

        footprints = list(board.GetFootprints())
        pads = sum(len(fp.Pads()) for fp in footprints)
        tracks = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
        vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
        zones = list(board.Zones())

        min_trace = min((t.GetWidth() * to_mm for t in tracks), default=None)
        min_drill = min((v.GetDrillValue() * to_mm for v in vias), default=None)

        layers = board.GetCopperLayerCount()

        return {
            "board_width_mm": width,
            "board_height_mm": height,
            "area_mm2": round(width * height, 2) if width is not None and height is not None else None,
            "layers": layers,
            "components": len(footprints),
            "footprints": len(footprints),
            "pads": pads,
            "vias": len(vias),
            "tracks": len(tracks),
            "zones": len(zones),
            "min_trace_width_mm": round(min_trace, 3) if min_trace is not None else None,
            "min_clearance_mm": None,
            "min_drill_diameter_mm": round(min_drill, 3) if min_drill is not None else None,
            "board_edge_clearance_mm": None,
            "source": "pcbnew",
        }
    except Exception:
        return None


_LAYER_RE = re.compile(r"\(layers\b", re.IGNORECASE)
_LAYER_LINE_RE = re.compile(r'^\s*\(\d+\s+"?[\w.]+"?\s+\w+', re.MULTILINE)
_FOOTPRINT_RE = re.compile(r"\(footprint\s")
_PAD_RE = re.compile(r"\(pad\s")
_VIA_RE = re.compile(r"\(via\s")
_SEGMENT_RE = re.compile(r"\(segment\s")
_ZONE_RE = re.compile(r"\(zone\s")
# Scoped to (segment ...) / (via ...) lines specifically so board-edge or
# silkscreen stroke widths don't get misread as copper trace widths.
_TRACK_WIDTH_RE = re.compile(r"\(segment[^\n]*?\(width\s+([\d.]+)\)")
_VIA_DRILL_RE = re.compile(r"\(via[^\n]*?\(drill\s+([\d.]+)\)")
_XY_RE = re.compile(r"\((?:xy|start|end)\s+(-?[\d.]+)\s+(-?[\d.]+)\)")


def _edge_cut_coordinates(text: str) -> list[tuple[str, str]]:
    """Read coordinate pairs from balanced Edge.Cuts graphics blocks."""
    points: list[tuple[str, str]] = []
    for match in re.finditer(r"\(gr_(?:line|arc|rect|poly)\b", text):
        depth = 0
        quoted = False
        escaped = False
        end = match.start()
        for end in range(match.start(), len(text)):
            char = text[end]
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
                    end += 1
                    break
        block = text[match.start():end]
        if '"Edge.Cuts"' in block:
            points.extend(_XY_RE.findall(block))
    return points


def _extract_sexpr_block(text: str, start: int) -> str:
    """Return one balanced S-expression block, respecting quoted strings."""
    depth = 0
    quoted = False
    escaped = False
    for end in range(start, len(text)):
        char = text[end]
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
                return text[start:end + 1]
    return ""



def _parse_fallback(file_path: str) -> Optional[dict]:
    """A dependency-free text/regex parser for the KiCad S-expression format.

    This intentionally does not attempt to be a full S-expression parser
    (that's what pcbnew is for). It extracts coarse, still-real metrics by
    counting tokens and reading explicit (xy ..), (width ..), (drill ..)
    fields anywhere in the file, which is robust to formatting differences
    across KiCad versions.
    """
    try:
        text = Path(file_path).read_text(errors="ignore")
    except Exception:
        return None

    if "(kicad_pcb" not in text:
        return None

    footprints = len(_FOOTPRINT_RE.findall(text))
    pads = len(_PAD_RE.findall(text))
    vias = len(_VIA_RE.findall(text))
    tracks = len(_SEGMENT_RE.findall(text))
    zones = len(_ZONE_RE.findall(text))

    # Count copper layer names, not KiCad's numeric layer IDs. IDs such as
    # 36 (B.SilkS) are enum values, not a 36-layer board. Some inner copper
    # layers are marked `power` rather than `signal`, so accept either type.
    layers = 2
    layer_match = re.search(r"\(layers\b", text)
    if layer_match:
        layer_block = _extract_sexpr_block(text, layer_match.start())
        cu_layers = set(re.findall(r'\(\s*\d+\s+"([^"\s]+\.Cu)"\s+[\w-]+', layer_block))
        layers = max(2, len(cu_layers))

    widths = [float(w) for w in _TRACK_WIDTH_RE.findall(text)]
    drills = [float(d) for d in _VIA_DRILL_RE.findall(text)]

    # Fall back to a looser, unscoped search only if the scoped patterns
    # found nothing (e.g. a differently-formatted/older KiCad export where
    # segment/via blocks span multiple lines), so we still extract *some*
    # real measurement rather than silently defaulting.
    if not widths:
        widths = [float(w) for w in re.findall(r"\(width\s+([\d.]+)\)", text)]
    if not drills:
        drills = [float(d) for d in re.findall(r"\(drill\s+([\d.]+)\)", text)]

    # Board bounding box: gather all xy coordinates within Edge.Cuts blocks;
    # fall back to all coordinates in the file if none are found.
    edge_xy = _edge_cut_coordinates(text)
    if not edge_xy:
        edge_xy = _XY_RE.findall(text)[:500]  # cap for performance

    if edge_xy:
        xs = [float(x) for x, _ in edge_xy]
        ys = [float(y) for _, y in edge_xy]
        width = max(xs) - min(xs) if xs else None
        height = max(ys) - min(ys) if ys else None
    else:
        width = None
        height = None

    if width is not None and width <= 0:
        width = None
    if height is not None and height <= 0:
        height = None

    result = {
        "board_width_mm": round(width, 2) if width is not None else None,
        "board_height_mm": round(height, 2) if height is not None else None,
        "area_mm2": round(width * height, 2) if width is not None and height is not None else None,
        "layers": layers,
        "components": footprints,
        "footprints": footprints,
        "pads": pads,
        "vias": vias,
        "tracks": tracks,
        "zones": zones,
        "min_trace_width_mm": round(min(widths), 3) if widths else None,
        "min_clearance_mm": None,
        "min_drill_diameter_mm": round(min(drills), 3) if drills else None,
        "board_edge_clearance_mm": None,
        "source": "fallback_parser",
    }

    # If the fallback parser found essentially nothing useful (e.g. an
    # unreadable/binary file was uploaded), treat it as a failure so the
    # caller can drop to the demo fixture instead of showing all-zero data.
    if footprints == 0 and pads == 0 and tracks == 0 and not edge_xy:
        return None

    return result


def analyze_pcb_file(file_path: str) -> dict:
    """Analyze actual board content or fail clearly; never substitute demo metrics."""
    result = _try_pcbnew(file_path)
    if result:
        return result

    result = _parse_fallback(file_path)
    if result:
        return result

    raise ValueError("The uploaded KiCad board could not be parsed. No sample-board values were substituted.")
