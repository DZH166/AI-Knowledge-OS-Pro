# V4.8 Release Zip User Experience Report

V4.8 improves release safety for people who inspect an extracted source zip instead of a Git checkout.

## Changes

- `scripts/check_secrets.py` now uses Git-tracked mode when `.git` is present.
- If Git metadata is absent, it switches to filesystem mode and skips generated/runtime directories such as `.next`, `node_modules`, `releases`, `uploads`, `logs`, `backend/data` and caches.
- `scripts/check_repo_clean.py` has the same Git/filesystem split.
- Output now includes `mode=git` or `mode=filesystem reason=no_git_metadata`.

## Verification

- `python scripts/check_secrets.py`: passed in Git mode.
- `python scripts/check_repo_clean.py`: passed in Git mode.
- `python -m pytest backend/tests/test_v4_8_release_zip_mode.py`: passed for no-Git extracted-source mode.
- `python scripts/release.py --version V4.8`: generated a local release zip.
- `python scripts/check_release.py --version V4.8`: passed with `files=454`, `forbidden=0`, `missing=0`.
- Extracted `releases/AI-Knowledge-OS-Pro-V4.8-20260705.zip` into a temporary `.pytest_tmp/release_no_git_v4_8_*` directory without `.git` metadata.
- In the extracted no-Git tree, `python scripts/check_version.py`: passed.
- In the extracted no-Git tree, `python scripts/check_secrets.py`: passed with `mode=filesystem reason=no_git_metadata`.
- In the extracted no-Git tree, `python scripts/check_repo_clean.py`: passed with `mode=filesystem reason=no_git_metadata`.
- In the extracted no-Git tree, `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_no_git_v4_8.json`: passed.

## Boundary

The authoritative archive digest is the `.sha256` file generated next to the zip. It is intentionally not copied into this versioned report because changing packaged docs changes the archive digest.
