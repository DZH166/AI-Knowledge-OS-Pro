from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MajorFile(BaseModel):
    path: str
    responsibility: str


class KnowledgePoint(BaseModel):
    name: str
    beginner_explanation: str
    project_usage: str
    code_locations: list[str] = Field(default_factory=list)
    review_suggestion: str
    interview_expression: str


class LearningLogCreate(BaseModel):
    version_name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80)
    summary: str
    implemented_features: list[str]
    major_files: list[MajorFile]
    knowledge_points: list[KnowledgePoint]
    focus: str
    review_suggestions: str
    interview_expression: str
    next_version_suggestion: str
    markdown_content: str | None = None


class LearningLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_name: str
    slug: str
    summary: str
    implemented_features: list[str]
    major_files: list[MajorFile]
    knowledge_points: list[KnowledgePoint]
    focus: str
    review_suggestions: str
    interview_expression: str
    next_version_suggestion: str
    markdown_content: str
    created_at: datetime


class LearningPackageCreate(BaseModel):
    version_name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80)
    summary: str
    implemented_features: list[str]
    major_files: list[MajorFile]
    knowledge_points: list[KnowledgePoint]
    focus: str
    review_suggestions: str
    interview_expression: str
    next_version_suggestion: str
    markdown_content: str | None = None


class LearningPackageRead(LearningPackageCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    markdown_content: str
    created_at: datetime
    confirmed_at: datetime | None = None


class KnowledgePointRead(KnowledgePoint):
    id: int
    package_id: int | None
    mastery_status: str
    notes: str
    created_at: datetime
    updated_at: datetime


class KnowledgePointProgressUpdate(BaseModel):
    mastery_status: str = Field(pattern="^(not_started|know|unclear|unknown|reviewing|mastered)$")
    note: str | None = None


class KnowledgePointNoteCreate(BaseModel):
    note: str = Field(min_length=1)


class LearningCardRead(BaseModel):
    id: int
    package_id: int | None
    knowledge_point_id: int | None
    front: str
    back: str
    mastery_status: str
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None
    review_count: int = 0
    difficulty: str = "normal"
    created_at: datetime


class LearningCardProgressUpdate(BaseModel):
    mastery_status: str = Field(pattern="^(know|unclear|unknown|reviewing|mastered)$")


class QuizQuestionRead(BaseModel):
    id: int
    package_id: int | None
    knowledge_point_id: int | None
    question: str
    options: list[str]
    explanation: str | None = None


class QuizAnswerRequest(BaseModel):
    answer: str


class QuizAnswerResponse(BaseModel):
    correct: bool
    correct_answer: str
    explanation: str


class MarkdownExportResponse(BaseModel):
    markdown: str
    message: str


class LearningNoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    knowledge_point_id: int | None = None
    document_id: int | None = None
    qa_log_id: int | None = None
    version_slug: str | None = None


class LearningNoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=180)
    content: str | None = None
    tags: list[str] | None = None


class LearningNoteRead(LearningNoteCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class LearningDashboard(BaseModel):
    current_version: str
    total_knowledge_points: int
    mastered_count: int
    learning_count: int
    review_needed_count: int
    due_card_count: int
    quiz_count: int
    note_count: int
    next_lesson: str


class KnowledgeRelationRead(BaseModel):
    source_point_id: int
    source_name: str
    target_point_id: int | None = None
    target_name: str | None = None
    relation_type: str
    reason: str


class LearningRoadmapStep(BaseModel):
    order: int
    knowledge_point_id: int
    title: str
    mastery_status: str
    relation_hint: str
    action_label: str
    code_locations: list[str] = Field(default_factory=list)
    interview_expression: str


class LearningRoadmapRead(BaseModel):
    total_steps: int
    review_needed_count: int
    generated_from: str
    steps: list[LearningRoadmapStep]
    relations: list[KnowledgeRelationRead]


LearningArtifactType = Literal["knowledge_point", "card", "quiz", "note", "interview_expression"]


class LearningArtifactCreate(BaseModel):
    source_id: int | None = None
    document_id: int | None = None
    chunk_id: int | None = None
    artifact_types: list[LearningArtifactType] = Field(min_length=1)
    title: str | None = Field(default=None, max_length=180)


class LearningArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artifact_type: str
    title: str
    content: str
    source_id: int | None = None
    document_id: int | None = None
    chunk_id: int | None = None
    document_chunk_id: int | None = None
    locator_json: str
    knowledge_point_id: int | None = None
    card_id: int | None = None
    quiz_id: int | None = None
    note_id: int | None = None
    created_at: datetime


class LearningArtifactBatchResponse(BaseModel):
    artifacts: list[LearningArtifactRead]
    message: str
