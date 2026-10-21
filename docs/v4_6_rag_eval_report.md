# V4.6 RAG Evaluation Evidence Report

## Scope

This is a V4.6 preparation increment on top of the stable V4.5 baseline. It improves the demo-safe RAG evaluation evidence without changing the visible product version, database schema or provider behavior.

## Delivered

- `scripts/evaluate_rag.py --demo` now accepts `--output <path>` to write a JSON evidence report.
- The report includes aggregate counts, citation source-type coverage, multimodal source-type coverage, locator-shape coverage and per-question traces for grounded and insufficient-context QA logs.
- `scripts/check_all.py --demo` writes `.pytest_tmp/v4_5_rag_eval_report.json` during the demo quality gate.
- `backend/tests/test_v3_9_rag_evaluation.py` verifies the JSON report shape and keeps the demo-only boundary explicit.

## Boundary

The report proves deterministic seeded retrieval, citation and locator plumbing. It does not claim real LLM answer quality, real OCR quality, real transcription quality or provider-backed evaluation. Real provider paths remain governed by explicit configuration and NOT_CONFIGURED-style refusal.

## Verification

```text
python -m pytest backend/tests/test_v3_9_rag_evaluation.py
2 passed

python scripts/seed_demo_data.py --database-path .pytest_tmp/v4_6_rag_eval_showcase.db --reset
python scripts/evaluate_rag.py --demo --database-path .pytest_tmp/v4_6_rag_eval_showcase.db --output .pytest_tmp/v4_6_rag_eval_report.json
result=passed
locator_shapes={"code_file_line": 2, "image_region": 1, "media_timestamp": 6}

python scripts/check_all.py --demo
result=passed

python -m compileall backend/app scripts
result=passed

python -m pytest
75 passed, 23 warnings

python scripts/check_all.py --quick
result=passed

python scripts/check_all.py --release
included_files=357
found_secrets=no
found_database=no
found_uploads=no
found_cache=no
result=passed
```
