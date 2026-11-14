# RAG Evaluation

RAG evaluation is a release-readiness gate. The current baseline includes a demo-safe evaluator at `scripts/evaluate_rag.py`, targeted backend tests for hybrid retrieval fallback, citation-jump contract tests, V4.5 provider readiness checks and strict live demo E2E that remain separate from RAG quality claims.

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

To write a machine-readable evidence report:

```powershell
python scripts/evaluate_rag.py --demo --output .pytest_tmp/rag_eval_report.json
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

The optional JSON report includes:

- aggregate summary counts;
- citation source type coverage;
- multimodal source type coverage;
- locator shape coverage such as media timestamps and code file/line references;
- per-question traces for grounded and insufficient-context answers;
- the explicit boundary that demo evaluation does not measure real LLM quality.

It returns a non-zero exit code when required checks fail.

## Current Status

- Demo evidence-chain evaluation implemented and strengthened in V4.2.
- V4.6 preparation adds optional JSON evidence output and wires `check_all --demo` to write `.pytest_tmp/v4_5_rag_eval_report.json`.
- Backend CI seeds demo data and runs demo readiness, RAG evaluation and full regression checks.
- Hybrid retrieval tests cover keyword fallback when dense search misses and ensure rerank scores are not faked.
- V4.4 added citation-jump contracts and runtime observability snapshots for recent retrievals.
- V4.5 validates the seeded chat and citation jump journey in a real browser through `scripts/run_demo_e2e.py --strict`.
- `scripts/evaluate_providers.py --dry-run` reports provider readiness without calling external services.
- Real provider quality scoring remains optional through `scripts/evaluate_providers.py --real-if-configured`; default CI does not require keys.
- V5.13 reran the demo evidence-chain evaluator after the storage/chat changes: `result=passed`, with 1 grounded answer, 1 refusal, 1 valid citation and 9 valid locators. The fixed 60-case Agent matrix also stayed at 60/60 with all hard gates true.
- Short pronoun follow-ups in chat sessions now pass a context-expanded retrieval query while answering, storing and citing the original question. This is a retrieval aid, not synonym inference; it is covered by public session tests.

默认 `--demo` 会在临时目录重新 seed，避免运行态聊天记录污染评测；`--database-path` 用于显式检查某个数据库。
