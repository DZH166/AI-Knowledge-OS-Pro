# V4.7 Interaction Performance Audit

V4.7 focuses on perceived speed rather than fake backend acceleration. The main finding was that many buttons did perform real work, but users did not always get immediate pending/disabled feedback.

## Baseline

- Main navigation targets before cleanup: 25.
- Static button count after V4.7 scan: 79.
- API-like buttons after V4.7 scan: 27.
- High-risk async-looking buttons after fixes: 0.
- API timeout handling: implemented in `frontend/services/api.ts` with `REQUEST_TIMEOUT_MS`.

## Fixed Areas

- Task Center retry/cancel now tracks `pendingJobId` and `pendingAction`.
- Task Center manual refresh shows pending without making background polling noisy.
- Learning card review buttons are disabled while recording progress.
- Quiz submission buttons are disabled while submitting and while no answer is selected.
- Learning package confirmation shows a confirming state.
- System refresh and provider test actions show busy state.
- Chat favorite action now shows a saving state.
- Generic `ErrorState` retry now has a retrying state.

## Remaining Boundaries

- The static scanner does not measure real browser frame time or network latency.
- Development-mode first route compilation can still feel slow in Next.js; production build should be used for release review.
- Provider-backed actions still depend on configured services and may return NOT_CONFIGURED.
