# Provider Diagnostics

Provider diagnostics help users understand why a capability is unavailable and what to configure next.

## Implemented In V3.9

- System page capability setup guide.
- Copyable example environment-variable lines with placeholder values only.
- Clear impact statements for Redis/Worker, Qdrant, LLM, Embedding, OCR/Vision and Speech-to-Text.
- Real-mode boundary reminders: missing providers must return NOT_CONFIGURED-style errors and must not create fake OCR, fake transcripts or fake answers.
- Frontend smoke check requires the System page to keep the provider guide and NOT_CONFIGURED boundary text.

## Provider Groups

| Group | Enables | Example variable |
| --- | --- | --- |
| Redis / Worker | Task Center processing, retry and cancel | `REDIS_URL=redis://localhost:6379/0` |
| Qdrant | Vector indexing and retrieval | `QDRANT_URL=http://localhost:6333` |
| LLM Provider | Real answers and interview expressions | `LLM_API_KEY=<your-llm-api-key>` |
| Embedding Provider | Real semantic indexing | `EMBEDDING_API_KEY=<your-embedding-api-key>` |
| OCR / Vision Provider | Image OCR and visual understanding | `OCR_API_KEY=<your-ocr-api-key>` |
| Speech-to-Text Provider | Audio/video transcripts and timestamp citations | `TRANSCRIPTION_API_KEY=<your-transcription-api-key>` |

## Safety Rules

- Examples must use placeholder values only.
- Real keys must stay in ignored `.env` files or secret managers.
- Demo mode can show workflow state, but cannot pretend to run providers.
- Provider errors should be actionable for users and specific enough for debugging.

## Current Limitations

- The UI shows setup guidance but does not validate every provider-specific URL/model combination.
- Real provider quality and latency metrics are planned for later V4.0 observability work.
