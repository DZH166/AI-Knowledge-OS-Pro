# V4.1 Cleanup Report

Generated during the V4.1 codebase cleanup and architecture consolidation pass.

## Completed Cleanup Actions

| Action | Files | Reason | Risk | Verification |
| --- | ---: | --- | --- | --- |
| Moved V2 historical reports into `docs/archive/v2` | 3 | Keep history while reducing docs-root noise. | Low | `git status` records renames, not deletion. |
| Moved V3 historical reports into `docs/archive/v3` | 16 | Keep version reports and learning package drafts under a versioned archive. | Low | README/release/test active references updated where required. |
| Moved V4.0 predevelopment audit into `docs/archive/v4` | 1 | Keep prior long-run audit but remove old report from docs root. | Low | README badge now links to the archive path. |
| Removed untracked `frontend/pnpm-lock.yaml` and `frontend/pnpm-workspace.yaml` | 2 | Local preview artifacts conflicted with the project standard npm/package-lock workflow. | Low | CI still uses `npm ci` with `frontend/package-lock.json`. |
| Removed frontend hooks lint suppression comments | 7 | Replaced `react-hooks/exhaustive-deps` suppressions with stable callbacks. | Medium | Frontend TypeScript check passed after the change. |
| Rewrote `docs/version_learning_package.md` as UTF-8 Markdown | 1 | The file was visibly unreadable and had an old root-level V2.5 path. | Low | `scripts/check_encoding.py` passed. |

## Archived Files

### `docs/archive/v2`

- `v2_5_acceptance_report.md`
- `v2_5_learning_package_draft.json`
- `v2_current_state_audit.md`

### `docs/archive/v3`

- `v3_1_image_metadata_report.md`
- `v3_3_error_archive_report.md`
- `v3_4_audio_transcription_report.md`
- `v3_5_video_pipeline_report.md`
- `v3_6_acceptance_report.md`
- `v3_6_learning_package_draft.json`
- `v3_7_acceptance_report.md`
- `v3_7_learning_package_draft.md`
- `v3_7_predevelopment_audit.md`
- `v3_8_acceptance_report.md`
- `v3_8_learning_package_draft.md`
- `v3_8_test_report.md`
- `v3_9_quality_gate_report.md`
- `v3_acceptance_report.md`
- `v3_learning_package_draft.json`
- `v3_predevelopment_audit.md`

### `docs/archive/v4`

- `v4_0_long_run_predevelopment_audit.md`

## Files Updated For New Paths

- `README.md`
- `scripts/check_release.py`
- `backend/tests/test_v3_6_citations_release_package.py`
- `docs/version_learning_package.md`

## Deletion Policy

No tracked historical learning archive was deleted. No database, upload, log, cache, release archive, environment file or media source was modified. No uncertain backend service, provider, model, route, frontend component or script was deleted in this pass.

## Validation So Far

- `python scripts/check_encoding.py`: passed for 272 UTF-8 text files, with preserved immutable legacy log warnings.
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: passed with bundled Python, 61 tests and 9 warnings.
- Frontend `tsc --noEmit`: passed after hooks cleanup.
- Frontend production build: passed, 28 generated routes.
- Alembic upgrade/current on an isolated `.pytest_tmp` SQLite database: passed, current head `0006_v3_6_unified_media_tasks`.
- `python scripts/check_encoding.py`: passed after new V4.1 docs, 284 UTF-8 files with 96 preserved immutable legacy log lines.
- `python scripts/check_version.py`: passed as `V3.8 / 3.8.0`.
- `python scripts/check_frontend_smoke.py`: passed, `required_routes=27`, `nav_targets=24`, `warnings=0`.
- `python scripts/check_secrets.py`: passed, scanned 282 tracked text files, findings=0.
- `python scripts/check_repo_clean.py`: passed, forbidden tracked files=0.
- `python scripts/evaluate_rag.py --demo`: passed, seeded citation and multimodal locator checks succeeded.
- `python scripts/release.py --dry-run`: passed, release_dry_run_version=V3.8, included_files=293, secrets/database/uploads/cache all no.

Final tracked-file safety checks were run after staging the V4.1 file set and again during the 2026-07-03 post-push revalidation.
