## V4.2 Learning Package Draft

- Generated at: 2026-07-03 22:46:30
- Version goal: Full regression, demo stability and release readiness
- Evidence: Git diff/status, backend route scan, dependency changes, migration changes and optional verification reports.

### Changed Files
- `M` `.github/workflows/ci.yml`
- `M` `README.md`
- `M` `backend/app/core/config.py`
- `M` `backend/tests/test_v3_9_rag_evaluation.py`
- `??` `backend/tests/test_v4_2_full_regression.py`
- `M` `docs/demo_mode.md`
- `M` `docs/rag_evaluation.md`
- `M` `docs/release_process.md`
- `M` `docs/roadmap.md`
- `M` `docs/scripts_reference.md`
- `??` `docs/v4_2_acceptance_report.md`
- `??` `docs/v4_2_demo_validation_report.md`
- `??` `docs/v4_2_full_regression_report.md`
- `??` `docs/v4_2_github_release_notes.md`
- `??` `docs/v4_2_learning_package_draft.md`
- `??` `docs/v4_2_rag_quality_report.md`
- `??` `docs/v4_2_test_report.md`
- `M` `frontend/package-lock.json`
- `M` `frontend/package.json`
- `M` `scripts/check_demo_ready.py`
- `??` `scripts/check_full_regression.py`
- `M` `scripts/check_release.py`
- `M` `scripts/check_version.py`
- `M` `scripts/evaluate_rag.py`
- `M` `scripts/release.py`
- `M` `scripts/seed_showcase.py`

### Git Summary
```text
.github/workflows/ci.yml                  |  13 +--
 README.md                                 |  20 ++--
 backend/app/core/config.py                |   4 +-
 backend/tests/test_v3_9_rag_evaluation.py |   3 +
 docs/demo_mode.md                         |   9 +-
 docs/rag_evaluation.md                    |  18 ++--
 docs/release_process.md                   |  12 ++-
 docs/roadmap.md                           |  15 ++-
 docs/scripts_reference.md                 |   5 +-
 frontend/package-lock.json                |   4 +-
 frontend/package.json                     |   2 +-
 scripts/check_demo_ready.py               |  57 ++++++++++-
 scripts/check_release.py                  |   4 +-
 scripts/check_version.py                  |   4 +-
 scripts/evaluate_rag.py                   | 151 +++++++++++++++++++++++++++---
 scripts/release.py                        |   2 +-
 scripts/seed_showcase.py                  | 140 ++++++++++++++++++++++++++-
 17 files changed, 399 insertions(+), 64 deletions(-)
```

### Commit Range
- No commit range was provided; the draft is based on the working tree.

### Dependency Changes
- `frontend/package-lock.json`
- `frontend/package.json`

### Migration Changes
- No migration file changes detected.

### API Route Snapshot
- `backend/app/api/routes_chat.py::@router.post("/ask", response_model=ChatResponse)`
- `backend/app/api/routes_chat.py::@router.get("/history", response_model=list[QALogRead])`
- `backend/app/api/routes_chat.py::@router.post("/sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_chat.py::@router.get("/sessions", response_model=list[ChatSessionRead])`
- `backend/app/api/routes_chat.py::@router.get("/sessions/{session_id}", response_model=ChatSessionRead)`
- `backend/app/api/routes_chat.py::@router.patch("/sessions/{session_id}", response_model=ChatSessionRead)`
- `backend/app/api/routes_chat.py::@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)`
- `backend/app/api/routes_chat.py::@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)`
- `backend/app/api/routes_chat.py::@router.post("/messages/{message_id}/regenerate", response_model=ChatResponse)`
- `backend/app/api/routes_chat.py::@router.post("/messages/{message_id}/favorite", response_model=ChatFavoriteResponse)`
- `backend/app/api/routes_code_repositories.py::@router.post("/ingest-local", response_model=CodeRepositoryIngestResponse, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_code_repositories.py::@router.get("", response_model=list[SourceDetail])`
- `backend/app/api/routes_code_repositories.py::@router.get("/{source_id}", response_model=SourceDetail)`
- `backend/app/api/routes_dashboard.py::@router.get("/summary", response_model=DashboardSummary)`
- `backend/app/api/routes_documents.py::@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_documents.py::@router.get("", response_model=list[DocumentRead])`
- `backend/app/api/routes_documents.py::@router.post("/bulk-delete", response_model=BulkDocumentActionResponse)`
- `backend/app/api/routes_documents.py::@router.post("/bulk-reindex", response_model=BulkDocumentActionResponse)`
- `backend/app/api/routes_documents.py::@router.post("/bulk-tags", response_model=BulkDocumentActionResponse)`
- `backend/app/api/routes_documents.py::@router.get("/{document_id}", response_model=DocumentRead)`
- `backend/app/api/routes_documents.py::@router.patch("/{document_id}", response_model=DocumentRead)`
- `backend/app/api/routes_documents.py::@router.delete("/{document_id}", response_model=DocumentActionResponse)`
- `backend/app/api/routes_documents.py::@router.post("/{document_id}/retry", response_model=DocumentActionResponse)`
- `backend/app/api/routes_documents.py::@router.post("/{document_id}/reparse", response_model=DocumentActionResponse)`
- `backend/app/api/routes_documents.py::@router.post("/{document_id}/reindex", response_model=DocumentActionResponse)`
- `backend/app/api/routes_documents.py::@router.get("/{document_id}/chunks", response_model=list[ChunkRead])`
- `backend/app/api/routes_errors.py::@router.get("", response_model=list[ErrorArchiveRead])`
- `backend/app/api/routes_errors.py::@router.post("/from-source/{source_id}", response_model=ErrorExtractionResponse)`
- `backend/app/api/routes_errors.py::@router.get("/{archive_id}", response_model=ErrorArchiveRead)`
- `backend/app/api/routes_errors.py::@router.patch("/{archive_id}", response_model=ErrorArchiveRead)`
- `backend/app/api/routes_ingestion_jobs.py::@router.get("", response_model=list[IngestionJobRead])`
- `backend/app/api/routes_ingestion_jobs.py::@router.get("/{job_id}", response_model=IngestionJobRead)`
- `backend/app/api/routes_ingestion_jobs.py::@router.get("/{job_id}/events", response_model=list[JobEventRead])`
- `backend/app/api/routes_ingestion_jobs.py::@router.post("/{job_id}/retry", response_model=IngestionJobRead)`
- `backend/app/api/routes_ingestion_jobs.py::@router.post("/{job_id}/cancel", response_model=IngestionJobRead)`
- `backend/app/api/routes_knowledge_spaces.py::@router.post("", response_model=KnowledgeSpaceRead, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_knowledge_spaces.py::@router.get("", response_model=list[KnowledgeSpaceDetail])`
- `backend/app/api/routes_knowledge_spaces.py::@router.get("/{space_id}", response_model=KnowledgeSpaceDetail)`
- `backend/app/api/routes_learning.py::@router.get("/logs", response_model=list[LearningLogRead])`
- `backend/app/api/routes_learning.py::@router.get("/dashboard", response_model=LearningDashboard)`
- `backend/app/api/routes_learning.py::@router.get("/versions", response_model=list[LearningLogRead])`
- `backend/app/api/routes_learning.py::@router.get("/logs/{slug}", response_model=LearningLogRead)`
- `backend/app/api/routes_learning.py::@router.post("/logs", response_model=LearningLogRead, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_learning.py::@router.post("/packages/generate-draft", response_model=LearningPackageRead)`
- `backend/app/api/routes_learning.py::@router.post("/packages", response_model=LearningPackageRead, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_learning.py::@router.get("/packages", response_model=list[LearningPackageRead])`
- `backend/app/api/routes_learning.py::@router.get("/packages/{slug}", response_model=LearningPackageRead)`
- `backend/app/api/routes_learning.py::@router.patch("/packages/{slug}", response_model=LearningPackageRead)`
- `backend/app/api/routes_learning.py::@router.post("/packages/{slug}/confirm", response_model=LearningPackageRead)`
- `backend/app/api/routes_learning.py::@router.post("/packages/{slug}/export", response_model=MarkdownExportResponse)`
- `backend/app/api/routes_learning.py::@router.get("/knowledge-points", response_model=list[KnowledgePointRead])`
- `backend/app/api/routes_learning.py::@router.get("/roadmap", response_model=LearningRoadmapRead)`
- `backend/app/api/routes_learning.py::@router.get("/knowledge-graph", response_model=list[KnowledgeRelationRead])`
- `backend/app/api/routes_learning.py::@router.get("/knowledge-points/{point_id}", response_model=KnowledgePointRead)`
- `backend/app/api/routes_learning.py::@router.patch("/knowledge-points/{point_id}/progress", response_model=KnowledgePointRead)`
- `backend/app/api/routes_learning.py::@router.post("/knowledge-points/{point_id}/notes", response_model=KnowledgePointRead)`
- `backend/app/api/routes_learning.py::@router.get("/cards", response_model=list[LearningCardRead])`
- `backend/app/api/routes_learning.py::@router.patch("/cards/{card_id}/progress", response_model=LearningCardRead)`
- `backend/app/api/routes_learning.py::@router.post("/cards/{card_id}/review", response_model=LearningCardRead)`
- `backend/app/api/routes_learning.py::@router.get("/quizzes", response_model=list[QuizQuestionRead])`
- `backend/app/api/routes_learning.py::@router.post("/quizzes/{quiz_id}/answer", response_model=QuizAnswerResponse)`
- `backend/app/api/routes_learning.py::@router.post("/export-markdown", response_model=MarkdownExportResponse)`
- `backend/app/api/routes_learning.py::@router.get("/notes", response_model=list[LearningNoteRead])`
- `backend/app/api/routes_learning.py::@router.post("/notes", response_model=LearningNoteRead, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_learning.py::@router.post("/from-source", response_model=LearningArtifactBatchResponse, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_learning.py::@router.patch("/notes/{note_id}", response_model=LearningNoteRead)`
- `backend/app/api/routes_learning.py::@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)`
- `backend/app/api/routes_media.py::@router.post("/images/upload", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_media.py::@router.post("/audio/upload", response_model=AudioUploadResponse, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_media.py::@router.post("/video/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)`
- `backend/app/api/routes_media.py::@router.get("/sources", response_model=list[SourceDetail])`
- `backend/app/api/routes_media.py::@router.get("/sources/{source_id}", response_model=SourceDetail)`
- `backend/app/api/routes_media.py::@router.get("/sources/{source_id}/file", response_class=FileResponse)`
- `backend/app/api/routes_media.py::@router.get("/assets/{asset_id}/file", response_class=FileResponse)`
- `backend/app/api/routes_media.py::@router.post("/sources/{source_id}/process", response_model=MediaTaskResponse, status_code=status.HTTP_202_ACCEPTED)`
- `backend/app/api/routes_media.py::@router.post("/sources/{source_id}/ocr", response_model=MediaTaskResponse, status_code=status.HTTP_202_ACCEPTED)`
- `backend/app/api/routes_media.py::@router.post("/sources/{source_id}/transcribe", response_model=MediaTaskResponse, status_code=status.HTTP_202_ACCEPTED)`
- `backend/app/api/routes_onboarding.py::@router.get("", response_model=OnboardingRead)`
- `backend/app/api/routes_onboarding.py::@router.patch("", response_model=OnboardingRead)`
- `backend/app/api/routes_onboarding.py::@router.post("/reset", response_model=OnboardingRead)`
- `backend/app/api/routes_portfolio.py::@router.get("/summary", response_model=PortfolioSummary)`
- `backend/app/api/routes_portfolio.py::@router.post("/generate-resume-entry", response_model=PortfolioMarkdownResponse)`
- `backend/app/api/routes_portfolio.py::@router.post("/generate-interview-qa", response_model=PortfolioMarkdownResponse)`
- `backend/app/api/routes_portfolio.py::@router.post("/generate-project-review", response_model=PortfolioMarkdownResponse)`
- `backend/app/api/routes_portfolio.py::@router.post("/export-markdown", response_model=PortfolioMarkdownResponse)`
- `backend/app/api/routes_system.py::@router.get("/status", response_model=SystemStatusResponse)`
- `backend/app/api/routes_system.py::@router.post("/test-llm", response_model=SystemTestResponse)`
- `backend/app/api/routes_system.py::@router.post("/test-embedding", response_model=SystemTestResponse)`
- `backend/app/api/routes_system.py::@router.post("/test-qdrant", response_model=SystemTestResponse)`

### Knowledge Topics
#### Release Verification
- Beginner explanation: A release package must be reproducible and must not include dependencies, caches, secrets or user data.
- Project usage: V4.2 keeps release.py exclusion rules and adds full-regression checks for demo data, RAG evidence and required release docs.
- Code locations: `.github/workflows/ci.yml`, `README.md`, `backend/app/core/config.py`, `backend/tests/test_v3_9_rag_evaluation.py`, `backend/tests/test_v4_2_full_regression.py`, `docs/demo_mode.md`, `docs/rag_evaluation.md`, `docs/release_process.md`
- Review suggestion: Review zip packaging, SHA256 checks, exclusion rules and acceptance reports.
- Interview expression: I treated release packaging as part of the product boundary, verifying that generated archives exclude secrets, databases, uploads and build caches.

#### Portfolio Documentation
- Beginner explanation: A GitHub portfolio project needs docs that help a stranger run, understand and evaluate it.
- Project usage: V4.2 updates quickstart-facing README commands, demo mode, RAG evaluation and release docs around full regression and release readiness.
- Code locations: `.github/workflows/ci.yml`, `README.md`, `backend/app/core/config.py`, `backend/tests/test_v3_9_rag_evaluation.py`, `backend/tests/test_v4_2_full_regression.py`, `docs/demo_mode.md`, `docs/rag_evaluation.md`, `docs/release_process.md`
- Review suggestion: Review README navigation, quickstart commands, demo boundaries and whether planned features are clearly separated.
- Interview expression: I turned the repository from a code dump into a portfolio-ready project with runnable demo docs, interview notes and honest capability boundaries.

#### Demo Reset Workflow
- Beginner explanation: A demo should be repeatable; reset scripts make it easy to recover a clean synthetic showcase state.
- Project usage: V4.2 strengthens seed/check flows so the demo database contains document, image, audio, video, code, task, QA and learning evidence.
- Code locations: `.github/workflows/ci.yml`, `README.md`, `backend/app/core/config.py`, `backend/tests/test_v3_9_rag_evaluation.py`, `backend/tests/test_v4_2_full_regression.py`, `docs/demo_mode.md`, `docs/rag_evaluation.md`, `docs/release_process.md`
- Review suggestion: Review path safety checks, synthetic data labels and demo readiness validation.
- Interview expression: I made the demo reproducible by adding a reset workflow that rebuilds only the isolated synthetic database and verifies required records.

#### Roadmap Specifications
- Beginner explanation: Large features should be specified before implementation so docs do not overpromise.
- Project usage: V4.2 moves full regression, demo readiness and RAG quality gates from roadmap intent into executable scripts and CI.
- Code locations: `.github/workflows/ci.yml`, `README.md`, `backend/app/core/config.py`, `backend/tests/test_v3_9_rag_evaluation.py`, `backend/tests/test_v4_2_full_regression.py`, `docs/demo_mode.md`, `docs/rag_evaluation.md`, `docs/release_process.md`
- Review suggestion: Review each design doc and mark implemented, requires configuration, demo-only, planned and limitation states.
- Interview expression: I documented the V4.0 architecture direction before coding it, which keeps roadmap claims honest and reviewable.

#### Version Governance
- Beginner explanation: A visible product version must match backend config, frontend package metadata, README badges and CI release commands.
- Project usage: V4.2 updates version consistency checks, backend config, frontend package metadata, README badge and CI release artifact naming.
- Code locations: `.github/workflows/ci.yml`, `README.md`, `backend/app/core/config.py`, `backend/tests/test_v3_9_rag_evaluation.py`, `backend/tests/test_v4_2_full_regression.py`, `docs/demo_mode.md`, `docs/rag_evaluation.md`, `docs/release_process.md`
- Review suggestion: Review check_version.py and every version-bearing file after a version bump.
- Interview expression: I treated versioning as a testable contract across backend, frontend, docs and CI instead of a README-only label.

### Test Report
```text
No test report file was provided.
```

### Build Report
```text
No build report file was provided.
```

### Migration Report
```text
No migration report file was provided.
```

### V4.2 Study Addendum

#### Full Regression As A Product Contract
- Beginner explanation: Full regression means checking that the important user journeys still work after cleanup.
- Project usage: `scripts/check_full_regression.py` validates backend routes, frontend pages, demo source types, task states, QA statuses, locators and learning assets.
- Debugging method: Seed a fresh demo DB, run full regression, fix the first missing route/table/locator, rerun.
- Interview expression: I converted release readiness into an executable checklist instead of relying on manual confidence.

#### Demo Honesty
- Beginner explanation: Demo data can teach the workflow, but it must not pretend to be real model output.
- Project usage: The V4.2 demo includes both grounded QA and insufficient-context refusal, plus a failed NOT_CONFIGURED task.
- Debugging method: Inspect `qa_logs.retrieval_status`, `ingestion_jobs.error_code` and `runtime_mode`.
- Interview expression: I used synthetic data to demonstrate product flow while preserving real-provider boundaries.

#### Citation Validity
- Beginner explanation: Citation validity means an answer citation can be resolved back to a real stored locator.
- Project usage: `scripts/evaluate_rag.py` now checks `CitationLocator` rows, timestamp locators and code file/line locators.
- Debugging method: Compare `citations_json`, `related_chunks_json`, `multimodal_chunks.locator_json` and `citation_locators.locator_json`.
- Interview expression: I strengthened RAG quality gates around evidence traceability, not just answer text.
