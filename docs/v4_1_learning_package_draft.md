## V4.1 Learning Package Draft

- Generated at: 2026-07-02 19:39:38
- Version goal: Clean up the codebase, archive historical reports, consolidate backend/frontend/script architecture boundaries, and strengthen quality gates without adding fake AI capabilities.
- Evidence: Git diff/status, backend route scan, dependency changes, migration changes and optional verification reports.

### Changed Files
- `M` `README.md`
- `M` `backend/tests/test_v3_6_citations_release_package.py`
- `M` `docs/architecture.md`
- `M` `docs/architecture_diagram.md`
- `R100` `docs/archive/v2/v2_5_acceptance_report.md`
- `R100` `docs/archive/v2/v2_5_learning_package_draft.json`
- `R100` `docs/archive/v2/v2_current_state_audit.md`
- `R100` `docs/archive/v3/v3_1_image_metadata_report.md`
- `R100` `docs/archive/v3/v3_3_error_archive_report.md`
- `R100` `docs/archive/v3/v3_4_audio_transcription_report.md`
- `R100` `docs/archive/v3/v3_5_video_pipeline_report.md`
- `R100` `docs/archive/v3/v3_6_acceptance_report.md`
- `R100` `docs/archive/v3/v3_6_learning_package_draft.json`
- `R100` `docs/archive/v3/v3_7_acceptance_report.md`
- `R100` `docs/archive/v3/v3_7_learning_package_draft.md`
- `R100` `docs/archive/v3/v3_7_predevelopment_audit.md`
- `R100` `docs/archive/v3/v3_8_acceptance_report.md`
- `R100` `docs/archive/v3/v3_8_learning_package_draft.md`
- `R100` `docs/archive/v3/v3_8_test_report.md`
- `R100` `docs/archive/v3/v3_9_quality_gate_report.md`
- `R100` `docs/archive/v3/v3_acceptance_report.md`
- `R100` `docs/archive/v3/v3_learning_package_draft.json`
- `R100` `docs/archive/v3/v3_predevelopment_audit.md`
- `R100` `docs/archive/v4/v4_0_long_run_predevelopment_audit.md`
- `??` `docs/backend_architecture.md`
- `??` `docs/frontend_architecture.md`
- `M` `docs/learning_log.md`
- `??` `docs/module_boundaries.md`
- `M` `docs/roadmap.md`
- `??` `docs/scripts_reference.md`
- `M` `docs/stage_delivery_log.md`
- `??` `docs/v4_1_acceptance_report.md`
- `??` `docs/v4_1_ci_release_audit.md`
- `??` `docs/v4_1_cleanup_report.md`
- `??` `docs/v4_1_code_inventory.json`
- `??` `docs/v4_1_code_inventory.md`
- `??` `docs/v4_1_config_audit.md`
- `??` `docs/v4_1_dead_code_plan.md`
- `??` `docs/v4_1_dead_code_report.md`
- `??` `docs/v4_1_dependency_audit.md`
- `??` `docs/v4_1_docs_cleanup_report.md`
- `??` `docs/v4_1_predevelopment_audit.md`
- `??` `docs/v4_1_test_audit.md`
- `M` `docs/version_learning_package.md`
- `M` `frontend/app/errors/page.tsx`
- `M` `frontend/app/media/page.tsx`
- `M` `frontend/app/media/sources/[id]/page.tsx`
- `M` `frontend/app/tasks/page.tsx`
- `M` `frontend/app/upload/page.tsx`
- `??` `scripts/audit_codebase.py`
- `M` `scripts/check_release.py`

### Git Summary
```text
README.md                                          |  2 +-
 .../tests/test_v3_6_citations_release_package.py   |  2 +-
 docs/architecture.md                               | 15 ++++++-
 docs/architecture_diagram.md                       | 19 +++++++++
 docs/{ => archive/v2}/v2_5_acceptance_report.md    |  0
 .../v2}/v2_5_learning_package_draft.json           |  0
 docs/{ => archive/v2}/v2_current_state_audit.md    |  0
 .../{ => archive/v3}/v3_1_image_metadata_report.md |  0
 docs/{ => archive/v3}/v3_3_error_archive_report.md |  0
 .../v3}/v3_4_audio_transcription_report.md         |  0
 .../{ => archive/v3}/v3_5_video_pipeline_report.md |  0
 docs/{ => archive/v3}/v3_6_acceptance_report.md    |  0
 .../v3}/v3_6_learning_package_draft.json           |  0
 docs/{ => archive/v3}/v3_7_acceptance_report.md    |  0
 .../v3}/v3_7_learning_package_draft.md             |  0
 docs/{ => archive/v3}/v3_7_predevelopment_audit.md |  0
 docs/{ => archive/v3}/v3_8_acceptance_report.md    |  0
 .../v3}/v3_8_learning_package_draft.md             |  0
 docs/{ => archive/v3}/v3_8_test_report.md          |  0
 docs/{ => archive/v3}/v3_9_quality_gate_report.md  |  0
 docs/{ => archive/v3}/v3_acceptance_report.md      |  0
 .../v3}/v3_learning_package_draft.json             |  0
 docs/{ => archive/v3}/v3_predevelopment_audit.md   |  0
 .../v4}/v4_0_long_run_predevelopment_audit.md      |  0
 docs/learning_log.md                               | 27 ++++++++++++
 docs/roadmap.md                                    | 15 +++++++
 docs/stage_delivery_log.md                         | 31 ++++++++++++++
 docs/version_learning_package.md                   | 23 ++++++----
 frontend/app/errors/page.tsx                       |  9 ++--
 frontend/app/media/page.tsx                        |  9 ++--
 frontend/app/media/sources/[id]/page.tsx           | 49 ++++++++++------------
 frontend/app/tasks/page.tsx                        | 11 +++--
 frontend/app/upload/page.tsx                       |  9 ++--
 scripts/check_release.py                           |  2 +-
 34 files changed, 164 insertions(+), 59 deletions(-)
```

### Commit Range
- No commit range was provided; the draft is based on the working tree.

### Dependency Changes
- No dependency file changes detected.

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
#### Citation Deep Links
- Beginner explanation: A citation should take the learner back to the evidence, not just name a file.
- Project usage: Chat citations now carry source_id/document_id and timestamp fields; CitationPanel links to document chunks or media timestamps.
- Code locations: `README.md`, `backend/tests/test_v3_6_citations_release_package.py`, `docs/architecture.md`, `docs/architecture_diagram.md`, `docs/archive/v2/v2_5_acceptance_report.md`, `docs/archive/v2/v2_5_learning_package_draft.json`, `docs/archive/v2/v2_current_state_audit.md`, `docs/archive/v3/v3_1_image_metadata_report.md`
- Review suggestion: Review citation payloads, URL query parameters, player seek and highlighted transcript chunks.
- Interview expression: I connected RAG citations to frontend routes so audio and video answers can jump to the exact timestamp that supports the answer.

#### Demo-Friendly Frontend
- Beginner explanation: A user-facing OS should explain the next action without exposing raw internal fields on primary screens.
- Project usage: V3.6 improves Upload Center, Task Center and media detail pages with clearer steps, result links, transcript highlighting and keyframe browsing.
- Code locations: `README.md`, `backend/tests/test_v3_6_citations_release_package.py`, `docs/architecture.md`, `docs/architecture_diagram.md`, `docs/archive/v2/v2_5_acceptance_report.md`, `docs/archive/v2/v2_5_learning_package_draft.json`, `docs/archive/v2/v2_current_state_audit.md`, `docs/archive/v3/v3_1_image_metadata_report.md`
- Review suggestion: Review workflow cards, task filters, media player state, responsive layout and progressive disclosure.
- Interview expression: I reshaped the frontend around user workflows: upload, process, inspect evidence, ask questions and turn evidence into learning assets.

#### Release Verification
- Beginner explanation: A release package must be reproducible and must not include dependencies, caches, secrets or user data.
- Project usage: V3.6 keeps release.py exclusion rules and adds tests/checks for forbidden archive entries.
- Code locations: `README.md`, `backend/tests/test_v3_6_citations_release_package.py`, `docs/architecture.md`, `docs/architecture_diagram.md`, `docs/archive/v2/v2_5_acceptance_report.md`, `docs/archive/v2/v2_5_learning_package_draft.json`, `docs/archive/v2/v2_current_state_audit.md`, `docs/archive/v3/v3_1_image_metadata_report.md`
- Review suggestion: Review zip packaging, SHA256 checks, exclusion rules and acceptance reports.
- Interview expression: I treated release packaging as part of the product boundary, verifying that generated archives exclude secrets, databases, uploads and build caches.

### Test Report
```text
# V4.1 Test Audit

## Current Test Inventory

The V4.1 inventory reports 34 backend test files under `backend/tests`.

Coverage areas include:

- Health and system status.
- Demo readiness and reset path safety.
- Document ingestion, deduplication, indexing and RAG citations.
- Task engine creation, retry, cancel and media job fields.
- Image upload/OCR refusal and error archive.
- Audio/video upload, transcription refusal/success paths and timestamp citations.
- Learning packages, learning artifacts, roadmap and graph endpoints.
- Code repository ingestion and provider refusal.
- Portfolio summary and generation refusal boundaries.
- Release exclusions and repository safety scripts.

## Recent Test-Related Cleanup

- Updated `backend/tests/test_v3_6_citations_release_package.py` to use the archived V3.6 acceptance report path.
- Removed frontend hooks dependency suppression comments and verified TypeScript with `tsc --noEmit`.

## Required Final Gates

V4.1 is not complete until these commands are run and recorded:

```powershell
python -m compileall backend/app scripts
python -m pytest
cd frontend; npm run typecheck
cd frontend; npm run build
python scripts/check_encoding.py
python scripts/check_secrets.py
python scripts/check_repo_clean.py
python scripts/release.py --dry-run
```

Optional when available:

```powershell
python scripts/evaluate_rag.py --demo
python scripts/check_frontend_smoke.py
```

## Current Evidence

- `python scripts/check_encoding.py`: passed after docs cleanup.
- `python -m compileall backend/app scripts`: passed.
- `python -m pytest`: passed, 61 tests and 8 warnings.
- Frontend `tsc --noEmit`: passed after hooks cleanup.
- Frontend production build: passed, 28 generated routes.
- Alembic upgrade/current against an isolated `.pytest_tmp` SQLite database: passed, current head `0006_v3_6_unified_media_tasks`.

Secret, repo-clean and release dry-run checks passed after the final V4.1 file set was staged for tracked-file analysis.
```

### Build Report
```text
# V4.1 Acceptance Report

Generated at: 2026-07-02 Asia/Shanghai

## Scope

V4.1 is a codebase cleanup, dead-code review, architecture consolidation and engineering quality pass. It does not claim new provider-backed AI capability and keeps `V3.8 / 3.8.0` as the current stable visible version until a final release tag is chosen.

## Delivered

- Added `scripts/audit_codebase.py` to generate predevelopment audit, code inventory, dead-code report and cleanup plan.
- Generated `docs/v4_1_predevelopment_audit.md`, `docs/v4_1_code_inventory.md`, `docs/v4_1_code_inventory.json`, `docs/v4_1_dead_code_report.md` and `docs/v4_1_dead_code_plan.md`.
- Archived historical V2, V3 and V4.0 reports under `docs/archive/v2`, `docs/archive/v3` and `docs/archive/v4`.
- Updated active references to archived report paths in README, release checks and tests.
- Rewrote `docs/version_learning_package.md` as readable UTF-8 Markdown.
- Added backend, frontend, module-boundary, script-reference, dependency, test, config, docs-cleanup and CI/release audit docs.
- Updated `docs/architecture.md`, `docs/architecture_diagram.md` and `docs/roadmap.md` for V4.1.
- Removed frontend hooks dependency suppression comments and replaced them with stable `useCallback` loaders.
- Removed untracked local pnpm preview artifacts and kept npm/package-lock as the frontend dependency standard.
- Appended V4.1 records to `docs/learning_log.md` and `docs/stage_delivery_log.md`.

## Verification Results

| Gate | Result |
| --- | --- |
| `python -m compileall backend/app scripts` | Passed |
| `python -m pytest` | Passed, 61 tests and 8 warnings |
| Frontend TypeScript check | Passed |
| Frontend production build | Passed, 28 app routes |
| Alembic upgrade/current on isolated SQLite | Passed, `0006_v3_6_unified_media_tasks (head)` |
| `python scripts/check_encoding.py` | Passed, 282 UTF-8 files; immutable legacy log warnings preserved |
| `python scripts/check_version.py` | Passed, `V3.8 / 3.8.0` |
| `python scripts/check_frontend_smoke.py` | Passed, `required_routes=27`, `nav_targets=24`, `warnings=0` |

## Final Staged Gates

The final safety gates were run after staging the V4.1 file set, so tracked-file scans included the new audit, architecture, archive and learning-package files.

- `python scripts/check_secrets.py`: passed, scanned 282 tracked text files, findings 0.
- `python scripts/check_repo_clean.py`: passed, forbidden tracked files 0.
- `python scripts/release.py --version V3.8 --dry-run`: passed, included files 293, secrets/database/uploads/cache all `no`.

## Cleanup Summary

- Archived historical files: 20.
- Removed untracked local preview artifacts: 2.
- Removed frontend hooks suppression comments: 7.
- Deleted tracked source files: 0.
- Deleted user data, databases, uploads, logs, releases, caches or secrets: 0.

## Honest Boundaries

- Static dead-code scanning found no deletion-safe source/service/component candidate. V4.1 therefore prioritized archive cleanup, documentation boundaries and low-risk frontend debt.
- Historical reports were moved, not deleted.
- `docs/learning_log.md` and `docs/stage_delivery_log.md` remain append-only.
- Real mode still must refuse missing LLM, embedding, OCR and transcription providers with explicit NOT_CONFIGURED-style errors.

## Suggested Commit Message

`chore: consolidate V4.1 codebase architecture and cleanup docs`

## Suggested Tag

`v4.1.0`.
```

### V4.1 Deep Knowledge Points

Each point below is tied to the V4.1 cleanup work and can be used for study, review and interview preparation.

#### 1. Technical Debt Identification
- Beginner explanation: Technical debt is work that still runs but makes future changes slower or riskier.
- Why this project needs it: V1-V4.0 created many features, reports and scripts; V4.1 needs a map before further expansion.
- Related files: `docs/v4_1_predevelopment_audit.md`, `docs/v4_1_code_inventory.md`.
- Impact scope: Docs, scripts, frontend, backend and release process.
- Common mistake: Treating every old file as trash instead of checking references.
- Debugging method: Compare `git status`, inventory JSON and `rg` references.
- Understanding question: What evidence proves a file is unused?
- Project exercise: Pick one asset from the inventory and trace its references.
- Interview expression: I started cleanup by measuring the codebase instead of deleting by intuition.
- Follow-up: Add richer function-level static analysis later.

#### 2. Zombie Code Cleanup
- Beginner explanation: Zombie code looks alive in the repo but has no active entrypoint or dependency.
- Why this project needs it: Large feature branches can leave old pages, services or reports behind.
- Related files: `docs/v4_1_dead_code_report.md`, `docs/v4_1_dead_code_plan.md`.
- Impact scope: Maintainability and release confidence.
- Common mistake: Deleting uncertain service code without route/test proof.
- Debugging method: Use `rg`, route scans, frontend API calls and tests together.
- Understanding question: Why did V4.1 avoid deleting uncertain backend services?
- Project exercise: Extend `audit_codebase.py` to mark API-client function usage.
- Interview expression: I made deletion evidence-based and kept risky candidates for review.
- Follow-up: Add import graph analysis.

#### 3. Code Asset Inventory
- Beginner explanation: An inventory lists what exists, what it does and where it is referenced.
- Why this project needs it: The repo now spans backend, frontend, docs, scripts, CI and release tooling.
- Related files: `scripts/audit_codebase.py`, `docs/v4_1_code_inventory.json`.
- Impact scope: Every future cleanup and refactor.
- Common mistake: Counting files but not recording purpose or test coverage.
- Debugging method: Inspect JSON assets and endpoint lists.
- Understanding question: What fields make an inventory actionable?
- Project exercise: Add owner/domain fields to the inventory.
- Interview expression: I built a repeatable inventory script so cleanup can be audited.
- Follow-up: Generate inventory diffs in CI.

#### 4. Static Reference Analysis
- Beginner explanation: Static analysis searches source text to infer which files call or mention another file.
- Why this project needs it: It catches many unused assets without executing the app.
- Related files: `scripts/audit_codebase.py`.
- Impact scope: Dead-code planning and archive decisions.
- Common mistake: Letting generated reports reference everything and pollute results.
- Debugging method: Exclude generated V4.1 reports from the reference index.
- Understanding question: Why are `page.tsx` and `layout.tsx` dangerous reference tokens?
- Project exercise: Add a list of common tokens to ignore.
- Interview expression: I controlled false positives in static analysis before trusting the report.
- Follow-up: Parse TypeScript imports structurally.

#### 5. Backend Module Consolidation
- Beginner explanation: Backend modules need clear route, service, model and provider responsibilities.
- Why this project needs it: Multimodal RAG, tasks, learning and portfolio features touch many layers.
- Related files: `docs/backend_architecture.md`, `docs/module_boundaries.md`.
- Impact scope: FastAPI routes, services, providers and SQLAlchemy models.
- Common mistake: Putting provider calls directly in routes.
- Debugging method: Trace request path from route to service to model/provider.
- Understanding question: Which layer owns NOT_CONFIGURED refusal?
- Project exercise: Draw the call chain for video transcription.
- Interview expression: I documented backend boundaries so future features have a clear home.
- Follow-up: Add route-to-service ownership tests.

#### 6. Frontend Component Consolidation
- Beginner explanation: Frontend pages should compose reusable UI instead of duplicating controls everywhere.
- Why this project needs it: Upload, media, tasks, learning and portfolio pages are growing.
- Related files: `docs/frontend_architecture.md`, `frontend/components/ui.tsx`.
- Impact scope: Page maintainability and UI consistency.
- Common mistake: Making every page own its own loading/error/status UI.
- Debugging method: Search for repeated card, empty and status patterns.
- Understanding question: Which components should move into `components/media` later?
- Project exercise: Extract a media transcript panel as a shared component.
- Interview expression: I identified component split points without forcing a risky rewrite.
- Follow-up: Introduce domain component folders.

#### 7. Dependency Governance
- Beginner explanation: Dependencies should be justified by actual imports or runtime needs.
- Why this project needs it: Media processing and AI providers can pull heavy optional packages.
- Related files: `docs/v4_1_dependency_audit.md`, `backend/requirements.txt`, `frontend/package.json`.
- Impact scope: CI speed, install reliability and release clarity.
- Common mistake: Removing provider/media dependencies just because one static search misses dynamic usage.
- Debugging method: Search imports and check scripts, tests and optional providers.
- Understanding question: Why keep `imageio-ffmpeg` and `Pillow`?
- Project exercise: Split runtime and dev requirements in a future branch.
- Interview expression: I audited dependencies conservatively and removed only local package-manager noise.
- Follow-up: Add dependency audit to CI.

#### 8. Script Governance
- Beginner explanation: Scripts are product tooling and need purpose, safety and examples.
- Why this project needs it: Demo, seed, release, check and learning scripts now form a toolchain.
- Related files: `docs/scripts_reference.md`, `scripts/*.py`.
- Impact scope: Local development, CI, demo and release.
- Common mistake: Letting scripts depend on absolute local paths.
- Debugging method: Run `--help` and inspect path safety checks.
- Understanding question: Which scripts can modify demo data?
- Project exercise: Add `--help` coverage tests for scripts.
- Interview expression: I documented scripts as maintainable operations tooling, not random helpers.
- Follow-up: Group scripts by category in a subpackage if the set grows.

#### 9. Documentation Archiving
- Beginner explanation: Archive old reports so history is preserved but active docs stay readable.
- Why this project needs it: V2-V4.0 reports were cluttering the docs root.
- Related files: `docs/archive`, `docs/v4_1_docs_cleanup_report.md`.
- Impact scope: GitHub browsing and release package readability.
- Common mistake: Deleting historical learning artifacts.
- Debugging method: Use `git mv` and update active references.
- Understanding question: Why not rewrite old learning log links?
- Project exercise: Add an archive index page.
- Interview expression: I preserved history while cleaning the active documentation surface.
- Follow-up: Move remaining older one-off notes when active links are mapped.

#### 10. CI Quality Gates
- Beginner explanation: CI gates are commands that prove the project still works after changes.
- Why this project needs it: A portfolio repo must be testable by strangers.
- Related files: `.github/workflows/ci.yml`, `docs/v4_1_ci_release_audit.md`.
- Impact scope: Backend, frontend, docs, release and safety checks.
- Common mistake: Running tests locally but forgetting tracked-file release scans.
- Debugging method: Match local commands to workflow steps.
- Understanding question: Why must secret checks run after staging?
- Project exercise: Add audit inventory generation as a CI artifact.
- Interview expression: I treated CI as evidence, not decoration.
- Follow-up: Add browser E2E smoke tests.

#### 11. Release Dry-Run Safety
- Beginner explanation: A release dry-run checks what would be packaged without creating a final release.
- Why this project needs it: The app has DBs, uploads, caches and local demo artifacts that must never ship.
- Related files: `scripts/release.py`, `scripts/check_release.py`.
- Impact scope: GitHub release hygiene and user privacy.
- Common mistake: Walking the working tree instead of tracked files and accidentally packaging caches.
- Debugging method: Inspect included/excluded counts and forbidden entry rules.
- Understanding question: Why did V4.1 update `check_release.py`?
- Project exercise: Add a required V4.1 acceptance report after final release.
- Interview expression: I validated release contents against explicit forbidden paths.
- Follow-up: Generate a release manifest report.

#### 12. Secret And Repo Clean Checks
- Beginner explanation: Secret checks look for key-like strings; repo-clean checks block generated/user data.
- Why this project needs it: AI apps often have provider keys, uploads and DB files locally.
- Related files: `scripts/check_secrets.py`, `scripts/check_repo_clean.py`.
- Impact scope: GitHub safety.
- Common mistake: Running checks before staging new files.
- Debugging method: Compare `git ls-files` output to working tree changes.
- Understanding question: Which files are intentionally ignored?
- Project exercise: Add a test fixture proving `.env.example` is allowed.
- Interview expression: I separated examples from real secrets and guarded release inputs.
- Follow-up: Add pre-commit docs for these checks.

#### 13. Architecture Boundaries
- Beginner explanation: Boundaries say which layer owns which responsibility.
- Why this project needs it: RAG, media tasks, learning and portfolio modules overlap conceptually.
- Related files: `docs/module_boundaries.md`, `docs/architecture.md`.
- Impact scope: Future feature placement.
- Common mistake: Duplicating status mapping or citation formatting in many places.
- Debugging method: Trace one workflow across route, service, model, provider and UI.
- Understanding question: Where should a new provider adapter live?
- Project exercise: Map image OCR from button click to stored chunk.
- Interview expression: I made module boundaries explicit so the system can keep growing safely.
- Follow-up: Enforce boundaries with import-lint rules later.

#### 14. Demo Mode Boundary
- Beginner explanation: Demo mode can show synthetic data but must not pretend providers ran.
- Why this project needs it: The repo needs reviewer-friendly demos without fake AI claims.
- Related files: `docs/demo_mode.md`, `docs/environment_variables.md`, `backend/app/core/config.py`.
- Impact scope: Trust, docs and tests.
- Common mistake: Filling missing OCR/transcription with placeholder text.
- Debugging method: Search for NOT_CONFIGURED tests and provider exceptions.
- Understanding question: What is allowed in synthetic demo data?
- Project exercise: Add a demo label to any new seeded media.
- Interview expression: I kept demo convenience separate from real-mode truthfulness.
- Follow-up: Add a demo-mode banner component audit.

#### 15. Provider Optional Design
- Beginner explanation: Optional providers allow the app to run without paid keys while refusing provider-backed work clearly.
- Why this project needs it: Users may run the project locally without LLM/OCR/transcription keys.
- Related files: `docs/provider_diagnostics.md`, `backend/app/services/providers.py`, `backend/app/services/transcription_service.py`.
- Impact scope: Real mode, tests and user trust.
- Common mistake: Letting a UI button silently succeed with fake output.
- Debugging method: Test missing-key paths and error codes.
- Understanding question: Why are upload and understanding separate actions?
- Project exercise: Add a provider diagnostic for a new adapter.
- Interview expression: I designed optional providers with explicit refusal instead of silent degradation.
- Follow-up: Centralize provider capability registry further.

#### 16. Citation Locator Governance
- Beginner explanation: Citations need structured locators so users can jump to exact evidence.
- Why this project needs it: Documents, images, audio, video and code all cite differently.
- Related files: `docs/citation_locator.md`, `frontend/components/CitationPanel.tsx`, `backend/app/models/source.py`.
- Impact scope: RAG trust and UI navigation.
- Common mistake: Returning only a filename as a citation.
- Debugging method: Inspect `document_id`, `source_id`, timestamp and chunk fields.
- Understanding question: How does video citation jumping differ from document citation jumping?
- Project exercise: Add a citation test for code line ranges.
- Interview expression: I treated citations as navigable evidence, not decorative metadata.
- Follow-up: Consolidate citation formatting into one shared frontend helper.

#### 17. Task Queue Observability
- Beginner explanation: Long-running tasks need durable progress and events.
- Why this project needs it: OCR, transcription, video keyframes and indexing can fail or take time.
- Related files: `docs/task_queue_flow.md`, `backend/app/services/media_task_service.py`, `frontend/app/tasks/page.tsx`.
- Impact scope: User recovery and debugging.
- Common mistake: Hiding task status inside local component state.
- Debugging method: Inspect `IngestionJob`, `JobEvent` and Task Center UI.
- Understanding question: Why do media jobs need `source_id`?
- Project exercise: Add stage-specific progress text for another media task.
- Interview expression: I unified document and media processing under observable jobs.
- Follow-up: Add worker heartbeat alerting.

#### 18. Frontend Hooks Hygiene
- Beginner explanation: Hook dependency rules prevent stale state and accidental missed updates.
- Why this project needs it: Upload, media, errors and task pages load live data.
- Related files: `frontend/app/upload/page.tsx`, `frontend/app/media/page.tsx`, `frontend/app/tasks/page.tsx`, `frontend/app/media/sources/[id]/page.tsx`.
- Impact scope: UI reliability.
- Common mistake: Suppressing exhaustive-deps instead of stabilizing callbacks.
- Debugging method: Run TypeScript/build and review effect dependencies.
- Understanding question: Why did `tasks/page.tsx` use functional `setSelectedJobId`?
- Project exercise: Convert another page loader to `useCallback`.
- Interview expression: I removed hook suppression comments without changing product behavior.
- Follow-up: Enable stricter frontend linting in CI.

#### 19. Documentation Trust
- Beginner explanation: Docs should say what is implemented, configured, demo-only or planned.
- Why this project needs it: Portfolio readers judge credibility from README and docs.
- Related files: `README.md`, `docs/architecture.md`, `docs/roadmap.md`.
- Impact scope: GitHub presentation and interviews.
- Common mistake: Marketing planned V4 features as shipped.
- Debugging method: Compare docs claims to routes, tests and configs.
- Understanding question: Why does V4.1 keep version `V3.8 / 3.8.0` for now?
- Project exercise: Audit one README section against code.
- Interview expression: I kept documentation honest by linking claims to current evidence.
- Follow-up: Add README required-section and claim checks.

#### 20. Long-Term Maintainability
- Beginner explanation: Maintainability means future changes are easier, safer and more explainable.
- Why this project needs it: The project is now large enough that architecture discipline matters.
- Related files: `docs/v4_1_acceptance_report.md`, `docs/v4_1_cleanup_report.md`, `docs/v4_1_test_audit.md`.
- Impact scope: Future V4.2+ development.
- Common mistake: Treating cleanup as a separate task from tests and docs.
- Debugging method: Require every cleanup batch to leave evidence.
- Understanding question: What would prove V4.1 is truly complete?
- Project exercise: Run a requirement-by-requirement acceptance audit.
- Interview expression: I demonstrated long-term ownership by combining cleanup, docs, tests and release safety.
- Follow-up: Create V4.2 issues for component splitting and E2E tests.

### Migration Report
```text
# V4.1 Acceptance Report

Generated at: 2026-07-02 Asia/Shanghai

## Scope

V4.1 is a codebase cleanup, dead-code review, architecture consolidation and engineering quality pass. It does not claim new provider-backed AI capability and keeps `V3.8 / 3.8.0` as the current stable visible version until a final release tag is chosen.

## Delivered

- Added `scripts/audit_codebase.py` to generate predevelopment audit, code inventory, dead-code report and cleanup plan.
- Generated `docs/v4_1_predevelopment_audit.md`, `docs/v4_1_code_inventory.md`, `docs/v4_1_code_inventory.json`, `docs/v4_1_dead_code_report.md` and `docs/v4_1_dead_code_plan.md`.
- Archived historical V2, V3 and V4.0 reports under `docs/archive/v2`, `docs/archive/v3` and `docs/archive/v4`.
- Updated active references to archived report paths in README, release checks and tests.
- Rewrote `docs/version_learning_package.md` as readable UTF-8 Markdown.
- Added backend, frontend, module-boundary, script-reference, dependency, test, config, docs-cleanup and CI/release audit docs.
- Updated `docs/architecture.md`, `docs/architecture_diagram.md` and `docs/roadmap.md` for V4.1.
- Removed frontend hooks dependency suppression comments and replaced them with stable `useCallback` loaders.
- Removed untracked local pnpm preview artifacts and kept npm/package-lock as the frontend dependency standard.
- Appended V4.1 records to `docs/learning_log.md` and `docs/stage_delivery_log.md`.

## Verification Results

| Gate | Result |
| --- | --- |
| `python -m compileall backend/app scripts` | Passed |
| `python -m pytest` | Passed, 61 tests and 8 warnings |
| Frontend TypeScript check | Passed |
| Frontend production build | Passed, 28 app routes |
| Alembic upgrade/current on isolated SQLite | Passed, `0006_v3_6_unified_media_tasks (head)` |
| `python scripts/check_encoding.py` | Passed, 282 UTF-8 files; immutable legacy log warnings preserved |
| `python scripts/check_version.py` | Passed, `V3.8 / 3.8.0` |
| `python scripts/check_frontend_smoke.py` | Passed, `required_routes=27`, `nav_targets=24`, `warnings=0` |

## Final Staged Gates

The final safety gates were run after staging the V4.1 file set, so tracked-file scans included the new audit, architecture, archive and learning-package files.

- `python scripts/check_secrets.py`: passed, scanned 282 tracked text files, findings 0.
- `python scripts/check_repo_clean.py`: passed, forbidden tracked files 0.
- `python scripts/release.py --version V3.8 --dry-run`: passed, included files 293, secrets/database/uploads/cache all `no`.

## Cleanup Summary

- Archived historical files: 20.
- Removed untracked local preview artifacts: 2.
- Removed frontend hooks suppression comments: 7.
- Deleted tracked source files: 0.
- Deleted user data, databases, uploads, logs, releases, caches or secrets: 0.

## Honest Boundaries

- Static dead-code scanning found no deletion-safe source/service/component candidate. V4.1 therefore prioritized archive cleanup, documentation boundaries and low-risk frontend debt.
- Historical reports were moved, not deleted.
- `docs/learning_log.md` and `docs/stage_delivery_log.md` remain append-only.
- Real mode still must refuse missing LLM, embedding, OCR and transcription providers with explicit NOT_CONFIGURED-style errors.

## Suggested Commit Message

`chore: consolidate V4.1 codebase architecture and cleanup docs`

## Suggested Tag

`v4.1.0`.
```
