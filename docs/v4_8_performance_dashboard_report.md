# V4.8 Performance Dashboard Report

The new `/system/performance` page gives learners and maintainers a visible place to inspect runtime behavior.

## Page Regions

- Backend request summary: total requests, slow requests, P95 latency and duplicate path count.
- Browser request cache panel: cache hits, misses, deduped requests and forced refreshes.
- Page load and route-switch panel: initial browser navigation timing plus AppShell main-navigation transition duration.
- Slow request list: recent high-latency API calls from the backend rolling buffer.
- Path distribution: aggregated count, average latency, max latency and slow count by route.
- Recent action timeline: button-level durations recorded by `PendingButton`.

## Honest UX Boundary

The page displays only measured local metadata. It does not claim provider speed, network quality or browser lab scores that were not measured.

## Verification So Far

- `python scripts/check_frontend_smoke.py`: passed with `/system/performance`.
- `python scripts/check_ui_performance_budget.py`: passed with 18 navigation targets.
- Frontend typecheck and production build passed with `frontend/services/page-metrics.ts` and the page timing panel.
