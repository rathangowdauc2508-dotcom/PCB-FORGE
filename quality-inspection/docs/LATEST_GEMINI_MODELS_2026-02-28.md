# Gemini Model Notes (Checked on 2026-02-28)

## Verification method

1. Official docs check
- https://ai.google.dev/gemini-api/docs/changelog
- https://ai.google.dev/gemini-api/docs/models
- https://ai.google.dev/gemini-api/docs/quickstart

2. Live API check with configured keys
- `models.list` called against real API keys
- vision probe executed with real image input (`data/assets/tested_board.png`)
- output saved to `data/model_probe_latest.json`

## Live-available model examples (from API)

- `gemini-3.1-pro-preview-customtools`
- `gemini-3.1-pro-preview`
- `gemini-3-flash-preview`
- `gemini-3-pro-preview`
- `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview`
- `gemini-2.5-pro`
- `gemini-2.5-flash`

## Vision-callable models confirmed today

From `data/model_probe_latest.json`:

- `gemini-3.1-pro-preview-customtools`
- `gemini-3.1-pro-preview`
- `gemini-3-flash-preview`
- `gemini-3-pro-preview`
- `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview`
- `gemini-2.5-pro`
- `gemini-2.5-flash`

## Operational note

Backend now enforces the latest recommended available model for orchestration and does not auto-fallback to older model families.
