# V4.3 Demo Walkthrough Validation

Generated at: 2026-07-04 Asia/Shanghai

## Scope

The V4.3 demo walkthrough uses an isolated synthetic database at `.pytest_tmp/v4_3_demo_showcase.db`. It does not read user databases, uploads or private files. The data is labelled synthetic and is not presented as real provider output.

## Commands

```powershell
python scripts/seed_demo_data.py --database-path .pytest_tmp/v4_3_demo_showcase.db --reset
python scripts/check_demo_ready.py --database-path .pytest_tmp/v4_3_demo_showcase.db
python scripts/evaluate_rag.py --demo --database-path .pytest_tmp/v4_3_demo_showcase.db
python scripts/check_full_regression.py --database-path .pytest_tmp/v4_3_demo_showcase.db
```

## Result

Passed.

## Evidence Counts

- `knowledge_spaces=1`
- `documents=2`
- `sources=4`
- `source_types=audio,code_repository,image,video`
- `multimodal_chunks=9`
- `citation_locators=9`
- `transcript_segments=6`
- `visual_frames=3`
- `media_assets=6`
- `ingestion_jobs=4`
- `job_statuses=completed,failed,running`
- `qa_logs=2`
- `qa_statuses=grounded,insufficient_context`
- `learning_cards=3`
- `knowledge_points=3`
- `quiz_questions=3`
- `learning_notes=1`

## RAG Demo Evaluation

- `grounded_answers=1`
- `refusal_answers=1`
- `citations=1`
- `valid_citations=1`
- `used_citations=1`
- `timestamp_citations=1`
- `code_locators=2`
- `result=passed`

## Boundary

Demo RAG evaluation checks deterministic seeded evidence, refusal behavior and citation/locator plumbing. It does not measure real LLM answer quality and does not generate fake OCR, transcription or provider-backed answers.
