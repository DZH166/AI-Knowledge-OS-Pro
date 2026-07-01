# RAG Evaluation

RAG evaluation is a V3.9/V4.0 quality gate. The current baseline does not yet include `scripts/evaluate_rag.py`.

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

## Planned Script

```powershell
python scripts/evaluate_rag.py --demo
```

The script should produce a readable report and return a non-zero exit code when required checks fail.

## Current Status

- Evaluation design documented.
- Script implementation pending.
- CI integration pending after the script exists.
