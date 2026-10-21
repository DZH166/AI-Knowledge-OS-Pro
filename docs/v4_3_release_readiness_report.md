# V4.3 Release Readiness Report

Generated at: 2026-07-04 Asia/Shanghai

## Scope

V4.3 makes the GitHub project easier to open, run, verify, explain and release. It builds on V4.2 full regression and V4.2.1 repository governance.

## Current Status

- Current branch: `feature/v4.3-real-demo-ux-hardening`.
- Base lineage: V4.2 commit `6de400a` plus V4.2.1 governance commit `e4fa458`.
- GitHub default branch is still `main`, and `main` lags V4.2/V4.3 until PR merge.
- Recommended release path remains PR to `main`, CI green, tag, GitHub Release.

## Readiness Checks

| Check | Result |
| --- | --- |
| Version consistency | Passed, `V4.3 / 4.3.0` |
| README local links | Passed |
| README assets | Passed |
| Demo walkthrough | Passed on isolated synthetic DB |
| Provider boundary tests | Passed |
| API regression tests | Passed |
| Backend compile/pytest | Passed |
| Frontend typecheck/build | Passed |
| Alembic isolated upgrade/current | Passed |
| Secret check | Passed |
| Repo clean check | Passed |
| Release dry-run | Passed, `included_files=321` |
| Release archive check | Passed, `files=321`, `forbidden=0`, `missing=0` |

## Current Limitations

- V4.2 has not yet been merged into `main`; GitHub default branch may still show older content until PR merge.
- Live browser E2E is still not automated.
- Real LLM, embedding, OCR, vision and transcription still require configured providers.
- Redis/Qdrant/Worker are required for production-like background tasks and semantic retrieval.
- Local release zip is generated under `releases/` and intentionally remains untracked.

## Local Release Artifact

- Zip: `releases/AI-Knowledge-OS-Pro-V4.3-20260704.zip`
- SHA256 file: `releases/AI-Knowledge-OS-Pro-V4.3-20260704.zip.sha256`
- SHA256: recorded in the local `.sha256` sidecar file rather than embedded here, to avoid self-referential archive hashes.
- Archive inspection: `files=321`, `forbidden=0`, `missing=0`

## Suggested PR

Title:

```text
Release V4.3: real demo UX hardening and release usability
```

Suggested tag after merge:

```text
v4.3.0
```
