# V4.2.1 Merge Plan

Generated at: 2026-07-04 Asia/Shanghai

## Recommended Plan

Use Plan A: merge by Pull Request.

- Base branch: `main`
- Head branch: `feature/v4.2-full-regression-demo-release-readiness`
- Reason: V4.2 is 15 commits ahead of `main`, while `main` has no commits missing from V4.2. A PR keeps review, CI and GitHub history visible.

## Alternatives Considered

- Plan B, local merge then push `main`: technically possible because `main` has no unique commits, but not recommended because it bypasses PR review and branch-protection visibility.
- Plan C, merge/rebase `main` into V4.2 first: not required right now because `main` has no commits ahead of the V4.2 branch.

## Risks

- GitHub default branch still displays the older V3.6-era README until the PR merges.
- No `v4.2.0` tag exists yet, so release identity is not anchored.
- Older feature branches remain visible; they should be retained until the V4.2 merge is complete and confirmed.
- GitHub Actions status could not be inspected with `gh` because GitHub CLI is not installed locally; PR CI should be treated as the remote source of truth.

## Required Tests Before Merge

- `python -m compileall backend/app scripts`
- `python -m pytest`
- frontend typecheck
- frontend production build
- `python scripts/check_encoding.py`
- `python scripts/check_version.py`
- `python scripts/check_secrets.py`
- `python scripts/check_repo_clean.py`
- `python scripts/check_demo_ready.py`
- `python scripts/evaluate_rag.py --demo`
- `python scripts/check_full_regression.py`
- `python scripts/release.py --version V4.2 --dry-run`
- `python scripts/check_release.py --version V4.2` after archive generation

## Suggested PR

Title:

```text
Release V4.2: full regression demo release readiness
```

Description:

```markdown
## Summary

Release V4.2 promotes AI Knowledge OS Pro from the V3.6 GitHub portfolio baseline through V4.1 architecture cleanup into a full-regression, demo-stability and release-readiness checkpoint.

## V4.2 Core Capabilities

- Unified visible version to V4.2 / 4.2.0.
- Strengthened synthetic demo data for document, image, audio, video, code repository, RAG, refusal, tasks and learning assets.
- Added full regression gate through scripts/check_full_regression.py.
- Hardened demo readiness and RAG evaluation scripts.
- Updated README, quickstart, demo mode, RAG, release and roadmap documentation.

## Regression Validation

- Backend compile and pytest passed in the V4.2 branch validation.
- Demo readiness, RAG demo evaluation and full regression checks passed.
- Frontend typecheck and production build passed.

## Demo Validation

Demo data is synthetic and explicitly labelled. It validates wiring, locators, citations and UI/data contracts without pretending to be real provider output.

## Quality Gates

CI runs backend compile/pytest/demo/RAG/full regression, frontend typecheck/build, encoding/version/secret/repo-clean checks and release packaging safety checks.

## Known Limitations

- Real LLM, embedding, OCR and transcription require configured providers.
- Redis, Qdrant and workers are required for real background processing and vector retrieval.
- Live browser E2E is not yet automated.

## Release Dry Run

V4.2 release dry-run passed locally with a clean package set and no secrets, databases, uploads, logs, node_modules, .next or cache directories.

## Sensitive Files

The release flow tracks Git-owned files and excludes .env, SQLite databases, uploads, logs, dependency folders, build caches, generated release zips and local runtime artifacts.
```

## Post-Merge Actions

1. Pull latest `main`.
2. Verify `README.md` on GitHub default branch shows V4.2.
3. Confirm GitHub Actions are green on `main`.
4. Create annotated tag `v4.2.0`.
5. Prepare GitHub Release using `docs/v4_2_github_release_notes.md`.
6. Keep older feature branches until the tag and release are confirmed.
