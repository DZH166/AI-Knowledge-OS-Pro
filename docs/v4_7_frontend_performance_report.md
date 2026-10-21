# V4.7 Frontend Performance Report

V4.7 improves perceived frontend speed by reducing decision load, adding pending feedback and making long waits explicit.

## Code Changes

- Added reusable UI primitives in `frontend/components/ui.tsx`: `PendingButton`, `ActionToast`, `SkeletonCard`, `LoadingOverlay`, `AsyncActionBoundary`, `SectionTabs`, `ProgressivePanel` and `CollapsibleTechnicalDetails`.
- Added fetch timeout handling in `frontend/services/api.ts`.
- Reduced the AppShell main navigation to 17 core entries.
- Rebuilt Dashboard as a command center with fewer, clearer visual regions.
- Rebuilt the project-structure page as a visual learning map.

## Validation

- `python scripts/check_ui_performance_budget.py`: passed with `main_nav_targets=17`.
- `python scripts/check_interaction_feedback.py`: passed with `high_risk=0`.
- Frontend typecheck: passed during V4.7 implementation.
- Frontend production build remains part of final release validation.

## What Was Not Claimed

- No fake runtime metrics were introduced.
- No provider output was fabricated.
- No real-device performance benchmark is claimed by the static budget checks.
