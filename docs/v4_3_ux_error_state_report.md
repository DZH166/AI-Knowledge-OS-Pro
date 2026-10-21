# V4.3 UX Error State Report

Generated at: 2026-07-04 Asia/Shanghai

## Scope

This report records the V4.3 user-experience hardening for visible status labels, provider-missing warnings, retryable errors, loading states, source-locator actions and task logs.

## Implemented Shared UI Surface

| Area | Evidence |
| --- | --- |
| Error explanation | `frontend/components/ui.tsx::ErrorState` accepts message, possible reason, impact, next step, provider-required marker, retry action and technical details. |
| Provider boundary warning | `frontend/components/ui.tsx::ProviderMissingWarning` displays provider name, NOT_CONFIGURED code, setup hint and retry option without exposing raw stack traces. |
| Capability warning | `frontend/components/ui.tsx::CapabilityWarning` uses status badges plus a concise message for unavailable or degraded capability states. |
| Demo mode banner | `frontend/components/ui.tsx::DemoModeBanner` labels synthetic demo data and avoids pretending demo text is real provider output. |
| Empty/loading states | `EmptyState` and `LoadingState` provide consistent non-crashing page states. |
| Status labels | `frontend/services/api.ts::statusLabel` maps queued/running/completed/failed/cancelled/retrying/not_configured/demo/real to readable Chinese labels. |
| Task states | `TaskStatusBadge` and `TaskLogDrawer` provide a reusable task status/timeline surface. |
| Citation/source jump | `SourceLocatorButton` gives a common source navigation control for citation-style flows. |
| Learning actions | `LearningActionBar` gives learning pages a common action strip. |

## Required Status Labels

| Raw status | UI label |
| --- | --- |
| `queued` | 排队中 |
| `running` | 处理中 |
| `completed` | 已完成 |
| `failed` | 失败 |
| `cancelled` | 已取消 |
| `retrying` | 重试中 |
| `not_configured` | 未配置 |
| `demo` | 演示模式 |
| `real` | 真实模式 |

## Regression Check

`scripts/check_frontend_smoke.py` now validates the presence of the shared UX components and the required status-label mappings in addition to route files, navigation targets, forbidden debug UI patterns and required page text.

## Boundaries

- This is a shared-component and static smoke hardening pass, not a full live browser E2E suite.
- Existing pages can continue to adopt the new shared components incrementally.
- Real providers are still required for real OCR, transcription, embedding and LLM output; missing providers must remain explicit NOT_CONFIGURED-style refusals.

