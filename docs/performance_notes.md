# Performance Notes

This document records practical performance considerations for the V4.0 roadmap.

## Current Baseline

- Long-running work is task-oriented.
- Frontend build succeeds with 15 app routes.
- Local pytest suite passes.
- Release dry-run scans tracked source files and excludes large generated data.

## Target Improvements

- Large upload warnings.
- Chunked/staged processing.
- Configurable upload size limits.
- Non-blocking long tasks.
- Batch embeddings.
- Configurable retrieval `top_k`.
- Cached capability checks.
- Paginated frontend lists.
- Lazy loading where useful.
- Keyframe count limits.
- Audio/video transcription segmentation.
- Paginated task logs.

## Current Limitations

- No formal performance benchmark exists.
- No load test exists.
- Media performance depends on FFmpeg, provider latency and local hardware.
