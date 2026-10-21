from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_space import KnowledgeSpace
from app.models.qa_log import QALog
from app.schemas.knowledge_schema import KnowledgeSpaceCreate, KnowledgeSpaceDetail, KnowledgeSpaceRead

router = APIRouter(prefix="/knowledge-spaces", tags=["knowledge spaces"])


@router.post("", response_model=KnowledgeSpaceRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_space(payload: KnowledgeSpaceCreate, db: Session = Depends(get_db)) -> KnowledgeSpace:
    space = KnowledgeSpace(name=payload.name, description=payload.description)
    db.add(space)
    db.commit()
    db.refresh(space)
    return space


@router.get("", response_model=list[KnowledgeSpaceDetail])
def list_knowledge_spaces(db: Session = Depends(get_db)) -> list[KnowledgeSpaceDetail]:
    spaces = db.scalars(select(KnowledgeSpace).order_by(KnowledgeSpace.created_at.desc())).all()
    return [_space_to_detail(db, space) for space in spaces]


@router.get("/{space_id}", response_model=KnowledgeSpaceDetail)
def get_knowledge_space(space_id: int, db: Session = Depends(get_db)) -> KnowledgeSpaceDetail:
    space = db.get(KnowledgeSpace, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge space not found.")
    return _space_to_detail(db, space)


def _count(db: Session, model: type, space_id: int) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(model.space_id == space_id)) or 0)


def _space_to_detail(db: Session, space: KnowledgeSpace) -> KnowledgeSpaceDetail:
    return KnowledgeSpaceDetail(
        id=space.id,
        name=space.name,
        description=space.description,
        created_at=space.created_at,
        updated_at=space.updated_at,
        document_count=_count(db, Document, space.id),
        chunk_count=_count(db, Chunk, space.id),
        qa_count=_count(db, QALog, space.id),
    )

