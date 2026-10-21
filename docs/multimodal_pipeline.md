# Multimodal Pipeline

## Implemented Source Types

- Documents: text, markdown and PDF ingestion.
- Images: upload, metadata and optional provider-backed OCR.
- Audio: upload, duration metadata and optional provider-backed transcription.
- Video: upload, metadata, audio extraction path, transcription path and keyframe extraction.

## Shared Data Concepts

- `Source`
- `MediaAsset`
- `TranscriptSegment`
- `VisualFrame`
- `MultimodalChunk`
- `CitationLocator`
- `IngestionJob`
- `JobEvent`

## Real Mode Rules

- No fake OCR.
- No fake transcripts.
- No fake keyframes.
- No fake model answers.
- Missing providers return explicit configuration errors.

## Planned V4.0 Work

- Stronger media task UX validation.
- Better media pipeline documentation.
- More browser-level smoke coverage for timestamp jumps.
