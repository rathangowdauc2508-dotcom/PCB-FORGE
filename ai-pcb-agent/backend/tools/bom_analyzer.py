"""BOM / component analysis.

WHAT CHANGED
------------
Previously the BOM was synthesized from a fixed template using only the
component COUNT, so every board with >= 9 components produced an IDENTICAL
parts list. It also implied that the synthetic parts came from the uploaded
board, which was not true.

Now the BOM is built from the actual footprints in the uploaded .kicad_pcb
(see tools/component_extractor.py):

  * footprints are grouped by type and counted -> real quantities
  * parts matched in data/components.json use that catalogue's real pricing,
    availability and alternatives
  * unmatched parts are still listed, with their real footprint name and an
    ESTIMATED cost derived from package class, clearly labelled

Uploaded boards never receive the demo template as a substitute. If their
footprints cannot be read, the analysis reports that clearly.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from models import BOMItem, BOMResult, Availability
from tools.component_extractor import classify

_DATA_PATH = Path(__file__).parent.parent / "data" / "components.json"
_COMPONENTS = json.loads(_DATA_PATH.read_text())

_TEMPLATE_ORDER = [
    ("STM32F401RET6", 1), ("AMS1117-3.3", 1), ("DRV8833", 1), ("MPU6050", 1),
    ("USB-C-16P", 1), ("XYZ123-CUSTOM", 1), ("SN74LVC1G17", 2),
    ("0402-RES", 1), ("0402-CAP", 1),
]

# Map common KiCad footprint names onto catalogue part numbers.
_FOOTPRINT_ALIASES = {
    "R_0402": "0402-RES",
    "C_0402": "0402-CAP",
    "USB_C_Receptacle": "USB-C-16P",
}


def _catalogue_lookup(footprint: str, value: str):
    for candidate in (value, footprint, _FOOTPRINT_ALIASES.get(footprint, "")):
        if candidate and candidate in _COMPONENTS:
            return candidate, _COMPONENTS[candidate]
    return None, None


def analyze_bom_from_components(components: list[dict]) -> BOMResult:
    """Build a BOM from real extracted footprints."""
    grouped = Counter((c["footprint"], c.get("value") or c["footprint"]) for c in components)

    refs_by_key: dict[tuple[str, str], list[str]] = {}
    for c in components:
        key = (c["footprint"], c.get("value") or c["footprint"])
        ref = c.get("reference")
        if ref:
            refs_by_key.setdefault(key, []).append(ref)

    items: list[BOMItem] = []
    estimated = 0

    for (footprint, value), qty in grouped.most_common():
        part_no, info = _catalogue_lookup(footprint, value)

        if info:
            description = info["description"]
            unit_cost = info["unit_cost_usd"]
            availability = Availability(info["availability"])
            alternatives = info["alternatives"]
            part_label = part_no
        else:
            estimated += 1
            unit_cost, description = classify(footprint, value)
            availability = Availability.AVAILABLE
            alternatives = []
            part_label = value or footprint

        refs = refs_by_key.get((footprint, value), [])
        if refs:
            shown = ", ".join(sorted(refs)[:6])
            if len(refs) > 6:
                shown += f" +{len(refs) - 6} more"
            description = f"{description} [{shown}]"

        items.append(BOMItem(
            part=part_label,
            description=description,
            quantity=qty,
            unit_cost_usd=unit_cost,
            availability=availability,
            alternatives=alternatives,
        ))

    total_cost = round(sum(i.unit_cost_usd * i.quantity for i in items), 2)
    risk_count = sum(1 for i in items if i.availability != Availability.AVAILABLE)

    return BOMResult(items=items, total_cost_usd=total_cost, risk_count=risk_count)


def analyze_bom_demo(component_count: int) -> BOMResult:
    """Template fallback, used ONLY when no footprints could be extracted."""
    items: list[BOMItem] = []
    remaining = max(component_count, 1)

    for part, base_qty in _TEMPLATE_ORDER:
        if remaining <= 0:
            break
        info = _COMPONENTS[part]
        qty = base_qty
        if part in ("0402-RES", "0402-CAP"):
            qty = max(remaining, base_qty)
        qty = min(qty, remaining)
        remaining -= qty
        items.append(BOMItem(
            part=part,
            description=f"[Demo/Sandbox BOM] {info['description']}",
            quantity=qty,
            unit_cost_usd=info["unit_cost_usd"],
            availability=Availability(info["availability"]),
            alternatives=info["alternatives"],
        ))

    total_cost = round(sum(i.unit_cost_usd * i.quantity for i in items), 2)
    risk_count = sum(1 for i in items if i.availability != Availability.AVAILABLE)
    return BOMResult(items=items, total_cost_usd=total_cost, risk_count=risk_count)


def analyze_bom(component_count: int, file_path: str | None = None) -> BOMResult:
    """Preferred entry point: derive from the real file when we have one."""
    if not file_path:
        return analyze_bom_demo(component_count)

    from tools.component_extractor import extract_components
    components = extract_components(file_path)
    if not components:
        raise ValueError(
            "No real footprints could be read from this KiCad board; a sample BOM was not substituted."
        )
    return analyze_bom_from_components(components)
