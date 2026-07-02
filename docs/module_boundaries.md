# Module Boundaries

V4.1 treats this project as a maintainable portfolio application. The boundaries below describe where code should live and where new work should not spread.

| Layer | Owns | Should Not Own |
| --- | --- | --- |
| FastAPI routes | Request parsing, response models, dependency injection and service calls. | Business rules, provider calls or persistence loops. |
| Services | Domain behavior, validation, orchestration and transaction-level decisions. | UI formatting or route-specific response envelopes. |
| Providers/adapters | External LLM, embedding, OCR, transcription, Qdrant and FFmpeg boundaries. | Product fallback fiction or demo-only fake outputs in real mode. |
| SQLAlchemy models | Durable relational state and relationships. | Request/response presentation concerns. |
| Alembic | Schema evolution and downgrade safety where supported. | Data deletion as a fix for application bugs. |
| Task engine | Durable jobs, events, retry, cancel and worker dispatch. | Separate hidden state machines for each modality. |
| Frontend API client | HTTP calls, envelopes, URL helpers and shared formatters. | Page-specific layout decisions. |
| Frontend pages | Product workflows and route composition. | Duplicated API wrappers or hidden mock data. |
| Shared frontend components | Reusable layout, feedback, media, chat, citation and learning primitives. | Domain persistence logic. |
| Scripts | Repeatable setup, demo, audit, release, check and learning-package operations. | User-specific absolute paths or real secret output. |
| Docs | Current truthful architecture, setup, release and learning explanation. | Claims about unimplemented provider-backed abilities. |

## Real/Demo Mode Boundary

Demo mode may use explicitly labelled synthetic data. Real mode must refuse missing providers with explicit NOT_CONFIGURED-style errors. This boundary is part of the product contract and must be preserved in code, tests and docs.

## Historical Archive Boundary

Historical version reports are preserved under `docs/archive`. They are not active product docs and should not be used as proof of the current implementation without checking current code and quality gates.
