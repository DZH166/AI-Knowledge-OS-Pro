# V4.7 Acceptance Report

## Scope

V4.7 is an interaction-performance, visual-learning and cleanup-governance release. It does not add fake AI, fake OCR, fake transcription, fake citations or fake tests.

## Completed

- Version surfaces unified to `V4.7 / 4.7.0`.
- AppShell navigation reduced to 17 core entries while preserving implemented routes.
- Dashboard redesigned as a visual command center.
- Project structure page redesigned as a visual learning map.
- High-frequency async buttons now expose pending/disabled states.
- API request timeout returns a clear user-facing error.
- UI performance and interaction feedback checks are executable and wired into `check_all.py` and CI.
- GitHub issue template version placeholder now matches `V4.7 / 4.7.0`.
- Script/test sprawl is documented with a keep/move/consolidate plan instead of unsafe deletion.
- V4.7 learning package now contains 18 beginner-friendly knowledge points with related files, debugging methods and interview expressions.

## Final Verification

- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_7.json`: passed.
- Backend tests: `190 passed, 15 warnings`.
- Frontend production build: passed and generated 29 app routes.
- Browser demo E2E: `22 passed`.
- Demo RAG evaluation: passed with deterministic seeded data and valid citation locators.
- Release dry-run: passed with `included_files=413`, no secrets, no database, no uploads and no cache.

Detailed command evidence is recorded in `docs/v4_7_test_report.md`.

## Acceptance Decision

V4.7 is accepted for release packaging after final doc append, release archive generation and `scripts/check_release.py --version V4.7`.
