# RAG Pipeline

## Ingestion

### Documents

1. Validate extension and upload size.
2. Save the original file.
3. Compute SHA256 and reject duplicates inside the same knowledge space.
4. Create an ingestion job.
5. Parse txt/md/pdf into text.
6. Split text into chunks with overlap.
7. Generate embeddings in batches.
8. Upsert vectors into Qdrant with payload metadata.
9. Save chunk point ids and document embedding fingerprint.

### Images

1. Upload png/jpg/jpeg/webp/bmp into a knowledge space.
2. Save the original image and inspect real width, height and format with Pillow.
3. Store `Source`, `SourceRevision` and `MediaAsset`.
4. If OCR is not configured, keep `ocr_status=not_configured` and do not generate fake text.
5. If OCR is configured, call the real OCR provider.
6. Save OCR text into `MultimodalChunk` with image locator metadata.
7. Create `CitationLocator` for the image source.
8. Embed OCR chunks and upsert them into Qdrant so Chat can cite image-derived text.

### Audio

1. Validate mp3/wav/m4a, size, MIME type and duplicate SHA256.
2. Read real duration with mutagen and save Source/MediaAsset metadata.
3. Call a configured real transcription provider; refuse with `TRANSCRIPTION_NOT_CONFIGURED` when absent.
4. Save provider segments as `TranscriptSegment` with start/end milliseconds and language.
5. Create timestamped `MultimodalChunk` and `CitationLocator` records.
6. Embed transcript chunks and upsert timestamp payloads into Qdrant.
7. Return `start_ms`/`end_ms` in Chat citations and show timestamps in the citation panel.

### Video

1. Validate mp4/mov, size, MIME type and duplicate SHA256.
2. Read real duration, width, height and audio-track presence with FFmpeg/ffprobe.
3. Save original video as `Source`, `SourceRevision` and `MediaAsset`.
4. Extract at least one real keyframe and save it as `VisualFrame` and keyframe `MediaAsset`.
5. Refuse transcription with `TRANSCRIPTION_NOT_CONFIGURED` when no real provider key is configured.
6. Extract a WAV audio track with FFmpeg and call the real transcription provider.
7. Save timestamped provider segments as `TranscriptSegment`.
8. Create video `MultimodalChunk` and `CitationLocator` records with `start_ms`/`end_ms` and original-video locator metadata.
9. Embed video transcript chunks and upsert timestamp payloads into Qdrant.
10. Return video citations in Chat with source type and timestamps for frontend display.

## Question Answering
1. Check knowledge space exists.
2. Check at least one ready indexed document or multimodal source exists.
3. Compare document/index revision fingerprint and current embedding fingerprint.
4. Embed the question.
5. Retrieve top-k chunks from Qdrant with score threshold.
6. Refuse when context is insufficient.
7. Build a prompt that treats retrieved content as data, not system instructions.
8. Generate answer with citation ids such as `[1]`.
9. Save QA history with retrieval status and confidence.

## Refusal Cases
- `no_ready_documents`: the space has no ready indexed documents or multimodal sources.
- `INDEX_INCOMPATIBLE`: current embedding/index config differs from stored document or multimodal index config.
- `insufficient_context`: retrieval returned no chunk above the threshold.
