# V4.8 Learning Package Draft

This learning package explains how V4.8 turns runtime performance evidence, request-cache behavior and release polish into teachable engineering features. It does not claim fake provider output, fake browser timing or fake release results; every section points back to files and checks that can be inspected locally.

## Knowledge Points

### 1. Runtime Performance Observability

- Beginner explanation: the backend keeps small request timing records so slow API paths can be inspected later.
- Project reason: users felt the app could be slow, and V4.8 needed evidence instead of guesses.
- Related files: `backend/app/services/performance_service.py`, `backend/app/api/routes_performance.py`, `backend/app/schemas/performance_schema.py`, `backend/app/core/responses.py`.
- Common mistake: logging request bodies or provider payloads while trying to debug latency.
- Debug method: visit API-backed pages, then call `/api/system/performance` or open `/system/performance`.
- Interview expression: "I added a lightweight request metadata buffer so the app can explain slow routes without storing sensitive content."
- Follow-up study: FastAPI middleware, rolling buffers, percentile latency and application performance monitoring basics.

### 2. Slow Request Analysis

- Beginner explanation: a slow-request panel separates normal API traffic from routes that exceed a threshold.
- Project reason: Dashboard, learning and media pages can call several APIs, so one slow route should be visible.
- Related files: `backend/app/services/performance_service.py`, `frontend/app/system/performance/page.tsx`.
- Common mistake: assuming the page is slow without checking whether frontend rendering, network or backend work is the cause.
- Debug method: compare recent request rows, path summaries and slow-request rows after refreshing a few pages.
- Interview expression: "I exposed slow-path summaries so performance work starts from measured API evidence."
- Follow-up study: request tracing, N+1 query diagnosis and endpoint-level SLOs.

### 3. Frontend Request Dedupe

- Beginner explanation: if two components ask for the same GET data at the same time, they can share one in-flight request.
- Project reason: system, dashboard and portfolio surfaces often request overlapping status data.
- Related files: `frontend/services/request-cache.ts`, `frontend/services/api.ts`, `scripts/check_request_cache.py`.
- Common mistake: deduping POST/PUT/DELETE mutations and accidentally hiding real writes.
- Debug method: inspect browser request-cache metrics on `/system/performance`.
- Interview expression: "I limited dedupe to idempotent reads so repeated dashboard loads do not multiply network work."
- Follow-up study: HTTP idempotency, SWR patterns and cache-key design.

### 4. Lightweight GET Cache

- Beginner explanation: recent GET responses can be reused for a short time instead of refetching instantly.
- Project reason: status-like data should feel fast while still allowing explicit refresh.
- Related files: `frontend/services/request-cache.ts`, `frontend/services/api.ts`.
- Common mistake: giving every endpoint a long TTL and making the UI show stale task state.
- Debug method: load a cached page twice and compare cache hit/miss counters.
- Interview expression: "I used a short TTL cache for read-heavy views and kept mutation-heavy flows uncached."
- Follow-up study: stale-while-revalidate, TTL tradeoffs and cache invalidation.

### 5. Cache Invalidation After Mutations

- Beginner explanation: after creating, retrying, cancelling or updating something, old cached reads must be cleared.
- Project reason: task center, media processing and learning actions must show real post-mutation state.
- Related files: `frontend/services/api.ts`, `frontend/services/request-cache.ts`.
- Common mistake: optimizing reads while forgetting to refresh data after writes.
- Debug method: trigger a mutation, then verify related GET reads do not reuse stale cached values.
- Interview expression: "I paired read caching with mutation invalidation to preserve correctness."
- Follow-up study: optimistic UI, mutation side effects and consistency models.

### 6. Button Runtime Timing

- Beginner explanation: shared async buttons record duration, success and failure so user-visible actions can be reviewed.
- Project reason: perceived speed depends on immediate feedback, not only backend latency.
- Related files: `frontend/components/ui.tsx`, `frontend/services/interaction-metrics.ts`, `frontend/app/system/performance/page.tsx`.
- Common mistake: measuring only API calls and ignoring long-running UI actions.
- Debug method: click refresh/provider-like actions and inspect the recent action timeline.
- Interview expression: "I treated UI responsiveness as measurable product behavior."
- Follow-up study: React event handling, user timing marks and interaction-to-next-paint concepts.

### 7. Slow Action Notice

- Beginner explanation: a long-running button changes copy over time so the user knows the app is still working.
- Project reason: provider checks, generation and diagnostics can take longer than a normal click.
- Related files: `frontend/components/ui.tsx`.
- Common mistake: leaving a spinner with no wording for ten seconds.
- Debug method: review `PendingButton` thresholds and test a slow async action locally.
- Interview expression: "I added escalating slow-action feedback instead of leaving users wondering whether a click registered."
- Follow-up study: loading state UX, timeout copy and retry affordances.

### 8. Performance Dashboard

- Beginner explanation: one page shows backend request timing, browser page-load timing, request-cache metrics and recent button action timing.
- Project reason: performance work should be visible inside the product, not buried only in logs.
- Related files: `frontend/app/system/performance/page.tsx`, `frontend/services/page-metrics.ts`, `frontend/components/AppShell.tsx`, `backend/app/api/routes_performance.py`.
- Common mistake: presenting local metrics as production-grade APM.
- Debug method: open `/system/performance`, switch between main navigation pages, refresh metrics and confirm the page labels local/runtime scope clearly.
- Interview expression: "I created a product-facing performance panel that explains local runtime evidence and its limits."
- Follow-up study: dashboards, metric scope labels and observability UX.

### 9. No-Git Release Mode

- Beginner explanation: release zips do not contain `.git`, so safety checks need a filesystem scan fallback.
- Project reason: users should be able to validate an extracted source zip without being in a Git checkout.
- Related files: `scripts/check_secrets.py`, `scripts/check_repo_clean.py`, `backend/tests/test_v4_8_release_zip_mode.py`.
- Common mistake: making release checks depend on `git ls-files` and then failing with a traceback in extracted archives.
- Debug method: extract the zip elsewhere and run `python scripts/check_secrets.py` and `python scripts/check_repo_clean.py`.
- Interview expression: "I made release validation portable beyond a developer checkout."
- Follow-up study: source archives, Git metadata assumptions and file tree scanning.

### 10. Git Scan Versus Filesystem Scan

- Beginner explanation: in a repo, Git scan checks tracked files; outside a repo, filesystem scan walks the release tree.
- Project reason: both developer checkout validation and user zip validation matter.
- Related files: `scripts/check_secrets.py`, `scripts/check_repo_clean.py`, `docs/v4_8_release_zip_user_experience_report.md`.
- Common mistake: scanning ignored local files in a developer checkout and reporting noisy false positives.
- Debug method: compare script output in the repo and in an extracted no-Git folder; mode and reason should be explicit.
- Interview expression: "I separated Git-aware checks from extracted-source checks so the same command is meaningful in both contexts."
- Follow-up study: `.gitignore`, tracked-file enumeration and CI artifact validation.

### 11. Maintenance Directory Migration

- Beginner explanation: rarely used self-check implementations moved out of the root script list.
- Project reason: V4.7 added useful quality tools, but the root `scripts/` directory was becoming hard to scan.
- Related files: `scripts/maintenance/self_check/`, `scripts/maintenance/ci/`, `docs/v4_8_script_maintenance_migration_report.md`.
- Common mistake: deleting low-frequency scripts just because they are noisy.
- Debug method: count root wrappers and maintenance implementations, then run representative wrappers.
- Interview expression: "I reduced tooling sprawl without losing historical quality workflows."
- Follow-up study: developer experience, compatibility wrappers and tooling lifecycle management.

### 12. Deprecated Compatibility Wrappers

- Beginner explanation: old root commands still work, but they now say they delegate to maintenance scripts.
- Project reason: docs, CI or user habits may still call root script names.
- Related files: root scripts such as `scripts/run_self_check.py`, `scripts/check_ci_artifacts.py`, `scripts/check_github_actions.py`.
- Common mistake: moving script files without leaving a stable command path.
- Debug method: run a wrapper directly and confirm it prints a deprecation notice to stderr while delegating.
- Interview expression: "I preserved backwards compatibility while nudging future maintenance toward the cleaner directory layout."
- Follow-up study: CLI deprecation strategy and migration windows.

### 13. Medium-Risk Interaction Cleanup

- Beginner explanation: static scanning can flag local UI controls even when they do not call APIs.
- Project reason: V4.8 needed to separate real duplicate-click risk from harmless local actions like tab or row selection.
- Related files: `scripts/check_frontend_interactions.py`, `docs/v4_8_button_latency_map.md`, `docs/v4_8_medium_risk_interaction_cleanup_report.md`.
- Common mistake: forcing every local click to show a network spinner just to satisfy a scanner.
- Debug method: inspect medium-risk rows and confirm whether they are local feedback actions or async operations.
- Interview expression: "I kept high-risk async issues at zero and documented why local controls should remain instant."
- Follow-up study: static analysis false positives and UX-driven risk triage.

### 14. Performance Optimization Interview Expression

- Beginner explanation: explain performance work as a loop: observe, prioritize, optimize, verify, document.
- Project reason: this project is a portfolio piece, so the work must be teachable and defensible.
- Related files: `docs/v4_8_runtime_performance_report.md`, `docs/v4_8_request_cache_report.md`, `docs/v4_8_performance_dashboard_report.md`.
- Common mistake: saying "I made it faster" without naming the evidence or tradeoff.
- Debug method: prepare a short demo: open `/system/performance`, show cache metrics, then explain request timing.
- Interview expression: "I improved perceived speed by combining backend timing evidence, GET dedupe, short-lived cache and button-level feedback."
- Follow-up study: performance narratives, tradeoff framing and before/after validation.

### 15. Technical Debt Governance Interview Expression

- Beginner explanation: technical debt work is not just deletion; it is classification, migration, compatibility and verification.
- Project reason: V4.7/V4.8 added many gates, so the project needed a sustainable maintenance story.
- Related files: `docs/v4_8_script_maintenance_migration_report.md`, `docs/scripts_reference.md`, root wrapper scripts, `scripts/maintenance/`.
- Common mistake: calling code "dead" without checking CI, docs and user workflows.
- Debug method: trace a moved script from root wrapper to maintenance implementation and confirm tests still pass.
- Interview expression: "I treated cleanup as a governed migration: keep stable entrypoints, move low-frequency implementation, document the replacement and verify the gates."
- Follow-up study: refactoring safety, code ownership and release governance.

## Suggested Study Order

1. Open `/system/performance` and connect the page to `backend/app/api/routes_performance.py`.
2. Read `frontend/services/request-cache.ts` before reading the performance page.
3. Read `frontend/components/ui.tsx` and trace how `PendingButton` records interaction timing.
4. Run `python scripts/check_request_cache.py` and `python scripts/check_frontend_interactions.py`.
5. Extract the release zip and run the no-Git checks to see how source validation behaves outside a repository.
