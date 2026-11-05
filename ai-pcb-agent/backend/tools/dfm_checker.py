"""
Deterministic DFM (Design for Manufacturability) rule engine.

CRITICAL PRINCIPLE: every measurement and pass/fail decision here is a plain
Python comparison against real numbers extracted by the PCB parser and the
chosen manufacturer's capability limits. Nothing here is invented by an LLM.
The LLM layer (llm_service.py) is only ever handed these *already computed*
facts and asked to explain them in plain English.
"""
from __future__ import annotations

from models import DFMCheck, DFMIssue, DFMResult, DFMStatus, PCBAnalysis, Severity, Manufacturer


def run_dfm_checks(pcb: PCBAnalysis, manufacturer: Manufacturer) -> DFMResult:
    issues: list[DFMIssue] = []
    checks: list[DFMCheck] = []

    def check(name: str, passed: bool | None):
        checks.append(DFMCheck(name=name, passed=passed))

    # 1. Minimum trace width
    trace_ok = None if pcb.min_trace_width_mm is None else pcb.min_trace_width_mm >= manufacturer.min_trace_width_mm
    check("Minimum trace width", trace_ok)
    if trace_ok is False:
        issues.append(DFMIssue(
            type="trace_width",
            severity=Severity.HIGH,
            actual=pcb.min_trace_width_mm,
            required=manufacturer.min_trace_width_mm,
            message=(
                f"Minimum trace width is {pcb.min_trace_width_mm} mm, below the "
                f"selected manufacturer's minimum of {manufacturer.min_trace_width_mm} mm."
            ),
        ))

    # 2. Minimum clearance
    clearance_ok = None if pcb.min_clearance_mm is None else pcb.min_clearance_mm >= manufacturer.min_clearance_mm
    check("Minimum clearance", clearance_ok)
    if clearance_ok is False:
        severity = Severity.HIGH if (manufacturer.min_clearance_mm - pcb.min_clearance_mm) > 0.02 else Severity.MEDIUM
        issues.append(DFMIssue(
            type="clearance",
            severity=severity,
            actual=pcb.min_clearance_mm,
            required=manufacturer.min_clearance_mm,
            message=(
                f"Clearance is {pcb.min_clearance_mm} mm while the selected "
                f"manufacturer's recommended minimum is {manufacturer.min_clearance_mm} mm."
            ),
        ))

    # 3. Minimum drill diameter
    drill_ok = None if pcb.min_drill_diameter_mm is None else pcb.min_drill_diameter_mm >= manufacturer.min_drill_diameter_mm
    check("Minimum drill diameter", drill_ok)
    if drill_ok is False:
        issues.append(DFMIssue(
            type="drill_diameter",
            severity=Severity.HIGH,
            actual=pcb.min_drill_diameter_mm,
            required=manufacturer.min_drill_diameter_mm,
            message=(
                f"Smallest drill diameter is {pcb.min_drill_diameter_mm} mm, below the "
                f"manufacturer's minimum drillable diameter of {manufacturer.min_drill_diameter_mm} mm."
            ),
        ))

    # 4. Board edge clearance (copper-to-edge)
    edge_ok = None if pcb.board_edge_clearance_mm is None else pcb.board_edge_clearance_mm >= 0.2
    check("Board edge clearance", edge_ok)
    if edge_ok is False:
        issues.append(DFMIssue(
            type="edge_clearance",
            severity=Severity.MEDIUM,
            actual=pcb.board_edge_clearance_mm,
            required=0.2,
            message=(
                f"Copper-to-edge clearance is {pcb.board_edge_clearance_mm} mm, below "
                "the recommended 0.2 mm safety margin."
            ),
        ))

    # 5. Layer compatibility
    layer_ok = pcb.layers <= manufacturer.max_layers
    check("Layer count compatibility", layer_ok)
    if not layer_ok:
        issues.append(DFMIssue(
            type="layer_count",
            severity=Severity.HIGH,
            actual=pcb.layers,
            required=manufacturer.max_layers,
            message=(
                f"Design uses {pcb.layers} layers, exceeding the manufacturer's "
                f"maximum of {manufacturer.max_layers} layers."
            ),
        ))

    # 6. Board dimensions (sane physical bounds, 5mm - 500mm per side)
    dims_ok = None if pcb.board_width_mm is None or pcb.board_height_mm is None else (
        5 <= pcb.board_width_mm <= 500 and 5 <= pcb.board_height_mm <= 500
    )
    check("Board dimensions within panel limits", dims_ok)
    if dims_ok is False:
        issues.append(DFMIssue(
            type="board_dimensions",
            severity=Severity.HIGH,
            actual=max(pcb.board_width_mm or 0, pcb.board_height_mm or 0),
            required=500,
            message="Board dimensions fall outside standard panel manufacturing limits (5-500 mm per side).",
        ))

    total_checks = len(checks)
    passed_checks = sum(1 for c in checks if c.passed is True)

    high_severity = any(i.severity == Severity.HIGH for i in issues)
    if high_severity:
        status = DFMStatus.FAIL
    elif issues or any(c.passed is None for c in checks):
        status = DFMStatus.WARNING
    else:
        status = DFMStatus.PASS

    return DFMResult(
        status=status,
        total_checks=total_checks,
        passed_checks=passed_checks,
        issues=issues,
        checks=checks,
    )
