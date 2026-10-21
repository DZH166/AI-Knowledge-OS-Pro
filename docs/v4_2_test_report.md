# V4.2 Test Report

Generated at: 2026-07-03 Asia/Shanghai

## Added Or Strengthened

- `scripts/check_full_regression.py`: full regression checklist for backend route files, frontend smoke routes, demo data, RAG, task center, learning assets, portfolio docs and release-support scripts.
- `scripts/check_demo_ready.py`: stricter demo chain validation across source types, task statuses, QA statuses, locators and learning assets.
- `scripts/evaluate_rag.py`: stronger citation/refusal/locator checks.
- `backend/tests/test_v4_2_full_regression.py`: pytest coverage for full regression and V4.2 demo readiness.
- `backend/tests/test_v3_9_rag_evaluation.py`: assertions for refusal answers, valid citations and code locators.

## Test Evidence

Command:

```powershell
python -m pytest backend/tests/test_v3_7_demo_release_checks.py backend/tests/test_v3_9_rag_evaluation.py backend/tests/test_v4_2_full_regression.py -q
```

Result:

- Targeted regression subset: `9 passed`.
- Full backend suite: `63 passed, 13 warnings`.
- Frontend TypeScript check: passed.
- Frontend production build: passed, 28 App Router routes.

## Full Gate Result

V4.2 final acceptance ran:

- `python -m compileall backend/app scripts`
- `python -m pytest`: passed, 63 tests.
- `python scripts/seed_demo_data.py --database-path .pytest_tmp/v4_2_demo_showcase.db --reset`
- `python scripts/check_demo_ready.py --database-path .pytest_tmp/v4_2_demo_showcase.db`
- `python scripts/evaluate_rag.py --demo --database-path .pytest_tmp/v4_2_demo_showcase.db`
- `python scripts/check_full_regression.py --database-path .pytest_tmp/v4_2_demo_showcase.db`
- frontend typecheck and build: passed.
- encoding, version, secret and repo-clean checks: passed.
- release dry-run: passed after staging with 302 included files and no secrets/databases/uploads/cache.
- release archive safety check: passed with `files=302`, `forbidden=0`, `missing=0`.

## Current Boundary

Live browser E2E against running FastAPI/Next.js/Redis/Qdrant is not yet automated. V4.2 uses static frontend smoke plus seeded full-regression checks as the release gate.
