# Demo Mode

Demo mode exists to make the product workflow understandable without private data, paid provider keys or long media processing runs.

## Implemented

- Synthetic knowledge space, documents, image/audio/video/code sources, tasks, chat history, grounded/refusal QA logs, learning cards and learning logs.
- Screenshots under `docs/assets/screenshots/` use synthetic data.
- Demo database lives at `backend/data/demo_showcase.db`.
- `DEMO_MODE=true` labels runtime behavior and helps presentation flows stay safe.
- V4.5 adds strict live browser E2E on top of `scripts/run_demo_e2e.py`; optional mode still skips honestly when Playwright is missing.

## What Demo Mode May Do

- Show the upload, task, media, chat and learning workflows.
- Use labelled synthetic examples.
- Seed deterministic demo records for repeatable screenshots.
- Demonstrate the flow from source evidence to RAG citation, refusal boundary, learning assets and portfolio explanation.
- Let a GitHub visitor inspect the product structure without provider keys.

## What Demo Mode Must Not Do

- Pretend synthetic records are real OCR output.
- Pretend synthetic records are real transcription output.
- Pretend a fake LLM answer came from a configured provider.
- Hide provider configuration failures.
- Store private user files in the repository.

## Real Mode Boundary

Real mode is enabled by configuring provider credentials and services:

- LLM provider for generated answers.
- Embedding provider for semantic indexing.
- OCR or vision provider for image understanding.
- Transcription provider for audio and video transcript generation.
- Redis/RQ worker for background processing.
- Qdrant for vector search.

If a required provider is missing, the system should return an explicit NOT_CONFIGURED-style error and should not fabricate content.

## Current Limitations

- Demo data is useful for portfolio presentation and deterministic plumbing checks, not real LLM quality scoring.
- V4.5 validates seeded database readiness, RAG citation/refusal behavior, static frontend smoke, live browser E2E, citation jumps and observability contracts.
- Live browser E2E is available through `scripts/run_demo_e2e.py --strict` when Playwright and browser binaries are installed; optional mode reports an explicit skip when they are absent.
