import { GraduationCap } from "lucide-react";

import type { LearningLog, LearningPackage } from "@/types/api";

type LogLike = LearningLog | LearningPackage;

export function LearningLogPanel({ log }: { log: LogLike }) {
  return (
    <div className="stack">
      <section className="panel">
        <div className="row">
          <GraduationCap size={20} />
          <h2>{log.version_name}</h2>
        </div>
        <p className="lead">{log.summary}</p>
      </section>
      <section className="panel">
        <h2>本版本实现功能</h2>
        <div className="list">
          {log.implemented_features.map((feature) => (
            <div className="list-item" key={feature}>
              {feature}
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>涉及知识点</h2>
        <div className="grid cols-2">
          {log.knowledge_points.map((point) => (
            <article className="card stack" key={point.name}>
              <h3>{point.name}</h3>
              <p><strong>小白解释：</strong>{point.beginner_explanation}</p>
              <p><strong>项目用法：</strong>{point.project_usage}</p>
              <p><strong>补课建议：</strong>{point.review_suggestion}</p>
              <p><strong>面试表达：</strong>{point.interview_expression}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="grid cols-3">
        <article className="card"><h3>重点理解</h3><p>{log.focus}</p></article>
        <article className="card"><h3>后续补课</h3><p>{log.review_suggestions}</p></article>
        <article className="card"><h3>下一版本</h3><p>{log.next_version_suggestion}</p></article>
      </section>
    </div>
  );
}
