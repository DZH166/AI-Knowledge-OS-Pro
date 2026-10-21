"use client";

import { useEffect, useState } from "react";
import { RefreshCw, ServerCog } from "lucide-react";

import { ButtonLoading, CopyButton, ErrorState, LoadingSkeleton, PageHeader, StatusBadge, TechnicalDetails } from "@/components/ui";
import { api } from "@/services/api";
import type { ComponentStatus, SystemStatus, SystemTestResponse } from "@/types/api";

function humanizeDetailKey(key: string) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function summarizeDetailValue(value: unknown) {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.length ? `已记录 ${value.length} 项` : "无记录";
  if (value && typeof value === "object") return `已记录 ${Object.keys(value).length} 项`;
  return "未记录";
}

function StatusCard({ title, status, action, busy = false }: { title: string; status: ComponentStatus; action?: () => void; busy?: boolean }) {
  return (
    <article className="card stack">
      <div className="row between">
        <h3>{title}</h3>
        <StatusBadge status={status.ok ? "ready" : status.status} label={status.ok ? "正常" : "需要处理"} />
      </div>
      <p>{status.message}</p>
      <p className="muted">{status.ok ? "相关功能可以使用。" : "可能影响上传、检索、任务处理或问答，请按提示修复。"}</p>
      {action && (
        <button className="button secondary small" disabled={busy} onClick={action} type="button">
          {busy ? <ButtonLoading label="检测中" /> : <><RefreshCw size={14} />重新检测</>}
        </button>
      )}
      <TechnicalDetails>
        {Object.entries(status.details || {}).map(([key, value]) => (
          <p key={key}>
            {humanizeDetailKey(key)}: {summarizeDetailValue(value)}
          </p>
        ))}
      </TechnicalDetails>
    </article>
  );
}

function CapabilityMatrix({ status }: { status: SystemStatus }) {
  const items = [
    { name: "文档上传、解析与学习档案", group: "可直接使用", ready: status.db.ok, note: "依赖本地 SQLite；txt/md/pdf 解析不需要付费模型。" },
    { name: "任务中心、重试和取消", group: "需要本地服务", ready: status.redis.ok && status.worker.ok, note: "需要 Redis 和 Worker；没有 Worker 时仍可看到任务记录。" },
    { name: "语义检索与 RAG 引用", group: "需要本地服务", ready: status.qdrant.ok && status.collection.ok && status.embedding.ok, note: "需要 Qdrant 与真实 Embedding Provider。" },
    { name: "真实问答", group: "需要真实 Provider", ready: status.llm.ok, note: "需要 LLM API Key；未配置时明确拒绝，不生成假回答。" },
    { name: "图片 OCR / 视觉描述", group: "需要真实 Provider", ready: status.ocr.ok, note: "需要 OCR/vision Provider；未配置时返回 OCR_NOT_CONFIGURED。" },
    { name: "音频/视频转写", group: "需要真实 Provider", ready: status.transcription.ok, note: "需要 speech-to-text Provider；未配置时返回 TRANSCRIPTION_NOT_CONFIGURED。" },
    { name: "视频关键帧", group: "需要本地服务", ready: true, note: "需要 FFmpeg/imageio-ffmpeg；Demo 可展示合成关键帧时间线。" },
    { name: "Demo 展示数据", group: "Demo 可展示", ready: status.runtime.runtime_mode === "demo", note: "Demo 数据是合成样例，不冒充真实模型输出。" },
    { name: "字幕导出和镜头级分割", group: "尚未实现", ready: false, note: "保留在路线图中，不在 README 中宣称已完成。" }
  ];
  const groups = ["可直接使用", "需要本地服务", "需要真实 Provider", "Demo 可展示", "尚未实现"];
  return (
    <section className="panel stack">
      <h2>能力可用性</h2>
      <p className="muted">按真实依赖划分能力，避免把 Demo 流程误解成零配置 AI 能力。</p>
      <div className="grid cols-3">
        {groups.map((group) => (
          <article className="card stack" key={group}>
            <h3>{group}</h3>
            {items
              .filter((item) => item.group === group)
              .map((item) => (
                <div className="stack compact" key={item.name}>
                  <div className="row between">
                    <strong>{item.name}</strong>
                    <StatusBadge status={item.ready ? "ready" : "pending"} label={item.ready ? "可用" : "需配置"} />
                  </div>
                  <p className="muted">{item.note}</p>
                </div>
              ))}
          </article>
        ))}
      </div>
    </section>
  );
}

function ProviderDiagnostics({ status }: { status: SystemStatus }) {
  const checks = [
    {
      name: "Redis / Worker",
      status: status.redis.ok && status.worker.ok,
      impact: "任务中心、媒体处理、重试和取消",
      fix: "启动 Redis，并运行 Worker 进程；没有 Worker 时任务记录仍可查看，但不会自动处理。",
      env: "REDIS_URL=redis://localhost:6379/0"
    },
    {
      name: "Qdrant",
      status: status.qdrant.ok && status.collection.ok,
      impact: "Embedding 入库、语义检索和 RAG 引用召回",
      fix: "启动 Qdrant，并确认 collection 名称与当前索引版本一致。",
      env: "QDRANT_URL=http://localhost:6333"
    },
    {
      name: "LLM Provider",
      status: status.llm.ok,
      impact: "真实问答、项目解释和面试表达生成",
      fix: "配置兼容 OpenAI 的 LLM provider。未配置时系统必须明确拒绝，不生成假回答。",
      env: "LLM_API_KEY=<your-llm-api-key>"
    },
    {
      name: "Embedding Provider",
      status: status.embedding.ok,
      impact: "真实语义索引和检索",
      fix: "配置 embedding provider。未配置时真实索引会被阻止，避免写入假向量。",
      env: "EMBEDDING_API_KEY=<your-embedding-api-key>"
    },
    {
      name: "OCR / Vision Provider",
      status: status.ocr.ok,
      impact: "图片 OCR、截图报错识别和关键帧视觉理解",
      fix: "配置 OCR 或 vision provider。未配置时返回 OCR_NOT_CONFIGURED 类错误。",
      env: "OCR_API_KEY=<your-ocr-api-key>"
    },
    {
      name: "Speech-to-Text Provider",
      status: status.transcription.ok,
      impact: "音频/视频真实转写和时间戳 citation",
      fix: "配置 transcription provider。未配置时返回 TRANSCRIPTION_NOT_CONFIGURED，不生成假字幕。",
      env: "TRANSCRIPTION_API_KEY=<your-transcription-api-key>"
    }
  ];
  const notReady = checks.filter((item) => !item.status);

  return (
    <section className="panel stack">
      <div className="row between wrap">
        <div>
          <h2>能力配置向导</h2>
          <p className="muted">按影响面说明当前缺什么、怎么修，以及哪些能力需要真实 Provider。</p>
        </div>
        <span className={notReady.length ? "pill gold" : "pill"}>{notReady.length ? `${notReady.length} 项需处理` : "全部就绪"}</span>
      </div>
      <div className="grid cols-3">
        {checks.map((item) => (
          <article className="card stack" key={item.name}>
            <div className="row between">
              <h3>{item.name}</h3>
              <StatusBadge status={item.status ? "ready" : "pending"} label={item.status ? "可用" : "需配置"} />
            </div>
            <p>{item.impact}</p>
            <p className="muted">{item.fix}</p>
            <div className="row between wrap">
              <code>{item.env.split("=")[0]}</code>
              <CopyButton label="复制示例" value={item.env} />
            </div>
          </article>
        ))}
      </div>
      <p className="quote">Demo 模式只展示工作流和合成数据；真实模式缺少 Provider 时必须明确返回 NOT_CONFIGURED 类错误。</p>
    </section>
  );
}

export default function SystemPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [testResult, setTestResult] = useState<SystemTestResponse | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [testing, setTesting] = useState(false);

  async function load() {
    setError("");
    setRefreshing(true);
    try {
      setStatus(await api.systemStatus());
      await api.updateOnboarding({ steps: { system_check: true } });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function runTest(fn: () => Promise<SystemTestResponse>) {
    setTesting(true);
    setError("");
    try {
      setTestResult(await fn());
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "检测失败");
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="系统"
        title="模型与服务"
        description="用人话查看数据库、Redis、Worker、Qdrant、LLM、Embedding 和索引状态。密钥不会返回到前端。"
        action={
          <button className="button" disabled={refreshing} onClick={load} type="button">
            {refreshing ? <ButtonLoading label="刷新中" /> : <><RefreshCw size={17} />刷新</>}
          </button>
        }
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {!status ? (
        <LoadingSkeleton lines={6} />
      ) : (
        <>
          <section className="panel stack">
            <div className="row">
              <ServerCog size={18} />
              <h2>当前运行模式</h2>
            </div>
            <div className="status-line">
              <StatusBadge status={status.runtime.runtime_mode} />
              <span className="pill gray">{status.runtime.app_version} / {status.runtime.semantic_version}</span>
              <span className="pill gray">{status.runtime.llm_provider} / {status.runtime.llm_model}</span>
              <span className="pill gray">{status.runtime.embedding_provider} / {status.runtime.embedding_model}</span>
              <span className="pill gray">{status.runtime.ocr_provider} / {status.runtime.ocr_model}</span>
              <span className="pill gray">{status.runtime.transcription_provider} / {status.runtime.transcription_model}</span>
              <span className="pill gray">{status.runtime.index_version}</span>
              <span className="pill gray">Redis {status.runtime.task_queue_name}</span>
            </div>
            <TechnicalDetails title="运行配置">
              <p>数据库：{status.runtime.database_url}</p>
              <p>Qdrant：{status.runtime.qdrant_url}</p>
              <p>Collection：{status.runtime.qdrant_collection}</p>
              <p>Redis：{status.runtime.redis_url}</p>
              <p>Worker 队列：{status.runtime.worker_queues}</p>
            </TechnicalDetails>
            {status.warnings.map((warning) => (
              <p className="quote" key={warning}>
                {warning}
              </p>
            ))}
          </section>
          <section className="grid cols-3">
            <StatusCard title="数据库" status={status.db} />
            <StatusCard title="Redis 任务队列" status={status.redis} />
            <StatusCard title="Worker 心跳" status={status.worker} />
            <StatusCard title="向量数据库" status={status.qdrant} action={() => runTest(api.testQdrant)} busy={testing} />
            <StatusCard title="Collection" status={status.collection} />
            <StatusCard title="AI 回答服务" status={status.llm} action={() => runTest(api.testLlm)} busy={testing} />
            <StatusCard title="知识检索模型" status={status.embedding} action={() => runTest(api.testEmbedding)} busy={testing} />
            <StatusCard title="图片 OCR" status={status.ocr} />
            <StatusCard title="音频转写" status={status.transcription} />
            <StatusCard title="文档索引" status={status.index} />
          </section>
          <CapabilityMatrix status={status} />
          <ProviderDiagnostics status={status} />
          {testResult && <span className={testResult.ok ? "pill" : "pill rose"}>{testResult.message}</span>}
        </>
      )}
    </div>
  );
}
