from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.learning_artifact import LearningArtifact
from app.models.learning_note import LearningNote
from app.models.learning_system import KnowledgePoint, LearningCard, QuizQuestion
from app.models.source import MultimodalChunk, Source
from app.schemas.learning_schema import LearningArtifactBatchResponse, LearningArtifactCreate, LearningArtifactRead


class LearningArtifactService:
    def create_from_source(self, db: Session, payload: LearningArtifactCreate) -> LearningArtifactBatchResponse:
        evidence = self._load_evidence(db, payload)
        title = payload.title or evidence["title"]
        content = evidence["content"]
        locator = evidence["locator"]
        knowledge_point: KnowledgePoint | None = None
        artifacts: list[LearningArtifact] = []

        for artifact_type in dict.fromkeys(payload.artifact_types):
            artifact = LearningArtifact(
                artifact_type=artifact_type,
                title=title,
                content=content,
                source_id=evidence["source_id"],
                document_id=evidence["document_id"],
                chunk_id=evidence["chunk_id"],
                document_chunk_id=evidence["document_chunk_id"],
                locator_json=json.dumps(locator, ensure_ascii=False),
            )
            if artifact_type == "knowledge_point":
                knowledge_point = KnowledgePoint(
                    package_id=None,
                    name=title,
                    beginner_explanation=content,
                    project_usage=f"来源定位：{self._locator_text(locator)}",
                    code_locations_json="[]",
                    review_suggestion="回到原始资料定位处复述要点，并用自己的项目例子验证理解。",
                    interview_expression=self._interview_expression(title, content, locator),
                    mastery_status="not_started",
                    notes="由真实资料片段生成。",
                )
                db.add(knowledge_point)
                db.flush()
                artifact.knowledge_point_id = knowledge_point.id
            elif artifact_type == "card":
                card = LearningCard(
                    package_id=None,
                    knowledge_point_id=knowledge_point.id if knowledge_point else None,
                    front=f"{title} 的核心内容是什么？",
                    back=content,
                    mastery_status="unclear",
                    difficulty="normal",
                )
                db.add(card)
                db.flush()
                artifact.card_id = card.id
            elif artifact_type == "quiz":
                answer = self._first_sentence(content, 180)
                quiz = QuizQuestion(
                    package_id=None,
                    knowledge_point_id=knowledge_point.id if knowledge_point else None,
                    question="以下哪项是该来源片段中实际出现的内容？",
                    options_json=json.dumps(
                        [
                            answer,
                            "该资料片段未提供这一信息。",
                            "需要脱离当前来源才能确认。",
                            "仅凭文件名即可得出结论。",
                        ],
                        ensure_ascii=False,
                    ),
                    correct_answer=answer,
                    explanation=f"正确答案直接来自原始资料：{self._locator_text(locator)}",
                )
                db.add(quiz)
                db.flush()
                artifact.quiz_id = quiz.id
            elif artifact_type == "note":
                note = LearningNote(
                    title=title,
                    content=f"{content}\n\n来源：{self._locator_text(locator)}",
                    tags_json=json.dumps(["多模态资料", evidence["source_type"]], ensure_ascii=False),
                    knowledge_point_id=knowledge_point.id if knowledge_point else None,
                    document_id=evidence["document_id"],
                    version_slug="v3-6-unified-multimodal-learning",
                )
                db.add(note)
                db.flush()
                artifact.note_id = note.id
            elif artifact_type == "interview_expression":
                artifact.content = self._interview_expression(title, content, locator)
            db.add(artifact)
            db.flush()
            artifacts.append(artifact)

        db.commit()
        for artifact in artifacts:
            db.refresh(artifact)
        return LearningArtifactBatchResponse(
            artifacts=[LearningArtifactRead.model_validate(artifact) for artifact in artifacts],
            message=f"已从真实来源生成 {len(artifacts)} 项学习资料。",
        )

    def _load_evidence(self, db: Session, payload: LearningArtifactCreate) -> dict:
        if bool(payload.source_id) == bool(payload.document_id):
            raise ValueError("source_id 和 document_id 必须且只能提供一个。")
        if payload.source_id:
            source = db.get(Source, payload.source_id)
            if source is None:
                raise ValueError("媒体资料不存在。")
            stmt = select(MultimodalChunk).where(
                MultimodalChunk.source_id == source.id,
                MultimodalChunk.status == "active",
            )
            if payload.chunk_id:
                stmt = stmt.where(MultimodalChunk.id == payload.chunk_id)
            else:
                stmt = stmt.where(MultimodalChunk.revision_id == source.active_revision_id).order_by(MultimodalChunk.chunk_index).limit(5)
            chunks = list(db.scalars(stmt))
            content = "\n\n".join(chunk.content_text.strip() for chunk in chunks if chunk.content_text.strip())
            if not content:
                content = str(source.metadata_data.get("vision_description") or "").strip()
            if not content:
                raise ValueError("当前媒体资料还没有可用于生成学习资料的真实文本，请先完成 OCR、视觉描述或转写。")
            chunk = chunks[0] if len(chunks) == 1 else None
            locator = self._chunk_locator(chunk) if chunk else {"source_id": source.id, "type": source.source_type}
            return {
                "title": source.title or source.original_filename or f"媒体资料 #{source.id}",
                "content": self._compact(content),
                "locator": locator,
                "source_id": source.id,
                "document_id": None,
                "chunk_id": chunk.id if chunk else None,
                "document_chunk_id": None,
                "source_type": source.source_type,
            }

        document = db.get(Document, payload.document_id)
        if document is None:
            raise ValueError("文档不存在。")
        stmt = select(Chunk).where(Chunk.document_id == document.id)
        if payload.chunk_id:
            stmt = stmt.where(Chunk.id == payload.chunk_id)
        else:
            stmt = stmt.order_by(Chunk.chunk_index).limit(5)
        chunks = list(db.scalars(stmt))
        content = "\n\n".join(chunk.content.strip() for chunk in chunks if chunk.content.strip())
        if not content:
            raise ValueError("当前文档还没有可用于生成学习资料的真实片段。")
        chunk = chunks[0] if len(chunks) == 1 else None
        locator = {
            "document_id": document.id,
            "page_number": chunk.page_number if chunk else None,
            "heading_path": chunk.heading_path if chunk else None,
            "chunk_id": chunk.id if chunk else None,
        }
        return {
            "title": document.title or document.original_filename,
            "content": self._compact(content),
            "locator": locator,
            "source_id": None,
            "document_id": document.id,
            "chunk_id": None,
            "document_chunk_id": chunk.id if chunk else None,
            "source_type": document.file_type,
        }

    @staticmethod
    def _chunk_locator(chunk: MultimodalChunk | None) -> dict:
        if chunk is None:
            return {}
        try:
            value = json.loads(chunk.locator_json or "{}")
        except json.JSONDecodeError:
            value = {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _compact(text: str, limit: int = 2400) -> str:
        compact = re.sub(r"[ \t]+", " ", text).strip()
        return compact if len(compact) <= limit else compact[:limit].rstrip() + "..."

    @staticmethod
    def _first_sentence(text: str, limit: int) -> str:
        sentence = re.split(r"(?<=[。！？.!?])\s*", text.strip(), maxsplit=1)[0]
        return sentence[:limit].rstrip() or text[:limit].rstrip()

    @staticmethod
    def _locator_text(locator: dict) -> str:
        if locator.get("page_number"):
            return f"第 {locator['page_number']} 页"
        if locator.get("heading_path"):
            return str(locator["heading_path"])
        if locator.get("start_ms") is not None:
            seconds = max(0, int(locator["start_ms"]) // 1000)
            return f"{seconds // 60:02d}:{seconds % 60:02d}"
        if locator.get("source_id"):
            return f"媒体资料 #{locator['source_id']}"
        if locator.get("document_id"):
            return f"文档 #{locator['document_id']}"
        return "来源片段"

    @classmethod
    def _interview_expression(cls, title: str, content: str, locator: dict) -> str:
        return (
            f"在 AI Knowledge OS Pro 中，我把《{title}》的真实资料片段沉淀为可追溯学习资产。"
            f"证据定位在{cls._locator_text(locator)}，核心内容是：{cls._first_sentence(content, 320)}"
        )


learning_artifact_service = LearningArtifactService()
