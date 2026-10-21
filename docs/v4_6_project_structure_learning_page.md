# V4.6 Project Structure Learning Page

This V4.6 increment adds an in-app project structure explanation page at `/learning/project-structure`.

## Purpose

The page helps a learner explain AI Knowledge OS Pro as a connected AI application rather than as isolated screens. It maps the product model, backend structure, frontend structure, RAG evidence flow, multimodal processing flow, release quality flow and recommended study order.

## Delivered Behavior

- Adds a static learning page that does not call provider-backed APIs or invent runtime metrics.
- Links the page from the `学习成长` navigation group as `项目构造`.
- Explains the real project boundaries: evidence-first RAG, explicit provider refusal, labelled demo data and append-only learning archives.
- Connects the learning path to existing product pages: Dashboard, upload center, task center, chat, media library, learning archive and portfolio review.
- Adds frontend smoke coverage for the new route and key UI text.

## Boundary

No backend API, database schema, provider configuration, RAG behavior, media processing behavior or release version is changed by this page. It is an educational layer over the current V4.5/V4.6 evidence baseline.

## Verification

Completed checks for this increment:

- `python scripts/check_frontend_smoke.py`: passed with `required_routes=28`.
- `python -m pytest backend/tests/test_v3_9_frontend_smoke.py`: `1 passed`.
- `python -m compileall backend/app scripts`: passed.
- `python scripts/check_all.py --quick`: passed.
- Frontend typecheck via local `tsc --noEmit`: passed.
- Frontend production build via local `next build`: passed and generated `/learning/project-structure`.
- `python -m pytest`: `75 passed`, `16 warnings`.
- `python scripts/check_all.py --release`: passed.
- `python scripts/check_release.py --version V4.5`: passed for the current local V4.5 archive with `files=357`, `forbidden=0`, `missing=0`.
