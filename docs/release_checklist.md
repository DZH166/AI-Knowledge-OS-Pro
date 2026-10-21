# Release Checklist

Use this local checklist before packaging AI Knowledge OS Pro `V4.8 / 4.8.0`.

For the GitHub release flow, also use [GitHub Release Checklist](github_release_checklist.md).

## Product and data

- [ ] Existing documents, media, tasks and learning archives remain intact.
- [ ] Demo data is isolated, synthetic and visibly labelled.
- [ ] Real mode refuses unconfigured OCR, vision, transcription, embedding and LLM providers.
- [ ] Document, image, audio and video citations return to source evidence.
- [ ] Audio/video timestamp links seek the player and highlight the transcript segment.
- [ ] Video keyframes include `timestamp_ms` and open the correct playback position.
- [ ] Learning artifacts are generated only from real source chunks.

## Verification

- [ ] `python -m compileall backend/app scripts` passes.
- [ ] `python -m pytest` passes.
- [ ] Alembic is at `0006_v3_6_unified_media_tasks (head)`.
- [ ] Frontend typecheck passes in `frontend/`.
- [ ] Frontend production build passes in `frontend/`.
- [ ] `scripts/check_encoding.py` passes.
- [ ] `scripts/check_version.py` passes.
- [ ] `scripts/check_ui_performance_budget.py` passes.
- [ ] `scripts/check_interaction_feedback.py` passes.
- [ ] `scripts/check_request_cache.py` passes.
- [ ] `scripts/check_all.py --full` passes.
- [ ] `scripts/run_demo_e2e.py --strict` passes locally or the GitHub Actions `live-e2e` job passes.

## Documentation

- [ ] README reflects current capabilities and boundaries.
- [ ] Screenshots and demo guide match the current UI.
- [ ] Architecture, roadmap and V4.8 release reports are current.
- [ ] Learning and stage delivery logs are appended, not rewritten.

## Package safety

- [ ] Run `python scripts/release.py --version V4.8`.
- [ ] Run `python scripts/check_release.py --version V4.8`.
- [ ] Confirm forbidden entries are zero.
- [ ] Record the generated SHA256 outside the archive.
