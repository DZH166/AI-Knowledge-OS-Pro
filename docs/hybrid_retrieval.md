# Hybrid Retrieval

Hybrid retrieval is planned for V4.0. The current V3.8 baseline mainly relies on semantic retrieval through embeddings and Qdrant when providers are configured.

## Target Design

```text
User query
-> vector retrieval
-> keyword / metadata retrieval
-> merge and deduplicate candidates
-> optional rerank
-> citation validation
-> answer generation
```

## Why It Is Needed

- Vector search can miss exact filenames, symbols or error codes.
- Keyword search can miss paraphrased concepts.
- Hybrid retrieval can improve recall for technical learning material.

## Planned Fallbacks

- If embedding provider is missing, refuse real semantic indexing instead of faking vectors.
- If rerank provider is missing, use deterministic score merging and mark rerank as not configured.
- If no evidence is found, return a refusal rather than a citation-free answer.

## Current Status

- Dedicated hybrid retrieval implementation: planned.
- Dedicated tests: planned.
- Documentation: this design note.
