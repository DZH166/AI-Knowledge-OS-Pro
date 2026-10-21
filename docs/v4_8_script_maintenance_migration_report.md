# V4.8 Script Maintenance Migration Report

V4.8 reduces root `scripts/` sprawl while preserving existing commands.

## Migration

Moved self-check implementations to `scripts/maintenance/self_check/`:

- `run_self_check.py`
- `run_next_self_check.py`
- `run_self_check_loop.py`
- `summarize_quality_report.py`
- `compare_quality_reports.py`
- `index_self_checks.py`
- `plan_self_check_improvements.py`
- `check_self_check_manifest.py`
- `check_self_check_loop_report.py`
- `check_next_self_check_report.py`
- `check_improvement_plan_commands.py`
- `check_quality_artifacts.py`

Moved CI diagnostic implementations to `scripts/maintenance/ci/`:

- `check_ci_artifacts.py`
- `check_ci_artifacts_report.py`
- `check_github_actions.py`
- `check_github_actions_report.py`

## Compatibility

Root-level wrapper files remain in place, so existing commands and CI steps such as `python scripts/run_self_check.py ...` still work.

## Verification So Far

- `python scripts/check_ci_artifacts.py`: passed through the root wrapper.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check_wrapper_probe --write-index --write-plan --dry-run`: passed through the root wrapper.
- `python -m compileall scripts/maintenance scripts/check_ci_artifacts.py scripts/run_self_check.py`: passed.

