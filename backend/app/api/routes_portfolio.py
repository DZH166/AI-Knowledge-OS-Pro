from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.portfolio_schema import PortfolioSummary
from app.services.portfolio_service import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
def get_portfolio_summary(db: Session = Depends(get_db)) -> PortfolioSummary:
    return portfolio_service.summary(db)
