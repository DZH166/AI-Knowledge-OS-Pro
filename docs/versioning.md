# Versioning

AI Knowledge OS Pro uses visible product milestones and semantic versions.

## Current Version

Current audited baseline:

```text
V4.3 / 4.3.0
```

Version locations include:

- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/tests/test_health.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `README.md`
- `.github/workflows/ci.yml`

Run:

```powershell
python scripts/check_version.py
```

## Release Version

V4.3 uses:

```text
V4.3 / 4.3.0
```

Do not update the public version badge before functionality, docs and verification evidence are aligned.

## Learning Archive Rule

`docs/learning_log.md` and `docs/stage_delivery_log.md` are append-only. New versions must add new entries instead of replacing historical records.

## Release Tag

Recommended V4.3 tag after final verification:

```text
v4.3.0
```
