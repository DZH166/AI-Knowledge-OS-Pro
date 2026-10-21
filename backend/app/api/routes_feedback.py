from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from app.modules.feedback.contracts import (
    ExportSamples, FeedbackDetail, FeedbackPage, FeedbackReceipt, ListFeedback,
    ReviewFeedback, SampleExport, SubmitFeedback,
)
from app.modules.feedback.service import SqlFeedback
from app.modules.feedback.wiring import get_feedback


def no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/v1/feedback", tags=["reviewed-feedback"], dependencies=[Depends(no_cache)])
FeedbackDependency = Annotated[SqlFeedback, Depends(get_feedback)]


@router.post("", response_model=FeedbackReceipt, status_code=201)
def submit_feedback(payload: SubmitFeedback, feedback: FeedbackDependency) -> FeedbackReceipt:
    return feedback.submit(payload)


@router.get("", response_model=FeedbackPage)
def list_feedback(feedback: FeedbackDependency, query: Annotated[ListFeedback, Query()]) -> FeedbackPage:
    return feedback.list(query)


@router.post("/cases/export", response_model=SampleExport)
def export_samples(payload: ExportSamples, feedback: FeedbackDependency) -> SampleExport:
    return feedback.export(payload)


@router.get("/{feedback_id}", response_model=FeedbackDetail)
def get_feedback_detail(feedback_id: Annotated[int, Path(gt=0)], feedback: FeedbackDependency) -> FeedbackDetail:
    return feedback.get(feedback_id)


@router.post("/{feedback_id}/review", response_model=FeedbackReceipt)
def review_feedback(feedback_id: Annotated[int, Path(gt=0)], payload: ReviewFeedback,
                    feedback: FeedbackDependency) -> FeedbackReceipt:
    return feedback.review(feedback_id, payload)
