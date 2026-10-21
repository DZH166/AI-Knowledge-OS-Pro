# V4.5 Release Documentation Hygiene Report

## Scope

This maintenance pass keeps the already published V4.5 baseline easier to operate from GitHub and from local release commands. It does not add provider-backed features, change database schema or rewrite historical learning records.

## Changes

- Added `codex/**` to the CI push branch filters so future Codex work branches run the same GitHub Actions checks as `feature/**` branches.
- Updated `docs/release_checklist.md` from the old V3.6 wording to the current `V4.5 / 4.5.0` release gate.
- Expanded `scripts/check_version.py` so version checks cover README, release process, versioning, local release checklist, GitHub release checklist and CI branch/version surfaces.
- Added this report to the V4.5 release archive required entries in `scripts/check_release.py`.

## Boundary

No fake OCR, fake transcript, fake LLM answer, fake provider readiness result or synthetic real-mode output was added. This pass only improves release documentation and CI hygiene.

## Verification

Commands run during this maintenance pass:

```text
python scripts/check_all.py --quick
result=passed

python scripts/check_version.py
Version consistency passed: V4.5 / 4.5.0

python -m compileall backend/app scripts
result=passed

python -m pytest
75 passed, 23 warnings

python scripts/check_all.py --release
result=passed

python scripts/release.py --version V4.5 --dry-run
included_files=356
found_secrets=no
found_database=no
found_uploads=no
found_cache=no
passed=yes

python scripts/check_release.py --version V4.5
files=356
forbidden=0
missing=0
```
