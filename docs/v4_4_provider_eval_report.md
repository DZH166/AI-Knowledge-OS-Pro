# V4.4 Provider Evaluation Report

## Scope

V4.4 adds provider readiness evaluation that preserves real-mode honesty.

## Modes

- `--dry-run`: inspect configuration only; no external calls.
- `--demo`: run local demo LLM/embedding checks and confirm OCR/transcription/rerank remain not configured.
- `--real-if-configured`: call providers only when the matching key exists.

## Dry-Run Evidence

`python scripts/evaluate_providers.py --dry-run` passed locally and reported:

- `LLM_NOT_CONFIGURED`
- `EMBEDDING_NOT_CONFIGURED`
- `OCR_NOT_CONFIGURED`
- `VISION_DESCRIPTION_NOT_CONFIGURED`
- `TRANSCRIPTION_NOT_CONFIGURED`
- `RERANK_NOT_CONFIGURED`

The script prints endpoint fingerprints only, never API keys.

## Boundary

Missing providers are not converted into fake OCR, fake transcripts, fake answers or fake rerank scores.
