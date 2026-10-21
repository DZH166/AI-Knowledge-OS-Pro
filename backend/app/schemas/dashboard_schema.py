from pydantic import BaseModel

from app.schemas.chat_schema import QALogRead
from app.schemas.document_schema import DocumentRead
from app.schemas.learning_schema import LearningLogRead


class DashboardSummary(BaseModel):
    knowledge_space_count: int
    document_count: int
    qa_count: int
    recent_documents: list[DocumentRead]
    recent_qa: list[QALogRead]
    current_version: str
    current_capabilities: list[str]
    recent_learning_log: LearningLogRead | None
    next_step_suggestion: str

