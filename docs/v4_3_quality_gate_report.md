# V4.3 Quality Gate Report

Generated at: 2026-07-04 Asia/Shanghai

## Scope

V4.3 adds `scripts/check_all.py` as a unified quality-gate entrypoint while keeping individual commands available for CI and diagnosis.

## Gates

- `scripts/check_docs_links.py`
- `scripts/check_readme_assets.py`
- `scripts/check_frontend_smoke.py`
- `scripts/check_all.py --quick`
- `scripts/check_all.py --demo`
- `scripts/check_all.py --release`
- `scripts/check_all.py --full`
- `scripts/check_all.py --skip-frontend` for backend/demo/release diagnosis when frontend checks are intentionally skipped.

## Latest Full Verification

Command:

```powershell
python scripts/check_all.py --full
```

Result: passed.

| Gate | Result |
| --- | --- |
| Backend compileall | Passed |
| Backend pytest | Passed, `70 passed, 10 warnings` |
| Frontend typecheck | Passed |
| Frontend production build | Passed, 28 App Router routes |
| Encoding check | Passed for 315 UTF-8 text files; 96 immutable legacy log lines preserved append-only |
| Version check | Passed, `V4.3 / 4.3.0` |
| Docs link check | Passed, 91 files, 49 local links, 7 local images, 11 Mermaid blocks |
| README asset check | Passed, 7 local images, 6 external badge images, 7 screenshots found |
| Frontend smoke | Passed, 27 required routes, 24 navigation targets, 0 warnings |
| Demo seed | Passed on `.pytest_tmp/v4_3_demo_showcase.db` |
| Demo readiness | Passed |
| Demo RAG evaluation | Passed |
| Full regression | Passed, 67 checks |
| Secret scan | Passed, `scanned=313`, `findings=0` |
| Repo clean | Passed, `forbidden tracked files=0` |
| Release dry-run | Passed, `included_files=324`, no secrets/databases/uploads/cache |

## Release Package Verification

- `python scripts/release.py --version V4.3`: generated `releases/AI-Knowledge-OS-Pro-V4.3-20260704.zip`.
- `python scripts/check_release.py --version V4.3`: passed, `files=324`, `forbidden=0`, `missing=0`.
- Final SHA256 is recorded in the local `.sha256` sidecar file rather than embedded here, to avoid self-referential archive hashes.

## Additional Checks

- Alembic isolated SQLite `upgrade head` and `current`: passed at `0006_v3_6_unified_media_tasks (head)`.
- `python scripts/check_all.py --help`: documents `--quick`, `--demo`, `--release`, `--full` and `--skip-frontend`.

