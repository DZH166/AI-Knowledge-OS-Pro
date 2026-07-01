import Link from "next/link";
import { TimerReset } from "lucide-react";

import { PageHeader, TechnicalDetails } from "@/components/ui";

export default function ObservabilityPage() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="系统"
        title="可观测性"
        description="整理 V4.0 需要持续追踪的 request_id、task_id、generation_id、retrieval_trace_id 和错误代码，不把日志细节堆到普通页面。"
        action={
          <Link className="button" href="/system">
            <TimerReset size={17} />
            模型与服务
          </Link>
        }
      />
      <section className="grid cols-2">
        <article className="panel stack">
          <h2>已落地线索</h2>
          <div className="list">
            <article className="list-item">
              <strong>request_id</strong>
              <p>后端响应 envelope 和错误处理链路已经携带请求标识，便于定位接口失败。</p>
            </article>
            <article className="list-item">
              <strong>task_id</strong>
              <p>任务中心围绕 ingestion job 展示状态、进度、事件、错误和恢复建议。</p>
            </article>
            <article className="list-item">
              <strong>retrieval_trace_id</strong>
              <p>作为 V4.0 混合检索和 RAG 质量报告的预留追踪字段，当前不伪造检索 trace。</p>
            </article>
          </div>
        </article>
        <article className="panel stack">
          <h2>后续接入</h2>
          <p>下一步会把 provider latency、token usage、retrieval count、citation validation status 和 task duration 接到统一技术详情面板。</p>
          <TechnicalDetails title="技术字段">
            <p>generation_id / provider_latency_ms / token_usage / dense_score / keyword_score / rerank_score / citation_validity</p>
          </TechnicalDetails>
        </article>
      </section>
    </div>
  );
}
