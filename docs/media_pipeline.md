# Media Pipeline

The media pipeline describes how images, audio and video become searchable evidence.

## Implemented

- Image upload and metadata.
- Optional provider-backed OCR.
- Audio upload and duration metadata.
- Optional provider-backed audio transcription.
- Video upload with duration/dimensions/audio metadata.
- Video transcription path through extracted audio.
- Keyframe extraction and frame records.
- Media tasks shown through the task center model.

## Shared Flow

```text
Upload
-> Source
-> MediaAsset
-> task job
-> OCR/transcript/keyframes
-> MultimodalChunk
-> CitationLocator
-> RAG and learning artifacts
```

## Provider Rules

- Missing OCR provider: explicit refusal.
- Missing transcription provider: explicit refusal.
- No fake subtitles, fake OCR or fake keyframes.

## Current Limitations

- Browser smoke coverage for every media flow is still limited.
- V4.0 should improve task logs, retry clarity and citation jump validation.
