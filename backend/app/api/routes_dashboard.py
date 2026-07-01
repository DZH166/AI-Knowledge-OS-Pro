import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import Document
from app.models.knowledge_space import KnowledgeSpace
from app.models.qa_log import QALog
from app.schemas.chat_schema import QALogRead
from app.schemas.dashboard_schema import DashboardSummary
from app.services.learning_log_service import learning_log_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    recent_documents = list(db.scalars(select(Document).order_by(Document.created_at.desc()).limit(5)).all())
    recent_qa_models = list(db.scalars(select(QALog).order_by(QALog.created_at.desc()).limit(5)).all())
    learning_logs = learning_log_service.list_logs(db)

    return DashboardSummary(
        knowledge_space_count=int(db.scalar(select(func.count()).select_from(KnowledgeSpace)) or 0),
        document_count=int(db.scalar(select(func.count()).select_from(Document)) or 0),
        qa_count=int(db.scalar(select(func.count()).select_from(QALog)) or 0),
        recent_documents=recent_documents,
        recent_qa=[
            QALogRead(
                id=log.id,
                space_id=log.space_id,
                question=log.question,
                answer=log.answer,
                answer_mode=log.answer_mode,
                citations=json.loads(log.citations_json or "[]"),
                used_citation_ids=json.loads(getattr(log, "used_citation_ids_json", "[]") or "[]"),
                related_chunks=json.loads(log.related_chunks_json or "[]"),
                answer_confidence=getattr(log, "answer_confidence", "unknown"),
                retrieval_score=getattr(log, "retrieval_score", None),
                retrieval_status=getattr(log, "retrieval_status", "unknown"),
                runtime_mode=getattr(log, "runtime_mode", "real"),
                created_at=log.created_at,
            )
            for log in recent_qa_models
        ],
        current_version="V3.8: GitHub portfolio demo docs and reset workflow",
        current_capabilities=[
            "Real/demo mode governance with explicit NOT_CONFIGURED provider errors",
            "Document and media jobs share the durable Task Center",
            "Image OCR, screenshot archive, audio/video transcription and video keyframe pipelines",
            "RAG citations include document IDs, source IDs and media timestamps",
            "Media detail pages support player seek, transcript highlights and keyframe browsing",
            "Learning artifacts are generated only from real document or multimodal chunks",
        ],
        recent_learning_log=learning_logs[0] if learning_logs else None,
        next_step_suggestion=(
            "Next, focus on subtitle export, richer video scene segmentation and provider diagnostics "
            "without weakening real-mode boundaries."
        ),
    )
