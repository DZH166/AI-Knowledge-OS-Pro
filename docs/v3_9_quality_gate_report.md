# V3.9 Quality Gate Report

Generated at: 2026-07-02 Asia/Shanghai

## Scope

This is an in-progress V3.9 report, not the final V3.9 acceptance report. It records two quality gates added after V3.8:

- Demo RAG evidence-chain evaluation.
- Lightweight frontend route and UI smoke check.

## Implemented

- Added `scripts/evaluate_rag.py --demo` to validate deterministic demo RAG citation plumbing without calling providers.
- Added `scripts/check_frontend_smoke.py` to validate required frontend pages, AppShell navigation targets and obvious raw/debug UI leakage.
- Added backend tests for both scripts.
- Added CI steps for demo seed/readiness/RAG evaluation and frontend smoke.
- Removed raw JSON metadata display from System and Media detail pages, replacing it with readable summaries.
- Added a System page provider setup guide with copyable placeholder env examples and NOT_CONFIGURED boundary text.
- Added Task Center recovery hints for active, failed, interrupted, cancelled, provider-missing and indexing-related jobs.

## Verification

| Check | Result |
| --- | --- |
| `python -m compileall backend/app scripts` | Passed |
| `python -m pytest` | Passed: 49 passed, 22 warnings in 104.54s |
| `python -m pytest backend/tests/test_v3_9_rag_evaluation.py` | Passed: 2 tests |
| `python -m pytest backend/tests/test_v3_9_frontend_smoke.py backend/tests/test_v3_9_rag_evaluation.py` | Passed: 3 tests |
| `python scripts/evaluate_rag.py --demo --database-path backend/data/demo_showcase.db` | Passed: 1 QA log, 1 timestamp citation, 7 multimodal chunks, 7 citation locators |
| `python scripts/check_frontend_smoke.py` | Passed with 4 navigation reuse warnings |
| Frontend typecheck | Passed |
| Frontend production build | Passed, 15 app routes |
| `python scripts/check_encoding.py` | Passed: 241 UTF-8 text files |
| `python scripts/check_secrets.py` | Passed: scanned 239 tracked text files, findings 0 |
| `python scripts/release.py --version V3.8 --dry-run` | Passed: 250 included files, no secrets/databases/uploads/cache |

## Honest Boundaries

- Demo RAG evaluation checks seeded evidence and citation plumbing only; it does not measure real LLM answer quality.
- Frontend smoke check is not a browser E2E test.
- AppShell still has duplicated navigation targets (`/chat`, `/learning`, `/learning/cards`, `/system`). The script reports these as warnings so the V4.0 information architecture pass can split them into dedicated pages.
- The application version remains `V3.8 / 3.8.0` until V3.9 is fully accepted.
- Provider diagnostics show placeholders only; they do not validate real paid-provider credentials.

## Next V3.9 Work

- Expand RAG evaluation with richer retrieval/citation metrics.
- Add provider diagnostic guidance to the System page.
- Improve media result navigation and convert Task Center recovery hints into richer event-aware guidance where backend error codes are available.
- Convert navigation reuse warnings into dedicated pages during the V4.0 UI/UX pass.
