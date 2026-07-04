# V4.4 Test Report

## Commands Run

This report is updated during V4.4 release closure.

| Command | Status | Notes |
| --- | --- | --- |
| `python -m compileall backend/app scripts` | Passed | Local `.venv` Python |
| `python -m pytest` | Passed | 74 tests, 23 warnings |
| `python -m pytest backend/tests/test_v4_4_observability.py backend/tests/test_citation_jump_contracts.py` | Passed | 3 tests |
| `python -m pytest backend/tests/test_observability.py backend/tests/test_v4_4_observability.py backend/tests/test_citation_jump_contracts.py -q` | Passed | 4 tests |
| `python scripts/check_version.py` | Passed | `V4.4 / 4.4.0` |
| `python scripts/evaluate_providers.py --dry-run` | Passed | No external calls |
| `python scripts/check_e2e.py` | Passed | Static scaffold check |
| `python scripts/run_demo_e2e.py` | Skipped | `PLAYWRIGHT_NOT_INSTALLED`; no live browser claim |
| `frontend tsc --noEmit` | Passed | Optional E2E excluded from default app typecheck |
| `frontend next build` | Passed | 28 routes generated |
| `python scripts/check_encoding.py` | Passed | 338 UTF-8 text files |
| `python scripts/check_docs_links.py` | Passed | 102 Markdown files, 49 local links |
| `python scripts/check_readme_assets.py` | Passed | 7 screenshots found |
| `python scripts/check_frontend_smoke.py` | Passed | 27 routes, 24 nav targets |
| `python scripts/seed_demo_data.py --database-path .pytest_tmp/v4_4_demo_showcase.db --reset` | Passed | Synthetic isolated DB |
| `python scripts/check_demo_ready.py --database-path .pytest_tmp/v4_4_demo_showcase.db` | Passed | Required demo tables/statuses present |
| `python scripts/evaluate_rag.py --demo --database-path .pytest_tmp/v4_4_demo_showcase.db` | Passed | Grounded/refusal/citation checks |
| `python scripts/check_full_regression.py --database-path .pytest_tmp/v4_4_demo_showcase.db` | Passed | 67 checks |
| `python scripts/check_secrets.py` | Passed | `findings=0` |
| `python scripts/check_repo_clean.py` | Passed | forbidden tracked files `0` |
| `python scripts/release.py --version V4.4 --dry-run` | Passed | `included_files=347`, no secrets/databases/uploads/cache after staging new V4.4 files |
| `python scripts/release.py --version V4.4` | Passed | Generated `releases/AI-Knowledge-OS-Pro-V4.4-20260705.zip` |
| `python scripts/check_release.py --version V4.4` | Passed | `files=347`, `forbidden=0`, `missing=0` |
| `python scripts/check_all.py --full` | Passed | compileall, pytest, frontend, quick, provider, E2E, demo and release gates |

## Package Gate

The release archive was generated locally under `releases/` and verified with `scripts/check_release.py`. The `.sha256` sidecar is kept local and untracked.
