# Contributing

溯知 Evidence OS is developed as an evidence-native research agent built on multimodal RAG. Changes should preserve existing data, migrations and append-only learning archives.

## Local setup

1. Copy `.env.example` to `.env` and `backend/.env.example` to `backend/.env`.
2. Start Qdrant and Redis with `docker compose up -d qdrant redis`.
3. Install Python dependencies from `backend/requirements.txt`.
4. Run `python -m alembic upgrade head`.
5. Install frontend dependencies with `npm ci` in `frontend/`.

See `README.md` and `docs/local_setup_windows.md` for complete commands.

## Required verification

```text
python -m compileall backend/app backend/alembic scripts
python -m pytest
python scripts/check_encoding.py
python scripts/check_version.py
cd frontend
npm run typecheck
npm run build
```

For release-related changes:

```text
python scripts/release.py --version V5.3
python scripts/check_release.py --version V5.3
```

## Engineering rules

- Keep real mode honest. Missing providers must return explicit `NOT_CONFIGURED`-style errors.
- Do not generate fake OCR, subtitles, citations, answers or learning content.
- Add Alembic migrations for schema changes and verify upgrade/downgrade behavior.
- Preserve source locators for document chunks, image evidence and media timestamps.
- Keep changes scoped and add tests proportional to behavioral risk.
- Append to `docs/learning_log.md` and `docs/stage_delivery_log.md`; never rewrite historical entries.
- Never commit `.env`, API keys, databases, uploads, logs, caches, `node_modules`, `.next` or release archives.
