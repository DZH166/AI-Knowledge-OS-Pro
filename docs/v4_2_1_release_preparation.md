# V4.2.1 Release Preparation

Generated at: 2026-07-04 Asia/Shanghai

## Release Identity

- Suggested tag: `v4.2.0`
- Suggested release title: `AI Knowledge OS Pro v4.2.0 - Full Regression, Demo Stability and Release Readiness`
- Source branch before merge: `feature/v4.2-full-regression-demo-release-readiness`
- Final release source after merge: `main`

## Tag Commands

After the V4.2 PR is merged and `main` is confirmed green:

```powershell
git switch main
git pull origin main
git tag -a v4.2.0 -m "AI Knowledge OS Pro v4.2.0"
git push origin v4.2.0
```

## Package Checks

Run from the merged `main` branch:

```powershell
python -m compileall backend/app scripts
python -m pytest
python scripts/check_encoding.py
python scripts/check_version.py
python scripts/check_secrets.py
python scripts/check_repo_clean.py
python scripts/check_demo_ready.py
python scripts/evaluate_rag.py --demo
python scripts/check_full_regression.py
python scripts/release.py --version V4.2 --dry-run
python scripts/release.py --version V4.2
python scripts/check_release.py --version V4.2
```

The release package must exclude:

- `.env` and environment files
- API keys and secrets
- SQLite databases
- `uploads/`
- `logs/`
- `node_modules/`
- `.next/`
- caches
- old release archives
- local runtime artifacts

## GitHub Release Draft

```markdown
# AI Knowledge OS Pro v4.2.0 - Full Regression, Demo Stability and Release Readiness

V4.2 is the release-readiness checkpoint for AI Knowledge OS Pro after the V4.1 architecture cleanup. It focuses on proving that the multimodal RAG project remains runnable, testable, demoable and safe to package.

## Highlights

- Full-regression gate covering routes, frontend pages, demo data, task states, learning assets, RAG locators and release-support files.
- Stronger synthetic demo data for documents, images, audio, video, code repositories, grounded QA and refusal QA.
- RAG evaluation checks for citation IDs, used citations, multimodal locators, timestamp citations, code locators and insufficient-context refusal.
- CI runs backend, frontend and release-safety gates.
- Release archive excludes secrets, databases, uploads, logs, dependencies, build output and cache files.

## Honest Boundaries

- Demo mode is synthetic and labelled.
- Real LLM, embedding, OCR and transcription require configured providers.
- Redis, Qdrant and worker processes are required for production-like background jobs and vector retrieval.
- Browser E2E is not yet automated.

## Verification

- Backend compileall: passed locally in V4.2 validation.
- Backend pytest: passed locally in V4.2 validation.
- Frontend typecheck/build: passed locally in V4.2 validation.
- Demo readiness, RAG evaluation and full regression: passed locally in V4.2 validation.
- Release dry-run and release archive safety check: passed locally in V4.2 validation.
```

## Post-Merge Checklist

1. Confirm `main` contains commit lineage through the V4.2 PR.
2. Confirm GitHub README default page shows `V4.2 / 4.2.0`.
3. Confirm GitHub Actions passed on `main`.
4. Create and push `v4.2.0`.
5. Create GitHub Release from `v4.2.0`.
6. Keep local `releases/` artifacts untracked.
7. Start V4.3 from the updated lineage.
