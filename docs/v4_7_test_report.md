# V4.7 Test Report

This report records the real local validation evidence for the V4.7 interaction-performance, visual-learning and cleanup-governance release.

## Early Implementation Checks

- `python scripts/check_ui_performance_budget.py`: passed with `main_nav_targets=17` and budget `18`.
- `python scripts/check_frontend_interactions.py`: passed with `buttons=79` and `high_risk=0`.
- `python scripts/check_interaction_feedback.py`: passed with `api_like_buttons=27` and `high_risk=0`.
- `python -m pytest backend/tests/test_v3_9_frontend_smoke.py backend/tests/test_v4_7_ui_quality_gates.py`: `3 passed`.
- Frontend typecheck: passed.
- `python scripts/check_version.py`: passed for `V4.7 / 4.7.0`.

## Final Full Gate

Command:

```bash
python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_7.json
```

Result: passed.

Key evidence:

- Backend compileall: passed.
- Backend pytest: `190 passed, 15 warnings`.
- Observability and citation contracts: `3 passed`.
- Frontend typecheck: passed.
- Frontend production build: passed; 29 app routes generated, including `/learning/project-structure`.
- Encoding check: passed for 406 UTF-8 text files; immutable legacy log lines were preserved.
- Version check: passed for `V4.7 / 4.7.0`.
- Docs links: passed with 130 files, 56 local links, 7 local images and 11 Mermaid blocks.
- README assets: passed with 7 local images, 6 external images and 7 screenshot placeholders.
- Frontend smoke: passed with `required_routes=28` and `nav_targets=17`.
- UI performance budget: passed with `main_nav_targets=17`, budget `18`, and `visual_pages=3`.
- Interaction feedback: passed with `buttons=79`, `api_like_buttons=27`, `high_risk=0`.
- CI artifacts: passed with 13 required commands and 32 required artifact paths.
- Provider dry-run: passed; no external provider call was made, and missing providers reported explicit NOT_CONFIGURED-style states.
- Optional demo browser E2E: passed with `22 passed`.
- Demo readiness: passed on isolated `.pytest_tmp/v4_7_demo_showcase.db`.
- Demo RAG evaluation: passed with deterministic seeded data, `valid_citations=1`, `valid_locators=9`, and `timestamp_citations=1`.
- Full regression: passed with 67 checks.
- Secret scan: passed with `findings=0`.
- Repo clean: passed with forbidden tracked files `0`.
- Release dry-run: passed with `included_files=413`, no secrets, no database, no uploads and no cache.

## Boundary Notes

- Browser E2E used seeded synthetic demo data that is explicitly labelled as synthetic.
- Provider evaluation was dry-run only and did not call paid or external services.
- No fake OCR, transcription, citation, answer, test result or release result was recorded.
