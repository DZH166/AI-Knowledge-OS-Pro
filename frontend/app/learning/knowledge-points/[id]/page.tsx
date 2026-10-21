"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { ButtonLoading, ErrorState, LoadingSkeleton, PageHeader, StatusBadge } from "@/components/ui";
import { api, statusLabel } from "@/services/api";
import type { LearningKnowledgePoint } from "@/types/api";

export default function KnowledgePointDetailPage() {
  const params = useParams<{ id: string }>();
  const pointId = Number(params.id);
  const [point, setPoint] = useState<LearningKnowledgePoint | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try { setPoint(await api.knowledgePoint(pointId)); } catch (exc) { setError(exc instanceof Error ? exc.message : "加载失败"); }
  }, [pointId]);
  useEffect(() => { load(); }, [load]);

  async function updateStatus(mastery_status: string) {
    setSaving(true);
    try {
      setPoint(await api.updateKnowledgePointProgress(pointId, { mastery_status, note: note.trim() || undefined }));
      setNote("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <PageHeader eyebrow="知识点" title={point?.name || "知识点详情"} description="围绕小白解释、项目用法、代码位置、补课建议和面试表达进行复习。" />
      {error && <ErrorState message={error} onRetry={load} />}
      {!point ? <LoadingSkeleton lines={7} /> : (
        <>
          <section className="panel stack">
            <div className="row between"><h2>{point.name}</h2><StatusBadge status={point.mastery_status} label={statusLabel(point.mastery_status)} /></div>
            <p><strong>小白解释：</strong>{point.beginner_explanation}</p>
            <p><strong>项目用法：</strong>{point.project_usage}</p>
            <p><strong>补课建议：</strong>{point.review_suggestion}</p>
            <p><strong>面试表达：</strong>{point.interview_expression}</p>
          </section>
          <section className="grid cols-2">
            <div className="panel">
              <h2>代码位置</h2>
              <div className="list">{point.code_locations?.map((location) => <div className="list-item" key={location}>{location}</div>)}</div>
            </div>
            <div className="panel stack">
              <h2>学习笔记</h2>
              <textarea className="textarea" onChange={(event) => setNote(event.target.value)} placeholder="写下你哪里懂了、哪里还模糊。" value={note} />
              <div className="row wrap">
                <button className="button secondary small" disabled={saving} onClick={() => updateStatus("learning")} type="button">学习中</button>
                <button className="button secondary small" disabled={saving} onClick={() => updateStatus("understood")} type="button">已理解</button>
                <button className="button secondary small" disabled={saving} onClick={() => updateStatus("review_needed")} type="button">待复习</button>
                <button className="button small" disabled={saving} onClick={() => updateStatus("mastered")} type="button">{saving ? <ButtonLoading label="保存中" /> : "已掌握"}</button>
              </div>
              {point.notes && <p className="quote pre-wrap">{point.notes}</p>}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
