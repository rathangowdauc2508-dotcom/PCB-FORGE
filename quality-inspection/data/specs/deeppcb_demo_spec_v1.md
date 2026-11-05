# DeepPCB Demo Spec Pack v1

This is a demo-oriented checklist derived from common PCB standards references.
Use this text as spec input for orchestration to produce traceable, standards-grounded resolutions.

## Referenced Standards (for demo mapping)

- IPC-2221: Generic Standard on Printed Board Design
- IPC-A-600: Acceptability of Printed Boards
- IPC-6012: Qualification and Performance Specification for Rigid Printed Boards

## Defect-Oriented Rule Checklist

[SPACING-SHORT-001]
When short or bridge-like behavior is observed, inspect conductor spacing, unintended copper bridges, and solder residues between adjacent nets.
Classify as short risk if conductive path exists across nets.

[OPEN-CIRCUIT-002]
When open-circuit or continuity break is observed, inspect cracks, etch over-removal, broken trace sections, or disconnected pad-to-trace transitions.
Classify as open risk if net continuity is interrupted.

[MOUSEBITE-EDGE-003]
When mousebite-like edge damage is observed, inspect board edge and trace boundaries for missing copper chunks causing irregular edge geometry.
Classify as mousebite risk if edge copper loss affects electrical clearance or continuity.

[SPUR-PROTRUSION-004]
When spur-like protrusion is observed, inspect for narrow copper spikes extending from target trace.
Classify as spur risk if protrusion can reduce spacing or create intermittent bridge under contamination.

[SPURIOUS-COPPER-005]
When spurious copper is observed, inspect for isolated copper islands or residual conductive fragments between intended traces.
Classify as spurious-copper risk if residual copper can create leakage or short paths.

[PINHOLE-006]
When pin-hole style void is observed, inspect for local copper voids on a trace area causing increased resistance and reduced current carrying capability.
Classify as pin-hole risk if void intersects current path region.

[FINAL-RESOLUTION-007]
Final resolution should include: immediate rework action, verification action (continuity/inspection), and process feedback action (etch/wash/solder control).
