# RAG Evaluation

RAG evaluation is a V3.9/V4.0 quality gate. The current baseline includes a demo-safe evaluator at `scripts/evaluate_rag.py`.

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
- Refusal correctness when providers are missing.
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
- answers are marked grounded;
- citation ids match used citation ids;
- related chunks are present;
- at least one audio/video timestamp citation exists;
- multimodal chunks and citation locators exist.

It returns a non-zero exit code when required checks fail.

## Current Status

- Demo evidence-chain evaluation implemented.
- Backend CI seeds demo data and runs the demo evaluator.
- V4.0 hybrid retrieval tests cover keyword fallback when dense search misses and ensure rerank scores are not faked.
- Real provider quality evaluation remains planned.
