"use client";

import Link from "next/link";
import { Settings } from "lucide-react";

import { PageHeader } from "@/components/ui";

export default function SettingsPage() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="系统"
        title="设置"
        description="集中说明本地配置、Demo 模式、Provider Key 安全和发布边界。真实密钥只应写入被忽略的环境文件或 secret manager。"
        action={
          <Link className="button" href="/system">
            <Settings size={17} />
            查看服务状态
          </Link>
        }
      />
      <section className="grid cols-2">
        <article className="panel stack">
          <h2>配置入口</h2>
          <p>当前项目通过环境变量配置数据库、Redis、Qdrant 和 Provider。不要在 GitHub、截图或文档里写真实 Key。</p>
          <div className="list">
            <Link className="list-item" href="/system">模型与服务状态</Link>
            <article className="list-item">
              <strong>环境变量文档</strong>
              <span className="muted">docs/environment_variables.md</span>
            </article>
            <article className="list-item">
              <strong>Provider 诊断文档</strong>
              <span className="muted">docs/provider_diagnostics.md</span>
            </article>
          </div>
        </article>
        <article className="panel stack">
          <h2>安全边界</h2>
          <p>Demo 模式使用合成数据展示工作流；真实模式缺少 Provider 时必须明确拒绝，不生成假回答、假 OCR 或假转写。</p>
          <p className="quote">发布包必须排除 `.env`、数据库、uploads、logs、node_modules、.next 和缓存。</p>
        </article>
      </section>
    </div>
  );
}
