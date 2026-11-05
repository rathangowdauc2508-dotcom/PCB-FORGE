# Demo Scenario Runbook (DeepPCB & Multi-Agent)

## 1) Input Files

- **Error log:** Text string or `.log/.txt` file
- **Spec:** `spec_excerpt` (string) or `spec_document_path` (PDF/TXT path)
- **CAD/Schematic image:** Reference design image (`template_board.png` or `*_temp.jpg`)
- **Tested PCB image:** Tested physical image (`tested_board.png` or `*_test.jpg`)

Supported N-file grouped batch inputs:
- Endpoint: `POST /orchestrate/grouped`
- Inputs separated by type:
  - `error_logs[]`
  - `design_images[]`
  - `tested_images[]`
  - `spec_excerpts[]` or `spec_document_paths[]`
- Preview mapping: `POST /orchestrate/grouped/preview`

## 2) Multi-Agent Orchestration Flow

1. **Agent 1:** Symptom Analyzer
2. **Agent 2A:** Spec Precheck (parallel)
3. **Agent 2B:** CAD Mapper (parallel)
4. **Agent 3:** Physical Defect Verifier
5. **Agent 4:** Spec Compliance Resolver

Handoff sequence:
- Agent 1 ➡️ `agent_2a, agent_2b`
- Agent 2A / 2B ➡️ `agent_3`
- Agent 3 ➡️ `agent_4`

## 3) Error Log Format (Recommended)

Format:
`[ERROR] <ERROR_CODE> - <SHORT_DESCRIPTION> (<RISK_HINT>)`

Examples:
- `[ERROR] I2C Bus Arbitration Lost - SDA line held LOW. Error Code: 0x08`
- `[ERROR] NET_SHORT_DETECTED - adjacent nets show conductive bridge signature (short risk).`
