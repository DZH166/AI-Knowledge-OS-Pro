# V4.2 RAG Quality Report

Generated at: 2026-07-03 Asia/Shanghai

## Scope

V4.2 strengthens deterministic RAG quality gates without pretending synthetic demo data measures real LLM quality.

## Commands

```powershell
python scripts/seed_demo_data.py --database-path .pytest_tmp/v4_2_demo_showcase.db --reset
python scripts/evaluate_rag.py --demo --database-path .pytest_tmp/v4_2_demo_showcase.db
python -m pytest backend/tests/test_v4_0_hybrid_retrieval.py backend/tests/test_v3_9_rag_evaluation.py
```

## Demo Evaluation Result

- `qa_logs=2`
- `grounded_answers=1`
- `refusal_answers=1`
- `retrieval_hit_rate=0.50`
- `citations=1`
- `valid_citations=1`
- `used_citations=1`
- `related_chunks=1`
- `timestamp_citations=1`
- `multimodal_chunks=9`
- `citation_locators=9`
- `valid_locators=9`
- `code_locators=2`
- `result=passed`

## What Is Verified

- Grounded demo answers contain citation ids, used citation ids and related chunks.
- Used citations appear in the answer text.
- Citation `chunk_id` values resolve to persisted `CitationLocator` rows.
- Audio/video citations include integer `start_ms` and `end_ms`.
- Code-repository evidence includes file/line locators.
- Multimodal chunk locator JSON is valid for image, audio, video and code source types.
- Insufficient-context questions refuse without fabricated citations.
- Hybrid retrieval fallback is covered by backend tests for dense miss plus keyword recall.
- Rerank scores are not faked when a real rerank provider is absent.

## Honest Boundary

This report validates deterministic plumbing and regression protection. It does not score real model answer quality, semantic relevance across an external corpus or provider latency under production load.
