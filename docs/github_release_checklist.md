# GitHub Release Checklist

Use this checklist before publishing AI Knowledge OS Pro `V3.8 / 3.8.0` or drafting a GitHub Release.

## Product Integrity

- [ ] Existing backend, frontend, docs, scripts, learning archives and historical version records are preserved.
- [ ] Real mode refuses unconfigured OCR, vision, transcription, embedding and LLM providers.
- [ ] Demo mode is visibly labelled and uses only synthetic/public sample data.
- [ ] README does not claim planned features are already implemented.
- [ ] Audio/video timestamp citations and media task results still work.

## Verification

- [ ] `python -m compileall backend/app scripts` passes.
- [ ] `python -m pytest` passes.
- [ ] `npm run typecheck` passes in `frontend/`.
- [ ] `npm run build` passes in `frontend/`.
- [ ] `python scripts/check_encoding.py` passes.
- [ ] `python scripts/check_secrets.py` passes.
- [ ] `python scripts/check_repo_clean.py` passes.
- [ ] `python scripts/release.py --version V3.8 --dry-run` passes.

## Documentation

- [ ] README contains positioning, screenshots/placeholders, demo path, architecture, workflows, limits and resume expression.
- [ ] `docs/demo_script.md` matches the current UI.
- [ ] `docs/architecture_diagram.md` renders Mermaid diagrams.
- [ ] `docs/resume_pitch.md` is current.
- [ ] `docs/learning_log.md` and `docs/stage_delivery_log.md` were appended, not rewritten.

## Release Safety

- [ ] No `.env`, API keys, SQLite DBs, uploads, logs, media files, caches, `node_modules`, `.next`, Qdrant/Redis data or old releases are tracked.
- [ ] Release dry-run reports included/excluded file counts and all risk flags as `no`.
- [ ] Generated release zip passes `scripts/check_release.py` before sharing.
- [ ] SHA256 is recorded outside the archive.

## GitHub Release Draft Notes

- Tag: `v3.8.0`.
- Title: `AI Knowledge OS Pro V3.8 - GitHub Portfolio Demo Docs and Reset Workflow`.
- Attach release zip only after local and CI checks pass.
