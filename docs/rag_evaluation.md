# RAG Evaluation

RAG evaluation is a release-readiness gate. The current baseline includes a demo-safe evaluator at `scripts/evaluate_rag.py`, targeted backend tests for hybrid retrieval fallback, citation-jump contract tests, and V4.4 provider readiness checks that remain separate from RAG quality claims.

## Target Evaluation Inputs

- Demo-safe question set.
- Expected evidence identifiers.
- Expected citation types.
- Provider configuration status.
- Retrieval settings such as `top_k`.

## Target Metrics

- Retrieval hit rate.
- Citation presence.
- Citation validity.
- Refusal correctness when source evidence is insufficient.
- Multimodal locator validity for image, audio, video and code-repository evidence.
- Hybrid retrieval fallback coverage.
- Latency.
- Error code clarity.
- Citation jump readiness for document, media and code locators.

## Demo Mode Rule

Demo evaluation may validate deterministic seeded records and citation plumbing. It must not claim synthetic demo answers measure real LLM quality.

## Implemented Demo Script

```powershell
python scripts/evaluate_rag.py --demo
```

The script checks deterministic seeded evidence and citation plumbing:

- demo QA logs exist;
- grounded answers and insufficient-context refusals both exist;
- citation ids match used citation ids;
- citations point to existing `CitationLocator` rows;
- related chunks are present;
- at least one audio/video timestamp citation exists;
- code-repository file/line locators exist;
- multimodal chunks and citation locators contain valid source-specific locator JSON.

It returns a non-zero exit code when required checks fail.

## Current Status

- Demo evidence-chain evaluation implemented and strengthened in V4.2.
- Backend CI seeds demo data and runs demo readiness, RAG evaluation and full regression checks.
- Hybrid retrieval tests cover keyword fallback when dense search misses and ensure rerank scores are not faked.
- V4.4 adds citation-jump contracts and runtime observability snapshots for recent retrievals.
- `scripts/evaluate_providers.py --dry-run` reports provider readiness without calling external services.
- Real provider quality scoring remains optional through `scripts/evaluate_providers.py --real-if-configured`; default CI does not require keys.
