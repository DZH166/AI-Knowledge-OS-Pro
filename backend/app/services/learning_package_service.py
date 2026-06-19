from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.learning_note import LearningNote
from app.models.learning_system import KnowledgePoint, LearningCard, LearningProgress, QuizQuestion, VersionLearningPackage
from app.schemas.learning_schema import (
    KnowledgePointNoteCreate,
    KnowledgePointProgressUpdate,
    KnowledgePointRead,
    LearningCardProgressUpdate,
    LearningCardRead,
    LearningDashboard,
    LearningLogCreate,
    LearningNoteCreate,
    LearningNoteRead,
    LearningNoteUpdate,
    LearningPackageCreate,
    LearningPackageRead,
    MarkdownExportResponse,
    QuizAnswerResponse,
    QuizQuestionRead,
)
from app.services.learning_log_service import learning_log_service


class LearningPackageService:
    def generate_draft(self, db: Session) -> LearningPackageRead:
        payload = self._load_generated_draft() or self._fallback_v3_6_draft()
        existing = self._get_package_model(db, payload.slug)
        if existing is not None:
            return self.to_read(existing)
        package = self._create_package_model(db, payload, status="draft")
        db.commit()
        db.refresh(package)
        return self.to_read(package)

    def create_package(self, db: Session, payload: LearningPackageCreate) -> LearningPackageRead:
        existing = self._get_package_model(db, payload.slug)
        if existing is not None:
            return self.to_read(existing)
        package = self._create_package_model(db, payload, status="draft")
        db.commit()
        db.refresh(package)
        return self.to_read(package)

    def update_package(self, db: Session, slug: str, payload: LearningPackageCreate) -> LearningPackageRead:
        package = self._get_package_model(db, slug)
        if package is None:
            raise ValueError("Learning package not found.")
        if package.status == "confirmed":
            raise ValueError("Confirmed learning packages cannot be edited.")
        data = payload.model_dump()
        package.version_name = payload.version_name
        package.slug = payload.slug
        package.summary = payload.summary
        package.implemented_features_json = json.dumps(data["implemented_features"], ensure_ascii=False)
        package.major_files_json = json.dumps(data["major_files"], ensure_ascii=False)
        package.focus = payload.focus
        package.review_suggestions = payload.review_suggestions
        package.interview_expression = payload.interview_expression
        package.next_version_suggestion = payload.next_version_suggestion
        package.markdown_content = payload.markdown_content or learning_log_service.render_markdown(data)
        db.commit()
        db.refresh(package)
        return self.to_read(package)

    def list_packages(self, db: Session) -> list[LearningPackageRead]:
        packages = db.scalars(
            select(VersionLearningPackage)
            .options(selectinload(VersionLearningPackage.knowledge_points))
            .order_by(VersionLearningPackage.created_at.desc())
        ).all()
        return [self.to_read(package) for package in packages]

    def get_package(self, db: Session, slug: str) -> LearningPackageRead | None:
        package = self._get_package_model(db, slug)
        return self.to_read(package) if package else None

    def confirm_package(self, db: Session, slug: str) -> LearningPackageRead:
        package = self._get_package_model(db, slug)
        if package is None:
            raise ValueError("Learning package not found.")
        if package.status != "confirmed":
            package.status = "confirmed"
            package.confirmed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(package)

        learning_log_service.create_log(
            db,
            LearningLogCreate(
                version_name=package.version_name,
                slug=package.slug,
                summary=package.summary,
                implemented_features=package.implemented_features,
                major_files=package.major_files,
                knowledge_points=[self._point_to_payload(point) for point in package.knowledge_points],
                focus=package.focus,
                review_suggestions=package.review_suggestions,
                interview_expression=package.interview_expression,
                next_version_suggestion=package.next_version_suggestion,
                markdown_content=package.markdown_content,
            ),
        )
        self._append_stage_delivery_once(package.slug)
        return self.to_read(package)

    def dashboard(self, db: Session) -> LearningDashboard:
        points = list(db.scalars(select(KnowledgePoint)).all())
        cards = list(db.scalars(select(LearningCard)).all())
        mastered = [point for point in points if point.mastery_status in {"mastered", "understood", "know"}]
        review_needed = [point for point in points if point.mastery_status in {"review_needed", "unknown", "unclear", "reviewing"}]
        learning = [point for point in points if point.mastery_status in {"learning", "not_started"}]
        due_cards = [card for card in cards if card.mastery_status in {"unknown", "unclear", "reviewing"}]
        next_lesson = learning[0].name if learning else (review_needed[0].name if review_needed else "继续上传资料并生成新的知识点")
        return LearningDashboard(
            current_version="V3.6",
            total_knowledge_points=len(points),
            mastered_count=len(mastered),
            learning_count=len(learning),
            review_needed_count=len(review_needed),
            due_card_count=len(due_cards),
            quiz_count=db.query(QuizQuestion).count(),
            note_count=db.query(LearningNote).count(),
            next_lesson=next_lesson,
        )

    def list_knowledge_points(self, db: Session) -> list[KnowledgePointRead]:
        points = db.scalars(select(KnowledgePoint).order_by(KnowledgePoint.created_at.desc())).all()
        return [self.point_to_read(point) for point in points]

    def get_knowledge_point(self, db: Session, point_id: int) -> KnowledgePointRead | None:
        point = db.get(KnowledgePoint, point_id)
        return self.point_to_read(point) if point else None

    def update_progress(self, db: Session, point_id: int, payload: KnowledgePointProgressUpdate) -> KnowledgePointRead:
        point = db.get(KnowledgePoint, point_id)
        if point is None:
            raise ValueError("Knowledge point not found.")
        point.mastery_status = payload.mastery_status
        note = payload.note or ""
        if note:
            point.notes = (point.notes + "\n" + note).strip() if point.notes else note
        db.add(LearningProgress(knowledge_point_id=point.id, mastery_status=payload.mastery_status, note=note))
        db.commit()
        db.refresh(point)
        return self.point_to_read(point)

    def add_note(self, db: Session, point_id: int, payload: KnowledgePointNoteCreate) -> KnowledgePointRead:
        point = db.get(KnowledgePoint, point_id)
        if point is None:
            raise ValueError("Knowledge point not found.")
        point.notes = (point.notes + "\n" + payload.note).strip() if point.notes else payload.note
        db.commit()
        db.refresh(point)
        return self.point_to_read(point)

    def list_cards(self, db: Session) -> list[LearningCardRead]:
        cards = db.scalars(select(LearningCard).order_by(LearningCard.created_at.desc())).all()
        return [LearningCardRead.model_validate(card, from_attributes=True) for card in cards]

    def update_card_progress(self, db: Session, card_id: int, payload: LearningCardProgressUpdate) -> LearningCardRead:
        return self.review_card(db, card_id, payload)

    def review_card(self, db: Session, card_id: int, payload: LearningCardProgressUpdate) -> LearningCardRead:
        card = db.get(LearningCard, card_id)
        if card is None:
            raise ValueError("Learning card not found.")
        card.mastery_status = payload.mastery_status
        card.last_reviewed_at = datetime.now(timezone.utc)
        card.review_count = (card.review_count or 0) + 1
        if payload.mastery_status in {"unknown", "unclear", "reviewing"}:
            card.difficulty = "hard" if payload.mastery_status == "unknown" else "normal"
            linked_status = "review_needed"
        else:
            linked_status = payload.mastery_status
        if card.knowledge_point_id:
            point = db.get(KnowledgePoint, card.knowledge_point_id)
            if point is not None:
                point.mastery_status = linked_status
                db.add(
                    LearningProgress(
                        knowledge_point_id=point.id,
                        mastery_status=linked_status,
                        note=f"学习卡片 #{card.id} 复习结果：{payload.mastery_status}",
                    )
                )
        db.commit()
        db.refresh(card)
        return LearningCardRead.model_validate(card, from_attributes=True)

    def list_quizzes(self, db: Session) -> list[QuizQuestionRead]:
        quizzes = db.scalars(select(QuizQuestion).order_by(QuizQuestion.created_at.desc())).all()
        return [
            QuizQuestionRead(
                id=quiz.id,
                package_id=quiz.package_id,
                knowledge_point_id=quiz.knowledge_point_id,
                question=quiz.question,
                options=quiz.options,
                explanation=None,
            )
            for quiz in quizzes
        ]

    def answer_quiz(self, db: Session, quiz_id: int, answer: str) -> QuizAnswerResponse:
        quiz = db.get(QuizQuestion, quiz_id)
        if quiz is None:
            raise ValueError("Quiz question not found.")
        normalized_answer = answer.strip()
        correct = normalized_answer == quiz.correct_answer
        if quiz.knowledge_point_id and not correct:
            point = db.get(KnowledgePoint, quiz.knowledge_point_id)
            if point is not None:
                point.mastery_status = "review_needed"
                db.add(
                    LearningProgress(
                        knowledge_point_id=point.id,
                        mastery_status="review_needed",
                        note=f"练习题 #{quiz.id} 答错，加入待复习。",
                    )
                )
                db.commit()
        return QuizAnswerResponse(correct=correct, correct_answer=quiz.correct_answer, explanation=quiz.explanation)

    def list_notes(self, db: Session) -> list[LearningNoteRead]:
        notes = db.scalars(select(LearningNote).order_by(LearningNote.created_at.desc())).all()
        return [self.note_to_read(note) for note in notes]

    def create_note(self, db: Session, payload: LearningNoteCreate) -> LearningNoteRead:
        note = LearningNote(
            title=payload.title,
            content=payload.content,
            tags_json=json.dumps(payload.tags, ensure_ascii=False),
            knowledge_point_id=payload.knowledge_point_id,
            document_id=payload.document_id,
            qa_log_id=payload.qa_log_id,
            version_slug=payload.version_slug,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return self.note_to_read(note)

    def update_note(self, db: Session, note_id: int, payload: LearningNoteUpdate) -> LearningNoteRead:
        note = db.get(LearningNote, note_id)
        if note is None:
            raise ValueError("Learning note not found.")
        if payload.title is not None:
            note.title = payload.title
        if payload.content is not None:
            note.content = payload.content
        if payload.tags is not None:
            note.tags_json = json.dumps(payload.tags, ensure_ascii=False)
        db.commit()
        db.refresh(note)
        return self.note_to_read(note)

    def delete_note(self, db: Session, note_id: int) -> None:
        note = db.get(LearningNote, note_id)
        if note is None:
            raise ValueError("Learning note not found.")
        db.delete(note)
        db.commit()

    def export_markdown(self, db: Session) -> MarkdownExportResponse:
        confirmed = db.scalars(select(VersionLearningPackage).where(VersionLearningPackage.status == "confirmed")).all()
        for package in confirmed:
            learning_log_service.append_markdown_once(package.slug, package.markdown_content)
        return MarkdownExportResponse(markdown="\n\n".join(package.markdown_content for package in confirmed), message="已导出确认过的学习包。")

    def to_read(self, package: VersionLearningPackage) -> LearningPackageRead:
        return LearningPackageRead(
            id=package.id,
            version_name=package.version_name,
            slug=package.slug,
            status=package.status,
            summary=package.summary,
            implemented_features=package.implemented_features,
            major_files=package.major_files,
            knowledge_points=[self._point_to_payload(point) for point in package.knowledge_points],
            focus=package.focus,
            review_suggestions=package.review_suggestions,
            interview_expression=package.interview_expression,
            next_version_suggestion=package.next_version_suggestion,
            markdown_content=package.markdown_content,
            created_at=package.created_at,
            confirmed_at=package.confirmed_at,
        )

    def point_to_read(self, point: KnowledgePoint) -> KnowledgePointRead:
        return KnowledgePointRead(
            id=point.id,
            package_id=point.package_id,
            name=point.name,
            beginner_explanation=point.beginner_explanation,
            project_usage=point.project_usage,
            code_locations=point.code_locations,
            review_suggestion=point.review_suggestion,
            interview_expression=point.interview_expression,
            mastery_status=point.mastery_status,
            notes=point.notes,
            created_at=point.created_at,
            updated_at=point.updated_at,
        )

    def note_to_read(self, note: LearningNote) -> LearningNoteRead:
        try:
            tags = json.loads(note.tags_json or "[]")
        except json.JSONDecodeError:
            tags = []
        return LearningNoteRead(
            id=note.id,
            title=note.title,
            content=note.content,
            tags=tags if isinstance(tags, list) else [],
            knowledge_point_id=note.knowledge_point_id,
            document_id=note.document_id,
            qa_log_id=note.qa_log_id,
            version_slug=note.version_slug,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    def _create_package_model(self, db: Session, payload: LearningPackageCreate, status: str) -> VersionLearningPackage:
        data = payload.model_dump()
        markdown_content = data.get("markdown_content") or learning_log_service.render_markdown(data)
        package = VersionLearningPackage(
            version_name=payload.version_name,
            slug=payload.slug,
            status=status,
            summary=payload.summary,
            implemented_features_json=json.dumps(data["implemented_features"], ensure_ascii=False),
            major_files_json=json.dumps(data["major_files"], ensure_ascii=False),
            focus=payload.focus,
            review_suggestions=payload.review_suggestions,
            interview_expression=payload.interview_expression,
            next_version_suggestion=payload.next_version_suggestion,
            markdown_content=markdown_content,
        )
        db.add(package)
        db.flush()
        for point_payload in payload.knowledge_points:
            point = KnowledgePoint(
                package_id=package.id,
                name=point_payload.name,
                beginner_explanation=point_payload.beginner_explanation,
                project_usage=point_payload.project_usage,
                code_locations_json=json.dumps(point_payload.code_locations, ensure_ascii=False),
                review_suggestion=point_payload.review_suggestion,
                interview_expression=point_payload.interview_expression,
            )
            db.add(point)
            db.flush()
            db.add(
                LearningCard(
                    package_id=package.id,
                    knowledge_point_id=point.id,
                    front=f"{point.name} 在 AI Knowledge OS Pro 中解决什么问题？",
                    back=point.project_usage,
                )
            )
            db.add(
                QuizQuestion(
                    package_id=package.id,
                    knowledge_point_id=point.id,
                    question=f"关于「{point.name}」，哪种说法更符合本项目？",
                    options_json=json.dumps(
                        [
                            "它是本版本真实使用到的工程能力",
                            "它只用于页面装饰",
                            "它会覆盖历史学习档案",
                        ],
                        ensure_ascii=False,
                    ),
                    correct_answer="它是本版本真实使用到的工程能力",
                    explanation=point.project_usage,
                )
            )
        return package

    def _get_package_model(self, db: Session, slug: str) -> VersionLearningPackage | None:
        return db.scalar(
            select(VersionLearningPackage)
            .options(selectinload(VersionLearningPackage.knowledge_points))
            .where(VersionLearningPackage.slug == slug)
        )

    @staticmethod
    def _point_to_payload(point: KnowledgePoint) -> dict[str, Any]:
        return {
            "name": point.name,
            "beginner_explanation": point.beginner_explanation,
            "project_usage": point.project_usage,
            "code_locations": point.code_locations,
            "review_suggestion": point.review_suggestion,
            "interview_expression": point.interview_expression,
        }

    def _append_stage_delivery_once(self, slug: str) -> None:
        path = settings.docs_dir / "stage_delivery_log.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else "# AI Knowledge OS Pro 阶段交付记录\n\n"
        marker = f"<!-- stage:{slug}:confirmed -->"
        if marker in existing:
            return
        if slug == "v3-6-unified-media-learning":
            entry = (
                f"\n{marker}\n"
                "## V3.6 阶段交付确认：统一多模态任务中心与来源学习资产\n\n"
                "- 已确认 V3.6 学习包，并追加到 `docs/learning_log.md`。\n"
                "- 本阶段包含统一文档/媒体任务中心、媒体引用跳转、播放器联动、多关键帧和来源学习资产。\n"
                "- 阶段结尾要求：保留历史学习记录，并生成 V3.6 release zip 与 sha256。\n"
            )
        else:
            entry = (
                f"\n{marker}\n"
                "## V2.5 阶段交付：产品化交互、任务可视化与学习闭环\n\n"
                "- 已确认 V2.5 学习包，并追加到 `docs/learning_log.md`。\n"
                "- 本阶段包含信息架构、任务化文档处理、引用校验、多轮会话、学习笔记和卡片复习。\n"
                "- 阶段结尾要求：保留教学记录，并生成 V2.5 release zip 与 sha256。\n"
            )
        path.write_text(existing.rstrip() + "\n\n" + entry.strip() + "\n", encoding="utf-8")

    def _load_generated_draft(self) -> LearningPackageCreate | None:
        for filename in ("v3_6_learning_package_draft.json", "v3_learning_package_draft.json"):
            path = settings.docs_dir / filename
            if not path.exists():
                continue
            try:
                return LearningPackageCreate(**json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return None

    def _fallback_v3_6_draft(self) -> LearningPackageCreate:
        return LearningPackageCreate(
            version_name="V3.6: unified multimodal tasks and source-based learning artifacts",
            slug="v3-6-unified-media-learning",
            summary="V3.6 turns the multimodal prototype into a stable task-driven learning system for documents, images, audio and video.",
            implemented_features=[
                "Unified document and media tasks in Task Center",
                "Media task retry, cancel, progress and result links",
                "Citation deep links for document chunks and media timestamps",
                "Multi-keyframe video timeline with OCR and visual-description tasks",
                "Learning artifacts generated from real source chunks only",
            ],
            major_files=[
                {"path": "backend/app/services/media_task_service.py", "responsibility": "Media task orchestration and recovery."},
                {"path": "backend/app/services/learning_artifact_service.py", "responsibility": "Source-based learning artifact creation."},
                {"path": "frontend/app/media/sources/[id]/page.tsx", "responsibility": "Media player, transcript, keyframe and learning interactions."},
            ],
            knowledge_points=[
                {
                    "name": "Unified multimodal task model",
                    "beginner_explanation": "Documents and media can use the same durable job/event structure when processing takes time.",
                    "project_usage": "V3.6 uses target_type, source_id and document_id so Task Center can manage both document and media processing.",
                    "code_locations": ["backend/app/models/ingestion_job.py", "backend/app/services/media_task_service.py"],
                    "review_suggestion": "Review job state machines, retry/cancel behavior and event logs.",
                    "interview_expression": "I unified document and media processing into one observable task engine, so failures can be recovered consistently.",
                },
                {
                    "name": "Source-based learning artifacts",
                    "beginner_explanation": "Cards and notes are trustworthy only when they link back to real evidence.",
                    "project_usage": "LearningArtifact records preserve source_id, document_id, chunk_id and locator_json for generated study material.",
                    "code_locations": ["backend/app/models/learning_artifact.py", "backend/app/services/learning_artifact_service.py"],
                    "review_suggestion": "Review audit tables, locators and deterministic generation from existing chunks.",
                    "interview_expression": "I generate learning material only from real source chunks, avoiding fake notes from empty media.",
                },
            ],
            focus="Understand how V3.6 connects task orchestration, evidence navigation and learning artifacts around real source chunks.",
            review_suggestions="Review unified tasks, media processing, citation links, player synchronization, keyframes, learning artifacts and release verification.",
            interview_expression="In V3.6 I unified image, audio and video processing under Task Center, made citations jump to evidence, and created learning assets only from real chunks.",
            next_version_suggestion="Add subtitle export, richer scene segmentation and stronger provider diagnostics.",
        )


learning_package_service = LearningPackageService()
