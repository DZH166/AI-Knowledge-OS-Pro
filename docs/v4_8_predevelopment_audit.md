# V4.8 Predevelopment Audit

This audit records the V4.8 runtime-performance and release-polish scope against the real repository state. It was completed after the first V4.8 implementation pass, so it includes both the original V4.7 risk framing and the current branch evidence.

## Branch And Commit

- Working branch: `feature/v4.8-runtime-performance-release-polish`
- Current commit during audit: `063dfb1`
- V4.7 base commit: `5a8ea30`
- V4.7 is not shown as merged into `origin/main`; it is contained by `origin/feature/v4.7-performance-visual-cleanup` and the current V4.8 feature branch.

## Version Surfaces

- Original V4.7 baseline targeted `V4.7 / 4.7.0`.
- Current V4.8 branch targets `V4.8 / 4.8.0`.
- README, backend config, frontend package metadata, AppShell brand, `check_all.py`, release scripts and version docs now align with `V4.8 / 4.8.0`.

## Script Inventory

- Root `scripts/*.py` entries: 44.
- Moved self-check implementations: 12 files under `scripts/maintenance/self_check/`.
- Moved CI diagnostic implementations: 4 files under `scripts/maintenance/ci/`.
- Root wrappers remain for compatibility and now emit a deprecated-wrapper notice on stderr when executed directly.

## Core Quality Gates

High-frequency gates remain callable from root `scripts/`:

- `check_all.py`
- `check_encoding.py`
- `check_version.py`
- `check_docs_links.py`
- `check_readme_assets.py`
- `check_frontend_smoke.py`
- `check_ui_performance_budget.py`
- `check_interaction_feedback.py`
- `check_request_cache.py`
- `check_secrets.py`
- `check_repo_clean.py`
- `check_demo_ready.py`
- `evaluate_rag.py`
- `evaluate_providers.py`
- `release.py`
- `check_release.py`
- `setup_demo.py`
- `seed_demo_data.py`
- `reset_demo_data.py`
- `run_demo_e2e.py`

## Git Dependency Review

- `scripts/check_secrets.py` and `scripts/check_repo_clean.py` use `git ls-files` when `.git` is present and filesystem scan mode when it is absent.
- `scripts/release.py` still uses Git-tracked files for packaging in a repository checkout; this is intentional for source release generation.
- `scripts/check_all.py` records Git provenance as `unknown` when Git metadata is unavailable instead of failing.
- `scripts/generate_learning_package.py` and portfolio Git-diff helpers still require Git because their job is explicitly diff/provenance analysis, not release-zip validation.

## Runtime Performance Findings

- V4.7 had static interaction scanning and UI budgets, but no runtime timing panel.
- V4.8 adds in-process backend request timing with a 200-record rolling buffer.
- Dashboard, System, Learning, Portfolio, Observability and Performance reads now support short TTL caching through `frontend/services/request-cache.ts`.
- Mutations continue to bypass cache and clear cached reads.
- Button runtime timing is recorded by `PendingButton` through `frontend/services/interaction-metrics.ts`.

## Pages Most Likely To Feel Slow

- Dashboard: several summary/status/dashboard reads on first load.
- System pages: status, observability and performance reads.
- Learning pages: dashboard/log/package/card reads.
- Portfolio pages: summary and provider-backed generation actions.
- Media detail pages: transcript, frames, asset and source metadata reads.

## Button Risk Findings

- Current generated map: `buttons=79`, `high_risk=0`, `medium local-feedback risk=24`.
- High-risk async-looking buttons remain at zero.
- Medium-risk items are mostly local UI actions such as menu collapse, tab switching, seek, copy, close and selected-row changes. They do not need network pending state, but they should retain immediate selected/copied/active feedback.

## Biggest V4.8 Risks

- Treating runtime metadata as production-grade APM would overstate the feature; this is a local rolling buffer.
- Caching the wrong endpoints could stale mutation-heavy flows; V4.8 limits TTL behavior to selected GET reads.
- Release-zip verification can drift if new files are not staged before packaging; `check_release.py` now requires V4.8 files.
- Root script wrappers preserve compatibility but still leave visible wrapper entries in `scripts/`; this is an intentional transition path.

