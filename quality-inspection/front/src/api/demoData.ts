import type { OrchestrationResponse } from '../types/api';

export function buildDemoResponse(): OrchestrationResponse {
  const now = new Date();
  const started = new Date(now.getTime() - 8400);

  return {
    run_id: 'demo-' + Math.random().toString(36).slice(2, 10),
    model_used: 'gemma-4',
    started_at: started.toISOString(),
    ended_at: now.toISOString(),
    input: {
      error_log: '[ERROR] I2C Bus Arbitration Lost - SDA line held LOW. Error Code: 0x08',
      spec_excerpt:
        'IPC-2221B Section 6.1: Minimum conductor spacing for 5V adjacent traces must be ≥ 0.10mm. Inspect for micro-bridges and residual copper.',
      design_image: { mime_type: 'image/png', file_path: 'data/assets/template_board.png' },
      tested_image: { mime_type: 'image/png', file_path: 'data/assets/tested_board.png' },
      heuristic_diff_bbox: { label: 'diff_hotspot', x1: 440, y1: 210, x2: 525, y2: 280, confidence: 0.88 },
    },
    output: {
      root_cause:
        'Design spacing was within spec (0.15mm), but residual copper from manufacturing wash/etch failure created a micro-short between SDA and GND lines, causing I2C bus errors.',
      impact: 'I2C communication failure, SDA held permanently LOW, and overcurrent risk to MCU input pins.',
      resolution: [
        'Micro-deburr / laser-trim the highlighted copper bridge at [X:445-520, Y:215-275] and re-test continuity',
        'Audit manufacturing wash cycle pressure and chemical concentration in etching line',
        'Update AOI inspection thresholds to detect spurious copper slivers under 0.12mm',
      ],
      confidence: 0.94,
      bounding_boxes: [
        { label: 'spurious_copper_short', x1: 445, y1: 215, x2: 520, y2: 275, confidence: 0.95 },
      ],
    },
    annotated_tested_image: null,
    agent_trace: [
      {
        agent_id: 'agent_1',
        agent_name: 'Error Analyzer',
        handoff_to: 'agent_2a,agent_2b',
        handoff_message: 'Routing to parallel spec check and CAD mapping based on error signature',
        output: {
          error_interpretation:
            'SDA line is held LOW, indicating a high likelihood of a short to an adjacent net caused by a manufacturing defect (copper bridge).',
          suspect_parts: [
            {
              part_name: 'SDA/GND trace pair',
              likely_fault_mode: 'micro short',
              why_related: 'Error code 0x08 and bus arbitration lost pattern are consistent with an SDA-GND short',
              confidence: 0.95,
            },
          ],
          handoff_message: 'Requesting parallel spec and CAD verification',
        },
      },
      {
        agent_id: 'agent_2a',
        agent_name: 'Spec Checker',
        handoff_to: 'agent_3',
        handoff_message: 'Requesting physical verification against rules SPACING-SHORT-001 and SPURIOUS-COPPER-005',
        output: {
          spec_watchlist: [
            {
              rule_id: 'IPC-2221B-SEC-6.1',
              what_to_check: 'Conductor Spacing & Clearance for 5V external traces (must be ≥ 0.10mm)',
              why_relevant: 'Essential standard for preventing unintended conductor contact or dielectric breakdown',
              priority: 'critical',
            },
            {
              rule_id: 'IPC-A-600-CL-3.2',
              what_to_check: 'Residual conductive copper slivers and etching cleanliness in adjacent track regions',
              why_relevant: 'Direct root cause for intermittent low-resistance short circuits on I2C bus lines',
              priority: 'high',
            },
          ],
          spec_risk_summary: 'Design spacing meets standard requirements (0.15mm), but residual manufacturing copper creates severe short-circuit failure risk.',
          handoff_message: 'Proceeding to physical image inspection with IPC-2221B & IPC-A-600 focus',
        },
      },
      {
        agent_id: 'agent_2b',
        agent_name: 'CAD Mapper',
        handoff_to: 'agent_3',
        handoff_message: 'Passing suspect region bounding box to physical inspection',
        output: {
          cad_mappings: [
            {
              part_name: 'SDA / GND trace pair (near R12/U3)',
              schematic_reference: 'U3.Pin4 (SDA) - R12 Pull-up junction',
              reason: 'High-density signal routing junction directly connected to I2C bus',
              bbox: { x1: 445, y1: 215, x2: 520, y2: 275 },
            },
          ],
          handoff_message: 'Requesting zoomed physical image verification',
        },
      },
      {
        agent_id: 'agent_3',
        agent_name: 'Defect Inspector',
        handoff_to: 'agent_4',
        handoff_message: 'Defect confirmed — requesting final spec-grounded resolution from Spec Resolver',
        output: {
          defect_verification: [
            {
              part_name: 'SDA/GND trace pair',
              defect_type: 'spurious copper bridge (micro-short)',
              evidence: 'Visual diff & contour analysis confirmed conductive residue bridging SDA and Ground nets at coordinates [445,215 → 520,275]',
              crop_note: 'Verified in ROI — zero dielectric spacing detected',
              confidence: 0.95,
              bbox: { x1: 445, y1: 215, x2: 520, y2: 275 },
            },
          ],
          root_cause_candidate: 'Micro-short caused by residual copper from etching process bridging SDA to GND',
          impact: 'I2C communication failure, SDA held permanently LOW, overcurrent hazard to MCU pin',
          handoff_message: 'Passing to final Spec Resolver',
        },
      },
      {
        agent_id: 'agent_4',
        agent_name: 'Spec Resolution',
        handoff_to: null,
        handoff_message: null,
        output: {
          spec_checks: [
            {
              rule_id: 'IPC-2221B-SEC-6.1',
              rule_text: 'Minimum Electrical Clearance: Distance between adjacent uninsulated conductors must be ≥ 0.10mm',
              compliance_status: 'FAIL',
              gap: 'Measured clearance is 0.00mm due to physical copper bridge between SDA and GND traces',
            },
            {
              rule_id: 'IPC-A-600-CL-3.2',
              rule_text: 'Etching Quality & Cleanliness: No metallic bridges or copper slivers allowed across isolation barriers',
              compliance_status: 'FAIL',
              gap: 'Violation confirmed: conductive metallic bridge spanning isolation channel',
            },
          ],
          final_root_cause: 'Design spacing was within IPC-2221B specifications (0.15mm), but residual copper from manufacturing wash/etch failure formed a conductive micro-short between SDA and GND lines, driving SDA LOW (Error 0x08).',
          final_resolution: [
            'Micro-deburr / laser-trim the highlighted copper bridge at [X:220-292, Y:185-295] and re-test continuity',
            'Issue corrective action to PCB fabrication line for etching wash cycle pressure and chemical concentration',
            'Update automated optical inspection (AOI) minimum gap threshold parameters to 0.12mm',
          ],
          final_confidence: 0.94,
        },
      },
    ],
  };
}

export const DEMO_INPUT = {
  errorLog:
    '[ERROR] I2C Bus Arbitration Lost - SDA line held LOW. Error Code: 0x08\n(Voltage drop detected on communication line)',
  specExcerpt:
    'IPC-2221C Section 6.1\nMinimum Electrical Clearance\nFor operating voltages below 5V, the minimum clearance between external conductors must be ≥ 0.10mm.',
};
