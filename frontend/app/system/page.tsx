"use client";

import { useEffect, useState } from "react";
import { RefreshCw, ServerCog } from "lucide-react";

import { ErrorState, LoadingSkeleton, PageHeader, StatusBadge, TechnicalDetails } from "@/components/ui";
import { api } from "@/services/api";
import type { ComponentStatus, SystemStatus, SystemTestResponse } from "@/types/api";

function StatusCard({ title, status, action }: { title: string; status: ComponentStatus; action?: () => void }) {
  return (
    <article className="card stack">
      <div className="row between">
        <h3>{title}</h3>
        <StatusBadge status={status.ok ? "ready" : status.status} label={status.ok ? "正常" : "需要处理"} />
      </div>
      <p>{status.message}</p>
      <p className="muted">{status.ok ? "相关功能可以使用。" : "可能影响上传、检索、任务处理或问答，请按提示修复。"}</p>
      {action && (
        <button className="button secondary small" onClick={action} type="button">
          <RefreshCw size={14} />
          重新检测
        </button>
      )}
      <TechnicalDetails>
        {Object.entries(status.details || {}).map(([key, value]) => (
          <p key={key}>
            {key}: {typeof value === "object" ? JSON.stringify(value) : String(value)}
          </p>
        ))}
      </TechnicalDetails>
    </article>
  );
}

export default function SystemPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [testResult, setTestResult] = useState<SystemTestResponse | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setStatus(await api.systemStatus());
      await api.updateOnboarding({ steps: { system_check: true } });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function runTest(fn: () => Promise<SystemTestResponse>) {
    setTestResult(await fn());
    await load();
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="系统"
        title="模型与服务"
        description="用人话查看数据库、Redis、Worker、Qdrant、LLM、Embedding 和索引状态。密钥不会返回到前端。"
        action={
          <button className="button" onClick={load} type="button">
            <RefreshCw size={17} />
            刷新
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
            <StatusCard title="向量数据库" status={status.qdrant} action={() => runTest(api.testQdrant)} />
            <StatusCard title="Collection" status={status.collection} />
            <StatusCard title="AI 回答服务" status={status.llm} action={() => runTest(api.testLlm)} />
            <StatusCard title="知识检索模型" status={status.embedding} action={() => runTest(api.testEmbedding)} />
            <StatusCard title="图片 OCR" status={status.ocr} />
            <StatusCard title="音频转写" status={status.transcription} />
            <StatusCard title="文档索引" status={status.index} />
          </section>
          {testResult && <span className={testResult.ok ? "pill" : "pill rose"}>{testResult.message}</span>}
        </>
      )}
    </div>
  );
}
