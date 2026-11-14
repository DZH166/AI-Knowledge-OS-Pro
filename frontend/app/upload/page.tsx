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
  document: ["上传文件", "解析正文", "切分片段", "生成向量", "建立索引", "带引用提问"],
  image: ["上传图片", "读取元数据", "执行 OCR / 视觉任务", "建立片段索引", "生成学习材料"],
  audio: ["上传音频", "读取时长", "执行转写任务", "按时间戳跳转", "生成卡片或笔记"],
  video: ["上传视频", "读取元数据", "抽取关键帧", "转写音轨", "跳转到证据"],
  code: ["选择本地仓库", "应用安全跳过规则", "生成文件/行片段", "生成向量", "针对代码提问"]
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
      setError(exc instanceof Error ? exc.message : "摄取中心加载失败。");
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
      setMessage(result.job_id ? `${result.message} 已创建任务 #${result.job_id}。` : result.message);
      setImageFile(null);
      await api.updateOnboarding({ steps: { upload_document: true } });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "图片上传失败。");
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
      setError(exc instanceof Error ? exc.message : "音频上传失败。");
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
      setError(exc instanceof Error ? exc.message : "视频上传失败。");
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
          : "把文档、图片、音频和视频接入同一个知识空间。系统先保存真实元数据和来源身份，再通过可观测任务完成解析、OCR、转写与索引；未配置真实模型时会明确提示，不生成假结果。"}
        eyebrow={returnToComparison ? "研究准备" : "证据摄取"}
        title={returnToComparison ? "准备对比资料" : "摄取与上传"}
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
              创建知识空间
            </Link>
          }
          description={returnToComparison ? "每份资料都需要归属一个知识空间，创建后再上传。" : "每个来源都必须归属一个知识空间。先创建空间，再上传文件。"}
          title="先创建知识空间"
        />
      ) : (
        <>
          {!returnToComparison && <section aria-label="摄取工作流" className="grid cols-5">
            <WorkflowCard icon={<FileText size={18} />} steps={workflows.document} title="文档" />
            <WorkflowCard icon={<ImagePlus size={18} />} steps={workflows.image} title="图片" />
            <WorkflowCard icon={<AudioLines size={18} />} steps={workflows.audio} title="音频" />
            <WorkflowCard icon={<Video size={18} />} steps={workflows.video} title="视频" />
            <WorkflowCard icon={<Code2 size={18} />} steps={workflows.code} title="代码仓库" />
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
              label="选择图片"
              note="OCR、视觉描述和截图分析都以显式媒体任务运行；缺少真实 Provider 时返回明确的 NOT_CONFIGURED 错误。"
              onFile={setImageFile}
              onSubmit={uploadImage}
              spaceId={imageSpaceId}
              spaces={spaces}
              statusLabelText="元数据优先"
              title="图片资料"
              updateSpace={setImageSpaceId}
            />

            <MediaUploadCard
              accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/mp4"
              busy={audioUploading}
              file={audioFile}
              icon={<AudioLines size={26} />}
              label="选择音频"
              note="系统先读取真实时长；转写在任务中心执行，完成后可按精确时间戳跳转。"
              onFile={setAudioFile}
              onSubmit={uploadAudio}
              spaceId={audioSpaceId}
              spaces={spaces}
              statusLabelText="时长"
              title="音频资料"
              updateSpace={setAudioSpaceId}
            />

            <MediaUploadCard
              accept=".mp4,.mov,video/mp4,video/quicktime"
              busy={videoUploading}
              file={videoFile}
              icon={<Video size={26} />}
              label="选择视频"
              note="系统读取真实时长、尺寸和音轨元数据；关键帧与转写由媒体任务处理。"
              onFile={setVideoFile}
              onSubmit={uploadVideo}
              spaceId={videoSpaceId}
              spaces={spaces}
              statusLabelText="元数据"
              title="视频资料"
              updateSpace={setVideoSpaceId}
            />
            </>}
          </section>
        </>
      )}

      {!returnToComparison && <section className="grid cols-4">
        <RecentDocuments documents={documents} />
        <RecentSources sources={imageSources} title="最近图片" />
        <RecentSources sources={audioSources} title="最近音频" />
        <RecentSources sources={videoSources} title="最近视频" />
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
        <label htmlFor={`${title}-space`}>知识空间</label>
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
        <span className="muted">{file ? formatFileSize(file.size) : "选择一个文件以建立可追溯的媒体来源。"}</span>
        <input accept={accept} onChange={(event) => onFile(event.target.files?.[0] || null)} style={{ display: "none" }} type="file" />
      </label>
      <button className="button" disabled={!spaceId || !file || busy} onClick={onSubmit} type="button">
        {busy ? (
          <ButtonLoading label="上传中" />
        ) : (
          <>
            <UploadCloud size={17} />
            上传并创建任务
          </>
        )}
      </button>
    </section>
  );
}

function RecentDocuments({ documents, comparisonMode = false }: { documents: DocumentItem[]; comparisonMode?: boolean }) {
  return (
    <div className="panel stack">
      <h2>{comparisonMode ? "本空间的文档" : "最近文档"}</h2>
      <div className="list">
        {documents.slice(0, 5).map((document) => (
          <Link className="list-item" href={`/documents/${document.id}`} key={document.id}>
            <strong>{document.original_filename}</strong>
            <span className="muted">
              {comparisonMode ? `${document.chunk_count} 个片段 · 处理进度 ${document.processing_progress}%` : `${document.chunk_count} 个片段 · 处理进度 ${document.processing_progress}%`}
            </span>
          </Link>
        ))}
        {documents.length === 0 && <EmptyState
          description={comparisonMode ? "上传三份 txt、md 或 pdf 文档；处理完成后再回工作台选择。" : "上传 txt、md 或 pdf 文件，建立可检索的文档证据。"}
          title="这里还没有文档"
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
        {sources.length === 0 && <EmptyState description="上传后的媒体会连同真实元数据和任务状态显示在这里。" title="暂无来源" />}
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
  if (source.source_type === "image") return `OCR：${statusLabel(metadataString(source, "ocr_status"))}`;
  if (source.source_type === "audio" || source.source_type === "video") {
    return `转写：${statusLabel(metadataString(source, "transcription_status"))}`;
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
