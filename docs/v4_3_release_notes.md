# V4.3 Release Notes Draft

## Title

AI Knowledge OS Pro V4.3 - Real Demo UX Hardening And Release Usability

## Highlights

- Added V4.2.1 repository source audit, mainline diff report, merge plan, release preparation and branch governance docs.
- Promoted current visible version to `V4.3 / 4.3.0`.
- Added README/docs local link checker.
- Added README asset and screenshot checker.
- Added `scripts/check_all.py` with quick, demo, release and full modes.
- Added provider-boundary tests for missing LLM, embedding, OCR, vision, transcription and disabled rerank.
- Added V4.3 API regression coverage for status/list/demo/refusal/learning/portfolio flows.
- Updated CI to run V4.3 docs/assets checks and V4.3 release package validation.
- Updated README, architecture, quickstart, release, scripts and roadmap docs for V4.3.

## Verification

- Backend compileall: passed.
- Backend pytest: `70 passed, 9 warnings`.
- Frontend typecheck/build: passed.
- Docs links: passed.
- README assets: passed.
- Demo readiness/RAG/full regression: passed.
- Alembic isolated upgrade/current: passed.
- Secret/repo-clean/release dry-run: passed.

## Honest Boundaries

- Demo data remains synthetic and labelled.
- Missing real providers still refuse clearly and do not generate fake content.
- `main` still needs PR merge before GitHub default branch shows the newest V4.3 state.
- Live browser E2E remains future work.

## Suggested Tag

`v4.3.0`
