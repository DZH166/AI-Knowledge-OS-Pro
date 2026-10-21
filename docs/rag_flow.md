# RAG Flow

## Implemented Flow

```text
Source upload
-> parsing / media extraction
-> chunks or multimodal chunks
-> embedding provider
-> Qdrant index
-> retrieval
-> prompt construction
-> LLM provider
-> answer with citations
```

## Provider Boundary

- Missing embedding provider blocks real semantic indexing.
- Missing LLM provider blocks real generated answers.
- Real mode must refuse instead of fabricating an answer.

## Citation Boundary

RAG answers should cite stored evidence:

- Document chunks.
- Image source details.
- Audio transcript timestamps.
- Video transcript timestamps and frame locators.

## Planned V4.0 Work

- Dedicated RAG evaluation script.
- Hybrid retrieval.
- Rerank adapter with explicit fallback.
- Citation validation report for evaluation runs.
