## Summary

Describe the user-visible outcome and the engineering boundary changed.

## Verification

- [ ] `python -m compileall backend/app backend/alembic scripts`
- [ ] `python -m pytest`
- [ ] `python scripts/check_encoding.py`
- [ ] `python scripts/check_version.py`
- [ ] `npm run typecheck` in `frontend/`
- [ ] `npm run build` in `frontend/`
- [ ] Release safety check when packaging behavior changes

## Real-mode boundary

- [ ] Missing providers return explicit `*_NOT_CONFIGURED` errors.
- [ ] No fake OCR, transcription, citation, answer, or learning artifact is persisted.

## Data and documentation

- [ ] Migration and downgrade behavior are documented when schema changes.
- [ ] `docs/learning_log.md` and `docs/stage_delivery_log.md` are append-only.
- [ ] No `.env`, database, uploads, logs, caches, build output, or private source material is committed.
