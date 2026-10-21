# Audio And Video Transcription Pipeline

## Supported Inputs

- MP3
- WAV
- M4A
- MP4
- MOV

The upload path validates extension, MIME type, size, duplicate SHA256 and real media duration. `mutagen` reads duration without requiring FFmpeg.

For video, FFmpeg/ffprobe reads real duration, width, height and audio-track presence. The system stores the original video and extracts at least one keyframe as `VisualFrame` and `MediaAsset`.

## Runtime Boundary

Audio and video upload work without a model key. Transcription does not.

- `TRANSCRIPTION_PROVIDER=openai_compatible_audio`
- `TRANSCRIPTION_API_KEY`
- `TRANSCRIPTION_BASE_URL`
- `TRANSCRIPTION_MODEL`

If no real provider is configured, the API returns `TRANSCRIPTION_NOT_CONFIGURED`. The system does not generate fake transcript text.

## Pipeline

1. Upload audio or video to a knowledge space.
2. Save `Source`, `SourceRevision` and `MediaAsset` with real duration and media metadata.
3. Call `POST /api/media/sources/{source_id}/transcribe`.
4. For video, extract a real WAV audio track with FFmpeg before calling the provider.
5. Send the audio to an OpenAI-compatible `/audio/transcriptions` endpoint using verbose JSON.
6. Store each timestamped result as `TranscriptSegment`.
7. Create one `MultimodalChunk` and `CitationLocator` per segment.
8. Generate embeddings and upsert timestamp payloads into Qdrant.
9. RAG returns citations with `start_ms` and `end_ms`.
10. The frontend displays the audio/video player, keyframe preview for video, and transcript timeline.

## APIs

- `POST /api/media/audio/upload`
- `POST /api/media/video/upload`
- `GET /api/media/sources/{source_id}`
- `GET /api/media/sources/{source_id}/file`
- `GET /api/media/assets/{asset_id}/file`
- `POST /api/media/sources/{source_id}/transcribe`

## Current Boundary

- Speaker diarization is preserved when a provider returns speaker labels, but the default provider does not guarantee diarization.
- Language is stored when returned by the provider.
- Video subtitles are stored as searchable transcript segments, but subtitle export files such as SRT/VTT are not implemented yet.
