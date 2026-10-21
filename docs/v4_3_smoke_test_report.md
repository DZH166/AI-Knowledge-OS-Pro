# V4.3 Smoke Test Report

Generated at: 2026-07-04 Asia/Shanghai

## Scope

V4.3 keeps the existing static frontend smoke check and verifies the production build. Browser E2E remains future work; this stage validates route presence, navigation targets, forbidden debug UI patterns and build-time route generation.

## Commands

```powershell
python scripts/check_frontend_smoke.py
node .\node_modules\typescript\bin\tsc --noEmit
node .\node_modules\next\dist\bin\next build
```

## Results

- Frontend smoke: passed.
- Required routes: `27`.
- Navigation targets: `24`.
- Warnings: `0`.
- TypeScript typecheck: passed.
- Production build: passed.
- App Router routes generated: `28`.

## Core Pages Covered

- `/`
- `/dashboard`
- `/upload`
- `/tasks`
- `/chat`
- `/chat/history`
- `/documents`
- `/knowledge`
- `/media`
- `/media/sources/[id]`
- `/learning`
- `/portfolio`
- `/portfolio/interview`
- `/system`
- `/system/observability`

## Boundary

This is not a live browser E2E test. It proves the checked-in routes and UI contracts compile and build, while live media playback/citation-jump browser automation remains a V4.4 candidate.
