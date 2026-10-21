# V4.8 Acceptance Report

V4.8 focuses on runtime performance evidence, frontend request-cache behavior, release zip friendliness and script maintenance cleanup.

## Accepted Scope

- Version surfaces target `V4.8 / 4.8.0`.
- Backend performance routes expose real request metadata.
- Frontend request cache and request dedupe are visible in `/system/performance`.
- Browser page load and AppShell route-switch timing are visible in `/system/performance`.
- Button runtime timing is recorded by shared interaction metrics.
- Release safety scripts support Git and no-Git source tree modes.
- Low-frequency self-check and CI report implementations moved under `scripts/maintenance/` with compatibility wrappers.

## Boundaries

- No fake LLM, OCR, transcription, citation, E2E or performance results were added.
- Runtime performance data is an in-process local buffer, not a production APM system.
- Browser cache metrics are local to the current frontend session.

## Final Status

Accepted after local full validation.

## Final Evidence

- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: 194 passed.
- Final rerun of `python -m pytest` passed with `194 passed, 23 warnings` after stopping stale local demo child processes that were holding generated `.pytest_tmp/local_demo_logs` files open.
- Isolated Alembic check passed: `python -m alembic upgrade head` and `python -m alembic current` reported `0006_v3_6_unified_media_tasks (head)`.
- `python -m pytest backend/tests/test_v4_4_observability.py backend/tests/test_citation_jump_contracts.py`: 3 passed.
- Frontend typecheck with bundled Node: passed.
- Frontend production build with bundled Node: passed; `/system/performance` is included in the build route list.
- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_8.json`: passed.
- Optional demo browser E2E inside `check_all --full`: 22 passed.
- Demo readiness, demo RAG evaluation and full regression passed on isolated `.pytest_tmp/v4_8_demo_showcase.db`.
- `python scripts/release.py --version V4.8 --dry-run`: passed with `found_secrets=no`, `found_database=no`, `found_uploads=no`, `found_cache=no`.
- `python scripts/release.py --version V4.8`: generated `releases/AI-Knowledge-OS-Pro-V4.8-20260705.zip`.
- `python scripts/check_release.py --version V4.8`: passed with `files=454 forbidden=0 missing=0` after adding browser page timing.
- Extracted no-Git release tree validation passed:
  - `python scripts/check_version.py`
  - `python scripts/check_secrets.py` with `mode=filesystem reason=no_git_metadata`
  - `python scripts/check_repo_clean.py` with `mode=filesystem reason=no_git_metadata`
  - `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_no_git_v4_8.json`
- Final SHA256 is recorded in the `.sha256` file next to the generated archive.
