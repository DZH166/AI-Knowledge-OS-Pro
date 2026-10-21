# Security Policy

## Supported version

Security fixes are maintained for the current `V3.6 / 3.6.0` line.

## Reporting a vulnerability

Use GitHub private vulnerability reporting:

`https://github.com/DZH166/AI-Knowledge-OS-Pro/security/advisories/new`

Do not open a public issue for leaked credentials, path traversal, arbitrary file access, prompt-injection data exposure, provider-token exposure, unsafe archive contents, or authorization defects.

Include the affected version, reproduction steps, impact, and a sanitized proof of concept. Never attach real API keys, private knowledge-base documents, SQLite databases, uploads, transcripts, or logs containing personal data.

## Security boundaries

- Real mode refuses model-dependent work when provider credentials are absent.
- API keys are loaded from ignored environment files and must never be committed.
- Release archives exclude secrets, databases, uploads, logs, dependencies, caches and frontend build output.
- Media and document filenames are treated as untrusted input.
- RAG citations and learning artifacts must remain traceable to persisted source evidence.
