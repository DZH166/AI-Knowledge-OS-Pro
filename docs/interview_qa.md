# Interview QA

These questions help explain AI Knowledge OS Pro as a portfolio project. Answers should stay honest about current implementation and limits.

## Project Positioning

1. What problem does AI Knowledge OS Pro solve?
   - It turns project materials, media and version work into searchable RAG evidence and learning artifacts for AI application learners.

2. Why is this more than a simple chat-with-docs app?
   - It includes ingestion governance, multimodal sources, durable tasks, timestamp citations, learning records, release checks and portfolio documentation.

3. Who is the target user?
   - A learner or junior AI application developer who wants to retain, review and explain project knowledge.

4. What is the strongest portfolio signal?
   - The project connects product UX, backend architecture, RAG, multimodal processing, CI, release safety and learning documentation.

## Architecture

5. What are the main modules?
   - Next.js frontend, FastAPI backend, SQLite relational data, Qdrant vector search, Redis/RQ tasks, provider adapters and docs/release tooling.

6. Why use FastAPI?
   - It is suitable for typed API contracts, async-friendly service boundaries and quick integration with Python AI tooling.

7. Why use SQLite?
   - It keeps local development and demos simple while still supporting SQLAlchemy/Alembic schema discipline.

8. Why use Qdrant?
   - It stores vectors for semantic retrieval and lets the project separate relational metadata from vector search.

9. Why use Redis/RQ?
   - Media and indexing work can be slow, so the project tracks it as durable background jobs with events and recovery controls.

## RAG

10. What is the RAG flow?
    - Ingest source, parse content, chunk, embed, index, retrieve relevant chunks, build prompt, call LLM and return citations.

11. How does the project prevent fake citations?
    - Citations are tied to stored chunks or multimodal locators; missing evidence or providers should produce refusal, not fabricated answers.

12. What happens when the LLM key is missing?
    - Real mode should return an explicit NOT_CONFIGURED-style error or refusal instead of a fake answer.

13. What is still missing for RAG quality?
    - V4.0 needs a dedicated RAG evaluation script, test set and report flow.

14. What is hybrid retrieval?
    - Combining vector retrieval with keyword or metadata retrieval; it is planned for V4.0 and must include fallback behavior.

## Multimodal

15. How are documents, images, audio and video unified?
    - Through source records, media assets, transcript segments, visual frames, multimodal chunks and citation locators.

16. How is audio handled?
    - Audio upload records real metadata and can call a real transcription provider when configured.

17. How is video handled?
    - Video upload records duration, dimensions and audio presence, can extract audio for transcription and stores keyframes.

18. What is the real-mode rule for OCR/transcription?
    - Missing providers must reject with configuration errors; the system must not create fake OCR or fake transcripts.

19. Why are timestamps important?
    - They let a cited answer jump back to the exact audio/video evidence.

## Task System

20. Why not process everything inside upload requests?
    - Long-running work would block requests and hide failures; background jobs make progress and recovery visible.

21. What does the task center show?
    - Job status, progress, stage events, target type, retry/cancel controls and links to result sources.

22. How do retry and cancel help?
    - They make processing recoverable without deleting data or manually editing the database.

## Learning System

23. What does the learning archive store?
    - Version records, knowledge points, learning cards, quizzes, notes and interview expressions.

24. Why keep version learning logs append-only?
    - They form a historical learning trail and support honest project retrospectives.

25. How are learning artifacts connected to sources?
    - V3.6/V3.7 links artifacts to real document or multimodal chunks instead of empty generated content.

## Engineering Quality

26. What does CI check?
    - Backend compile/tests/migrations, frontend typecheck/build and quality checks such as encoding, version and release safety.

27. What does release dry-run protect?
    - It verifies the archive would exclude secrets, databases, uploads, logs, dependencies and caches.

28. How is secret leakage reduced?
    - `.gitignore`, secret scan, repo clean check and release safety checks all protect the boundary.

29. What is the biggest current limitation?
    - V4.0-level features such as RAG evaluation, hybrid retrieval, code repository ingestion, portfolio generation and mock interview UI are not complete yet.

30. How would you continue the project?
    - Add measurable RAG evaluation, implement hybrid retrieval, ingest code repositories, build portfolio/interview modules and add lightweight E2E smoke tests.
