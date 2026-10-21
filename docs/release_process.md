# Release Process

This project treats release packaging as an engineering feature, not a manual zip operation.

## Implemented

- Release dry-run.
- Release archive generation.
- SHA256 generation.
- Release archive safety check.
- GitHub Actions quality job.
- Exclusion rules for secrets, databases, uploads, logs, caches, dependencies and build output.

## Local Verification

```powershell
python -m compileall backend/app scripts
python -m pytest
cd frontend
npm run typecheck
npm run build
cd ..
python scripts/check_encoding.py
python scripts/check_secrets.py
python scripts/check_repo_clean.py
python scripts/check_version.py
python scripts/seed_demo_data.py --database-path backend/data/demo_showcase.db --reset
python scripts/check_demo_ready.py --database-path backend/data/demo_showcase.db
python scripts/evaluate_rag.py --demo --database-path backend/data/demo_showcase.db
python scripts/check_full_regression.py --database-path backend/data/demo_showcase.db
python scripts/evaluate_providers.py --dry-run
python scripts/check_e2e.py
python scripts/run_demo_e2e.py
python scripts/run_demo_e2e.py --strict
python scripts/check_ui_performance_budget.py
python scripts/check_interaction_feedback.py
python scripts/release.py --version V4.7 --dry-run
```

## Generate Archive

```powershell
python scripts/release.py --version V4.7
python scripts/check_release.py --version V4.7
```

## Excluded Content

- `.git`
- `.env` and environment variants
- SQLite databases
- uploads and storage
- logs
- `node_modules`
- `.next`
- Python caches
- pytest caches
- release archives from older runs
- Qdrant/Redis storage
- media/transcript/keyframe caches
- API keys or secret-looking values

## Current Limitations

- V4.7 release preparation updates the visible version to `V4.7 / 4.7.0` only after docs links, README assets, demo, RAG, provider dry-run, strict live E2E, UI performance budget, interaction feedback and release-safety gates pass.
- GitHub Release creation is prepared by documentation; it is not automatically published from this local workflow.
