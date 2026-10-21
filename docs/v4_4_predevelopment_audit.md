# V4.4 Predevelopment Audit

Generated at: 2026-07-04 Asia/Shanghai

## Branch And Source State

- Current branch: `feature/v4.4-demo-e2e-observability`.
- Base commit: `eff032d docs: finalize V4.3 release hardening`.
- `main` status before branching: synchronized with `origin/main`.
- V4.3 tag: `v4.3.0` exists.
- V4.3 GitHub Release: exists at `https://github.com/DZH166/AI-Knowledge-OS-Pro/releases/tag/v4.3.0`.
- README visible version before V4.4 work: `V4.3 / 4.3.0`.
- `scripts/check_all.py`: exists and supports quick/demo/release/full plus `--skip-frontend`.

## Current E2E State

- `frontend/playwright.config.ts`: missing.
- `frontend/e2e/`: missing.
- `frontend/package.json` has no `test:e2e` script.
- Default CI currently runs backend pytest, frontend typecheck/build, docs/assets checks, quick gate and release package checks.
- Browser E2E is not yet implemented and must not be claimed as passing until a real browser or explicit environment skip is recorded.

## Current Observability State

- Backend response envelopes already carry `request_id`.
- `/system/observability` exists as a static frontend explanation page.
- Backend does not yet expose `/api/system/observability` or recent request/task/retrieval/provider subroutes.
- `QALog` stores citations, related chunks, retrieval status, runtime mode and created time; this can seed recent retrieval observability without adding a heavy APM stack.
- `IngestionJob` and `JobEvent` store task status, duration, progress, stage, error codes and events.
- Provider status exists through `system_service.status(db)` and can be reused safely.

## Current Citation Jump State

- `CitationPanel` links media citations to `/media/sources/{source_id}?t={start_ms}&chunk={chunk_id}`.
- `CitationPanel` links document citations to `/documents/{document_id}?page=...&heading=...&chunk=...`.
- `CitationPanel` does not yet provide a dedicated code repository link when `file_path` / `line_start` / `line_end` are present.
- Document detail page reads `chunk`, `page` and `heading`, then scrolls to the target chunk.
- Media detail page reads `t` and `chunk`, seeks audio/video and highlights active transcript segment.
- Missing locator fallback is currently generic and should be made user-friendly.

## Current Provider Evaluation State

- Provider boundary tests already prove missing providers refuse clearly.
- There is no `scripts/evaluate_providers.py`.
- Default release checks do not call paid providers.
- V4.4 should add dry-run and real-if-configured modes where missing keys produce explicit NOT_CONFIGURED output without failing default CI.

## Current Frontend Consolidation State

- Shared components exist for `DemoModeBanner`, `ProviderMissingWarning`, `TaskLogDrawer`, `SourceLocatorButton`, `LearningActionBar`, `StatusBadge`, `EmptyState`, `ErrorState` and `TechnicalDetails`.
- Many pages still use local wording and bespoke structures, but V4.4 can focus first on observability and citation surfaces rather than broad cosmetic rewrites.
- Static smoke checks already assert the shared component names and required Chinese status labels.

## Largest Risks

- Browser E2E requires a real browser runtime. If Playwright browsers are not installed locally or in CI, the E2E gate must skip clearly and document the environment reason.
- Citation jump E2E needs seeded synthetic demo data and a running backend/frontend. The tests must not fabricate AI outputs.
- Observability must not expose API keys, full local file paths, uploaded private content or raw stack traces in the main UI.
- Adding Playwright dependencies without keeping `package-lock.json` in sync would break `npm ci`; default CI should remain stable.

## Most Needed Tests

- Backend observability API regression.
- Citation jump contract tests for document, media and code locator hrefs.
- Provider evaluation dry-run test with missing credentials.
- Optional browser E2E specs for demo smoke, citation jump and observability.

## Most Needed Docs

- Browser E2E command/report.
- Citation jump report.
- Observability report.
- Provider evaluation report.
- Frontend consolidation report.
- V4.4 quality gate and acceptance reports.

