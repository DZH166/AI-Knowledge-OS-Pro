# V4.7 Project Structure Visual Redesign Report

The `/learning/project-structure` page was redesigned from a text-heavy explanation into an in-app learning map.

## Delivered

- First screen mental model with three closed loops: source intake, question/RAG, learning archive.
- Module relationship map for frontend, backend, evidence storage and provider boundaries.
- Route-to-API-to-service-to-model mapping for common user actions.
- RAG evidence flow with chunk, embedding, Qdrant, citation and jump steps.
- Multimodal processing flow for image OCR, audio transcription, video transcription and keyframes.
- Learning stepper mapping pages, code files, docs and interview expression.
- Interview mode with 60-second, 3-minute and technical follow-up talking tracks.

## Boundaries

- The page is static educational UI and does not call providers.
- It does not invent runtime metrics.
- It links only to existing in-app routes.
