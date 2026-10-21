# Portfolio System

The portfolio system is in V4.0 incremental implementation. The current repository now has a dedicated summary API and in-app portfolio pages that organize real project facts, while LLM-generated resume/interview drafts remain planned until a real provider path is implemented.

## Existing Baseline

- Professional README.
- Demo script and screenshots.
- Resume pitch document.
- Versioned learning logs.
- Learning artifacts with interview expressions.
- Release safety checks.

## Target Pages

- `/portfolio`: implemented as a real project overview backed by `GET /api/portfolio/summary`.
- `/portfolio/resume`: implemented as deterministic resume bullets from project facts.
- `/portfolio/interview`: implemented as interview talking points and honest boundaries.
- `/portfolio/project-review`: implemented as a recommended demo/storyline page.

## Target APIs

- `GET /api/portfolio/summary`: implemented. It aggregates real database counts for knowledge spaces, documents, sources, citation locators, tasks and learning assets.
- `POST /api/portfolio/generate-resume-entry`: planned. Must call a real LLM provider or return a NOT_CONFIGURED-style refusal.
- `POST /api/portfolio/generate-interview-qa`: planned. Must not return fake model feedback.
- `POST /api/portfolio/generate-project-review`: planned. Must be grounded in real project facts, git diff and verification results.
- `POST /api/portfolio/export-markdown`: planned.

## Output Types

- Resume version.
- Interview version.
- GitHub README version.
- Project review version.
- Future portfolio website version.

## Current Status

- Dedicated portfolio summary module: implemented in `backend/app/services/portfolio_service.py`, `backend/app/api/routes_portfolio.py` and `backend/app/schemas/portfolio_schema.py`.
- Frontend portfolio pages: implemented in `frontend/app/portfolio/*`.
- Smoke coverage: `scripts/check_frontend_smoke.py` includes portfolio pages and fails duplicate AppShell navigation targets.
- Tests: `backend/tests/test_v4_0_portfolio_summary.py` covers service aggregation and the public API response contract.
- Boundary: this is not yet the full V4.0 portfolio generator. It does not use fake LLM output, fake interviews or fake scoring.
