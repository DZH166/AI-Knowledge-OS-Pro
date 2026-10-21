# RAG Evaluation

RAG evaluation is a V4.2 release-readiness gate. The current baseline includes a demo-safe evaluator at `scripts/evaluate_rag.py` and targeted backend tests for hybrid retrieval fallback.

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
- Real provider quality evaluation remains planned.
