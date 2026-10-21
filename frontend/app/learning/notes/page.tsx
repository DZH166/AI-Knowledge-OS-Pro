"use client";

import { useEffect, useState } from "react";
import { NotebookPen, Plus } from "lucide-react";

import { EmptyState, ErrorState, PageHeader } from "@/components/ui";
import { api, formatDate } from "@/services/api";
import type { LearningNote } from "@/types/api";

export default function LearningNotesPage() {
  const [notes, setNotes] = useState<LearningNote[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setError("");
    try {
      setNotes(await api.learningNotes());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载笔记失败。");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createNote() {
    if (!title.trim() || !content.trim()) {
      setError("请填写标题和内容。");
      return;
    }
    await api.createLearningNote({ title, content, tags: ["manual"] });
    setTitle("");
    setContent("");
    setMessage("笔记已保存。");
    await load();
  }

  return (
    <div className="page">
      <PageHeader eyebrow="学习成长" title="学习笔记" description="记录复盘、调试发现和面试表达草稿，让学习资料从来源证据继续沉淀。" />
      {error && <ErrorState message={error} onRetry={load} />}
      {message && <span className="pill">{message}</span>}
      <section className="grid cols-2">
        <div className="panel stack">
          <div className="row">
            <Plus size={18} />
            <h2>新建笔记</h2>
          </div>
          <input className="input" onChange={(event) => setTitle(event.target.value)} placeholder="笔记标题" value={title} />
          <textarea className="textarea" onChange={(event) => setContent(event.target.value)} placeholder="写下你的复盘、问题或面试表达" rows={8} value={content} />
          <button className="button" onClick={createNote} type="button">
            <NotebookPen size={17} />
            保存笔记
          </button>
        </div>
        <div className="panel stack">
          <h2>全部笔记</h2>
          <div className="list">
            {notes.length === 0 ? (
              <EmptyState title="暂无笔记" description="可以手动记录，也可以从知识点、问答或媒体证据生成笔记。" />
            ) : (
              notes.map((note) => (
                <article className="list-item" key={note.id}>
                  <strong>{note.title}</strong>
                  <p>{note.content}</p>
                  <span className="muted">{formatDate(note.updated_at)} / {note.tags.join(", ") || "未标记"}</span>
                </article>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
