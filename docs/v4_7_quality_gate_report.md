# V4.7 Quality Gate Report

This report is the V4.7 quality-gate landing page. Detailed command results are recorded in `docs/v4_7_test_report.md` and acceptance status is recorded in `docs/v4_7_acceptance_report.md`.

## New V4.7 Gates

- `python scripts/check_ui_performance_budget.py`
- `python scripts/check_interaction_feedback.py`
- `python scripts/check_frontend_interactions.py`

## Final Local Evidence

- `python scripts/check_frontend_interactions.py`: passed with `buttons=79` and `high_risk=0`.
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_v4_7.json`: passed with 9 quick gates.
- `python scripts/check_all.py --release --json-report .pytest_tmp/check_all_release_v4_7.json`: passed.
- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full_v4_7.json`: passed.

## Full Gate Summary

- Backend compileall: passed.
- Backend pytest: `190 passed, 15 warnings`.
- Frontend typecheck/build: passed.
- Quick gates: encoding, version, docs links, README assets, frontend smoke, UI performance budget, interaction feedback, E2E scaffolding and CI artifacts all passed.
- Provider dry-run: passed without external calls.
- Browser demo E2E: `22 passed`.
- Demo readiness, demo RAG evaluation and full regression: passed.
- Secret scan, repo clean and release dry-run: passed.

## Boundaries

- Static UI gates are quality budgets, not real-user performance benchmarks.
- Provider dry-run proves boundary behavior; it does not claim real provider quality.
- Demo RAG evaluation uses deterministic seeded synthetic data and does not claim live LLM quality.
