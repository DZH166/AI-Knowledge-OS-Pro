# Versioning

AI Knowledge OS Pro uses visible product milestones and semantic versions.

## Current Version

Current audited baseline:

```text
V3.8 / 3.8.0
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

## Planned V4.0 Version

V4.0 should use:

```text
V4.0 / 4.0.0
```

Do not update the public version badge before V4.0 functionality, docs and verification evidence are aligned.

## Learning Archive Rule

`docs/learning_log.md` and `docs/stage_delivery_log.md` are append-only. New versions must add new entries instead of replacing historical records.

## Release Tag

Recommended V4.0 tag after final verification:

```text
v4.0.0
```
