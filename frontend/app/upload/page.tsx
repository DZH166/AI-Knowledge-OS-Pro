"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AudioLines, Code2, FileText, ImagePlus, UploadCloud, Video } from "lucide-react";
import { useSearchParams } from "next/navigation";

import { DocumentUploader } from "@/components/DocumentUploader";
import { workbenchJourneyHref } from "@/modules/evidence-agent/research-journey";
import { ButtonLoading, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api, formatDate, formatDuration, formatFileSize, statusLabel } from "@/services/api";
import type { DocumentItem, KnowledgeSpace, SourceItem } from "@/types/api";

function metadata(source: SourceItem) {
  try {
    const parsed = JSON.parse(source.metadata_json || "{}");
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function metadataString(source: SourceItem, key: string, fallback = "not configured") {
  const value = metadata(source)[key];
  return typeof value === "string" && value.trim() ? value : fallback;
}

const workflows = {
  document: ["Upload file", "Parse text", "Split chunks", "Embed", "Index", "Ask with citations"],
  image: ["Upload image", "Read metadata", "Run OCR or vision task", "Index chunks", "Create learning artifacts"],
  audio: ["Upload audio", "Read duration", "Run transcription task", "Jump by timestamp", "Create cards or notes"],
  video: ["Upload video", "Read metadata", "Extract keyframes", "Transcribe audio track", "Jump to evidence"],
  code: ["Choose local repository", "Apply safety skip rules", "Create file/line chunks", "Embed", "Ask code questions"]
};

function UploadContent() {
  const searchParams = useSearchParams();
  const defaultSpaceId = Number(searchParams.get("space_id") || 0);
  const returnToComparison = searchParams.get("scenario") === "compare";
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [imageSpaceId, setImageSpaceId] = useState(0);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  const [audioSpaceId, setAudioSpaceId] = useState(0);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioUploading, setAudioUploading] = useState(false);
  const [videoSpaceId, setVideoSpaceId] = useState(0);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoUploading, setVideoUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [spaceData, documentData, sourceData] = await Promise.all([api.listSpaces(), api.listDocuments(), api.listSources()]);
      setSpaces(spaceData);
      setDocuments(documentData);
      setSources(sourceData);
      setImageSpaceId(defaultSpaceId || spaceData[0]?.id || 0);
      setAudioSpaceId(defaultSpaceId || spaceData[0]?.id || 0);
      setVideoSpaceId(defaultSpaceId || spaceData[0]?.id || 0);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load upload center.");
    }
  }, [defaultSpaceId]);

  useEffect(() => {
    load();
  }, [load]);

  async function uploadImage() {
    if (!imageSpaceId || !imageFile) return;
    setImageUploading(true);
    setMessage("");
    setError("");
    try {
      const result = await api.uploadImage(imageSpaceId, imageFile);
      setSources((old) => [result.source, ...old]);
      setMessage(result.job_id ? `${result.message} Task #${result.job_id} was created.` : result.message);
      setImageFile(null);
      await api.updateOnboarding({ steps: { upload_document: true } });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Image upload failed.");
    } finally {
      setImageUploading(false);
    }
  }

  async function uploadAudio() {
    if (!audioSpaceId || !audioFile) return;
    setAudioUploading(true);
    setMessage("");
    setError("");
    try {
      const result = await api.uploadAudio(audioSpaceId, audioFile);
      setSources((old) => [result.source, ...old]);
      setMessage(result.job_id ? `${result.message} Task #${result.job_id} was created.` : result.message);
      setAudioFile(null);
      await api.updateOnboarding({ steps: { upload_document: true } });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Audio upload failed.");
    } finally {
      setAudioUploading(false);
    }
  }

  async function uploadVideo() {
    if (!videoSpaceId || !videoFile) return;
    setVideoUploading(true);
    setMessage("");
    setError("");
    try {
      const result = await api.uploadVideo(videoSpaceId, videoFile);
      setSources((old) => [result.source, ...old]);
      setMessage(result.job_id ? `${result.message} Task #${result.job_id} was created.` : result.message);
      setVideoFile(null);
      await api.updateOnboarding({ steps: { upload_document: true } });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Video upload failed.");
    } finally {
      setVideoUploading(false);
    }
  }

  const imageSources = sources.filter((source) => source.source_type === "image");
  const audioSources = sources.filter((source) => source.source_type === "audio");
  const videoSources = sources.filter((source) => source.source_type === "video");
  const journeySpaceId = spaces.length > 0 && !spaces.some((space) => space.id === defaultSpaceId)
    ? spaces[0].id : defaultSpaceId;

  return (
    <div className="page">
      <PageHeader
        description={returnToComparison
          ? "将三份技术资料上传到同一个知识空间。上传成功不代表已经可以引用，请等待处理任务完成。"
          : "Upload documents, images, audio and video into the same knowledge workspace. Media files keep real metadata first, then provider-backed tasks can OCR, transcribe, analyze, index and turn evidence into learning material."}
        eyebrow={returnToComparison ? "研究准备" : "Knowledge intake"}
        title={returnToComparison ? "准备对比资料" : "Upload Center"}
      />
      {returnToComparison && (
        <section aria-label="返回对比研究" className="panel stack">
          <strong>下一步：固定三份可用资料</strong>
          <p className="muted">处理完成并建立有效版本后，返回工作台选择资料和比较维度。仍在处理的文件不会被当作可引用证据。</p>
          <Link className="button secondary" href={workbenchJourneyHref({ recording: false, comparison: true, spaceId: journeySpaceId })}>
            返回三资料对比
          </Link>
        </section>
      )}
      {error && <ErrorState message={error} onRetry={load} />}
      {message && <span className="pill">{message}</span>}
      {spaces.length === 0 ? (
        <EmptyState
          action={
            <Link className="button" href="/knowledge">
              {returnToComparison ? "创建知识空间" : "Create a space"}
            </Link>
          }
          description={returnToComparison ? "每份资料都需要归属一个知识空间，创建后再上传。" : "Every source belongs to a knowledge space. Create one before uploading files."}
          title={returnToComparison ? "先创建知识空间" : "Create a knowledge space first"}
        />
      ) : (
        <>
          {!returnToComparison && <section className="grid cols-4">
            <WorkflowCard icon={<FileText size={18} />} steps={workflows.document} title="Documents" />
            <WorkflowCard icon={<ImagePlus size={18} />} steps={workflows.image} title="Images" />
            <WorkflowCard icon={<AudioLines size={18} />} steps={workflows.audio} title="Audio" />
            <WorkflowCard icon={<Video size={18} />} steps={workflows.video} title="Video" />
            <WorkflowCard icon={<Code2 size={18} />} steps={workflows.code} title="Code repositories" />
          </section>}

          <section className={returnToComparison ? "grid cols-2" : "grid cols-4"}>
            <DocumentUploader
              comparisonMode={returnToComparison}
              defaultSpaceId={returnToComparison ? journeySpaceId : defaultSpaceId || spaces[0]?.id}
              onUploaded={(document) => {
                setDocuments((old) => [document, ...old]);
                api.updateOnboarding({ steps: { upload_document: true } });
              }}
              spaces={spaces}
            />

            {returnToComparison ? <RecentDocuments comparisonMode documents={documents.filter((document) => document.space_id === journeySpaceId)} /> : <>

            <MediaUploadCard
              accept=".png,.jpg,.jpeg,.webp,.bmp,image/png,image/jpeg,image/webp,image/bmp"
              busy={imageUploading}
              file={imageFile}
              icon={<ImagePlus size={26} />}
              label="Choose image"
              note="OCR, visual description and screenshot analysis run as explicit media tasks. Missing providers return clear NOT_CONFIGURED errors."
              onFile={setImageFile}
              onSubmit={uploadImage}
              spaceId={imageSpaceId}
              spaces={spaces}
              statusLabelText="Metadata first"
              title="Image Source"
              updateSpace={setImageSpaceId}
            />

            <MediaUploadCard
              accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/mp4"
              busy={audioUploading}
              file={audioFile}
              icon={<AudioLines size={26} />}
              label="Choose audio"
              note="The system reads real duration first. Transcription runs in Task Center and can later jump to exact timestamps."
              onFile={setAudioFile}
              onSubmit={uploadAudio}
              spaceId={audioSpaceId}
              spaces={spaces}
              statusLabelText="Duration"
              title="Audio Source"
              updateSpace={setAudioSpaceId}
            />

            <MediaUploadCard
              accept=".mp4,.mov,video/mp4,video/quicktime"
              busy={videoUploading}
              file={videoFile}
              icon={<Video size={26} />}
              label="Choose video"
              note="The system reads real duration, size and audio-track metadata. Keyframes and transcription are handled by media tasks."
              onFile={setVideoFile}
              onSubmit={uploadVideo}
              spaceId={videoSpaceId}
              spaces={spaces}
              statusLabelText="Metadata"
              title="Video Source"
              updateSpace={setVideoSpaceId}
            />
            </>}
          </section>
        </>
      )}

      {!returnToComparison && <section className="grid cols-4">
        <RecentDocuments documents={documents} />
        <RecentSources sources={imageSources} title="Recent Images" />
        <RecentSources sources={audioSources} title="Recent Audio" />
        <RecentSources sources={videoSources} title="Recent Video" />
      </section>}
    </div>
  );
}

function WorkflowCard({ icon, title, steps }: { icon: React.ReactNode; title: string; steps: string[] }) {
  return (
    <article className="card stack">
      <div className="row">
        {icon}
        <h3>{title}</h3>
      </div>
      <ol className="mini-steps">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </article>
  );
}

function MediaUploadCard({
  accept,
  busy,
  file,
  icon,
  label,
  note,
  onFile,
  onSubmit,
  spaceId,
  spaces,
  statusLabelText,
  title,
  updateSpace
}: {
  accept: string;
  busy: boolean;
  file: File | null;
  icon: React.ReactNode;
  label: string;
  note: string;
  onFile: (file: File | null) => void;
  onSubmit: () => void;
  spaceId: number;
  spaces: KnowledgeSpace[];
  statusLabelText: string;
  title: string;
  updateSpace: (spaceId: number) => void;
}) {
  return (
    <section className="panel stack">
      <div className="row between">
        <h2>{title}</h2>
        <StatusBadge status="ready" label={statusLabelText} />
      </div>
      <p className="muted">{note}</p>
      <div className="field">
        <label htmlFor={`${title}-space`}>Knowledge space</label>
        <select className="select" id={`${title}-space`} onChange={(event) => updateSpace(Number(event.target.value))} value={spaceId}>
          {spaces.map((space) => (
            <option key={space.id} value={space.id}>
              {space.name}
            </option>
          ))}
        </select>
      </div>
      <label className="dropzone">
        {icon}
        <strong>{file ? file.name : label}</strong>
        <span className="muted">{file ? formatFileSize(file.size) : "Select a file to create a traceable media source."}</span>
        <input accept={accept} onChange={(event) => onFile(event.target.files?.[0] || null)} style={{ display: "none" }} type="file" />
      </label>
      <button className="button" disabled={!spaceId || !file || busy} onClick={onSubmit} type="button">
        {busy ? (
          <ButtonLoading label="Uploading" />
        ) : (
          <>
            <UploadCloud size={17} />
            Upload
          </>
        )}
      </button>
    </section>
  );
}

function RecentDocuments({ documents, comparisonMode = false }: { documents: DocumentItem[]; comparisonMode?: boolean }) {
  return (
    <div className="panel stack">
      <h2>{comparisonMode ? "本空间的文档" : "Recent Documents"}</h2>
      <div className="list">
        {documents.slice(0, 5).map((document) => (
          <Link className="list-item" href={`/documents/${document.id}`} key={document.id}>
            <strong>{document.original_filename}</strong>
            <span className="muted">
              {comparisonMode ? `${document.chunk_count} 个片段 · 处理进度 ${document.processing_progress}%` : `${document.chunk_count} chunks / ${document.processing_progress}%`}
            </span>
          </Link>
        ))}
        {documents.length === 0 && <EmptyState
          description={comparisonMode ? "上传三份 txt、md 或 pdf 文档；处理完成后再回工作台选择。" : "Upload txt, md or pdf files to start document RAG."}
          title={comparisonMode ? "这里还没有文档" : "No documents"}
        />}
      </div>
    </div>
  );
}

function RecentSources({ sources, title }: { sources: SourceItem[]; title: string }) {
  return (
    <div className="panel stack">
      <h2>{title}</h2>
      <div className="list">
        {sources.slice(0, 5).map((source) => (
          <Link className="list-item" href={`/media/sources/${source.id}`} key={source.id}>
            <div className="row between">
              <strong>{source.title || source.original_filename || `Source #${source.id}`}</strong>
              <StatusBadge status={source.status} />
            </div>
            <span className="muted">{sourceSummary(source)}</span>
            <span className="pill gray">{statusText(source)}</span>
          </Link>
        ))}
        {sources.length === 0 && <EmptyState description="Uploaded media appears here with real metadata and task status." title="No sources" />}
      </div>
    </div>
  );
}

function sourceSummary(source: SourceItem) {
  const size = formatFileSize(source.file_size);
  const created = formatDate(source.created_at);
  if (source.source_type === "image") return `${source.width || 0} x ${source.height || 0} / ${size} / ${created}`;
  if (source.source_type === "audio") return `${formatDuration(source.duration_ms)} / ${size} / ${created}`;
  if (source.source_type === "video") return `${formatDuration(source.duration_ms)} / ${source.width || 0} x ${source.height || 0} / ${size}`;
  return `${size} / ${created}`;
}

function statusText(source: SourceItem) {
  if (source.source_type === "image") return `OCR: ${statusLabel(metadataString(source, "ocr_status"))}`;
  if (source.source_type === "audio" || source.source_type === "video") {
    return `Transcription: ${statusLabel(metadataString(source, "transcription_status"))}`;
  }
  return statusLabel(source.status);
}

export default function UploadPage() {
  return (
    <Suspense fallback={null}>
      <UploadContent />
    </Suspense>
  );
}
