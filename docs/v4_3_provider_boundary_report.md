# V4.3 Provider Boundary Report

Generated at: 2026-07-04 Asia/Shanghai

## Scope

V4.3 locks the real-mode boundary with regression tests. Missing provider credentials must return explicit NOT_CONFIGURED-style errors and must not write fake OCR, fake vision descriptions, fake transcripts, fake answers or fake rerank scores.

## Tests Added

- `backend/tests/test_provider_boundaries.py`
- V4.3 API regression coverage for chat provider refusal in `backend/tests/test_v4_3_api_regression.py`

## Covered Boundaries

| Capability | Missing-provider behavior |
| --- | --- |
| LLM answer generation | `LLM_NOT_CONFIGURED` |
| Embeddings/indexing | `EMBEDDING_NOT_CONFIGURED` |
| Image OCR | `OCR_NOT_CONFIGURED` |
| Vision description | `VISION_DESCRIPTION_NOT_CONFIGURED` |
| Audio/video transcription | `TRANSCRIPTION_NOT_CONFIGURED` |
| Rerank | Disabled provider; no fake rerank scores |
| Qdrant unavailable | Reported as unavailable by system status; semantic retrieval cannot be trusted |
| Redis unavailable | Reported as unavailable; background task dispatch cannot be trusted |
| FFmpeg unavailable | Video/keyframe operations fail explicitly through video tooling errors; no fake keyframes are claimed |

## Verification

Targeted V4.3 tests:

```text
7 passed, 2 warnings
```

Full backend suite:

```text
70 passed, 9 warnings
```

## Boundary

The warning about Qdrant server version is an environment/service availability warning during local tests. It does not indicate fake provider output; tests still assert explicit refusal paths.
