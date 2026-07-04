# V4.4 Release Notes

AI Knowledge OS Pro V4.4 - Demo E2E Contracts And Runtime Observability

## Highlights

- Added lightweight runtime observability APIs and a data-driven `/system/observability` page.
- Added citation deep-link contracts for document, media and code evidence.
- Added optional Playwright demo smoke, citation-jump and observability specs.
- Added provider readiness evaluation with dry-run, demo and real-if-configured modes.
- Promoted visible version to `V4.4 / 4.4.0`.
- Updated CI and `scripts/check_all.py` for V4.4 release gates.

## Real-Mode Boundary

Default CI does not call paid providers. Missing providers return explicit NOT_CONFIGURED-style states and do not create fake OCR, fake transcripts, fake answers or fake rerank scores.

## Verification

See `docs/v4_4_test_report.md` and `docs/v4_4_quality_gate_report.md`.

Local release archive:

- `releases/AI-Knowledge-OS-Pro-V4.4-20260705.zip`
- `scripts/check_release.py --version V4.4`: `files=347`, `forbidden=0`, `missing=0`
- SHA256 is stored in the local `.sha256` sidecar rather than embedded in tracked docs.

## Upgrade Note

No database migration is required for V4.4. The observability request buffer is process-local and resets on API restart.
