# GitHub Demo Showcase

This guide presents AI Knowledge OS Pro V4.4 as a coherent product workflow rather than a collection of isolated pages.

## Demo data policy

- Use only synthetic or public sample content.
- Never capture `.env` values, API keys, local filesystem paths, private documents, databases or personal transcripts.
- Keep `DEMO_MODE=true` visibly labelled when provider-backed features are not configured.
- Do not imply that OCR, transcription or visual analysis ran successfully unless a real provider produced the stored result.

## Recommended walkthrough

1. **Dashboard**: introduce the current version, knowledge-space counts and next learning action.
2. **Upload Center**: show separate document, image, audio, video and code-repository workflows and their capability states.
3. **Task Center**: show durable progress, stages, retry/cancel controls and result links.
4. **Media Library**: compare source types, processing status and available evidence.
5. **Video Detail**: click a keyframe or transcript segment and verify player seek/highlight behavior.
6. **Knowledge Chat**: ask a grounded question, open a document/media/code citation and show insufficient-context refusal behavior.
7. **Learning Archive**: convert source evidence into a knowledge point, card, quiz, note or interview expression.
8. **System Status**: finish with provider, Redis, Worker and Qdrant diagnostics.

## Reproducible local showcase

Create an isolated synthetic database. The script refuses filenames that do not contain `showcase` and never touches the normal application database.

```powershell
python scripts/seed_showcase.py --reset
$env:DATABASE_URL="sqlite:///C:/absolute/path/to/backend/data/showcase.db"
$env:DEMO_MODE="true"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start the frontend with `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`, then follow the walkthrough above.

Capture the seven checked-in screenshots with:

```powershell
python scripts/capture_showcase.py --base-url http://127.0.0.1:3000
```

The capture script waits for page-specific data, rejects pages containing `Failed to fetch`, and rejects visually blank screenshots.

## Screenshot inventory

| File | Route | Evidence shown |
| --- | --- | --- |
| `docs/assets/screenshots/dashboard.png` | `/dashboard` | Product identity, version and learning overview |
| `docs/assets/screenshots/upload-center.png` | `/upload` | Four source types and real processing steps |
| `docs/assets/screenshots/knowledge-chat.png` | `/chat` | RAG answer, validated citations and source navigation |
| `docs/assets/screenshots/media-library.png` | `/media` | Image/audio/video source governance |
| `docs/assets/screenshots/video-detail.png` | `/media/sources/{id}` | Player, timestamped transcript and keyframes |
| `docs/assets/screenshots/learning-archive.png` | `/learning` | Version package and source-derived learning assets |
| `docs/assets/screenshots/task-center.png` | `/tasks` | Job progress, stage events and recovery actions |

## Capture standard

- Desktop viewport: `1440 x 960`.
- PNG format, no browser chrome, no cropped controls.
- Keep text readable at GitHub README width.
- Use the same synthetic workspace across all screenshots.
- Re-capture after material layout or workflow changes.

## V4.4 one-command preparation

V4.4 keeps setup/reset scripts that keep demo data isolated from normal application data and adds docs/readme/release, provider dry-run, observability and optional E2E quality gates:

```powershell
python scripts/setup_demo.py --reset
```

The script starts Redis/Qdrant through Docker Compose, seeds `backend/data/demo_showcase.db`, validates required demo tables and prints the exact API/frontend commands. Use `--skip-docker` when services are already running.

Synthetic demo records include a knowledge space, documents, image/audio/video/code sources, task records, grounded and refusal Q&A, learning cards and a learning archive. They are labelled as demo/showcase data and must not be described as real provider outputs.

Run the V4.4 regression checks after seeding:

```powershell
python scripts/check_demo_ready.py --database-path backend/data/demo_showcase.db
python scripts/evaluate_rag.py --demo --database-path backend/data/demo_showcase.db
python scripts/check_full_regression.py --database-path backend/data/demo_showcase.db
python scripts/evaluate_providers.py --dry-run
python scripts/check_e2e.py
```
