# V4.7 Predevelopment Audit

This audit records the real starting point for the V4.7 interaction, visualization and cleanup pass. It is based on branch `feature/v4.7-performance-visual-cleanup`, created from `codex/v4.6-project-structure-learning` at commit `888e312`.

## Git Baseline

- Current branch before V4.7 work: `codex/v4.6-project-structure-learning`
- V4.7 working branch: `feature/v4.7-performance-visual-cleanup`
- Starting commit: `888e312`
- Diff base: `main...codex/v4.6-project-structure-learning`
- Diff size: 45 files changed, 8535 insertions, 13 deletions
- Working tree before edits: clean

## V4.6 Delta From Main

Added files: 35

- Backend test files added: 16
- Script files added: 16
- Documentation report files added: 2
- Frontend page files added: 1

Modified files: 10

- CI workflow
- Existing frontend smoke and API regression tests
- README-adjacent docs and append-only learning logs
- `frontend/components/AppShell.tsx`
- `scripts/check_all.py`
- `scripts/check_frontend_smoke.py`

## New V4.6 Script Files

- `scripts/check_ci_artifacts.py`
- `scripts/check_ci_artifacts_report.py`
- `scripts/check_github_actions.py`
- `scripts/check_github_actions_report.py`
- `scripts/check_improvement_plan_commands.py`
- `scripts/check_next_self_check_report.py`
- `scripts/check_quality_artifacts.py`
- `scripts/check_self_check_loop_report.py`
- `scripts/check_self_check_manifest.py`
- `scripts/compare_quality_reports.py`
- `scripts/index_self_checks.py`
- `scripts/plan_self_check_improvements.py`
- `scripts/run_next_self_check.py`
- `scripts/run_self_check.py`
- `scripts/run_self_check_loop.py`
- `scripts/summarize_quality_report.py`

## Version Inconsistency

- `README.md` still presents `V4.5 / 4.5.0`.
- `frontend/package.json` still uses `4.5.0`.
- `frontend/components/AppShell.tsx` still brands the product as V4.5.
- `backend/app/core/config.py` still uses `V4.5 / 4.5.0`.
- `scripts/check_all.py`, `scripts/check_version.py`, `scripts/release.py`, `scripts/check_release.py` still default to V4.5.

This is a real release-readiness issue, not only a cosmetic mismatch. V4.7 must update current-version surfaces while preserving historical V4.5 and V4.6 reports as historical records.

## Navigation And Information Architecture

Current AppShell nav targets: 25.

High-frequency entries are present, but low-frequency diagnostic or deep pages are mixed into the main path:

- Documents, code repositories and error archive are useful, but they create extra main-nav weight.
- Learning has 8 direct entries, which is too many for a beginner trying to decide where to start.
- Portfolio has both summary and project-review entries; both are valuable, but the distinction is not obvious from navigation alone.
- System diagnostics are correctly grouped, but the overall sidebar still feels like a site map instead of a guided product workflow.

V4.7 should keep all existing routes, but reduce the main navigation to the routes that represent daily user decisions.

## Interaction Feedback Audit

Static frontend scan:

- Total `<button>` elements: 78
- Buttons with `onClick`: 74
- Buttons with explicit `disabled`: 36

This means many clickable controls may not declare a disabled/pending state. Some are simple local UI toggles and do not need network pending state, but high-frequency async actions need consistent feedback:

- Upload media/document actions
- Task retry/cancel/refresh actions
- Chat ask/regenerate/favorite actions
- Provider test actions
- Portfolio generation/export actions
- Learning review/progress/generation actions

The main risk is not backend slowness alone; it is user-perceived latency caused by unclear feedback during async actions and repeated-click uncertainty.

## Page Experience Findings

- Dashboard already has useful data, but the first screen is still closer to status cards than a guided command center.
- `/learning/project-structure` is valuable, but it reads like a documentation page placed inside the app. It needs diagrams, evidence chains, module maps and learning stepper interactions.
- Task Center already exposes progress and events, but retry/cancel actions should show per-task pending state and prevent repeated clicks.
- Upload Center shows a good process map, but the five workflow cards overload the first visible section.
- Portfolio pages include evidence, but generation buttons need clearer pending and retry behavior.

## Script And Test Sprawl Risk

V4.6 added a useful self-check system, but the footprint is heavy:

- 16 new scripts are all in the root `scripts/` directory.
- 16 new backend tests validate the self-check/report layer.
- Several names are close enough to confuse maintainers: `check_*_report`, `run_*_self_check`, `index_*`, `summarize_*`, `plan_*`.

These files should not be deleted blindly. V4.7 should classify them into:

- Core gates used by CI or `check_all.py`
- Maintenance helpers used by self-check workflows
- Report validators that could be grouped or documented as support tooling
- Historical reports that can be archived without breaking release evidence

## Initial Hypotheses For Slowness

- First-page development latency is partly caused by Next.js route compilation, not product code alone.
- User-perceived button slowness is likely caused by missing immediate pending/disabled feedback.
- Repeated-click risk exists where async actions set message/error but do not track action-specific pending state.
- Main-thread blocking risk is currently low; most heavy work is backend-side. The frontend risk is more about repeated fetches, long text rendering and page density.
- The sidebar creates cognitive latency: users spend time deciding where to go before acting.

## V4.7 Implementation Direction

1. Update current-version surfaces to `V4.7 / 4.7.0`.
2. Add lightweight interaction and performance budget checks.
3. Add reusable async UI primitives for pending, feedback and progressive disclosure.
4. Reduce main navigation while preserving deep routes.
5. Redesign `/learning/project-structure` as a visual learning map.
6. Improve Dashboard as the guided command center.
7. Document script/test sprawl and move or consolidate only when a replacement path is clear.
8. Preserve append-only learning and stage delivery logs.
