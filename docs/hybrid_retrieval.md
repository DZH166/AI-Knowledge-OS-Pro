# Hybrid Retrieval

Hybrid retrieval is in V4.0 incremental implementation. The current branch now uses a lightweight hybrid retriever inside `RAGService`: dense vector retrieval still comes from Qdrant, while keyword recall scans already-indexed SQLite document chunks and active multimodal chunks. Results are fused deterministically, and optional rerank degrades without fake scores when no rerank provider is configured.

## Current Design

```text
User query
-> embedding query vector
-> dense retrieval from Qdrant
-> keyword retrieval from ready document chunks and active multimodal chunks
-> merge and deduplicate candidates
-> deterministic score fusion
-> optional rerank provider
-> citation validation
-> answer generation
```

## Why It Is Needed

- Vector search can miss exact filenames, symbols or error codes.
- Keyword search can miss paraphrased concepts.
- Hybrid retrieval can improve recall for technical learning material.

## Implemented Result Fields

Each fused retrieval result carries:

- `source_id`
- `chunk_id`
- `modality`
- `locator`
- `dense_score`
- `keyword_score`
- `rerank_score`
- `final_score`
- `reason`
- `citation_ready`

`Citation` and `RelatedChunk` responses expose the trace fields as optional values. Main UI can keep these in technical details rather than forcing raw debug payloads into ordinary views.

## Fallbacks

- If embedding provider is missing, refuse real semantic indexing instead of faking vectors.
- If rerank provider is missing, use deterministic score merging and mark rerank as not configured.
- If no evidence is found, return a refusal rather than a citation-free answer.

## Current Status

- Dedicated hybrid retrieval implementation: `backend/app/services/hybrid_retriever.py`.
- Rerank adapter boundary: `backend/app/services/rerank_provider.py`.
- RAG integration: `backend/app/services/rag_service.py`.
- Tests: `backend/tests/test_v4_0_hybrid_retrieval.py`.
- Current keyword path is a lightweight SQLite scan, not a full BM25/FTS5 index.
- Rerank provider is intentionally disabled until a real provider adapter is configured; `rerank_score` remains `null` instead of using fabricated scores.
