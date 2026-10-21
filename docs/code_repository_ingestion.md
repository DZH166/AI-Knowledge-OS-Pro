# Code Repository Ingestion

Code repository ingestion is in V4.0 incremental implementation. The current branch supports local repository scanning, safe include/exclude rules, code file chunking, file/line locators, Qdrant indexing through the real embedding provider and code-aware RAG citations.

## Target Capability

- Import a local Git repository path.
- Scan files with safe include/exclude rules.
- Parse code files into chunks.
- Preserve path, line range and symbol locators.
- Index chunks for code-aware RAG.
- Generate project review, resume and interview material from real code evidence.

## Implemented API

- `POST /api/code-repositories/ingest-local`
- `GET /api/code-repositories`
- `GET /api/code-repositories/{source_id}`

The implementation reuses the multimodal `Source`, `SourceRevision`, `MultimodalChunk`, `CitationLocator` and `IndexRevision` tables instead of adding a new migration in this pass:

- `Source.source_type = code_repository`
- `MultimodalChunk.modality = code_file`
- `locator_json` stores `file_path`, `line_start`, `line_end`, `symbol_name` and optional `github_url`.

## Target Locator

```text
file_path
line_start
line_end
symbol_name
github_url
```

## Safety Rules

- Do not ingest `.env`, keys, databases, uploads, logs or build outputs.
- Do not ingest `.git`, `node_modules`, `.next`, caches or virtual environments.
- Do not ingest binary/media files or oversized files.
- Keep repository ingestion local unless the user explicitly configures a remote source.
- Do not fabricate code explanations without retrieved evidence.
- Missing embedding provider returns `EMBEDDING_NOT_CONFIGURED`; no fake vectors are generated.

## Current Status

- Product capability: implemented as a safe local repository snapshot.
- API routes: implemented in `backend/app/api/routes_code_repositories.py`.
- Service: implemented in `backend/app/services/code_repository_service.py`.
- Frontend page: implemented at `/code`.
- Tests: `backend/tests/test_v4_0_code_repository_ingestion.py`.
- Current limitations: no remote clone/sync, no full AST symbol graph, no commit hash capture and no provider-backed project review generation yet.
