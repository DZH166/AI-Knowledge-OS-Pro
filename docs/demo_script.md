# V3.7 60-Second Demo Script

This script is designed for a short portfolio walkthrough. Use the synthetic demo database created by `scripts/setup_demo.py` or `scripts/seed_demo_data.py`.

## 0-10s: Dashboard

Open `http://localhost:3000/dashboard`. Explain that AI Knowledge OS Pro is a personal multimodal knowledge OS for AI application learners: project sources become searchable evidence, RAG answers, tasks and learning archives.

## 10-18s: System Status

Open `/system`. Point out the capability matrix:

- Document parsing is directly usable.
- Redis/Qdrant/Worker are local services.
- LLM, Embedding, OCR and Transcription require real providers.
- Demo data is clearly synthetic and does not pretend provider work happened.

## 18-26s: Upload A Source

Open `/upload`. Show the four intake tracks: documents, images, audio and video. Mention that provider-backed work is queued as durable tasks and missing providers return NOT_CONFIGURED errors.

## 26-34s: Task Progress

Open `/tasks`. Show active/completed/failed media jobs, stage events, retry/cancel controls and result links.

## 34-43s: Ask A Question

Open `/chat`. Ask a short question about traceable multimodal RAG. Explain that grounded answers keep validated citations instead of inventing sources.

## 43-50s: Click Evidence

Open a citation or media source. For video/audio, jump to a timestamp and show transcript highlighting; for documents, jump to the relevant chunk.

## 50-56s: Create Learning Material

Open a media or document source and generate/source learning material. Emphasize that learning cards and notes are derived from persisted chunks, not empty media.

## 56-60s: Learning Archive

Open `/learning`. Close by showing version records, knowledge points, cards, notes and interview-ready expression.

## Recording Notes

- Keep `DEMO_MODE=true` visible if using demo data.
- Do not show `.env`, API keys, local private files, raw uploads or databases.
- Do not claim real OCR/transcription/LLM results unless a real provider was configured and used.
