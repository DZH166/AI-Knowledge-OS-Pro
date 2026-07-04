# V3.5 Video Pipeline Acceptance Report

## Scope

V3.5 completes the first usable video pipeline for AI Knowledge OS Pro:

- MP4/MOV upload.
- Real duration, width, height and audio-track metadata.
- Original video storage as `MediaAsset`.
- Keyframe extraction as `VisualFrame` and keyframe `MediaAsset`.
- Video detail player, metadata, keyframe preview and transcript timeline.
- Video audio extraction before transcription.
- Configured real transcription provider only; unconfigured provider returns `TRANSCRIPTION_NOT_CONFIGURED`.
- Timestamped `TranscriptSegment`, `MultimodalChunk`, `CitationLocator` and `IndexRevision`.
- RAG citations carrying `source_type=video`, `start_ms` and `end_ms`.

## Real Mode Boundary

Video upload can run without model keys because it only stores files, metadata and real keyframes. Video transcription requires a real provider key.

When transcription is not configured:

- The service raises `TRANSCRIPTION_NOT_CONFIGURED`.
- No fake subtitles are generated.
- No extracted audio asset is written.
- Existing source metadata remains in metadata-only state.

## Data Flow

1. `POST /api/media/video/upload` saves the upload under `uploads/video`.
2. `VideoTooling.probe()` reads metadata with ffprobe or ffmpeg fallback.
3. `MediaService.upload_video()` creates `Source`, `SourceRevision` and original-video `MediaAsset`.
4. `VideoTooling.extract_keyframe()` stores a real JPEG keyframe.
5. Keyframe is recorded as both `VisualFrame` and keyframe `MediaAsset`.
6. `POST /api/media/sources/{id}/transcribe` verifies provider configuration.
7. FFmpeg extracts a mono 16 kHz WAV audio track.
8. The real transcription provider returns verbose timestamped segments.
9. Each segment is saved as `TranscriptSegment` and `video_transcript` `MultimodalChunk`.
10. `CitationLocator` stores original-video locator metadata.
11. Embeddings are upserted to Qdrant with video timestamp payloads.
12. Chat returns video citations with source type and timestamps.

## Acceptance Tests

- `test_video_upload_reads_real_metadata_and_keyframe`
  - Generates tiny MP4/MOV fixtures through FFmpeg.
  - Verifies duration, width, height, `has_audio`, original video asset and keyframe.
- `test_video_transcription_requires_real_provider_without_extracting_audio`
  - Verifies `TRANSCRIPTION_NOT_CONFIGURED`.
  - Verifies no extracted audio asset is written.
- `test_video_transcription_creates_timestamped_rag_chunks_and_video_citations`
  - Uses a fake configured provider.
  - Verifies WAV extraction, transcript segments, chunks, citation locators, keyframe reuse and RAG video citations.

## Verification

- `python -m compileall backend/app backend/alembic scripts`: passed.
- `python -m pytest`: 31 passed, 10 warnings.
- Frontend typecheck: passed.
- Frontend production build: passed.
- Alembic current: `0005_v3_3_error_archive`.

## Boundaries

- Subtitle export files such as SRT/VTT are not implemented.
- Clicking a citation does not yet seek the player to the timestamp.
- Multi-keyframe shot segmentation is not implemented.
- Visual frame OCR/captioning is not implemented.
