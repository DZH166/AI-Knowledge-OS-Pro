"use client";

import { useEffect, useState } from "react";
import { Plus } from "lucide-react";

import { KnowledgeSpaceList } from "@/components/KnowledgeSpaceList";
import { ButtonLoading, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/services/api";
import type { KnowledgeSpace } from "@/types/api";

export default function KnowledgePage() {
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function load() {
    setError("");
    try {
      setSpaces(await api.listSpaces());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  }

  useEffect(() => { load(); }, []);

  async function createSpace(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    setIsSaving(true);
    try {
      await api.createSpace({ name: name.trim(), description: description.trim() || undefined });
      setName("");
      setDescription("");
      await load();
      await api.updateOnboarding({ steps: { create_space: true } });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "创建失败");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="page">
      <PageHeader eyebrow="知识管理" title="知识库" description="按项目或主题创建知识库空间，让上传资料、问答历史和学习沉淀归属清楚。" />
      {error && <ErrorState message={error} onRetry={load} />}
      <form className="panel stack" onSubmit={createSpace}>
        <h2>创建知识库</h2>
        <div className="grid cols-2">
          <div className="field"><label htmlFor="name">名称</label><input className="input" id="name" onChange={(event) => setName(event.target.value)} placeholder="例如：RAG 项目学习资料" value={name} /></div>
          <div className="field"><label htmlFor="description">用途</label><input className="input" id="description" onChange={(event) => setDescription(event.target.value)} placeholder="例如：记录 AI 应用开发项目资料" value={description} /></div>
        </div>
        <button className="button" disabled={!name.trim() || isSaving} type="submit">{isSaving ? <ButtonLoading label="创建中" /> : <><Plus size={17} />创建知识库</>}</button>
      </form>
      <KnowledgeSpaceList spaces={spaces} />
    </div>
  );
}
