from datetime import datetime
import json

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VersionLearningPackage(Base):
    __tablename__ = "version_learning_packages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    version_name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    implemented_features_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    major_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    focus: Mapped[str] = mapped_column(Text, nullable=False)
    review_suggestions: Mapped[str] = mapped_column(Text, nullable=False)
    interview_expression: Mapped[str] = mapped_column(Text, nullable=False)
    next_version_suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    knowledge_points = relationship("KnowledgePoint", back_populates="package", cascade="all, delete-orphan")
    cards = relationship("LearningCard", back_populates="package", cascade="all, delete-orphan")
    quiz_questions = relationship("QuizQuestion", back_populates="package", cascade="all, delete-orphan")

    @property
    def implemented_features(self) -> list[str]:
        try:
            value = json.loads(self.implemented_features_json or "[]")
        except json.JSONDecodeError:
            return []
        return value if isinstance(value, list) else []

    @property
    def major_files(self) -> list[dict]:
        try:
            value = json.loads(self.major_files_json or "[]")
        except json.JSONDecodeError:
            return []
        return value if isinstance(value, list) else []


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("version_learning_packages.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    beginner_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    project_usage: Mapped[str] = mapped_column(Text, nullable=False)
    code_locations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    review_suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    interview_expression: Mapped[str] = mapped_column(Text, nullable=False)
    mastery_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_started")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    package = relationship("VersionLearningPackage", back_populates="knowledge_points")
    progress_records = relationship("LearningProgress", back_populates="knowledge_point", cascade="all, delete-orphan")

    @property
    def code_locations(self) -> list[str]:
        try:
            value = json.loads(self.code_locations_json or "[]")
        except json.JSONDecodeError:
            return []
        return value if isinstance(value, list) else []


class LearningCard(Base):
    __tablename__ = "learning_cards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("version_learning_packages.id"), nullable=True, index=True)
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True, index=True)
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    mastery_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unclear")
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    package = relationship("VersionLearningPackage", back_populates="cards")
    knowledge_point = relationship("KnowledgePoint")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("version_learning_packages.id"), nullable=True, index=True)
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    correct_answer: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    package = relationship("VersionLearningPackage", back_populates="quiz_questions")
    knowledge_point = relationship("KnowledgePoint")

    @property
    def options(self) -> list[str]:
        try:
            value = json.loads(self.options_json or "[]")
        except json.JSONDecodeError:
            return []
        return value if isinstance(value, list) else []


class LearningProgress(Base):
    __tablename__ = "learning_progress"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=False, index=True)
    mastery_status: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    knowledge_point = relationship("KnowledgePoint", back_populates="progress_records")
