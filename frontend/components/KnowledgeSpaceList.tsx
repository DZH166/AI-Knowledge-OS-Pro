import Link from "next/link";
import { BookOpen, MessageSquare, UploadCloud } from "lucide-react";

import { EmptyState } from "@/components/ui";
import { formatDate } from "@/services/api";
import type { KnowledgeSpace } from "@/types/api";

export function KnowledgeSpaceList({ spaces }: { spaces: KnowledgeSpace[] }) {
  if (spaces.length === 0) {
    return <EmptyState title="还没有知识库" description="先创建一个知识库空间，用来承载你的项目资料和学习记录。" />;
  }

  return (
    <div className="grid cols-2">
      {spaces.map((space) => (
        <article className="card stack" key={space.id}>
          <div>
            <h3>{space.name}</h3>
            <p className="muted">{space.description || "未填写用途说明"}</p>
          </div>
          <div className="status-line">
            <span className="pill">
              <BookOpen size={14} />
              {space.document_count ?? 0} 文档
            </span>
            <span className="pill gray">{space.chunk_count ?? 0} 片段</span>
            <span className="pill gold">{space.qa_count ?? 0} 问答</span>
          </div>
          <p className="muted">创建于 {formatDate(space.created_at)}</p>
          <div className="row wrap">
            <Link className="button secondary" href={`/upload?space_id=${space.id}`}>
              <UploadCloud size={16} />
              上传资料
            </Link>
            <Link className="button secondary" href={`/chat?space_id=${space.id}`}>
              <MessageSquare size={16} />
              开始提问
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
