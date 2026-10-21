# V4.4 Browser E2E Report

## Scope

V4.4 adds browser-level E2E scaffolding for the GitHub demo path without making default CI depend on paid providers or a preinstalled browser runtime.

## Implemented

- `frontend/playwright.config.ts`
- `frontend/e2e/demo-smoke.spec.ts`
- `frontend/e2e/citation-jump.spec.ts`
- `frontend/e2e/system-observability.spec.ts`
- `frontend/e2e/run-optional-e2e.mjs`
- `scripts/check_e2e.py`
- `scripts/run_demo_e2e.py`
- `frontend/package.json` script: `npm run test:e2e`

## Covered Pages

- `/`
- `/dashboard`
- `/upload`
- `/tasks`
- `/chat`
- `/media`
- `/learning`
- `/portfolio`
- `/portfolio/resume`
- `/portfolio/interview`
- `/system`
- `/system/observability`

## Honest Skip Policy

`npm run test:e2e` reports `skipped` and exits successfully when `@playwright/test` or browser binaries are not installed. This is intentional for default CI. A prepared E2E environment should install Playwright browsers and treat the same specs as a hard gate.

## Demo Runner

`python scripts/run_demo_e2e.py` seeds `.pytest_tmp/v4_4_e2e_demo.db`, starts the FastAPI backend with `DEMO_MODE=true`, starts the Next.js frontend with `NEXT_PUBLIC_API_BASE_URL`, and then runs `scripts/check_e2e.py --run-browser`.

The local environment used for this closure does not have `@playwright/test` installed, so the command reported:

```text
demo_e2e_status=skipped reason=PLAYWRIGHT_NOT_INSTALLED
```

This is an environment limitation, not a production build failure.

## Local Static Evidence

- `python scripts/check_e2e.py`: passed.
- `python scripts/run_demo_e2e.py`: skipped with `PLAYWRIGHT_NOT_INSTALLED`.

## Failure Output Paths

- `frontend/test-results/`
- `frontend/playwright-report/`

## Remaining Limit

Live browser execution is not claimed unless the environment has Playwright, browser binaries, backend and frontend services running.
