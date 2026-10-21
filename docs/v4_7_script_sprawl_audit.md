# V4.7 Script Sprawl Audit

## Core Quality Gates

Keep these in `scripts/` root because they are CI or release-facing:

- `check_all.py`
- `check_encoding.py`
- `check_version.py`
- `check_docs_links.py`
- `check_readme_assets.py`
- `check_frontend_smoke.py`
- `check_ui_performance_budget.py`
- `check_interaction_feedback.py`
- `check_secrets.py`
- `check_repo_clean.py`
- `release.py`
- `check_release.py`

## Self-Check Support Tools

These are valuable but dense. They should be documented as a self-check subsystem and may later move under `scripts/maintenance/self_check/` if CI paths are updated together.

- `run_self_check.py`
- `run_next_self_check.py`
- `run_self_check_loop.py`
- `summarize_quality_report.py`
- `compare_quality_reports.py`
- `index_self_checks.py`
- `plan_self_check_improvements.py`
- `check_*_report.py` validators

## V4.7 Decision

No move was performed in this pass. The replacement entry points are documented before any future relocation.
