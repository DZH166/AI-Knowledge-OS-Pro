# V4.7 Test Sprawl Audit

## Findings

- Backend test files: 56.
- V4.6 added 16 self-check/report tests.
- V4.7 adds focused UI quality-gate regression tests in `backend/tests/test_v4_7_ui_quality_gates.py`.

## Kept

The V4.6 tests are kept because they protect report schema, CI artifact contracts, comparison baselines and command allowlists.

## Cleanup Direction

- Group future self-check tests by subsystem instead of one file per small script.
- Prefer shared fixtures for report JSON payloads.
- Keep high-level smoke tests for user-facing pages separate from evidence-pipeline tests.
