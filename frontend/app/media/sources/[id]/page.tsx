"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  AudioLines,
  BookOpenCheck,
  Bug,
  Eye,
  FileQuestion,
  Images,
  Layers3,
  NotebookPen,
  Play,
  ScanText,
  Sparkles,
  StickyNote,
  Video
} from "lucide-react";

import { ButtonLoading, EmptyState, ErrorState, PageHeader, StatusBadge, TechnicalDetails } from "@/components/ui";
import { api, formatDate, formatDuration, formatFileSize, mediaAssetFileUrl, sourceFileUrl, statusLabel } from "@/services/api";
import type {
  ErrorArchive,
  LearningArtifactType,
  MediaAsset,
  MediaOperation,
  SourceItem,
  TranscriptSegment,
  VisualFrame
} from "@/types/api";

function parseMetadata(value: string | null | undefined) {
  try {
    const parsed = JSON.parse(value || "{}");
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function displayValue(value: unknown) {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  return "未记录";
}

function metadataLabel(key: string) {
  const labels: Record<string, string> = {
    audio_status: "音轨提取",
    duration_ms: "时长",
    error_archive_status: "报错档案",
    has_audio: "音轨",
    height: "高度",
    keyframe_count: "关键帧数量",
    keyframe_status: "关键帧抽取",
    ocr_status: "OCR",
    parser_version: "解析器",
    transcription_status: "转写",
    transcript_segment_count: "转写片段",
    video_status: "视频分析",
    vision_description_status: "视觉描述",
    width: "宽度"
  };
  return labels[key] || key.replace(/_/g, " ");
}

function metadataSummaryEntries(metadata: Record<string, unknown>) {
  return Object.entries(metadata)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => {
      const label = metadataLabel(key);
      if (key.endsWith("_ms") && typeof value === "number") return [label, formatDuration(value)] as const;
      if (typeof value === "object") {
        const count = Array.isArray(value) ? value.length : Object.keys(value as Record<string, unknown>).length;
        return [label, count ? `已记录 ${count} 项` : "未记录"] as const;
      }
      return [label, displayValue(value)] as const;
    });
}

function isTranscribable(source: SourceItem | null) {
  return source?.source_type === "audio" || source?.source_type === "video";
}

function mediaLabel(source: SourceItem | null) {
  if (source?.source_type === "video") return "Video";
  if (source?.source_type === "audio") return "Audio";
  if (source?.source_type === "image") return "Image";
  return "Media";
}

function latestAsset(assets: MediaAsset[], assetType: string) {
  return assets
    .filter((asset) => asset.asset_type === assetType && !parseMetadata(asset.metadata_json).superseded)
    .sort((a, b) => b.id - a.id)[0] || null;
}

function operationLabel(operation: MediaOperation) {
  const labels: Record<MediaOperation, string> = {
    image_ocr: "Image OCR",
    image_visual_description: "Visual description",
    image_screenshot_analysis: "Screenshot error analysis",
    image_full_analysis: "Full image analysis",
    audio_transcription: "Audio transcription",
    video_transcription: "Video transcription",
    video_keyframes: "Extract keyframes",
    video_keyframe_ocr: "Keyframe OCR",
    video_visual_description: "Keyframe visual description",
    video_full_pipeline: "Full video pipeline"
  };
  return labels[operation];
}

function buildChapters(segments: TranscriptSegment[]) {
  if (segments.length <= 1) return segments;
  const chapterSize = Math.max(1, Math.ceil(segments.length / 6));
  return segments.filter((_, index) => index % chapterSize === 0);
}

function frameTimestamp(frameOrAsset: VisualFrame | MediaAsset) {
  const metadata = parseMetadata(frameOrAsset.metadata_json);
  const raw = metadata.timestamp_ms;
  return typeof raw === "number" ? raw : null;
}

function matchingFrame(asset: MediaAsset, frames: VisualFrame[]) {
  const timestamp = frameTimestamp(asset);
  return frames.find((frame) => frame.timestamp_ms === timestamp) || null;
}

export default function MediaSourceDetailPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const sourceId = Number(params.id);
  const requestedTimestamp = Number(searchParams.get("t") || 0);
  const requestedChunkId = Number(searchParams.get("chunk") || 0);
  const [source, setSource] = useState<SourceItem | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [processingOperation, setProcessingOperation] = useState<MediaOperation | null>(null);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [activeSegmentId, setActiveSegmentId] = useState<number | null>(null);
  const [selectedChunkId, setSelectedChunkId] = useState<number | null>(null);
  const [learningRunning, setLearningRunning] = useState(false);
  const [errorArchives, setErrorArchives] = useState<ErrorArchive[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(sourceId)) return;
    setError("");
    try {
      const [sourceData, archiveData] = await Promise.all([api.getSource(sourceId), api.listErrors({ sourceId })]);
      setSource(sourceData);
      setErrorArchives(archiveData);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load media source.");
    }
  }, [sourceId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!activeJobId) return;
    const timer = window.setInterval(async () => {
      try {
        const job = await api.getIngestionJob(activeJobId);
        if (["completed", "failed", "cancelled", "interrupted"].includes(job.status)) {
          window.clearInterval(timer);
          setProcessingOperation(null);
          setActiveJobId(null);
          setMessage(job.status === "completed" ? `Task #${job.id} completed.` : `Task #${job.id} ${statusLabel(job.status)}.`);
          await load();
        }
      } catch {
        window.clearInterval(timer);
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [activeJobId, load]);

  const metadata = useMemo(() => (source ? parseMetadata(source.metadata_json) : {}), [source]);
  const assets = source?.media_assets || [];
  const activeRevision = source?.revisions.find((revision) => revision.id === source.active_revision_id) || source?.revisions[0] || null;
  const ocrChunks = activeRevision?.chunks.filter((chunk) => chunk.modality === "image_text" || chunk.modality === "video_frame_text") || [];
  const visualChunks = activeRevision?.chunks.filter((chunk) => chunk.modality === "image_description" || chunk.modality === "video_frame_description") || [];
  const transcriptChunks = activeRevision?.chunks.filter((chunk) => chunk.modality === "audio_transcript" || chunk.modality === "video_transcript") || [];
  const transcriptSegments = activeRevision?.transcript_segments || [];
  const visualFrames = (activeRevision?.visual_frames || []).filter((frame) => !parseMetadata(frame.metadata_json).superseded);
  const keyframeAssets = assets
    .filter((asset) => asset.asset_type === "keyframe" && !parseMetadata(asset.metadata_json).superseded)
    .sort((a, b) => (frameTimestamp(a) || 0) - (frameTimestamp(b) || 0));
  const keyframeAsset = useMemo(() => latestAsset(assets, "keyframe"), [assets]);
  const chapters = useMemo(() => buildChapters(transcriptSegments), [transcriptSegments]);
  const selectedSegment = transcriptSegments.find((segment) => segment.id === activeSegmentId) || null;
  const selectedChunk =
    transcriptChunks.find((chunk) => chunk.id === selectedChunkId) ||
    (selectedSegment ? transcriptChunks.find((chunk) => chunk.start_ms === selectedSegment.start_ms) : null) ||
    ocrChunks.find((chunk) => chunk.id === selectedChunkId) ||
    visualChunks.find((chunk) => chunk.id === selectedChunkId) ||
    (source?.source_type === "image" ? ocrChunks[0] || visualChunks[0] || null : null);
  const busy = processingOperation !== null;

  const seekTo = useCallback((milliseconds: number, autoplay = true) => {
    const media = source?.source_type === "video" ? videoRef.current : audioRef.current;
    if (media) {
      media.currentTime = Math.max(0, milliseconds / 1000);
      if (autoplay) media.play().catch(() => undefined);
    }
    const segment = transcriptSegments.find((item) => milliseconds >= item.start_ms && milliseconds <= item.end_ms) || null;
    setActiveSegmentId(segment?.id || null);
    if (segment) {
      const chunk = transcriptChunks.find((item) => item.start_ms === segment.start_ms);
      setSelectedChunkId(chunk?.id || null);
      window.setTimeout(() => {
        document.getElementById(`segment-${segment.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 60);
    }
  }, [source?.source_type, transcriptChunks, transcriptSegments]);

  useEffect(() => {
    if (!source) return;
    if (requestedChunkId) setSelectedChunkId(requestedChunkId);
    if (requestedTimestamp && transcriptSegments.length) seekTo(requestedTimestamp, false);
  }, [source, requestedTimestamp, requestedChunkId, transcriptSegments.length, seekTo]);

  async function enqueueOperation(operation: MediaOperation) {
    if (!source) return;
    setProcessingOperation(operation);
    setError("");
    setMessage("");
    try {
      const result = await api.processMedia(source.id, operation);
      setSource(result.source);
      setActiveJobId(result.job.id);
      setMessage(`Task #${result.job.id} entered the task center.`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to create media task.");
      setProcessingOperation(null);
    }
  }

  function syncActiveSegment(currentTimeSeconds: number) {
    const milliseconds = currentTimeSeconds * 1000;
    const segment = transcriptSegments.find((item) => milliseconds >= item.start_ms && milliseconds <= item.end_ms);
    if (segment && segment.id !== activeSegmentId) {
      setActiveSegmentId(segment.id);
      const chunk = transcriptChunks.find((item) => item.start_ms === segment.start_ms);
      setSelectedChunkId(chunk?.id || null);
    }
  }

  async function createLearningArtifacts(types: LearningArtifactType[]) {
    if (!source || !selectedChunk) {
      setError("Select a real OCR, visual, or transcript chunk before creating learning artifacts.");
      return;
    }
    setLearningRunning(true);
    setError("");
    try {
      const result = await api.createLearningArtifacts({
        source_id: source.id,
        chunk_id: selectedChunk.id,
        artifact_types: types,
        title: `${source.title || source.original_filename || "Media source"}${selectedSegment ? ` ${formatDuration(selectedSegment.start_ms)}` : ""}`
      });
      setMessage(result.message);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to create learning artifacts.");
    } finally {
      setLearningRunning(false);
    }
  }

  function ProcessingButton({
    operation,
    icon,
    secondary = false
  }: {
    operation: MediaOperation;
    icon: React.ReactNode;
    secondary?: boolean;
  }) {
    const isCurrent = processingOperation === operation;
    return (
      <button className={`button ${secondary ? "secondary" : ""}`} disabled={busy} onClick={() => enqueueOperation(operation)} type="button">
        {isCurrent ? <ButtonLoading label="Running" /> : icon}
        {!isCurrent && operationLabel(operation)}
      </button>
    );
  }

  return (
    <div className="page">
      <PageHeader
        action={
          <Link className="button secondary" href="/media">
            <ArrowLeft size={16} />
            Back to media
          </Link>
        }
        description="Inspect real media metadata, run provider-backed processing tasks, and jump from RAG citations into the exact media timestamp or chunk."
        eyebrow="Media library"
        title={source?.title || source?.original_filename || `Source #${sourceId}`}
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {message && <span className="pill">{message}</span>}
      {activeJobId && (
        <Link className="pill gold" href="/tasks">
          Active task #{activeJobId}
        </Link>
      )}
      {!Number.isFinite(sourceId) ? (
        <EmptyState description="Open a concrete media source from the library." title="Invalid source address" />
      ) : !source && !error ? (
        <EmptyState description="Loading media details." title="Loading" />
      ) : source ? (
        <>
          <section className="grid cols-4">
            <article className="card">
              <span className="muted">Type</span>
              <p className="stat-value">{source.source_type}</p>
            </article>
            <article className="card">
              <span className="muted">File size</span>
              <p className="stat-value">{formatFileSize(source.file_size)}</p>
            </article>
            <article className="card">
              <span className="muted">{isTranscribable(source) ? "Duration" : "Dimensions"}</span>
              <p className="stat-value">
                {isTranscribable(source) ? formatDuration(source.duration_ms) : source.width && source.height ? `${source.width} x ${source.height}` : "not recorded"}
              </p>
            </article>
            <article className="card">
              <span className="muted">Status</span>
              <p className="stat-value">
                <StatusBadge status={source.status} />
              </p>
            </article>
          </section>

          <section className="split">
            <article className="panel stack">
              <h2>Preview</h2>
              <div className="list">
                <div className="list-item">
                  <span className="muted">Original file</span>
                  <strong>{source.original_filename || "not recorded"}</strong>
                </div>
                <div className="list-item">
                  <span className="muted">MIME type</span>
                  <strong>{source.mime_type || "not recorded"}</strong>
                </div>
                <div className="list-item">
                  <span className="muted">Knowledge space</span>
                  <strong>{source.space_id}</strong>
                </div>
                <div className="list-item">
                  <span className="muted">Created</span>
                  <strong>{formatDate(source.created_at)}</strong>
                </div>
              </div>

              {source.source_type === "audio" && (
                <audio
                  controls
                  onTimeUpdate={(event) => syncActiveSegment(event.currentTarget.currentTime)}
                  preload="metadata"
                  ref={audioRef}
                  src={sourceFileUrl(source.id)}
                  style={{ width: "100%" }}
                />
              )}
              {source.source_type === "video" && (
                <video
                  className="media-player"
                  controls
                  onTimeUpdate={(event) => syncActiveSegment(event.currentTarget.currentTime)}
                  poster={keyframeAsset ? mediaAssetFileUrl(keyframeAsset.id) : undefined}
                  preload="metadata"
                  ref={videoRef}
                  src={sourceFileUrl(source.id)}
                />
              )}
              {source.source_type === "image" && (
                <img alt={source.original_filename || "Uploaded image"} className="source-image-preview" src={sourceFileUrl(source.id)} />
              )}

              <div className="row wrap">
                {source.source_type === "image" && (
                  <>
                    <ProcessingButton icon={<ScanText size={16} />} operation="image_ocr" />
                    <ProcessingButton icon={<Eye size={16} />} operation="image_visual_description" secondary />
                    <ProcessingButton icon={<Bug size={16} />} operation="image_screenshot_analysis" secondary />
                    <ProcessingButton icon={<Sparkles size={16} />} operation="image_full_analysis" secondary />
                  </>
                )}
                {source.source_type === "audio" && <ProcessingButton icon={<AudioLines size={16} />} operation="audio_transcription" />}
                {source.source_type === "video" && (
                  <>
                    <ProcessingButton icon={<Images size={16} />} operation="video_keyframes" secondary />
                    <ProcessingButton icon={<ScanText size={16} />} operation="video_keyframe_ocr" secondary />
                    <ProcessingButton icon={<Eye size={16} />} operation="video_visual_description" secondary />
                    <ProcessingButton icon={<Video size={16} />} operation="video_transcription" />
                    <ProcessingButton icon={<Layers3 size={16} />} operation="video_full_pipeline" secondary />
                  </>
                )}
              </div>

              <div className="status-line">
                <span className="pill gray">OCR: {displayValue(metadata.ocr_status)}</span>
                <span className="pill gray">Vision: {displayValue(metadata.vision_description_status)}</span>
                {isTranscribable(source) && <span className="pill gray">Transcription: {displayValue(metadata.transcription_status)}</span>}
                {source.source_type === "video" && <span className="pill gray">Keyframes: {displayValue(metadata.keyframe_status)}</span>}
                {source.source_type === "video" && <span className="pill gray">Has audio: {displayValue(metadata.has_audio)}</span>}
              </div>
            </article>

            <article className="panel stack">
              <h2>处理详情</h2>
              <TechnicalDetails title="元数据摘要">
                {metadataSummaryEntries(metadata).length === 0 ? (
                  <p>暂未记录元数据。</p>
                ) : (
                  metadataSummaryEntries(metadata).map(([key, value]) => (
                    <p key={key}>
                      {key}: {value}
                    </p>
                  ))
                )}
              </TechnicalDetails>
              <div className="list">
                {assets.length === 0 ? (
                  <EmptyState description="No derived media assets have been saved yet." title="No assets" />
                ) : (
                  assets.map((asset) => (
                    <div className="list-item" key={asset.id}>
                      <div className="row between">
                        <strong>{asset.asset_type}</strong>
                        <StatusBadge status="ready" label="Saved" />
                      </div>
                      <span className="muted">{asset.storage_path}</span>
                      <span className="muted">
                        {formatFileSize(asset.file_size)}
                        {asset.width && asset.height ? ` / ${asset.width} x ${asset.height}` : ""}
                        {asset.duration_ms ? ` / ${formatDuration(asset.duration_ms)}` : ""}
                        {frameTimestamp(asset) !== null ? ` / ${formatDuration(frameTimestamp(asset))}` : ""}
                      </span>
                      {asset.asset_type === "keyframe" && <img alt="Video keyframe" className="keyframe-preview" src={mediaAssetFileUrl(asset.id)} />}
                    </div>
                  ))
                )}
              </div>
            </article>
          </section>

          {source.source_type === "video" && (
            <section className="panel stack">
              <div className="row between wrap">
                <h2>Keyframe timeline</h2>
                <span className="pill gray">{keyframeAssets.length} frames</span>
              </div>
              {keyframeAssets.length === 0 ? (
                <EmptyState description="Run keyframe extraction or the full video pipeline to save real video frames." title="No keyframes" />
              ) : (
                <div className="keyframe-strip">
                  {keyframeAssets.map((asset) => {
                    const frame = matchingFrame(asset, visualFrames);
                    const timestamp = frameTimestamp(asset) || frame?.timestamp_ms || 0;
                    return (
                      <button className="keyframe-tile" key={asset.id} onClick={() => seekTo(timestamp)} type="button">
                        <img alt={`Keyframe at ${formatDuration(timestamp)}`} src={mediaAssetFileUrl(asset.id)} />
                        <strong>{formatDuration(timestamp)}</strong>
                        {frame?.ocr_text && <span>{frame.ocr_text}</span>}
                        {frame?.visual_description && <span>{frame.visual_description}</span>}
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {isTranscribable(source) && (
            <section className="panel stack">
              <div className="row between wrap">
                <h2>{mediaLabel(source)} transcript timeline</h2>
                {transcriptChunks.length > 0 && <span className="pill">{transcriptChunks.length} chunks indexed</span>}
              </div>
              {chapters.length > 1 && (
                <div className="chapter-list">
                  {chapters.map((segment) => (
                    <button className="button secondary small" key={segment.id} onClick={() => seekTo(segment.start_ms)} type="button">
                      <Play size={14} />
                      {formatDuration(segment.start_ms)}
                    </button>
                  ))}
                </div>
              )}
              {transcriptSegments.length === 0 ? (
                <EmptyState
                  description="Configure a real transcription provider and run transcription. The system returns an explicit NOT_CONFIGURED error instead of fake subtitles."
                  title="No transcript segments"
                />
              ) : (
                <div className="list">
                  {transcriptSegments.map((segment) => {
                    const chunk = transcriptChunks.find((item) => item.start_ms === segment.start_ms);
                    return (
                      <button
                        className={`list-item transcript-segment ${segment.id === activeSegmentId ? "active" : ""}`}
                        id={`segment-${segment.id}`}
                        key={segment.id}
                        onClick={() => {
                          setSelectedChunkId(chunk?.id || null);
                          seekTo(segment.start_ms);
                        }}
                        type="button"
                      >
                        <div className="row between">
                          <strong>
                            {formatDuration(segment.start_ms)} - {formatDuration(segment.end_ms)}
                          </strong>
                          <StatusBadge status="ready" label={segment.language || "language unknown"} />
                        </div>
                        <p className="pre-wrap">{segment.text}</p>
                        {segment.confidence !== null && <span className="muted">Confidence {segment.confidence}%</span>}
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {(ocrChunks.length > 0 || visualChunks.length > 0 || source.source_type === "image") && (
            <section className="panel stack">
              <div className="row between wrap">
                <h2>Visual text and descriptions</h2>
                <span className="pill gray">{ocrChunks.length + visualChunks.length} chunks</span>
              </div>
              {ocrChunks.length + visualChunks.length === 0 ? (
                <EmptyState
                  description="Run OCR or visual description with a configured real provider. Missing configuration is reported explicitly."
                  title="No visual chunks"
                />
              ) : (
                <div className="list">
                  {[...ocrChunks, ...visualChunks].map((chunk) => (
                    <button
                      className={`list-item task-row ${selectedChunk?.id === chunk.id ? "active" : ""}`}
                      id={`chunk-${chunk.id}`}
                      key={chunk.id}
                      onClick={() => setSelectedChunkId(chunk.id)}
                      type="button"
                    >
                      <div className="row between">
                        <strong>
                          {chunk.modality} #{chunk.chunk_index + 1}
                        </strong>
                        <StatusBadge status={chunk.status} />
                      </div>
                      <p className="pre-wrap">{chunk.content_text}</p>
                    </button>
                  ))}
                </div>
              )}
            </section>
          )}

          {source.source_type === "image" && (
            <section className="panel stack">
              <div className="row between wrap">
                <h2>Error archive</h2>
                <Link className="button secondary small" href="/errors">
                  View all
                </Link>
              </div>
              {errorArchives.length === 0 ? (
                <EmptyState description="Run screenshot error analysis after OCR to archive explicit, real error evidence." title="No archived errors" />
              ) : (
                <div className="list">
                  {errorArchives.map((archive) => (
                    <article className="list-item" key={archive.id}>
                      <div className="row between">
                        <strong>{archive.error_type}</strong>
                        <StatusBadge status={archive.status} />
                      </div>
                      <p className="quote">{archive.error_message}</p>
                      <span className="muted">
                        Confidence {archive.confidence}% / {archive.language || "language unknown"}
                      </span>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          <section className="panel stack">
            <div className="row between wrap">
              <h2>Learning actions</h2>
              {selectedChunk ? <span className="pill gray">Selected chunk #{selectedChunk.id}</span> : <span className="pill gray">No chunk selected</span>}
            </div>
            <div className="row wrap">
              <button className="button" disabled={!selectedChunk || learningRunning} onClick={() => createLearningArtifacts(["knowledge_point"])} type="button">
                {learningRunning ? <ButtonLoading label="Creating" /> : <BookOpenCheck size={16} />}
                Knowledge point
              </button>
              <button className="button secondary" disabled={!selectedChunk || learningRunning} onClick={() => createLearningArtifacts(["card"])} type="button">
                <StickyNote size={16} />
                Card
              </button>
              <button className="button secondary" disabled={!selectedChunk || learningRunning} onClick={() => createLearningArtifacts(["quiz"])} type="button">
                <FileQuestion size={16} />
                Quiz
              </button>
              <button className="button secondary" disabled={!selectedChunk || learningRunning} onClick={() => createLearningArtifacts(["note"])} type="button">
                <NotebookPen size={16} />
                Note
              </button>
              <button
                className="button secondary"
                disabled={!selectedChunk || learningRunning}
                onClick={() => createLearningArtifacts(["knowledge_point", "card", "quiz", "note", "interview_expression"])}
                type="button"
              >
                <Layers3 size={16} />
                Full set
              </button>
            </div>
            {selectedChunk && (
              <TechnicalDetails title="Selected evidence">
                <pre className="pre-wrap">{selectedChunk.content_text}</pre>
              </TechnicalDetails>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
