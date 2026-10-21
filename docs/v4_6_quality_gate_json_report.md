# V4.6 Quality Gate JSON Report

V4.6 extends the unified quality gate with optional machine-readable output:

```powershell
python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick.json
```

## Purpose

Terminal output is useful while developing, but it is hard to reuse in CI artifacts, learning package generation and future self-check dashboards. The JSON report records the selected mode, overall status, gate count and per-gate status/duration/failure/next-step fields.

## Behavior

- `--json-report <path>` can be used with any `check_all.py` mode.
- Relative paths are resolved from the repository root.
- Parent directories are created automatically.
- The report is written in the `finally` block, so partial gate evidence is preserved when a gate fails.
- The report includes Git provenance fields: `git.branch`, `git.commit`, `git.short_commit` and `git.dirty`.
- The feature does not call external providers, change application data or change release packaging behavior.

## Git Provenance

Each generated quality report now records the Git state at the time the gate ran:

```json
{
  "git": {
    "branch": "codex/v4.6-project-structure-learning",
    "commit": "cc136206d19b9bc5845692edfd93e7d8edaad666",
    "short_commit": "cc13620",
    "dirty": false
  }
}
```

This keeps local self-check evidence, CI artifacts, history indexes and future learning-package drafts tied to a concrete source revision. If Git metadata cannot be read, string fields fall back to `unknown` and `dirty` becomes `null`; the quality gate itself does not fail just because Git is unavailable.

## CI Integration

GitHub Actions now runs:

```powershell
python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp
```

The quality job uploads `.pytest_tmp/check_all_*.json`, `.pytest_tmp/check_all_*_summary.md`, self-check indexes, next-command readiness files, loop reports, loop step readiness files and GitHub Actions status diagnostic reports as the `quality-gate-json` artifact when present.

`run_self_check.py` expands to:

```powershell
python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick.json
python scripts/summarize_quality_report.py --input .pytest_tmp/check_all_quick.json --output .pytest_tmp/check_all_quick_summary.md
python scripts/check_quality_artifacts.py --json .pytest_tmp/check_all_quick.json --summary .pytest_tmp/check_all_quick_summary.md --expected-mode quick --require-passed
```

## Verification

- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick.json`: passed and wrote `mode=quick`, `status=passed`, `gate_count=7`.
- `python -m pytest backend/tests/test_v4_3_api_regression.py::test_v4_3_static_quality_gate_scripts_pass`: `1 passed`, covering the quick report contract.

## Markdown Summary

`scripts/summarize_quality_report.py` converts a JSON quality report into a Markdown summary with Git provenance, gate counts, per-gate status and an optimization focus section. The next-action wording uses the report mode, so quick and release artifacts can be read without mode confusion. It is intended for CI artifacts, learning-package evidence and future self-check dashboards.

Verified commands:

- `python -m pytest backend/tests/test_v4_6_quality_report_summary.py`: `2 passed`.
- `python scripts/summarize_quality_report.py --input .pytest_tmp/check_all_quick.json --output .pytest_tmp/check_all_quick_summary.md`: passed after the quick JSON report was generated.

## Artifact Validation

`scripts/check_quality_artifacts.py` validates the JSON schema, Git provenance, mode, report status, gate count, gate fields, gate durations and required Markdown summary sections. It lets CI fail before uploading malformed self-check evidence.

## One-Command Self-Check

`scripts/run_self_check.py` is the preferred local and CI entrypoint for this evidence loop:

```powershell
python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --write-index
```

It runs the quality gate, writes JSON evidence, creates a Markdown summary, validates both artifacts and can refresh the self-check history index. `--mode release` is available for release-safety evidence, and `--mode full` now preserves full-gate evidence in the same self-check bundle.

Optional comparison against a previous report:

```powershell
python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-to .pytest_tmp/previous/check_all_quick.json
```

Automatic comparison against the previous report in the same output directory:

```powershell
python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan
```

When `--compare-latest` is used, the wrapper checks whether `check_all_<mode>.json` already exists in the output directory before the new run starts. If it exists, the wrapper copies it to `baseline_check_all_<mode>.json` and compares the new report against that saved baseline. If no previous report exists, it prints `auto_compare=skipped reason=no_previous_report` and continues without inventing comparison evidence.

The saved auto-comparison baseline is stored in an isolated system temporary directory keyed by the self-check output path, rather than inside the active output directory. This keeps full-gate comparisons stable even when demo/E2E steps recreate `.pytest_tmp` artifacts during the run.

The comparison layer is powered by `scripts/compare_quality_reports.py`. It detects status changes, failed-current gates, missing gates, new gates and gate slowdowns above a configurable threshold. This is meant for continuous optimization review, not for fake scoring.

Repeated gate names are preserved by occurrence. For example, full mode runs `E2E scaffolding` twice; the first occurrence keeps the original name and the second is compared as `E2E scaffolding #2`, so the comparison gate count stays aligned with the source report.

Verified commands:

- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_quality_artifacts.py backend/tests/test_v4_6_quality_report_summary.py`: `7 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check`: passed.
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_quality_report_comparison.py backend/tests/test_v4_6_self_check_improvement_plan.py`: `15 passed`.

## Quality Report Comparison

`scripts/compare_quality_reports.py` compares two JSON reports:

```powershell
python scripts/compare_quality_reports.py --base old.json --current new.json --output comparison.md --json-output comparison.json
```

It reports:

- status changes such as `passed -> failed`;
- missing and newly added gates;
- slower gates above `--slow-threshold-sec`;
- a `regression_count` for failed-current or missing gate regressions.

Verified commands:

- `python -m pytest backend/tests/test_v4_6_quality_report_comparison.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_quality_artifacts.py backend/tests/test_v4_6_quality_report_summary.py`: `10 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-to .pytest_tmp/self_check_baseline/check_all_quick.json --fail-on-regression`: passed with `regression_count=0`.
- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_improvement_plan_commands.py`: `36 passed` after moving auto-comparison baselines outside the active output directory.
- `python -m pytest backend/tests/test_v4_6_quality_report_comparison.py backend/tests/test_v4_6_run_self_check.py`: `21 passed` after preserving repeated gate occurrences.
- `python scripts/compare_quality_reports.py --base <full-baseline> --current <same-full-baseline> --json-output .pytest_tmp/check_all_full_duplicate_gate_comparison.json --output .pytest_tmp/check_all_full_duplicate_gate_comparison.md --fail-on-regression`: passed with `base_gate_count=22`, `current_gate_count=22` and `regression_count=0`.

## GitHub Actions Status Diagnostic

`scripts/check_github_actions.py` can query the latest GitHub Actions run for a branch and commit, or evaluate a saved Actions API JSON payload offline:

```powershell
python scripts/check_github_actions.py --json-output .pytest_tmp/github_actions.json --markdown-output .pytest_tmp/github_actions.md
```

The script reads `GH_TOKEN` or `GITHUB_TOKEN` when available, but it never prints token values. Without remote access, missing permissions or a private-repo 404, it reports `result=unavailable` by default instead of breaking local quality gates. Use `--require-success` when a release operator explicitly wants remote CI success to be mandatory.

GitHub Actions runs the diagnostic with `GITHUB_TOKEN: ${{ github.token }}` and `actions: read` permission, then uploads `.pytest_tmp/github_actions_status.json` and `.pytest_tmp/github_actions_status.md` with the quality evidence bundle. The artifact is diagnostic evidence only; the default CI step does not use `--require-success`.

`scripts/check_github_actions_report.py` validates this status evidence before it is trusted. It checks schema version, result/status/conclusion consistency, owner/repo shape, Actions run URL shape, branch/head branch agreement, unavailable failure text and optional Markdown content. `check_github_actions.py` now invokes the validator automatically after writing JSON, and CI runs the validator explicitly as a separate step.

`scripts/check_ci_artifacts.py` also checks ordering for the evidence flow. It now verifies that quick self-check runs before next-command readiness validation, loop reports are validated after generation, release comparison precedes full-ready handoff, GitHub Actions status reports are generated before validation, and the `quality-gate-json` upload appears after the status report validator.

The checker can now write its own contract evidence:

```powershell
python scripts/check_ci_artifacts.py --json-output .pytest_tmp/ci_artifacts_contract.json --markdown-output .pytest_tmp/ci_artifacts_contract.md
```

CI uploads those two files with the rest of `quality-gate-json`, so the artifact bundle contains the contract that proved the bundle was configured correctly.

`scripts/check_ci_artifacts_report.py` validates the contract evidence before it is trusted. It checks schema version, pass/fail consistency, safe workflow path shape, required count fields, failure count alignment and optional Markdown content. `check_ci_artifacts.py` now invokes this validator automatically after writing JSON/Markdown output, and CI runs the validator explicitly as a separate step before uploading `quality-gate-json`.

Verified commands:

- `python -m pytest backend/tests/test_v4_6_github_actions_status.py`: `7 passed` for offline GitHub Actions success, failure, pending and unavailable states.
- `python scripts/check_github_actions.py --json-output .pytest_tmp/github_actions_status.json --markdown-output .pytest_tmp/github_actions_status.md`: completed with `result=unavailable` and `failure=github_api_http_404`, preserving a local report without failing the default diagnostic.
- `python -m pytest backend/tests/test_v4_6_github_actions_report.py backend/tests/test_v4_6_github_actions_status.py backend/tests/test_v4_6_ci_artifacts.py`: `22 passed` after adding the status report validator.
- `python scripts/check_github_actions.py --json-output .pytest_tmp/github_actions_status_validator.json --markdown-output .pytest_tmp/github_actions_status_validator.md`: completed with `result=unavailable` and automatically validated the JSON/Markdown reports.
- `python scripts/check_ci_artifacts.py`: passed with `required_commands=11`, `required_artifact_paths=30`, `required_workflow_snippets=2` after requiring the explicit CI status report validator step.
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py`: `12 passed` after adding required CI evidence ordering checks.
- `python scripts/check_ci_artifacts.py`: passed with `required_ordered_groups=5`.
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py`: `16 passed` after adding CI artifact contract JSON/Markdown report coverage and failed-report coverage.
- `python scripts/check_ci_artifacts.py --json-output .pytest_tmp/ci_artifacts_contract_local.json --markdown-output .pytest_tmp/ci_artifacts_contract_local.md`: passed with `required_commands=12`, `required_artifact_paths=32`, `required_workflow_snippets=2`, `required_ordered_groups=6`.
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py backend/tests/test_v4_6_ci_artifacts_report.py`: `25 passed` after adding CI artifact contract report validation.
- `python scripts/check_ci_artifacts.py --json-output .pytest_tmp/ci_artifacts_contract_local_validator.json --markdown-output .pytest_tmp/ci_artifacts_contract_local_validator.md`: passed with `required_commands=13`, `required_artifact_paths=32`, `required_workflow_snippets=2`, `required_ordered_groups=6` and `ci_artifacts_report=checked`.

## Self-Check History Index

`scripts/index_self_checks.py` scans self-check artifact directories and creates trend-friendly JSON plus Markdown:

```powershell
python scripts/index_self_checks.py --input-dir .pytest_tmp --output .pytest_tmp/self_check_index.json --markdown-output .pytest_tmp/self_check_index.md
```

The index records run count, passed/failed run counts, regression run count, latest run metadata, Git provenance and a table of runs. It is a local artifact for learning and continuous-improvement review.

The indexer ignores pytest `test_*` temporary folders so synthetic test fixtures cannot pollute real self-check history.

Verified commands:

- `python -m pytest backend/tests/test_v4_6_self_check_index.py`: `3 passed`.
- `python scripts/index_self_checks.py --input-dir .pytest_tmp --output .pytest_tmp/self_check_index.json --markdown-output .pytest_tmp/self_check_index.md`: passed and indexed the real quick self-check run.

`run_self_check.py --write-index` now refreshes `self_check_index.json` and `self_check_index.md` automatically in the selected output directory.

Verified commands:

- `python -m pytest backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_self_check_index.py`: `8 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --write-index`: passed and wrote the history index.

## Self-Check Improvement Plan

`scripts/plan_self_check_improvements.py` turns self-check history into a data-driven action list with executable command suggestions:

```powershell
python scripts/plan_self_check_improvements.py --index .pytest_tmp/self_check/self_check_index.json --output .pytest_tmp/self_check/self_check_improvement_plan.md --json-output .pytest_tmp/self_check/self_check_improvement_plan.json
```

It recommends actions for failed runs, regression reports, missing comparison baselines and slower gates. Each item includes a `command` field when the next step can be safely expressed as a repeatable local command; human-inspection items keep the command empty. It does not create a fake quality score; it only summarizes recorded self-check evidence.

`scripts/check_improvement_plan_commands.py` validates executable `command` suggestions in the JSON plan against a narrow self-check allowlist. It accepts deterministic quality commands such as `run_self_check.py` quick/release/full loops and the legacy `check_all.py --full --json-report` handoff, requires artifact paths to stay under `.pytest_tmp`, and rejects unrelated commands.

`run_self_check.py --write-plan` refreshes this plan after the self-check artifacts and index are generated, then runs the command validator automatically. The final self-check summary also prints `next_command_priority`, `next_command_title` and `next_command` when a validated command suggestion exists.

The wrapper also writes:

- `self_check_next_command.json`
- `self_check_next_command.md`
- `self_check_manifest.json`
- `self_check_manifest.md`

The next-command files contain the first validated next command or an explicit `status=none` marker. The manifest records the self-check mode, comparison state, artifact paths, artifact existence and next command summary in one place. GitHub Actions uploads these files with the other quality-gate artifacts.

`scripts/check_self_check_manifest.py` validates the manifest itself before the wrapper finishes. It accepts quick, release and full self-check modes, requires declared artifact paths to stay under `.pytest_tmp`, checks each `exists` flag against the filesystem, requires the core quality JSON/Markdown artifacts to exist, and reuses the command allowlist for `next_command.command`.

`scripts/run_next_self_check.py` is the safe handoff from evidence to automation. By default it reads `self_check_next_command.json`, validates the embedded command through the same allowlist and prints `result=ready` or `result=none`. With `--json-output` and `--markdown-output`, it writes machine-readable and human-readable readiness reports under `.pytest_tmp`. It only executes the command when called with `--execute`, and execution uses tokenized subprocess calls instead of shell strings.

`scripts/check_next_self_check_report.py` validates the readiness JSON before CI trusts it. It checks schema version, status/result consistency, safe `.pytest_tmp` paths, optional Markdown artifact existence and command allowlist compliance.

`scripts/run_self_check_loop.py` wraps the same evidence path in a bounded loop. It starts from `run_self_check.py`, inspects generated next-command artifacts, and can optionally execute validated next steps up to `--max-steps`. CI uses dry-run mode to preserve JSON and Markdown loop reports without running extra heavy gates; local users can opt into `--execute-next`. Real loop steps also write `next_self_check_step_N.md`, so each machine-readable readiness JSON has a matching human-readable handoff.

`scripts/check_self_check_loop_report.py` validates loop reports before they are trusted or uploaded. It checks schema version, mode, bounded step counts, `.pytest_tmp` paths, readiness JSON/Markdown artifact existence and allowlisted commands.

Verified commands:

- `python -m pytest backend/tests/test_v4_6_self_check_improvement_plan.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_self_check_index.py`: `12 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --write-index --write-plan`: passed and generated a data-driven improvement plan.
- `python -m pytest backend/tests/test_v4_6_improvement_plan_commands.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_self_check_improvement_plan.py`: `20 passed`.
- `python -m pytest backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `22 passed`.
- `python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression`: passed and automatically validated `self_check_manifest.json`.
- `python -m pytest backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `26 passed`.
- `python -m pytest backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `25 passed` after aligning manifest validation with full self-check mode.
- `python scripts/check_self_check_manifest.py --manifest-json .pytest_tmp/self_check_full/self_check_manifest.json`: passed for a generated full self-check manifest.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json`: passed with `result=ready`.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --execute`: passed and executed the validated quick comparison self-check.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_release/self_check_next_command.json --execute`: passed and advanced release self-check to a full-gate recommendation.
- `python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full.json`: passed through the earlier next-command runner with backend tests, frontend typecheck/build, demo E2E, demo RAG evaluation, full regression and release dry-run all green.
- `python -m pytest backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_self_check_manifest.py backend/tests/test_v4_6_run_self_check.py backend/tests/test_v4_6_improvement_plan_commands.py`: `29 passed`.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --json-output .pytest_tmp/next_self_check.json`: passed and wrote `result=ready`.
- `python -m pytest backend/tests/test_v4_6_run_self_check_loop.py backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_run_self_check.py`: `27 passed`.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop --max-steps 1 --json-output .pytest_tmp/self_check_loop.json`: passed and wrote a bounded loop report with one ready next step.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop_ci --max-steps 1 --dry-run --json-output .pytest_tmp/self_check_loop_dry_run.json`: passed and wrote a dry-run loop plan.
- `python -m pytest backend/tests/test_v4_6_self_check_loop_report.py backend/tests/test_v4_6_run_self_check_loop.py`: `12 passed`.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop_ci --max-steps 1 --dry-run --json-output .pytest_tmp/self_check_loop.json`: passed and automatically validated the dry-run loop report.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop --max-steps 1 --json-output .pytest_tmp/self_check_loop_real.json`: passed and automatically validated the loop report with one ready step.
- `python -m pytest backend/tests/test_v4_6_self_check_loop_report.py backend/tests/test_v4_6_run_self_check_loop.py`: `13 passed` after adding Markdown loop reports.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop --max-steps 1 --dry-run --json-output .pytest_tmp/self_check_loop.json --markdown-output .pytest_tmp/self_check_loop.md`: passed and wrote/validated the Markdown summary.
- `python -m pytest backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_run_self_check_loop.py`: `16 passed` after adding Markdown readiness reports.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --json-output .pytest_tmp/next_self_check.json --markdown-output .pytest_tmp/next_self_check.md`: passed and wrote `result=ready`.
- `python -m pytest backend/tests/test_v4_6_next_self_check_report.py backend/tests/test_v4_6_run_next_self_check.py`: `15 passed`.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --json-output .pytest_tmp/next_self_check.json --markdown-output .pytest_tmp/next_self_check.md`: passed and automatically validated `next_self_check.json`.
- `python -m pytest backend/tests/test_v4_6_run_self_check_loop.py backend/tests/test_v4_6_self_check_loop_report.py backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_next_self_check_report.py`: `29 passed` after adding per-step readiness Markdown to loop reports.
- `python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop_step_markdown_real --max-steps 1 --json-output .pytest_tmp/self_check_loop_step_markdown_real.json --markdown-output .pytest_tmp/self_check_loop_step_markdown_real.md`: passed and generated `next_self_check_step_1.md`.
- `python scripts/check_ci_artifacts.py`: passed with `required_commands=9` and `required_artifact_paths=28`.
- `python scripts/check_ci_artifacts.py`: passed with `required_commands=10`, `required_artifact_paths=30`, `required_workflow_snippets=2` after adding CI GitHub Actions status artifact coverage.
- `python scripts/check_all.py --quick --json-report .pytest_tmp/check_all_quick_ci_artifacts.json`: passed with the `CI artifacts` gate included.
- `python scripts/run_self_check.py --mode full --output-dir .pytest_tmp/self_check_full --write-index --write-plan --dry-run`: passed and planned the full self-check artifact bundle.
- `python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --compare-latest --write-index --write-plan --fail-on-regression`: passed and now recommends `python scripts/run_self_check.py --mode full --output-dir .pytest_tmp/self_check_full --write-index --write-plan`.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_release/self_check_next_command.json --json-output .pytest_tmp/self_check_release/next_self_check_full_ready.json --markdown-output .pytest_tmp/self_check_release/next_self_check_full_ready.md`: passed and validated the full self-check handoff with `result=ready`.
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py backend/tests/test_v4_6_run_next_self_check.py backend/tests/test_v4_6_next_self_check_report.py`: `20 passed` after adding CI release-to-full handoff artifact validation.
- `python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --write-index --write-plan`: passed and generated the release self-check baseline.
- `python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --compare-latest --write-index --write-plan --fail-on-regression`: passed with `regression_count=0` and recommended the full self-check command.
- `python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_release/self_check_next_command.json --json-output .pytest_tmp/self_check_release/next_self_check_full_ready.json --markdown-output .pytest_tmp/self_check_release/next_self_check_full_ready.md`: passed with `result=ready`.
- `python scripts/check_next_self_check_report.py --report-json .pytest_tmp/self_check_release/next_self_check_full_ready.json`: passed.
- `python -m pytest backend/tests/test_v4_6_github_actions_status.py`: `7 passed` for the GitHub Actions status diagnostic.
- `python scripts/check_github_actions.py --json-output .pytest_tmp/github_actions_status.json --markdown-output .pytest_tmp/github_actions_status.md`: completed with `result=unavailable` because the unauthenticated GitHub API returned `github_api_http_404`.
- `python -m pytest backend/tests/test_v4_6_ci_artifacts.py backend/tests/test_v4_6_github_actions_status.py`: `15 passed` after requiring CI Actions read permission, token env injection and status diagnostic artifact upload paths.
- `python -m pytest backend/tests/test_v4_6_github_actions_report.py backend/tests/test_v4_6_github_actions_status.py backend/tests/test_v4_6_ci_artifacts.py`: `22 passed` after requiring GitHub Actions status report schema validation.
- `python scripts/check_ci_artifacts.py`: passed with `required_commands=11`, `required_artifact_paths=30`, `required_workflow_snippets=2`, `required_ordered_groups=5`.
