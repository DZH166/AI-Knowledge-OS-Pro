## V4.4 Learning Package Draft

- Generated at: 2026-07-05 00:47:37
- Version goal: Browser-level demo E2E contracts, citation jump validation, runtime observability and optional provider evaluation.
- Evidence: Git diff/status, backend route scan, dependency changes, migration changes and optional verification reports.

### V4.4 Focus Knowledge Points

| Topic | Beginner Explanation | Why This Project Needs It | Related Files | Call Chain | Common Error | Debug Method | Interview Expression | Review Suggestion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Browser E2E | Browser tests open the product like a real reviewer instead of only compiling files. | GitHub portfolio pages must prove the demo path can load in a browser. | `frontend/e2e/demo-smoke.spec.ts`, `scripts/run_demo_e2e.py` | seed demo DB -> start API -> start Next.js -> Playwright routes | Treating missing Playwright as a fake pass | Run `python scripts/check_all.py --e2e` and read skip reason | I added browser-level smoke coverage with honest skip behavior when runtime dependencies are missing. | Install Playwright locally and promote the same specs to a hard gate. |
| Playwright | Playwright automates Chromium navigation, assertions, screenshots and traces. | Citation jumps and observability pages are navigation behaviors, not only unit functions. | `frontend/playwright.config.ts`, `frontend/e2e/run-optional-e2e.mjs` | `npm run test:e2e` -> optional runner -> Playwright CLI | Missing browser binaries | Check `frontend/test-results/` and `frontend/playwright-report/` | I separated Playwright scaffolding from default app typecheck so CI stays provider-free. | Add browser install steps in a dedicated E2E workflow. |
| Demo Smoke | A smoke test checks the most important pages do not crash. | The demo needs Dashboard, Upload, Tasks, Chat, Media, Learning, Portfolio, Interview and System pages. | `frontend/e2e/demo-smoke.spec.ts` | route list -> `page.goto` -> body assertions | Backend not running causes `Failed to fetch` | Start with `scripts/run_demo_e2e.py` | I validated the demo journey at route level before claiming portfolio readiness. | Add page-specific assertions once UI text stabilizes. |
| Citation Jump Contract | A citation should carry enough locator data for the frontend to navigate to evidence. | RAG credibility depends on returning to source chunks, media timestamps or code lines. | `frontend/components/CitationPanel.tsx`, `backend/tests/test_citation_jump_contracts.py` | RAG citation -> `citationHref` -> document/media/code route | Missing `source_id` or `document_id` | Run citation contract tests and inspect hrefs | I made citations actionable evidence links instead of static labels. | Add live browser clicks with seeded citations. |
| Audio/Video Timestamp Seek | Media citations use `start_ms`/`end_ms` to land near the evidence moment. | Audio/video answers are only useful when users can inspect the exact transcript segment. | `frontend/app/media/sources/[id]/page.tsx`, `frontend/e2e/citation-jump.spec.ts` | citation timestamp -> `t` query -> media detail seek/highlight | Segment missing or no player available | Open `/media/sources/{id}?t=12&chunk=7` | I carried media timestamps through RAG citations into UI navigation. | Verify real seek behavior in live E2E when Playwright is installed. |
| Code File/Line Locator | Code citations use file path and line ranges to explain where evidence lives. | AI app learners need to explain implementation evidence precisely. | `frontend/app/code/page.tsx`, `frontend/components/CitationPanel.tsx` | citation -> `/code?file=&line=&line_end=` -> locator panel | `useSearchParams` without Suspense broke production build | Run `npm run build` | I added file/line citation routing and fixed the Next.js Suspense boundary. | Add repository detail rendering for file excerpts in a later version. |
| Observability | Observability shows what happened recently and why something failed. | A portfolio demo must be diagnosable when providers or services are missing. | `backend/app/core/observability.py`, `frontend/app/system/observability/page.tsx` | middleware/request DB logs -> system service -> frontend page | Showing raw JSON or private text | Open `/api/system/observability` and `/system/observability` | I connected request, task, retrieval and provider signals into one reviewable page. | Persist metrics if multi-process production deployment is introduced. |
| Request ID | A request id is a small trace label for API calls. | It lets users connect frontend errors to backend observations. | `backend/app/core/responses.py`, `backend/app/core/observability.py` | middleware -> response envelope/header -> observability buffer | Losing id on error responses | Trigger a 404/500-style API error and inspect envelope/header | I made request IDs visible for both success and error triage. | Add frontend display for request id in technical details when helpful. |
| Retrieval Trace | Retrieval trace summarizes the evidence used for an answer. | RAG quality needs evidence counts, source mix and citation validation state. | `backend/app/services/system_service.py`, `backend/app/schemas/system_schema.py` | `qa_logs` -> recent retrievals -> observability UI | Treating refusals as failures | Inspect `recent_retrievals` and `citation_validation_status` | I exposed retrieval traces without leaking prompts or private source text. | Add latency and token metrics when providers return them safely. |
| Provider Status | Provider status reports configured, demo, not configured or unavailable states. | Real mode must refuse missing LLM/OCR/transcription instead of inventing output. | `scripts/evaluate_providers.py`, `backend/app/services/system_service.py` | settings -> provider adapters -> status/eval report | Printing keys or calling paid APIs in CI | Run `python scripts/evaluate_providers.py --dry-run` | I made provider readiness testable without requiring keys in public CI. | Use `--real-if-configured` only with owned keys. |
| Runtime Error Classification | Error codes categorize failures such as NOT_CONFIGURED or insufficient context. | Users need recovery actions, not stack traces. | `backend/app/core/responses.py`, `docs/v4_4_observability_report.md` | service exception -> error envelope -> `x-error-code` -> UI/report | Exposing raw stack traces | Check error envelopes and `error_categories` | I turned runtime failures into classified signals that can be explained. | Expand Chinese recovery messages for common errors. |
| Optional Provider Evaluation | Optional evaluation can test real providers only when keys exist. | Default CI stays free, while local real-mode validation remains possible. | `scripts/evaluate_providers.py`, `docs/v4_4_provider_eval_report.md` | mode selection -> dry/demo/real-if-configured -> Markdown/JSON output | Failing CI because a key is absent | Compare dry-run vs real-if-configured output | I separated readiness diagnostics from demo RAG scoring. | Add small controlled corpora for real RAG quality later. |
| CI Optional Job | Optional checks should report why they skipped. | A green CI should not imply unavailable browser/provider tests ran. | `.github/workflows/ci.yml`, `scripts/check_all.py` | CI quality job -> check_e2e -> run_demo_e2e -> provider dry-run | Silent skip | Read CI logs for `PLAYWRIGHT_NOT_INSTALLED` or NOT_CONFIGURED | I made optional gates auditable instead of invisible. | Split live E2E into a separate workflow with browser install. |
| Frontend Component Consolidation | Shared UI components keep warnings, citations and technical details consistent. | Repeated ad hoc UI makes demos harder to understand and maintain. | `frontend/components/CitationPanel.tsx`, `frontend/components/ui.tsx` | data -> shared component -> page-specific layout | Raw JSON on primary pages | Run frontend smoke and inspect main pages | I consolidated citation behavior and kept technical details behind focused UI. | Continue extracting large media/code sections into components. |
| Release Quality Gate | A release gate groups compile, tests, frontend build, docs, demo, safety and package checks. | Portfolio releases must be reproducible and safe to share. | `scripts/check_all.py`, `scripts/release.py`, `scripts/check_release.py` | `check_all --full` -> release dry-run -> zip check | Shipping caches, DBs or uploads | Run release dry-run and archive inspection | I treated release packaging as part of the product boundary. | Keep final zip generation after the last doc/log append. |

### Changed Files
- `M` `.github/workflows/ci.yml`
- `M` `.gitignore`
- `M` `README.md`
- `M` `backend/app/api/routes_dashboard.py`
- `M` `backend/app/api/routes_system.py`
- `M` `backend/app/core/config.py`
- `??` `backend/app/core/observability.py`
- `M` `backend/app/core/responses.py`
- `M` `backend/app/main.py`
- `M` `backend/app/schemas/system_schema.py`
- `M` `backend/app/services/system_service.py`
- `??` `backend/tests/test_citation_jump_contracts.py`
- `M` `backend/tests/test_health.py`
- `??` `backend/tests/test_observability.py`
- `M` `backend/tests/test_v3_system_status.py`
- `M` `backend/tests/test_v4_0_portfolio_summary.py`
- `M` `backend/tests/test_v4_3_api_regression.py`
- `??` `backend/tests/test_v4_4_observability.py`
- `M` `docs/architecture.md`
- `M` `docs/assets/demo/README.md`
- `M` `docs/assets/screenshots/README.md`
- `M` `docs/citation_locator.md`
- `M` `docs/demo_mode.md`
- `M` `docs/demo_showcase.md`
- `M` `docs/github_release_checklist.md`
- `M` `docs/local_development.md`
- `M` `docs/observability.md`
- `M` `docs/quickstart.md`
- `M` `docs/rag_evaluation.md`
- `M` `docs/release_process.md`
- `M` `docs/roadmap.md`
- `M` `docs/scripts_reference.md`
- `??` `docs/v4_4_acceptance_report.md`
- `??` `docs/v4_4_browser_e2e_report.md`
- `??` `docs/v4_4_citation_jump_report.md`
- `??` `docs/v4_4_frontend_consolidation_report.md`
- `??` `docs/v4_4_observability_report.md`
- `M` `docs/v4_4_planning.md`
- `??` `docs/v4_4_predevelopment_audit.md`
- `??` `docs/v4_4_provider_eval_report.md`
- `??` `docs/v4_4_quality_gate_report.md`
- `??` `docs/v4_4_release_notes.md`
- `??` `docs/v4_4_test_report.md`
- `M` `docs/versioning.md`
- `M` `frontend/app/code/page.tsx`
- `M` `frontend/app/system/observability/page.tsx`
- `M` `frontend/app/tasks/page.tsx`
- `M` `frontend/components/AppShell.tsx`
- `M` `frontend/components/CitationPanel.tsx`
- `??` `frontend/e2e/citation-jump.spec.ts`
- `??` `frontend/e2e/demo-smoke.spec.ts`
- `??` `frontend/e2e/run-optional-e2e.mjs`
- `??` `frontend/e2e/system-observability.spec.ts`
- `M` `frontend/package-lock.json`
- `M` `frontend/package.json`
- `??` `frontend/playwright.config.ts`
- `M` `frontend/services/api.ts`
- `M` `frontend/tsconfig.json`
- `M` `frontend/types/api.ts`
- `M` `scripts/capture_showcase.py`
- `M` `scripts/check_all.py`
- `??` `scripts/check_e2e.py`
- `M` `scripts/check_readme_assets.py`
- `M` `scripts/check_release.py`
- `M` `scripts/check_version.py`
- `??` `scripts/evaluate_providers.py`
- `M` `scripts/generate_learning_package.py`
- `M` `scripts/release.py`
- `??` `scripts/run_demo_e2e.py`
- `M` `scripts/seed_demo_data.py`
- `M` `scripts/seed_showcase.py`
- `M` `scripts/setup_demo.py`

### Git Summary
```text
.github/workflows/ci.yml                     |  15 +-
 .gitignore                                   |   3 +
 README.md                                    |  20 ++-
 backend/app/api/routes_dashboard.py          |   2 +-
 backend/app/api/routes_system.py             |  35 +++-
 backend/app/core/config.py                   |   4 +-
 backend/app/core/responses.py                |  14 ++
 backend/app/main.py                          |   2 +-
 backend/app/schemas/system_schema.py         |  59 +++++++
 backend/app/services/system_service.py       | 156 +++++++++++++++++-
 backend/tests/test_health.py                 |   4 +-
 backend/tests/test_v3_system_status.py       |   4 +-
 backend/tests/test_v4_0_portfolio_summary.py |   4 +-
 backend/tests/test_v4_3_api_regression.py    |   4 +-
 docs/architecture.md                         |  12 +-
 docs/assets/demo/README.md                   |   4 +-
 docs/assets/screenshots/README.md            |   2 +-
 docs/citation_locator.md                     |   8 +-
 docs/demo_mode.md                            |   5 +-
 docs/demo_showcase.md                        |  10 +-
 docs/github_release_checklist.md             |  10 +-
 docs/local_development.md                    |  15 +-
 docs/observability.md                        |  25 +--
 docs/quickstart.md                           |   8 +-
 docs/rag_evaluation.md                       |   7 +-
 docs/release_process.md                      |  11 +-
 docs/roadmap.md                              |  17 +-
 docs/scripts_reference.md                    |   7 +-
 docs/v4_4_planning.md                        |  11 +-
 docs/versioning.md                           |  10 +-
 frontend/app/code/page.tsx                   |  32 +++-
 frontend/app/system/observability/page.tsx   | 237 +++++++++++++++++++++++----
 frontend/app/tasks/page.tsx                  |   2 +-
 frontend/components/AppShell.tsx             |   2 +-
 frontend/components/CitationPanel.tsx        |  65 +++++---
 frontend/package-lock.json                   |   4 +-
 frontend/package.json                        |   5 +-
 frontend/services/api.ts                     |   2 +
 frontend/tsconfig.json                       |   4 +-
 frontend/types/api.ts                        |  59 +++++++
 scripts/capture_showcase.py                  |   4 +-
 scripts/check_all.py                         |  44 ++++-
 scripts/check_readme_assets.py               |   4 +-
 scripts/check_release.py                     |  15 +-
 scripts/check_version.py                     |   4 +-
 scripts/generate_learning_package.py         |  29 +++-
 scripts/release.py                           |   2 +-
 scripts/seed_demo_data.py                    |   2 +-
 scripts/seed_showcase.py                     |  12 +-
 scripts/setup_demo.py                        |   2 +-
 50 files changed, 851 insertions(+), 167 deletions(-)
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
- `backend/app/api/routes_system.py::@router.get("/observability", response_model=ObservabilitySummary)`
- `backend/app/api/routes_system.py::@router.get("/observability/recent-requests", response_model=list[ObservabilityRequest])`
- `backend/app/api/routes_system.py::@router.get("/observability/recent-tasks", response_model=list[ObservabilityTask])`
- `backend/app/api/routes_system.py::@router.get("/observability/recent-retrievals", response_model=list[ObservabilityRetrieval])`
- `backend/app/api/routes_system.py::@router.get("/observability/provider-status", response_model=list[ObservabilityProviderStatus])`

### Knowledge Topics
#### Citation Deep Links
- Beginner explanation: A citation should take the learner back to the evidence, not just name a file.
- Project usage: Chat citations now carry source_id/document_id and timestamp fields; CitationPanel links to document chunks or media timestamps.
- Code locations: `frontend/components/CitationPanel.tsx`
- Review suggestion: Review citation payloads, URL query parameters, player seek and highlighted transcript chunks.
- Interview expression: I connected RAG citations to frontend routes so audio and video answers can jump to the exact timestamp that supports the answer.

#### Demo-Friendly Frontend
- Beginner explanation: A user-facing OS should explain the next action without exposing raw internal fields on primary screens.
- Project usage: V3.6 improves Upload Center, Task Center and media detail pages with clearer steps, result links, transcript highlighting and keyframe browsing.
- Code locations: `frontend/app/tasks/page.tsx`
- Review suggestion: Review workflow cards, task filters, media player state, responsive layout and progressive disclosure.
- Interview expression: I reshaped the frontend around user workflows: upload, process, inspect evidence, ask questions and turn evidence into learning assets.

#### Release Verification
- Beginner explanation: A release package must be reproducible and must not include dependencies, caches, secrets or user data.
- Project usage: V4.2 keeps release.py exclusion rules and adds full-regression, RAG and demo-readiness checks before release.
- Code locations: `scripts/check_release.py`, `scripts/release.py`
- Review suggestion: Review zip packaging, SHA256 checks, exclusion rules and acceptance reports.
- Interview expression: I treated release packaging as part of the product boundary, verifying that generated archives exclude secrets, databases, uploads and build caches.

#### Portfolio Documentation
- Beginner explanation: A GitHub portfolio project needs docs that help a stranger run, understand and evaluate it.
- Project usage: V4.2 keeps README, demo mode, local development, release, versioning, interview QA and roadmap documents aligned with executable checks.
- Code locations: `docs/demo_mode.md`, `docs/local_development.md`, `docs/quickstart.md`
- Review suggestion: Review README navigation, quickstart commands, demo boundaries and whether planned features are clearly separated.
- Interview expression: I turned the repository from a code dump into a portfolio-ready project with runnable demo docs, interview notes and honest capability boundaries.

#### Demo Reset Workflow
- Beginner explanation: A demo should be repeatable; reset scripts make it easy to recover a clean synthetic showcase state.
- Project usage: V4.2 strengthens demo seed/readiness scripts so the synthetic database proves the source-to-RAG-to-learning walkthrough.
- Code locations: `scripts/seed_demo_data.py`
- Review suggestion: Review path safety checks, synthetic data labels and demo readiness validation.
- Interview expression: I made the demo reproducible by adding a reset workflow that rebuilds only the isolated synthetic database and verifies required records.

#### Roadmap Specifications
- Beginner explanation: Large features should be specified before implementation so docs do not overpromise.
- Project usage: V4.2 records which V4.0/V4.1 capabilities are implemented and which release-readiness gaps remain.
- Code locations: `backend/app/core/observability.py`, `backend/tests/test_observability.py`, `backend/tests/test_v4_4_observability.py`, `docs/observability.md`, `docs/rag_evaluation.md`, `docs/v4_4_observability_report.md`, `frontend/app/system/observability/page.tsx`, `frontend/e2e/system-observability.spec.ts`
- Review suggestion: Review each design doc and mark implemented, requires configuration, demo-only, planned and limitation states.
- Interview expression: I documented the V4.0 architecture direction before coding it, which keeps roadmap claims honest and reviewable.

#### Version Governance
- Beginner explanation: A visible product version must match backend config, frontend package metadata, README badges and CI release commands.
- Project usage: V4.2 updates version consistency checks, health tests, package metadata, README badge and CI release artifact naming.
- Code locations: `frontend/package-lock.json`, `frontend/package.json`, `scripts/check_version.py`
- Review suggestion: Review check_version.py and every version-bearing file after a version bump.
- Interview expression: I treated versioning as a testable contract across backend, frontend, docs and CI instead of a README-only label.

#### Documentation Link Integrity
- Beginner explanation: A portfolio README is only trustworthy if its links and referenced files actually exist.
- Project usage: V4.3 adds check_docs_links.py to validate local README/docs links and Mermaid fences without requiring network access.
- Code locations: `README.md`, `docs/assets/demo/README.md`, `docs/assets/screenshots/README.md`, `docs/demo_showcase.md`, `docs/quickstart.md`
- Review suggestion: Review Markdown parsing, local-path resolution, archive exclusions and failure messages.
- Interview expression: I added a docs link gate so GitHub visitors do not hit broken quickstart, demo, roadmap or release references.

#### README Asset Safety
- Beginner explanation: Screenshots and GIFs should not be referenced until they exist and are safe to publish.
- Project usage: V4.3 adds check_readme_assets.py to verify local README images, required screenshot files and missing demo GIF risks.
- Code locations: `docs/assets/demo/README.md`, `docs/assets/screenshots/README.md`, `scripts/check_readme_assets.py`
- Review suggestion: Review screenshot inventory, local image parsing, demo GIF placeholders and sensitive-data boundaries.
- Interview expression: I made README media part of CI so the portfolio page cannot silently ship broken screenshots or missing demo assets.

#### Quality Gate Orchestration
- Beginner explanation: A release checklist becomes safer when one command can run the same gates consistently.
- Project usage: V4.3 adds check_all.py with quick, demo, release and full modes for compile, tests, frontend, docs, demo, RAG and release checks.
- Code locations: `docs/v4_4_quality_gate_report.md`, `scripts/check_all.py`, `scripts/check_release.py`, `scripts/release.py`
- Review suggestion: Review subprocess orchestration, frontend runtime fallback, isolated demo DB paths and release dry-run integration.
- Interview expression: I grouped the project quality gates into one script with mode-specific scopes, which makes local validation and CI easier to explain and repeat.

#### Runtime Observability
- Beginner explanation: A demo-ready app should show recent requests, tasks, retrieval traces and provider status in a form that helps debugging.
- Project usage: V4.4 adds request-id capture, recent request/task/retrieval/provider endpoints and a data-driven observability page.
- Code locations: `backend/app/core/observability.py`, `backend/tests/test_observability.py`, `backend/tests/test_v4_4_observability.py`, `docs/observability.md`, `docs/v4_4_observability_report.md`, `frontend/app/system/observability/page.tsx`, `frontend/e2e/system-observability.spec.ts`
- Review suggestion: Review request middleware, bounded in-process buffers, DB-backed task/retrieval summaries and frontend error-state handling.
- Interview expression: I added a lightweight observability layer that connects API request IDs, task events, retrieval traces and provider status into a reviewer-friendly runtime page.

#### Optional Browser E2E
- Beginner explanation: Browser tests prove real navigation paths, but CI should not pretend they passed when the browser runtime is missing.
- Project usage: V4.4 ships Playwright config and demo/citation/observability specs plus an optional runner that skips honestly without Playwright or browser binaries.
- Code locations: `docs/v4_4_browser_e2e_report.md`, `frontend/e2e/citation-jump.spec.ts`, `frontend/e2e/demo-smoke.spec.ts`, `frontend/e2e/run-optional-e2e.mjs`, `frontend/e2e/system-observability.spec.ts`, `frontend/playwright.config.ts`, `scripts/check_e2e.py`, `scripts/run_demo_e2e.py`
- Review suggestion: Review Playwright setup, skip semantics, screenshot/trace output paths and how to promote the optional gate to a hard gate in a prepared environment.
- Interview expression: I added browser-level E2E coverage in a way that is runnable when the environment supports it and explicit when it is skipped.

#### Provider Readiness Evaluation
- Beginner explanation: Provider diagnostics should verify configuration and optional real calls without leaking secrets or fabricating outputs.
- Project usage: V4.4 adds evaluate_providers.py with dry-run, demo and real-if-configured modes for LLM, embedding, OCR, vision, transcription and rerank boundaries.
- Code locations: `docs/v4_4_provider_eval_report.md`, `scripts/evaluate_providers.py`
- Review suggestion: Review NOT_CONFIGURED codes, endpoint fingerprinting, no-key default behavior and real-if-configured failure handling.
- Interview expression: I made provider readiness testable without requiring paid keys in CI, while preserving the rule that missing providers refuse instead of creating fake AI results.

### Test Report
```text
# V4.4 Test Report

## Commands Run

This report is updated during V4.4 release closure.

| Command | Status | Notes |
| --- | --- | --- |
| `python -m compileall backend/app scripts` | Passed | Local `.venv` Python |
| `python -m pytest backend/tests/test_v4_4_observability.py backend/tests/test_citation_jump_contracts.py -q` | Passed | 3 tests |
| `python scripts/check_version.py` | Passed | `V4.4 / 4.4.0` |
| `python scripts/evaluate_providers.py --dry-run` | Passed | No external calls |
| `python scripts/check_e2e.py` | Passed | Static scaffold check |
| `python scripts/run_demo_e2e.py` | Skipped | `PLAYWRIGHT_NOT_INSTALLED`; no live browser claim |
| `frontend tsc --noEmit` | Passed | Optional E2E excluded from default app typecheck |
| `frontend next build` | Passed | 28 routes generated |
| `python scripts/seed_demo_data.py --database-path .pytest_tmp/v4_4_demo_showcase.db --reset` | Passed | Synthetic isolated DB |
| `python scripts/check_demo_ready.py --database-path .pytest_tmp/v4_4_demo_showcase.db` | Passed | Required demo tables/statuses present |
| `python scripts/evaluate_rag.py --demo --database-path .pytest_tmp/v4_4_demo_showcase.db` | Passed | Grounded/refusal/citation checks |
| `python scripts/check_full_regression.py --database-path .pytest_tmp/v4_4_demo_showcase.db` | Passed | 67 checks |
| `python scripts/check_secrets.py` | Passed | `findings=0` |
| `python scripts/check_repo_clean.py` | Passed | forbidden tracked files `0` |
| `python scripts/release.py --version V4.4 --dry-run` | Passed | `included_files=324`, no secrets/databases/uploads/cache |

## Pending Full Gates

- Final `python scripts/check_all.py --full` after all V4.4 docs/log append updates.
- Final release build and archive inspection after the last append-only log update.
```

### Build Report
```text
# V4.4 Quality Gate Report

## Scope

V4.4 extends the unified quality gate with observability tests, provider dry-run diagnostics and optional E2E scaffolding checks.

## New Gates

- `python scripts/check_all.py --observability`
- `python scripts/check_all.py --provider-eval`
- `python scripts/check_all.py --e2e`
- `python scripts/check_all.py --full`

## Current Evidence

- `python -m compileall backend/app scripts`: passed.
- Targeted V4.4 backend tests: passed.
- `python scripts/check_version.py`: passed for `V4.4 / 4.4.0`.
- `python scripts/evaluate_providers.py --dry-run`: passed.
- `python scripts/check_e2e.py`: passed.
- `python scripts/run_demo_e2e.py`: skipped honestly because `@playwright/test` is not installed in the current local frontend dependencies.
- Frontend `tsc --noEmit`: passed after excluding optional E2E files from default app typecheck.
- Frontend production build: passed after wrapping `/code` query-param handling in a Suspense boundary.

Final full validation results are recorded in `docs/v4_4_test_report.md` and the append-only delivery logs.
```

### Migration Report
```text
# V4.4 Observability Report

## Scope

V4.4 adds lightweight runtime observability for demo review and local debugging.

## Implemented

- Request ID middleware records recent API requests in a bounded in-process ring buffer.
- Error responses include `x-error-code`.
- System service exposes recent requests, tasks, retrievals, provider status and error categories.
- FastAPI routes:
  - `GET /api/system/observability`
  - `GET /api/system/observability/recent-requests`
  - `GET /api/system/observability/recent-tasks`
  - `GET /api/system/observability/recent-retrievals`
  - `GET /api/system/observability/provider-status`
- Frontend page: `/system/observability`

## Backend Contract Tests

- `backend/tests/test_v4_4_observability.py`

## Limit

The request buffer is process-local and resets on API restart. Long-term metrics storage and distributed tracing remain future work.
```
