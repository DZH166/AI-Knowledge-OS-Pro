# V4.4 Citation Jump Report

## Scope

V4.4 validates citation deep-link contracts for document, image, audio, video and code evidence.

## Implemented

- `frontend/components/CitationPanel.tsx` exports citation URL construction for document, media and code locators.
- Document citations link to `/documents/{document_id}` with page, heading and chunk query parameters.
- Media citations link to `/media/sources/{source_id}` with timestamp and chunk query parameters.
- Code citations link to `/code` with file and line query parameters.
- Missing locators show a friendly fallback instead of crashing.

## Backend Contract Tests

- `backend/tests/test_citation_jump_contracts.py`

## Status

Targeted citation contract tests passed during V4.4 implementation. Full-suite status is recorded in `docs/v4_4_test_report.md`.
