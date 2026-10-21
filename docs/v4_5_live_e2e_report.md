# V4.5 Live E2E Report

## Scope

V4.5 promotes the seeded browser demo path from optional scaffolding to a strict release gate for prepared environments.

## Covered Flow

- Seed an isolated synthetic showcase database whose filename contains `showcase`.
- Start FastAPI with `DEMO_MODE=true` and the temporary SQLite database.
- Start Next.js with `NEXT_PUBLIC_API_BASE_URL` pointed at the temporary backend.
- Run Playwright Chromium specs for dashboard, upload center, task center, chat, media library, timestamp media detail pages and observability.
- Upload Playwright HTML report and test results in GitHub Actions as `playwright-live-demo-report`.

## Commands

```powershell
python scripts/check_e2e.py
python scripts/run_demo_e2e.py --strict
```

Optional mode remains honest:

```powershell
python scripts/run_demo_e2e.py
```

If Playwright or browser binaries are missing, optional mode reports `PLAYWRIGHT_NOT_INSTALLED` or `PLAYWRIGHT_BROWSER_NOT_INSTALLED` instead of claiming a pass. Strict mode fails.

## Verification Status

- Static E2E scaffold: passed with `python scripts/check_e2e.py`.
- Strict local browser E2E: passed with `python scripts/run_demo_e2e.py --strict`, `22 passed`.
- `check_all --e2e`: passed and executed the optional browser path because Playwright and Chromium were installed locally, `22 passed`.
- CI live-e2e job: configured in `.github/workflows/ci.yml`; GitHub result is confirmed after push.

## Real-Mode Boundary

The E2E suite uses synthetic seeded data and does not call paid LLM, embedding, OCR, vision or transcription APIs. Missing providers remain explicit NOT_CONFIGURED states. In `DEMO_MODE=true`, the browser demo can fall back to local keyword retrieval if Qdrant is unavailable; real mode still raises the underlying dependency error instead of fabricating retrieval.
