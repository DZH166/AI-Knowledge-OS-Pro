import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.learning_log import LearningLog
from app.schemas.learning_schema import LearningLogCreate, LearningLogRead


class LearningLogService:
    def list_logs(self, db: Session) -> list[LearningLogRead]:
        logs = db.scalars(select(LearningLog).order_by(LearningLog.created_at.desc())).all()
        return [self.to_read(log) for log in logs]

    def get_log(self, db: Session, slug: str) -> LearningLogRead | None:
        log = db.scalar(select(LearningLog).where(LearningLog.slug == slug))
        return self.to_read(log) if log else None

    def create_log(self, db: Session, payload: LearningLogCreate, commit: bool = True) -> LearningLogRead:
        existing = db.scalar(select(LearningLog).where(LearningLog.slug == payload.slug))
        if existing is not None:
            return self.to_read(existing)

        data = payload.model_dump()
        markdown_content = data.get("markdown_content") or self.render_markdown(data)
        log = LearningLog(
            version_name=payload.version_name,
            slug=payload.slug,
            summary=payload.summary,
            implemented_features_json=json.dumps(data["implemented_features"], ensure_ascii=False),
            major_files_json=json.dumps([item.model_dump() if hasattr(item, "model_dump") else item for item in data["major_files"]], ensure_ascii=False),
            knowledge_points_json=json.dumps(
                [item.model_dump() if hasattr(item, "model_dump") else item for item in data["knowledge_points"]],
                ensure_ascii=False,
            ),
            focus=payload.focus,
            review_suggestions=payload.review_suggestions,
            interview_expression=payload.interview_expression,
            next_version_suggestion=payload.next_version_suggestion,
            markdown_content=markdown_content,
        )
        db.add(log)
        if commit:
            db.commit()
            db.refresh(log)
        self.append_markdown_once(payload.slug, markdown_content)
        return self.to_read(log)

    def to_read(self, log: LearningLog) -> LearningLogRead:
        return LearningLogRead(
            id=log.id,
            version_name=log.version_name,
            slug=log.slug,
            summary=log.summary,
            implemented_features=json.loads(log.implemented_features_json or "[]"),
            major_files=json.loads(log.major_files_json or "[]"),
            knowledge_points=json.loads(log.knowledge_points_json or "[]"),
            focus=log.focus,
            review_suggestions=log.review_suggestions,
            interview_expression=log.interview_expression,
            next_version_suggestion=log.next_version_suggestion,
            markdown_content=log.markdown_content,
            created_at=log.created_at,
        )

    def render_markdown(self, data: dict[str, Any]) -> str:
        major_files = [item.model_dump() if hasattr(item, "model_dump") else item for item in data["major_files"]]
        knowledge_points = [
            item.model_dump() if hasattr(item, "model_dump") else item for item in data["knowledge_points"]
        ]
        lines = [
            f"<!-- slug:{data['slug']} -->",
            f"## {data['version_name']}",
            "",
            "### 版本总结",
            data["summary"],
            "",
            "### 本版本实现了什么",
        ]
        lines.extend([f"- {item}" for item in data["implemented_features"]])
        lines.extend(["", "### 本版本新增或修改的主要文件"])
        lines.extend([f"- `{item['path']}`：{item['responsibility']}" for item in major_files])
        lines.extend(["", "### 本版本涉及的 AI 应用开发知识点"])
        for point in knowledge_points:
            code_locations = point.get("code_locations") or []
            lines.extend(
                [
                    f"#### {point['name']}",
                    f"- 小白解释：{point['beginner_explanation']}",
                    f"- 项目用法：{point['project_usage']}",
                    f"- 代码位置：{', '.join(code_locations) if code_locations else '见本版本主要文件'}",
                    f"- 后续补课：{point['review_suggestion']}",
                    f"- 面试表达：{point['interview_expression']}",
                    "",
                ]
            )
        lines.extend(
            [
                "### 我应该重点理解什么",
                data["focus"],
                "",
                "### 下一步应该学什么",
                data["review_suggestions"],
                "",
                "### 面试表达方式",
                data["interview_expression"],
                "",
                "### 下一版本学习重点",
                data["next_version_suggestion"],
                "",
            ]
        )
        return "\n".join(lines)

    def append_markdown_once(self, slug: str, markdown_content: str) -> None:
        path = settings.learning_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else "# AI Knowledge OS Pro 学习档案\n\n"
        if f"<!-- slug:{slug} -->" in existing:
            return
        separator = "\n" if existing.endswith("\n") else "\n\n"
        path.write_text(existing + separator + markdown_content.strip() + "\n", encoding="utf-8")


learning_log_service = LearningLogService()
