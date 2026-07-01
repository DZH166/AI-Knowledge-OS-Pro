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
python scripts/release.py --version V3.8 --dry-run
```

## Generate Archive

```powershell
python scripts/release.py --version V3.8
python scripts/check_release.py --version V3.8
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

- V4.0 release should update the version to `V4.0 / 4.0.0` only after the V4.0 scope is actually implemented and verified.
- GitHub Release creation is prepared by documentation; it is not automatically published from this local workflow.
