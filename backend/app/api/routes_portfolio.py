from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.portfolio_schema import PortfolioMarkdownResponse, PortfolioSummary
from app.services.portfolio_service import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
def get_portfolio_summary(db: Session = Depends(get_db)) -> PortfolioSummary:
    return portfolio_service.summary(db)


@router.post("/generate-resume-entry", response_model=PortfolioMarkdownResponse)
def generate_resume_entry(db: Session = Depends(get_db)) -> PortfolioMarkdownResponse:
    try:
        return portfolio_service.generate_resume_entry(db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/generate-interview-qa", response_model=PortfolioMarkdownResponse)
def generate_interview_qa(db: Session = Depends(get_db)) -> PortfolioMarkdownResponse:
    try:
        return portfolio_service.generate_interview_qa(db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/generate-project-review", response_model=PortfolioMarkdownResponse)
def generate_project_review(db: Session = Depends(get_db)) -> PortfolioMarkdownResponse:
    try:
        return portfolio_service.generate_project_review(db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/export-markdown", response_model=PortfolioMarkdownResponse)
def export_markdown(db: Session = Depends(get_db)) -> PortfolioMarkdownResponse:
    return portfolio_service.export_markdown(db)
