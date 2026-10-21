# Citation Flow

## Implemented Flow

```text
Chunk or multimodal evidence
-> citation metadata
-> chat response citation
-> frontend citation panel
-> route to document, media source or timestamp
```

## Current Citation Targets

- Documents: document detail and chunk context.
- Images: media source detail.
- Audio: media source detail with transcript timestamp.
- Video: media source detail with transcript timestamp and keyframe context.

## Safety Rule

If evidence cannot be located, the answer should not pretend a citation exists.

## Planned V4.0 Work

- Code citations.
- Citation validation report in RAG evaluation.
- Better UI highlighting after timestamp jumps.
