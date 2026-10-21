from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.learning_schema import (
    KnowledgePointNoteCreate,
    KnowledgePointProgressUpdate,
    KnowledgePointRead,
    LearningDashboard,
    LearningArtifactBatchResponse,
    LearningArtifactCreate,
    LearningCardProgressUpdate,
    LearningCardRead,
    LearningLogCreate,
    LearningLogRead,
    LearningNoteCreate,
    LearningNoteRead,
    LearningNoteUpdate,
    LearningPackageCreate,
    LearningPackageRead,
    LearningRoadmapRead,
    KnowledgeRelationRead,
    MarkdownExportResponse,
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizQuestionRead,
)
from app.services.learning_log_service import learning_log_service
from app.services.learning_package_service import learning_package_service
from app.services.learning_artifact_service import learning_artifact_service

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/logs", response_model=list[LearningLogRead])
def list_learning_logs(db: Session = Depends(get_db)) -> list[LearningLogRead]:
    return learning_log_service.list_logs(db)


@router.get("/dashboard", response_model=LearningDashboard)
def learning_dashboard(db: Session = Depends(get_db)) -> LearningDashboard:
    return learning_package_service.dashboard(db)


@router.get("/versions", response_model=list[LearningLogRead])
def learning_versions(db: Session = Depends(get_db)) -> list[LearningLogRead]:
    return learning_log_service.list_logs(db)


@router.get("/logs/{slug}", response_model=LearningLogRead)
def get_learning_log(slug: str, db: Session = Depends(get_db)) -> LearningLogRead:
    log = learning_log_service.get_log(db, slug)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning log not found.")
    return log


@router.post("/logs", response_model=LearningLogRead, status_code=status.HTTP_201_CREATED)
def append_learning_log(payload: LearningLogCreate, db: Session = Depends(get_db)) -> LearningLogRead:
    existing = learning_log_service.get_log(db, payload.slug)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Learning log slug already exists.")
    return learning_log_service.create_log(db, payload)


@router.post("/packages/generate-draft", response_model=LearningPackageRead)
def generate_learning_package_draft(db: Session = Depends(get_db)) -> LearningPackageRead:
    return learning_package_service.generate_draft(db)


@router.post("/packages", response_model=LearningPackageRead, status_code=status.HTTP_201_CREATED)
def create_learning_package(payload: LearningPackageCreate, db: Session = Depends(get_db)) -> LearningPackageRead:
    return learning_package_service.create_package(db, payload)


@router.get("/packages", response_model=list[LearningPackageRead])
def list_learning_packages(db: Session = Depends(get_db)) -> list[LearningPackageRead]:
    return learning_package_service.list_packages(db)


@router.get("/packages/{slug}", response_model=LearningPackageRead)
def get_learning_package(slug: str, db: Session = Depends(get_db)) -> LearningPackageRead:
    package = learning_package_service.get_package(db, slug)
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning package not found.")
    return package


@router.patch("/packages/{slug}", response_model=LearningPackageRead)
def update_learning_package(slug: str, payload: LearningPackageCreate, db: Session = Depends(get_db)) -> LearningPackageRead:
    try:
        return learning_package_service.update_package(db, slug, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/packages/{slug}/confirm", response_model=LearningPackageRead)
def confirm_learning_package(slug: str, db: Session = Depends(get_db)) -> LearningPackageRead:
    try:
        return learning_package_service.confirm_package(db, slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/packages/{slug}/export", response_model=MarkdownExportResponse)
def export_learning_package(slug: str, db: Session = Depends(get_db)) -> MarkdownExportResponse:
    package = learning_package_service.get_package(db, slug)
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning package not found.")
    learning_log_service.append_markdown_once(package.slug, package.markdown_content)
    return MarkdownExportResponse(markdown=package.markdown_content, message="学习包已追加导出。")


@router.get("/knowledge-points", response_model=list[KnowledgePointRead])
def list_knowledge_points(db: Session = Depends(get_db)) -> list[KnowledgePointRead]:
    return learning_package_service.list_knowledge_points(db)


@router.get("/roadmap", response_model=LearningRoadmapRead)
def get_learning_roadmap(db: Session = Depends(get_db)) -> LearningRoadmapRead:
    return learning_package_service.roadmap(db)


@router.get("/knowledge-graph", response_model=list[KnowledgeRelationRead])
def get_knowledge_graph(db: Session = Depends(get_db)) -> list[KnowledgeRelationRead]:
    return learning_package_service.knowledge_graph(db)


@router.get("/knowledge-points/{point_id}", response_model=KnowledgePointRead)
def get_knowledge_point(point_id: int, db: Session = Depends(get_db)) -> KnowledgePointRead:
    point = learning_package_service.get_knowledge_point(db, point_id)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge point not found.")
    return point


@router.patch("/knowledge-points/{point_id}/progress", response_model=KnowledgePointRead)
def update_knowledge_point_progress(
    point_id: int,
    payload: KnowledgePointProgressUpdate,
    db: Session = Depends(get_db),
) -> KnowledgePointRead:
    try:
        return learning_package_service.update_progress(db, point_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/knowledge-points/{point_id}/notes", response_model=KnowledgePointRead)
def add_knowledge_point_note(
    point_id: int,
    payload: KnowledgePointNoteCreate,
    db: Session = Depends(get_db),
) -> KnowledgePointRead:
    try:
        return learning_package_service.add_note(db, point_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/cards", response_model=list[LearningCardRead])
def list_learning_cards(db: Session = Depends(get_db)) -> list[LearningCardRead]:
    return learning_package_service.list_cards(db)


@router.patch("/cards/{card_id}/progress", response_model=LearningCardRead)
def update_learning_card_progress(
    card_id: int,
    payload: LearningCardProgressUpdate,
    db: Session = Depends(get_db),
) -> LearningCardRead:
    try:
        return learning_package_service.update_card_progress(db, card_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/cards/{card_id}/review", response_model=LearningCardRead)
def review_learning_card(
    card_id: int,
    payload: LearningCardProgressUpdate,
    db: Session = Depends(get_db),
) -> LearningCardRead:
    try:
        return learning_package_service.review_card(db, card_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/quizzes", response_model=list[QuizQuestionRead])
def list_quizzes(db: Session = Depends(get_db)) -> list[QuizQuestionRead]:
    return learning_package_service.list_quizzes(db)


@router.post("/quizzes/{quiz_id}/answer", response_model=QuizAnswerResponse)
def answer_quiz(
    quiz_id: int,
    payload: QuizAnswerRequest,
    db: Session = Depends(get_db),
) -> QuizAnswerResponse:
    try:
        return learning_package_service.answer_quiz(db, quiz_id, payload.answer)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/export-markdown", response_model=MarkdownExportResponse)
def export_markdown(db: Session = Depends(get_db)) -> MarkdownExportResponse:
    return learning_package_service.export_markdown(db)


@router.get("/notes", response_model=list[LearningNoteRead])
def list_learning_notes(db: Session = Depends(get_db)) -> list[LearningNoteRead]:
    return learning_package_service.list_notes(db)


@router.post("/notes", response_model=LearningNoteRead, status_code=status.HTTP_201_CREATED)
def create_learning_note(payload: LearningNoteCreate, db: Session = Depends(get_db)) -> LearningNoteRead:
    return learning_package_service.create_note(db, payload)


@router.post("/from-source", response_model=LearningArtifactBatchResponse, status_code=status.HTTP_201_CREATED)
def create_learning_artifacts(
    payload: LearningArtifactCreate,
    db: Session = Depends(get_db),
) -> LearningArtifactBatchResponse:
    try:
        return learning_artifact_service.create_from_source(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/notes/{note_id}", response_model=LearningNoteRead)
def update_learning_note(note_id: int, payload: LearningNoteUpdate, db: Session = Depends(get_db)) -> LearningNoteRead:
    try:
        return learning_package_service.update_note(db, note_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_learning_note(note_id: int, db: Session = Depends(get_db)) -> None:
    try:
        learning_package_service.delete_note(db, note_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
