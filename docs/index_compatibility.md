# Index Compatibility

Embedding vectors from different providers, models or dimensions should not be mixed in one retrieval flow.

V2 stores these fields on each indexed document:
- `embedding_provider`
- `embedding_model`
- `embedding_dimensions`
- `embedding_fingerprint`
- `index_version`

The current fingerprint is built from:
- provider name
- safe hash of embedding base URL host
- embedding model
- dimensions
- index version
- normalization strategy

Before answering, RAG checks all ready documents in the selected knowledge space. If any ready document does not match the current fingerprint and index version, the API returns `INDEX_INCOMPATIBLE` and asks the user to rebuild the index.

V3.2 also stores these compatibility fields on `IndexRevision` for multimodal sources such as image OCR chunks:
- `embedding_provider`
- `embedding_model`
- `embedding_dimensions`
- `embedding_fingerprint`
- `index_version`
- `qdrant_collection`

Before answering, RAG checks both ready documents and active multimodal index revisions in the selected knowledge space. A mismatch in either path returns `INDEX_INCOMPATIBLE`.

When changing embedding model, dimensions, provider or index version, run document reindex.
