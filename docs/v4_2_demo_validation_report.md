# V4.2 Demo Validation Report

Generated at: 2026-07-03 Asia/Shanghai

## Scope

V4.2 validates that the README-driven demo is not just seeded data, but a coherent product walkthrough:

source evidence -> task center -> RAG answer/refusal -> citation locator -> learning assets -> portfolio/interview explanation.

## Demo Data Boundary

- Database used for verification: `.pytest_tmp/v4_2_demo_showcase.db`.
- Seed command: `python scripts/seed_demo_data.py --database-path .pytest_tmp/v4_2_demo_showcase.db --reset`.
- The data is synthetic and labelled. It does not claim real OCR, transcription, LLM output or private user data.

## Readiness Evidence

`python scripts/check_demo_ready.py --database-path .pytest_tmp/v4_2_demo_showcase.db` passed with:

- `knowledge_spaces=1`
- `documents=2`
- `sources=4`
- `source_types={'audio': 1, 'code_repository': 1, 'image': 1, 'video': 1}`
- `multimodal_chunks=9`
- `citation_locators=9`
- `transcript_segments=6`
- `visual_frames=3`
- `ingestion_jobs=4`
- `job_statuses={'completed': 2, 'failed': 1, 'running': 1}`
- `qa_logs=2`
- `qa_statuses={'grounded': 1, 'insufficient_context': 1}`
- learning cards, knowledge points, quizzes, notes and version learning package records present.

## Demo Walkthrough

1. Open Dashboard and confirm project metrics load.
2. Open Upload Center and explain document, image, audio, video and code-repository ingestion paths.
3. Open Task Center and show completed, running and `NOT_CONFIGURED` failed task states.
4. Open Chat and explain grounded answer citations plus insufficient-context refusal behavior.
5. Open Media Library and video detail to show timestamp transcript/keyframe evidence.
6. Open Learning Center to show source-derived cards, quizzes and notes.
7. Open Portfolio and Interview pages to explain how project facts become resume/interview material.

## Current Limitations

- Browser automation is represented by static frontend smoke checks in V4.2; live Playwright against running services remains future work.
- Redis/Qdrant are still required for real background dispatch and vector retrieval.
- Real OCR/transcription/LLM/embedding quality requires configured providers and is not measured by synthetic demo data.
