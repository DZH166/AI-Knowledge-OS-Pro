import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.db.session import get_db
from app.schemas.chat_schema import (
    ChatFavoriteResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionMessageCreate,
    ChatSessionRead,
    ChatSessionUpdate,
    QALogRead,
)
from app.services.chat_session_service import chat_session_service
from app.services.rag_service import rag_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask", response_model=ChatResponse)
def ask_question(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        return rag_service.ask_question(
            db=db,
            space_id=payload.space_id,
            question=payload.question,
            answer_mode=payload.answer_mode,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"RAG request failed: {exc}") from exc


@router.get("/history", response_model=list[QALogRead])
def list_history(space_id: int | None = None, db: Session = Depends(get_db)) -> list[QALogRead]:
    logs = rag_service.list_history(db=db, space_id=space_id)
    return [
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
        for log in logs
    ]


@router.post("/sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: ChatSessionCreate, db: Session = Depends(get_db)) -> ChatSessionRead:
    try:
        return chat_session_service.create_session(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[ChatSessionRead])
def list_sessions(space_id: int | None = None, db: Session = Depends(get_db)) -> list[ChatSessionRead]:
    return chat_session_service.list_sessions(db, space_id=space_id)


@router.get("/sessions/{session_id}", response_model=ChatSessionRead)
def get_session(session_id: int, db: Session = Depends(get_db)) -> ChatSessionRead:
    session = chat_session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")
    return session


@router.patch("/sessions/{session_id}", response_model=ChatSessionRead)
def update_session(session_id: int, payload: ChatSessionUpdate, db: Session = Depends(get_db)) -> ChatSessionRead:
    try:
        return chat_session_service.update_session(db, session_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: Session = Depends(get_db)) -> None:
    try:
        chat_session_service.delete_session(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)
def ask_in_session(session_id: int, payload: ChatSessionMessageCreate, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        return chat_session_service.ask_in_session(db, session_id, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/messages/{message_id}/regenerate", response_model=ChatResponse)
def regenerate_message(message_id: int, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        return chat_session_service.regenerate_message(db, message_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/messages/{message_id}/favorite", response_model=ChatFavoriteResponse)
def favorite_message(message_id: int, db: Session = Depends(get_db)) -> ChatFavoriteResponse:
    try:
        return chat_session_service.favorite_message(db, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
