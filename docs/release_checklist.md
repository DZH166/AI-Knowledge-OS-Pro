# Release Checklist

Use this local checklist before packaging 溯知 Evidence OS `V5.1 / 5.1.0`.

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
- [ ] Alembic has one head at `0008_v5_agent_runtime`.
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
- [ ] V5 architecture, fixed evaluation and acceptance report are current.
- [ ] Learning and stage delivery logs are appended, not rewritten.

## Package safety

- [ ] Run `python scripts/evaluate_agentic_rag.py --mode demo --output docs/v5_agentic_rag/evaluation_report.json`.
- [ ] Run `python scripts/check_v5_acceptance.py`.
- [ ] Run `python scripts/release.py --version V5.1`.
- [ ] Run `python scripts/check_release.py --version V5.1`.
- [ ] Confirm forbidden entries are zero.
- [ ] Record the generated SHA256 outside the archive.
