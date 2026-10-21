# V4.1 Documentation Cleanup Report

## Goals

- Keep historical learning artifacts.
- Reduce docs-root noise.
- Make active docs easier to scan.
- Fix unreadable documentation without overwriting append-only logs.

## Current Structure

- Active guides remain in `docs/`.
- Historical reports now live under `docs/archive/v2`, `docs/archive/v3` and `docs/archive/v4`.
- Screenshot and demo assets remain under `docs/assets`.
- `docs/learning_log.md` and `docs/stage_delivery_log.md` were not rewritten.

## Active Documentation Kept In Root

- Quickstart and local setup: `quickstart.md`, `local_development.md`, `local_setup_windows.md`, `demo_mode.md`, `deployment.md`, `docker_deployment.md`.
- Architecture and flows: `architecture.md`, `architecture_diagram.md`, `rag_flow.md`, `media_pipeline.md`, `task_queue_flow.md`, `citation_locator.md`, `learning_system.md`, `portfolio_system.md`, `interview_system.md`.
- Quality and release: `release_process.md`, `github_release_checklist.md`, `document_quality_checklist.md`, `environment_variables.md`, `provider_diagnostics.md`.
- V4.1 working reports: `v4_1_predevelopment_audit.md`, `v4_1_code_inventory.md`, `v4_1_dead_code_report.md`, `v4_1_dead_code_plan.md`, `v4_1_cleanup_report.md`.

## Encoding Cleanup

`docs/version_learning_package.md` was rewritten as readable UTF-8 Markdown. Append-only historical logs were not altered; the encoding checker still warns about legacy irreversible lines but preserves them by design.

## Remaining Documentation Debt

- Some active docs still overlap in RAG/media/citation terminology and can be consolidated in a later pass.
- README still reports V3.8 as the latest stable public version; V4.1 should only become visible as stable after all quality gates pass.
- V4.1 final acceptance and learning package documents are still pending full test/build evidence.
