import json
import re

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import IndexIncompatibleError
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_space import KnowledgeSpace
from app.models.qa_log import QALog
from app.models.source import IndexRevision, Source, SourceRevision
from app.schemas.chat_schema import ChatResponse, Citation, RelatedChunk
from app.services.embedding_service import EmbeddingService
from app.services.hybrid_retriever import HybridRetriever
from app.services.ingestion_service import ingestion_service
from app.services.llm_service import LLMService
from app.services.prompt_builder import PromptBuilder
from app.services.rerank_provider import get_rerank_provider
from app.services.vector_store import VectorStore


class RAGService:
    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()
        self.prompt_builder = PromptBuilder()
        self.llm_service = LLMService()
        self.rerank_provider = get_rerank_provider()

    def ingest_document(
        self,
        db: Session,
        space_id: int,
        upload_file: UploadFile,
        *,
        process_immediately: bool = True,
    ) -> tuple[Document, int]:
        document, job = ingestion_service.ingest_upload(
            db=db,
            space_id=space_id,
            upload_file=upload_file,
            process_immediately=process_immediately,
        )
        return document, job.id

    def ask_question(
        self,
        db: Session,
        space_id: int,
        question: str,
        answer_mode: str,
        *,
        retrieval_query: str | None = None,
    ) -> ChatResponse:
        """Answer one question; retrieval_query may carry prior-turn context.

        The user-visible question stays unchanged so citations and history never
        pretend the follow-up was rewritten. Only embedding and keyword search
        use the context-expanded query.
        """
        space = db.get(KnowledgeSpace, space_id)
        if space is None:
            raise ValueError("知识库不存在。")

        ready_documents = list(
            db.scalars(
                select(Document).where(
                    Document.space_id == space_id,
                    Document.status == "ready",
                    Document.vector_status == "indexed",
                )
            )
        )
        persisted_chunk_document_ids = set(
            db.scalars(
                select(Chunk.document_id).where(Chunk.space_id == space_id).distinct()
            )
        )
        ready_multimodal_indexes = list(
            db.scalars(
                select(IndexRevision)
                .join(SourceRevision, IndexRevision.revision_id == SourceRevision.id)
                .join(Source, IndexRevision.source_id == Source.id)
                .where(
                    Source.space_id == space_id,
                    IndexRevision.status == "active",
                    IndexRevision.point_count > 0,
                )
            )
        )
        if not ready_documents and not ready_multimodal_indexes:
            return self._save_and_return_refusal(
                db=db,
                space_id=space.id,
                question=question,
                answer_mode=answer_mode,
                retrieval_status="no_ready_documents",
                answer="当前知识库还没有完成索引的文档或多模态资料，暂时无法基于资料回答。请先上传资料并等待处理完成。",
            )

        current_fingerprint = self.embedding_service.fingerprint()
        incompatible = [
            document
            for document in ready_documents
            if document.embedding_fingerprint != current_fingerprint or document.index_version != settings.index_version
        ]
        incompatible_multimodal = [
            index_revision
            for index_revision in ready_multimodal_indexes
            if index_revision.embedding_fingerprint != current_fingerprint or index_revision.index_version != settings.index_version
        ]
        if incompatible or incompatible_multimodal:
            raise IndexIncompatibleError(
                "当前 Embedding 配置或索引版本与已有资料不兼容，请对文档或多模态资料执行重建索引。",
                details={
                    "current_fingerprint": current_fingerprint,
                    "index_version": settings.index_version,
                    "document_ids": [document.id for document in incompatible],
                    "source_ids": [index_revision.source_id for index_revision in incompatible_multimodal],
                },
            )

        effective_query = (retrieval_query or question).strip() or question
        query_vector = self.embedding_service.embed_query(effective_query)
        hits = HybridRetriever(vector_store=self.vector_store, rerank_provider=self.rerank_provider).search(
            db,
            space_id=space.id,
            query=effective_query,
            query_vector=query_vector,
            limit=settings.retrieval_top_k,
            score_threshold=settings.retrieval_score_threshold,
        )
        if not hits:
            documents_missing_chunks = [document for document in ready_documents if document.id not in persisted_chunk_document_ids]
            if documents_missing_chunks and not ready_multimodal_indexes:
                return self._save_and_return_refusal(
                    db=db,
                    space_id=space.id,
                    question=question,
                    answer_mode=answer_mode,
                    retrieval_status="insufficient_context",
                    answer=(
                        "资料记录存在，但可检索片段尚未准备好。请在任务中心或文档详情中重新处理这些资料，"
                        "确认解析、切片和索引完成后再提问。"
                    ),
                )
            return self._save_and_return_refusal(
                db=db,
                space_id=space.id,
                question=question,
                answer_mode=answer_mode,
                retrieval_status="insufficient_context",
                answer=(
                    "当前资料不足以回答这个问题。系统已经检索该知识库，但没有找到超过相似度阈值的片段。"
                    "建议补充更相关的资料，或换一个更贴近已上传资料的问题。"
                ),
            )
        hits = sorted(hits, key=lambda hit: (-hit.score, self._payload_position(hit.payload)))

        citations: list[Citation] = []
        related_chunks: list[RelatedChunk] = []
        contexts: list[str] = []

        for index, hit in enumerate(hits, start=1):
            payload = hit.payload
            chunk_id = int(payload.get("chunk_id", 0))
            chunk_index = int(payload.get("chunk_index", 0))
            document_name = str(payload.get("document_name", "未知文档"))
            content = str(payload.get("content", ""))
            content_preview = str(payload.get("content_preview", content[:220]))
            page_number = self._optional_int(payload.get("page_number"))
            heading_path = self._optional_str(payload.get("heading_path"))
            section_title = self._optional_str(payload.get("section_title"))
            source_type = self._optional_str(payload.get("source_type"))
            source_id = self._optional_int(payload.get("source_id"))
            document_id = self._optional_int(payload.get("document_id"))
            modality = self._optional_str(payload.get("modality"))
            start_ms = self._optional_int(payload.get("start_ms"))
            end_ms = self._optional_int(payload.get("end_ms"))
            dense_score = self._optional_float(payload.get("dense_score"))
            keyword_score = self._optional_float(payload.get("keyword_score"))
            rerank_score = self._optional_float(payload.get("rerank_score"))
            final_score = self._optional_float(payload.get("final_score")) or round(hit.score, 4)
            retrieval_reason = self._optional_str(payload.get("retrieval_reason"))
            citation_ready = bool(payload.get("citation_ready", True))
            file_path = self._optional_str(payload.get("file_path"))
            line_start = self._optional_int(payload.get("line_start"))
            line_end = self._optional_int(payload.get("line_end"))
            symbol_name = self._optional_str(payload.get("symbol_name"))
            citation_id = f"[{index}]"

            citations.append(
                Citation(
                    citation_id=citation_id,
                    document_name=document_name,
                    chunk_id=chunk_id,
                    chunk_index=chunk_index,
                    content_preview=content_preview,
                    score=round(hit.score, 4),
                    page_number=page_number,
                    heading_path=heading_path,
                    section_title=section_title,
                    source_type=source_type,
                    source_id=source_id,
                    document_id=document_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    dense_score=dense_score,
                    keyword_score=keyword_score,
                    rerank_score=rerank_score,
                    final_score=final_score,
                    retrieval_reason=retrieval_reason,
                    citation_ready=citation_ready,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    symbol_name=symbol_name,
                )
            )
            related_chunks.append(
                RelatedChunk(
                    chunk_id=chunk_id,
                    document_name=document_name,
                    content=content,
                    score=round(hit.score, 4),
                    page_number=page_number,
                    heading_path=heading_path,
                    section_title=section_title,
                    source_type=source_type,
                    source_id=source_id,
                    document_id=document_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    dense_score=dense_score,
                    keyword_score=keyword_score,
                    rerank_score=rerank_score,
                    final_score=final_score,
                    retrieval_reason=retrieval_reason,
                    citation_ready=citation_ready,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    symbol_name=symbol_name,
                )
            )
            location = []
            if file_path:
                line_text = f":{line_start}-{line_end}" if line_start and line_end else ""
                location.append(f"{file_path}{line_text}")
            if symbol_name:
                location.append(symbol_name)
            if page_number:
                location.append(f"第 {page_number} 页")
            if heading_path:
                location.append(heading_path)
            if source_type == "image":
                location.append("图片 OCR")
            if modality:
                location.append(modality)
            if start_ms is not None:
                location.append(self._format_timestamp(start_ms))
            location_text = f"（{' / '.join(location)}）" if location else ""
            contexts.append(f"{citation_id} 文档：{document_name}{location_text} / chunk #{chunk_index}\n{content}")

        system_prompt, user_prompt = self.prompt_builder.build(
            question=question,
            contexts=contexts,
            answer_mode=answer_mode,  # type: ignore[arg-type]
        )
        answer = self.llm_service.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        used_citation_ids = self._extract_used_citations(answer, citations)

        retrieval_score = round(max(hit.score for hit in hits), 4)
        retrieval_status = "success"
        answer_confidence = self._confidence(retrieval_score)
        if not used_citation_ids:
            retrieval_status = "citation_validation_failed"
            answer_confidence = "low"
            answer = (
                f"{answer.rstrip()}\n\n"
                "引用校验提示：本次回答没有使用可验证的引用编号，因此系统不会把任何检索片段标记为已引用。"
            )

        response = ChatResponse(
            answer=answer,
            citations=citations,
            used_citation_ids=used_citation_ids,
            related_chunks=related_chunks,
            answer_confidence=answer_confidence,
            retrieval_score=retrieval_score,
            retrieval_status=retrieval_status,
            runtime_mode=settings.runtime_mode,
            retrieval_query=effective_query if effective_query != question else None,
            qa_log_id=0,
        )
        response.qa_log_id = self._save_qa_log(db, space.id, question, answer_mode, response)
        return response

    def list_history(self, db: Session, space_id: int | None = None) -> list[QALog]:
        stmt = select(QALog).order_by(QALog.created_at.desc())
        if space_id is not None:
            stmt = stmt.where(QALog.space_id == space_id)
        return list(db.scalars(stmt).all())

    def _save_and_return_refusal(
        self,
        db: Session,
        space_id: int,
        question: str,
        answer_mode: str,
        retrieval_status: str,
        answer: str,
    ) -> ChatResponse:
        response = ChatResponse(
            answer=answer,
            citations=[],
            used_citation_ids=[],
            related_chunks=[],
            answer_confidence="low",
            retrieval_score=None,
            retrieval_status=retrieval_status,
            runtime_mode=settings.runtime_mode,
            qa_log_id=0,
        )
        response.qa_log_id = self._save_qa_log(db, space_id, question, answer_mode, response)
        return response

    def _save_qa_log(
        self,
        db: Session,
        space_id: int,
        question: str,
        answer_mode: str,
        response: ChatResponse,
    ) -> int:
        qa_log = QALog(
            space_id=space_id,
            question=question,
            answer=response.answer,
            answer_mode=answer_mode,
            citations_json=json.dumps([citation.model_dump() for citation in response.citations], ensure_ascii=False),
            related_chunks_json=json.dumps([chunk.model_dump() for chunk in response.related_chunks], ensure_ascii=False),
            used_citation_ids_json=json.dumps(response.used_citation_ids, ensure_ascii=False),
            answer_confidence=response.answer_confidence,
            retrieval_score=response.retrieval_score,
            retrieval_status=response.retrieval_status,
            runtime_mode=response.runtime_mode,
        )
        db.add(qa_log)
        db.commit()
        db.refresh(qa_log)
        return qa_log.id

    @staticmethod
    def _extract_used_citations(answer: str, citations: list[Citation]) -> list[str]:
        available = {citation.citation_id for citation in citations}
        used = [f"[{match}]" for match in re.findall(r"\[(\d+)\]", answer)]
        return [citation_id for citation_id in dict.fromkeys(used) if citation_id in available]

    @staticmethod
    def _confidence(score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.45:
            return "medium"
        return "low"

    @staticmethod
    def _optional_int(value) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_str(value) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _optional_float(value) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _payload_position(cls, payload: dict) -> int:
        for key in ("start_ms", "page_number", "chunk_index"):
            value = cls._optional_int(payload.get(key))
            if value is not None:
                return value
        return 0

    @staticmethod
    def _format_timestamp(milliseconds: int) -> str:
        total_seconds = max(0, milliseconds // 1000)
        return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"



rag_service = RAGService()
