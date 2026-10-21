from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.chat_session import ChatMessage, ChatSession
from app.models.knowledge_space import KnowledgeSpace
from app.schemas.chat_schema import (
    ChatFavoriteResponse,
    ChatMessageRead,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionMessageCreate,
    ChatSessionRead,
    ChatSessionUpdate,
)
from app.services.rag_service import rag_service


class ChatSessionService:
    def create_session(self, db: Session, payload: ChatSessionCreate) -> ChatSessionRead:
        if db.get(KnowledgeSpace, payload.space_id) is None:
            raise ValueError("知识库不存在。")
        session = ChatSession(
            space_id=payload.space_id,
            title=payload.title or "新的知识问答",
            answer_mode=payload.answer_mode,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return self.to_read(session)

    def list_sessions(self, db: Session, space_id: int | None = None) -> list[ChatSessionRead]:
        stmt = (
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.is_archived == False)  # noqa: E712
            .order_by(ChatSession.updated_at.desc())
        )
        if space_id is not None:
            stmt = stmt.where(ChatSession.space_id == space_id)
        return [self.to_read(session) for session in db.scalars(stmt).all()]

    def get_session(self, db: Session, session_id: int) -> ChatSessionRead | None:
        session = db.scalar(
            select(ChatSession).options(selectinload(ChatSession.messages)).where(ChatSession.id == session_id)
        )
        return self.to_read(session) if session else None

    def update_session(self, db: Session, session_id: int, payload: ChatSessionUpdate) -> ChatSessionRead:
        session = db.get(ChatSession, session_id)
        if session is None:
            raise ValueError("会话不存在。")
        if payload.title is not None:
            session.title = payload.title
        if payload.answer_mode is not None:
            session.answer_mode = payload.answer_mode
        if payload.is_archived is not None:
            session.is_archived = payload.is_archived
        db.commit()
        db.refresh(session)
        return self.to_read(session)

    def delete_session(self, db: Session, session_id: int) -> None:
        session = db.get(ChatSession, session_id)
        if session is None:
            raise ValueError("会话不存在。")
        db.delete(session)
        db.commit()

    def ask_in_session(self, db: Session, session_id: int, payload: ChatSessionMessageCreate) -> ChatResponse:
        session = db.get(ChatSession, session_id)
        if session is None:
            raise ValueError("会话不存在。")
        answer_mode = payload.answer_mode or session.answer_mode
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=payload.question,
            answer_mode=answer_mode,
        )
        db.add(user_message)
        db.flush()

        response = rag_service.ask_question(
            db=db,
            space_id=session.space_id,
            question=payload.question,
            answer_mode=answer_mode,
        )
        assistant_message = self._message_from_response(session.id, response, answer_mode)
        db.add(assistant_message)
        if session.title == "新的知识问答":
            session.title = payload.question[:60]
        session.answer_mode = answer_mode
        db.commit()
        return response

    def regenerate_message(self, db: Session, message_id: int) -> ChatResponse:
        message = db.get(ChatMessage, message_id)
        if message is None or message.role != "assistant":
            raise ValueError("只能重新生成 AI 回答。")
        previous_user = db.scalar(
            select(ChatMessage)
            .where(ChatMessage.session_id == message.session_id, ChatMessage.role == "user", ChatMessage.id < message.id)
            .order_by(ChatMessage.id.desc())
        )
        if previous_user is None:
            raise ValueError("没有找到可重新生成的问题。")
        return self.ask_in_session(
            db,
            message.session_id,
            ChatSessionMessageCreate(question=previous_user.content, answer_mode=message.answer_mode or "normal"),
        )

    def favorite_message(self, db: Session, message_id: int) -> ChatFavoriteResponse:
        message = db.get(ChatMessage, message_id)
        if message is None:
            raise ValueError("消息不存在。")
        message.is_favorite = not message.is_favorite
        db.commit()
        return ChatFavoriteResponse(message_id=message.id, is_favorite=message.is_favorite)

    def to_read(self, session: ChatSession) -> ChatSessionRead:
        messages = sorted(session.messages, key=lambda item: item.created_at) if session.messages else []
        return ChatSessionRead(
            id=session.id,
            space_id=session.space_id,
            title=session.title,
            answer_mode=session.answer_mode,
            is_archived=session.is_archived,
            messages=[self.message_to_read(message) for message in messages],
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    def message_to_read(self, message: ChatMessage) -> ChatMessageRead:
        return ChatMessageRead(
            id=message.id,
            session_id=message.session_id,
            qa_log_id=message.qa_log_id,
            role=message.role,
            content=message.content,
            answer_mode=message.answer_mode,
            citations=json.loads(message.citations_json or "[]"),
            used_citation_ids=json.loads(message.used_citation_ids_json or "[]"),
            related_chunks=json.loads(message.related_chunks_json or "[]"),
            retrieval_status=message.retrieval_status,
            answer_confidence=message.answer_confidence,
            is_favorite=message.is_favorite,
            created_at=message.created_at,
        )

    @staticmethod
    def _message_from_response(session_id: int, response: ChatResponse, answer_mode: str) -> ChatMessage:
        return ChatMessage(
            session_id=session_id,
            qa_log_id=response.qa_log_id,
            role="assistant",
            content=response.answer,
            answer_mode=answer_mode,
            citations_json=json.dumps([citation.model_dump() for citation in response.citations], ensure_ascii=False),
            used_citation_ids_json=json.dumps(response.used_citation_ids, ensure_ascii=False),
            related_chunks_json=json.dumps([chunk.model_dump() for chunk in response.related_chunks], ensure_ascii=False),
            retrieval_status=response.retrieval_status,
            answer_confidence=response.answer_confidence,
        )


chat_session_service = ChatSessionService()
