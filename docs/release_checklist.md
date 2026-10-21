# Release Checklist

Use this checklist before publishing AI Knowledge OS Pro `V3.6 / 3.6.0`.

## Product and data

- [ ] Existing documents, media, tasks and learning archives remain intact.
- [ ] Real mode refuses unconfigured OCR, vision and transcription providers.
- [ ] Document, image, audio and video citations return to source evidence.
- [ ] Audio/video timestamp links seek the player and highlight the transcript segment.
- [ ] Video keyframes include `timestamp_ms` and open the correct playback position.
- [ ] Learning artifacts are generated only from real source chunks.

## Verification

- [ ] Backend compile passes.
- [ ] Pytest passes.
- [ ] Alembic is at `0006_v3_6_unified_media_tasks (head)`.
- [ ] Frontend typecheck passes.
- [ ] Frontend production build passes.
- [ ] `scripts/check_encoding.py` passes.
- [ ] `scripts/check_version.py` passes.

## Documentation

- [ ] README reflects current capabilities and boundaries.
- [ ] Screenshots and demo guide match the current UI.
- [ ] Architecture, roadmap and V3.6 acceptance report are current.
- [ ] Learning and stage delivery logs are appended, not rewritten.

## Package safety

- [ ] Run `python scripts/release.py --version V3.6`.
- [ ] Run `python scripts/check_release.py --version V3.6`.
- [ ] Confirm forbidden entries are zero.
- [ ] Record the generated SHA256 outside the archive.
