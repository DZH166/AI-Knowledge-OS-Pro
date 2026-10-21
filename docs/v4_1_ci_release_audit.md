# V4.1 CI And Release Audit

## GitHub Actions

The project has one workflow: `.github/workflows/ci.yml`.

Current CI jobs:

- Backend: install Python dependencies, compile backend/scripts, run pytest, seed/check demo data, run demo RAG evaluation and Alembic upgrade/current.
- Frontend: `npm ci`, `npm run typecheck`, `npm run build`.
- Quality and release: encoding, version, secret, repo-clean, frontend-smoke, release dry-run, release build, release archive inspection and artifact upload.

## Release Scripts

- `scripts/release.py` builds release archives from tracked files and excludes secrets, databases, uploads, logs, caches, dependencies, `.next`, `releases`, `.git`, `.agents`, `.codex` and `sub2api`.
- `scripts/check_release.py` inspects generated archives for forbidden entries and required project files.
- V4.1 updated `check_release.py` so the required V3.6 acceptance report points to `docs/archive/v3/v3_6_acceptance_report.md`.

## Current Findings

- CI does not require real provider keys.
- Release exclusions cover node modules, `.next`, SQLite DBs, uploads, logs and generated caches.
- Release required entries were updated after docs archive cleanup.
- Public release naming still targets `V3.8`; V4.1 should not be released until all final gates pass.

## Pending Evidence

Completed local evidence:

- `python scripts/check_version.py`: passed as `V3.8 / 3.8.0`.
- `python scripts/check_frontend_smoke.py`: passed.
- Frontend production build: passed.

Completed staged-file evidence:

- `python scripts/check_secrets.py`: passed, scanned 282 tracked text files, findings=0.
- `python scripts/check_repo_clean.py`: passed, forbidden tracked files=0.
- `python scripts/release.py --version V3.8 --dry-run`: passed, included_files=293, secrets/database/uploads/cache all no.

A real release zip can be generated after the maintainer decides whether V4.1 should remain a cleanup branch or become a tagged public release.
