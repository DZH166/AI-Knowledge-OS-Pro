# Resume And Interview Pitch

## Project Name

AI Knowledge OS Pro

## One-Sentence Introduction

A versioned evidence-native RAG Agent that plans, retrieves, verifies and produces traceable knowledge artifacts across documents, media and code.

## Resume Description

Built an end-to-end evidence-native RAG Agent with FastAPI, Next.js, SQLAlchemy, Alembic, Qdrant and Redis/RQ. The system turns versioned document, media and code evidence into durable Agent Runs with planning, adaptive retrieval, claim-level citation checks, approvals, recovery and traceable Artifacts. Added a fixed 60-case evaluation pipeline, immutable Policy Lab and offline retrieval optimizer with deterministic Trials, Pareto/observation-guided candidate selection, cumulative budgets, human-gated draft conversion and a typed experiment Workbench.

## Tech Stack

- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite.
- Frontend: Next.js, React, TypeScript.
- Retrieval: Qdrant, OpenAI-compatible embeddings.
- Tasks: Redis, RQ, persistent job events.
- Providers: OpenAI-compatible LLM, OCR/vision and speech-to-text adapters.
- Agent runtime: persistent events, checkpoints, leases, SQL Outbox, Server-Sent Events and bounded recovery.
- Engineering: pytest, Vitest, Playwright, Ruff, TypeScript, Next.js build, GitHub Actions, fixed RAG evaluation, migration round-trip, release archive verification and secret checks.

## Core Features

- Knowledge spaces with document upload, parsing, chunking and vector indexing.
- RAG Q&A with validated citations and chat history.
- Evidence-native Agent Runs with planning, retrieval, evidence assessment, synthesis, approval, clarification, cancellation and budget controls.
- Versioned retrieval policies with deterministic comparison/simulation, evaluation-gated activation and audited rollback.
- Offline retrieval optimization Studies with reproducible Trials, Pareto frontier, observation-guided rounds, category evidence, report export and no automatic activation.
- Source-pinned issue feedback with idempotent submission, terminal human review, atomic reviewed-sample creation and mode/split-isolated local export; no automatic grading of these new samples.
- Expiring, sanitized, read-only Run Trace sharing with copy and immediate revoke controls.
- Image OCR, audio transcription, video transcription and video keyframes through durable media tasks.
- Citation jumps to document chunks or media timestamps.
- Learning artifacts: knowledge points, cards, quizzes, notes and interview expressions.
- V4.2 demo setup/reset workflow with synthetic data, explicit real/demo boundaries and insufficient-context refusal checks.
- Quickstart, demo mode, local development, release, versioning, interview QA and V4.x roadmap module docs.

## Technical Challenges

- Keeping real provider boundaries honest while still offering a useful demo.
- Unifying document jobs and media processing under one task model.
- Preserving citation traceability across text, image, audio and video evidence.
- Avoiding release archives that accidentally include databases, uploads, logs, dependencies or secrets.
- Making the project explainable for GitHub visitors and interviewers.
- Preventing retries, expired workers and database upgrades from duplicating optimizer rounds or overwriting newer results.

## Solutions

- Provider adapters return explicit NOT_CONFIGURED errors instead of fake OCR, fake subtitles or fake answers.
- `IngestionJob` supports both `document_id` and `source_id` plus `target_type`.
- `CitationLocator`, timestamp fields and frontend deep links preserve evidence navigation.
- Release scripts use Git-tracked files, dry-run analysis and forbidden-file checks.
- Demo seed creates isolated synthetic document, image, audio, video, code, task, Q&A and learning data.
- Demo reset rebuilds only the isolated synthetic database and refuses non-demo database paths.
- Full regression checks prove the seeded demo, key frontend routes, backend route files, RAG locators and release-support docs still hold after cleanup.
- Historical next-round receipts are migrated into an append-only command table; lease fences and Outbox recovery reject stale writes while preserving retryable work.

## Project Highlights

- Built a real multimodal RAG workflow instead of a static chatbot demo.
- Added durable background processing and observable task events.
- Designed evidence-first learning artifacts that can be reviewed and explained.
- Implemented CI/CD and release hygiene suitable for an open GitHub portfolio.
- Turned retrieval tuning into a reviewable product workflow instead of a notebook-only parameter search.

## Quantified Expressions

- 733 backend tests pass, with 1 platform-dependent skip, covering ingestion, RAG, Agent recovery, policy/optimizer/feedback lifecycle, evaluation, media, release and migration safety.
- 121 frontend unit tests and 47 strict browser scenarios cover typed presentation and service workflows; model outputs in these checks are explicitly labeled test data, not real-model quality evidence.
- 44 Next.js page routes form the current product surface.
- 7 checked-in screenshots document the main workflow.
- One release dry-run reports included/excluded file counts and checks for secrets, databases, uploads and caches.
- 30 interview Q&A prompts explain architecture, RAG, multimodal processing, task orchestration and engineering quality.

## Interview Follow-Ups And Answer Templates

### How did you design RAG?

I parse sources into traceable chunks, embed them into Qdrant, retrieve relevant chunks for a question, and only return citations that map back to persisted evidence. I also avoid forcing citations when the model did not actually ground the answer.

### How did you handle multimodal data?

I model every upload as a `Source` with revisions and assets. Image OCR, audio transcription, video transcription and keyframe extraction produce chunks, transcript segments, frames and citation locators, so media can participate in the same retrieval and learning flow as documents.

### How did you handle long-running tasks?

I use Redis/RQ plus persistent `IngestionJob` and `JobEvent` records. The UI reads state from the database, not process memory, so progress, failures, retries and cancellation remain visible.

### How did you avoid fake AI capability?

Real mode requires provider configuration. Missing LLM, embedding, OCR or transcription providers return explicit NOT_CONFIGURED-style errors. Demo data is labelled synthetic and does not claim that providers ran.

### How did you make this GitHub-ready?

I added CI, issue/PR templates, security and contribution docs, release dry-run checks, secret scanning, UTF-8 checks, demo seed/readiness scripts, RAG evaluation, full regression checks, screenshots, architecture diagrams and a README that states both capabilities and limits.

## Connecting The Project To AI Application Development Ability

This project demonstrates product thinking, RAG architecture, multimodal data modeling, task orchestration, provider boundary design, frontend evidence navigation, learning-system design and engineering discipline. It is not just a page; it is a small but complete AI application lifecycle.
