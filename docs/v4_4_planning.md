# V4.4 Planning: Evidence-Driven Demo E2E And Runtime Observability

Generated at: 2026-07-04 Asia/Shanghai

## Planning Principle

V4.4 should not blindly add large new AI features. V4.3 made the repository readable, testable and releasable. The next highest-value work is to prove the most important user journeys in a running browser and make runtime failures easier to explain.

## Recommended Direction

1. Add browser E2E smoke coverage for the demo walkthrough:
   - Dashboard opens in demo mode.
   - Upload Center shows document/image/audio/video capability states.
   - Chat shows grounded demo answers and citation links.
   - Media detail pages open audio/video timestamps.
   - Task Center displays stage logs, retry/cancel affordances and result links.

2. Validate citation jumps end to end:
   - Document citations route to document/chunk evidence.
   - Image citations route to source detail.
   - Audio/video citations seek to timestamps and highlight the transcript segment.
   - Code citations route to repository/file/line evidence.

3. Add runtime observability snapshots:
   - Request id and retrieval trace id visibility.
   - Provider refusal category.
   - Task queue stage duration.
   - Retrieval source mix and citation validation result.

4. Improve provider-backed evaluation without fake outputs:
   - Keep synthetic demo checks provider-free.
   - Add an optional real-provider evaluation profile that runs only when keys are configured.
   - Record NOT_CONFIGURED when keys are absent instead of failing the default release path.

5. Continue frontend consolidation:
   - Move large page-specific sections into domain components.
   - Reuse `ProviderMissingWarning`, `TaskLogDrawer`, `SourceLocatorButton` and `LearningActionBar`.
   - Keep visible error text user-readable and move stack-like details behind technical disclosure controls.

## Non-Goals For V4.4

- Do not add fake OCR, fake transcripts, fake embeddings or fake LLM answers.
- Do not replace the current V4.3 release flow.
- Do not delete historical reports or rewrite append-only learning archives.
- Do not introduce paid-provider requirements into default CI.

## Suggested Branch

```text
feature/v4.4-demo-e2e-observability
```

## Suggested Acceptance Gates

- Browser E2E smoke passes locally or documents the exact browser/runtime blocker.
- Existing backend pytest and frontend typecheck/build remain green.
- `scripts/check_all.py --full` remains green.
- Optional provider-backed checks skip clearly with NOT_CONFIGURED when keys are absent.
- Learning and stage logs append a V4.4 entry without rewriting V1-V4.3 records.

