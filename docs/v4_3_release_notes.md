# V4.3 Release Notes

## Title

AI Knowledge OS Pro V4.3 - Real Demo UX Hardening And Release Usability

## Published State

- Tag: `v4.3.0`
- Initial main merge commit: `c61d653 Merge V4.3 real demo UX hardening`
- Post-release hardening: tracked on `main` after the initial release merge.
- Pull request: `https://github.com/DZH166/AI-Knowledge-OS-Pro/pull/1`
- GitHub Release: `https://github.com/DZH166/AI-Knowledge-OS-Pro/releases/tag/v4.3.0`

## Highlights

- Added V4.2.1 repository source audit, mainline diff report, merge plan, release preparation and branch governance docs.
- Promoted current visible version to `V4.3 / 4.3.0`.
- Added README/docs local link checker.
- Added README asset and screenshot checker plus a dedicated README asset report.
- Added `scripts/check_all.py` with quick, demo, release, full and skip-frontend diagnostic modes.
- Added provider-boundary tests for missing LLM, embedding, OCR, vision, transcription and disabled rerank.
- Added V4.3 API regression coverage for status/list/demo/refusal/learning/portfolio flows.
- Added shared UX components for provider-missing warnings, structured error states, task log drawer, source locator button and learning action bar.
- Updated CI to run V4.3 docs/assets checks and V4.3 release package validation.
- Updated README, architecture, quickstart, release, scripts, roadmap and V4.4 planning docs.

## Verification

- Backend compileall: passed.
- Backend pytest: `70 passed, 9 warnings`.
- Frontend typecheck/build: passed.
- Docs links: passed.
- README assets: passed.
- Demo readiness/RAG/full regression: passed.
- Alembic isolated upgrade/current: passed.
- Secret/repo-clean/release dry-run: passed.
- Release archive check for the regenerated V4.3 asset: `files=324`, `forbidden=0`, `missing=0`.
- Feature-branch GitHub CI: passed.
- `main` merge-commit GitHub CI: passed.
- Release SHA256: recorded in the `.sha256` sidecar file rather than embedded here, to avoid self-referential archive hashes.

## Honest Boundaries

- Demo data remains synthetic and labelled.
- Missing real providers still refuse clearly and do not generate fake content.
- The repository is private, so unauthorized browsers may see a GitHub 404.
- Live browser E2E remains V4.4 work.

## Suggested Next Version

`V4.4` should focus on browser E2E demo validation, citation-jump verification and runtime observability rather than broad new feature expansion.
