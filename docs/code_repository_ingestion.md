# Code Repository Ingestion

Code repository ingestion is planned for V4.0. It is not implemented in the current V3.8 baseline.

## Target Capability

- Import a local Git repository.
- Scan files with safe include/exclude rules.
- Parse code files into chunks.
- Preserve path, line range and symbol locators.
- Index chunks for code-aware RAG.
- Generate project review, resume and interview material from real code evidence.

## Target Data Model

Potential models:

- `CodeRepository`
- `CodeFile`
- `CodeChunk`
- `CodeSymbol`

## Target Locator

```text
file_path
line_start
line_end
symbol_name
commit_sha
```

## Safety Rules

- Do not ingest `.env`, keys, databases, uploads, logs or build outputs.
- Keep repository ingestion local unless the user explicitly configures a remote source.
- Do not fabricate code explanations without retrieved evidence.

## Current Status

- Product capability: planned.
- API routes: missing.
- Frontend page: missing.
- Tests: missing.
