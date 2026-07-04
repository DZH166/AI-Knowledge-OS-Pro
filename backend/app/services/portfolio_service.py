from __future__ import annotations

import json
import os
import subprocess

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConfigurationError
from app.core.config import settings
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_space import KnowledgeSpace
from app.models.learning_note import LearningNote
from app.models.learning_system import KnowledgePoint, LearningCard, QuizQuestion, VersionLearningPackage
from app.models.qa_log import QALog
from app.models.source import CitationLocator, MultimodalChunk, Source, VisualFrame
from app.schemas.portfolio_schema import (
    PortfolioCapability,
    PortfolioMarkdownResponse,
    PortfolioMetric,
    PortfolioSummary,
)
from app.services.llm_service import LLMService


class PortfolioService:
    def __init__(self) -> None:
        self.llm_service = LLMService()

    def summary(self, db: Session) -> PortfolioSummary:
        metric_values = {
            "knowledge_spaces": self._count(db, KnowledgeSpace),
            "documents": self._count(db, Document),
            "sources": self._count(db, Source),
            "code_repositories": self._count_sources(db, "code_repository"),
            "multimodal_chunks": self._count(db, MultimodalChunk),
            "citation_locators": self._count(db, CitationLocator),
            "visual_frames": self._count(db, VisualFrame),
            "tasks": self._count(db, IngestionJob),
            "qa_logs": self._count(db, QALog),
            "learning_assets": self._learning_asset_count(db),
            "learning_packages": self._count(db, VersionLearningPackage),
        }

        return PortfolioSummary(
            project_name=settings.app_name,
            version=settings.app_version,
            semantic_version=settings.app_semver,
            runtime_mode=settings.runtime_mode,
            positioning=(
                "面向 AI 应用开发学习者的多模态个人知识操作系统，围绕项目知识库、"
                "RAG 问答、来源引用、任务队列和版本学习档案形成可展示的学习作品。"
            ),
            metrics=[
                PortfolioMetric(
                    key="knowledge_spaces",
                    label="知识库空间",
                    value=metric_values["knowledge_spaces"],
                    description="当前数据库中可管理的学习资料空间数量。",
                ),
                PortfolioMetric(
                    key="documents",
                    label="文档资料",
                    value=metric_values["documents"],
                    description="已经进入文档表的 txt、md、pdf 等资料。",
                ),
                PortfolioMetric(
                    key="sources",
                    label="多模态来源",
                    value=metric_values["sources"],
                    description="图片、音频、视频等 Source 记录，不包含原始私有文件。",
                ),
                PortfolioMetric(
                    key="code_repositories",
                    label="代码仓库",
                    value=metric_values["code_repositories"],
                    description="按安全白名单接入并生成文件行号 locator 的代码仓库快照。",
                ),
                PortfolioMetric(
                    key="citation_locators",
                    label="引用定位",
                    value=metric_values["citation_locators"],
                    description="可用于文档页码、媒体时间戳或关键帧跳转的定位记录。",
                ),
                PortfolioMetric(
                    key="tasks",
                    label="处理任务",
                    value=metric_values["tasks"],
                    description="文档、多媒体处理和重试/取消相关任务记录。",
                ),
                PortfolioMetric(
                    key="learning_assets",
                    label="学习资产",
                    value=metric_values["learning_assets"],
                    description="知识点、卡片、练习题和笔记的真实记录总数。",
                ),
            ],
            capabilities=self._capabilities(metric_values),
            resume_bullets=[
                "构建 FastAPI + Next.js 多模态 RAG 学习系统，支持文档、图片、音频、视频资料接入和引用溯源。",
                "设计 Redis/RQ 任务中心，将 OCR、转写、关键帧和索引处理纳入可重试、可取消、可追踪的异步流程。",
                "建立 GitHub 作品集工程化体系，覆盖 CI、pytest、frontend build、编码检查、secret scan 和 release dry-run。",
                "沉淀版本学习档案、学习卡片、练习题、笔记和面试表达，把项目开发过程转化为可复习知识资产。",
            ],
            interview_talking_points=[
                "为什么 Real mode 不能生成假回答、假 OCR 或假转写，以及 NOT_CONFIGURED 错误如何保护可信边界。",
                "RAG 回答如何从资料切片、向量检索、引用校验到 CitationLocator 完成证据链闭环。",
                "为什么媒体处理需要任务队列，以及前端任务中心如何呈现进度、错误和恢复建议。",
                "这个项目如何从功能 Demo 演进成 GitHub 可展示、可运行、可测试、可讲解的作品集。",
            ],
            recommended_storyline=[
                "先用 README 和 Dashboard 说明项目定位：个人多模态知识操作系统。",
                "演示上传中心和媒体库，说明资料如何进入文档/媒体模型与任务中心。",
                "演示知识问答和引用跳转，突出 RAG 证据链与拒答边界。",
                "最后展示学习档案、质量门和发布检查，说明工程化能力和面试表达能力。",
            ],
            honest_boundaries=[
                "作品集概览只汇总真实数据库和静态工程事实，不调用 LLM 生成内容。",
                "真实 LLM、Embedding、OCR、Vision、Speech-to-Text 能力仍依赖用户配置 provider key；缺失时必须返回 NOT_CONFIGURED 类错误。",
                "Demo 数据是明确标识的合成数据，不代表真实用户资料或真实模型输出。",
                "V4.0 的代码仓库接入、混合检索、模拟面试和更强作品集生成仍在增量实现中。",
            ],
            next_steps=[
                "补齐 portfolio 生成 API 的真实 LLM provider 路径，并在未配置时返回明确 NOT_CONFIGURED。",
                "增加代码仓库 Source 类型和 file/line citation locator。",
                "扩展 RAG evaluation 报告，加入 retrieval_hit_rate、citation_validity 和 refusal_accuracy。",
                "新增模拟面试记录、反馈和复习卡片联动。",
            ],
        )

    def _capabilities(self, metric_values: dict[str, int]) -> list[PortfolioCapability]:
        return [
            PortfolioCapability(
                name="多模态资料接入",
                status="implemented",
                evidence=f"{metric_values['sources']} 个 Source，{metric_values['multimodal_chunks']} 个 MultimodalChunk。",
                boundary="媒体原文件不进入 release；真实 OCR/转写需要 provider 或本地工具链配置。",
            ),
            PortfolioCapability(
                name="RAG 引用溯源",
                status="implemented",
                evidence=f"{metric_values['citation_locators']} 个 CitationLocator，{metric_values['qa_logs']} 条问答记录。",
                boundary="资料不足或索引不兼容时必须拒答或提示重建索引。",
            ),
            PortfolioCapability(
                name="任务队列治理",
                status="implemented",
                evidence=f"{metric_values['tasks']} 条任务记录，支持状态、进度、事件、重试和取消。",
                boundary="Redis/Worker 未运行时只展示明确异常，不伪造后台进度。",
            ),
            PortfolioCapability(
                name="学习档案与复习资产",
                status="implemented",
                evidence=f"{metric_values['learning_assets']} 个学习资产，{metric_values['learning_packages']} 个版本学习包。",
                boundary="从真实资料或真实版本 diff 生成，不覆盖历史 learning log。",
            ),
            PortfolioCapability(
                name="代码仓库理解",
                status="in_progress",
                evidence=f"{metric_values['code_repositories']} 个代码仓库 Source，可生成 file_path/line locator。",
                boundary="当前支持本地仓库安全扫描和代码片段索引；远程同步、符号图谱和 LLM 复盘仍在后续阶段。",
            ),
            PortfolioCapability(
                name="作品集/面试系统",
                status="in_progress",
                evidence="当前提供真实项目概览、简历要点、讲解路线和边界说明。",
                boundary="自动生成简历和模拟面试反馈需要后续接入真实 LLM provider。",
            ),
        ]

    def _count(self, db: Session, model: type) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    def _count_sources(self, db: Session, source_type: str) -> int:
        return int(db.scalar(select(func.count()).select_from(Source).where(Source.source_type == source_type)) or 0)

    def _learning_asset_count(self, db: Session) -> int:
        return (
            self._count(db, KnowledgePoint)
            + self._count(db, LearningCard)
            + self._count(db, QuizQuestion)
            + self._count(db, LearningNote)
        )

    def generate_resume_entry(self, db: Session) -> PortfolioMarkdownResponse:
        return self._generate_markdown_entry(
            db,
            title="Resume Entry",
            section_name="简历表达",
            prompt_style="resume",
        )

    def generate_interview_qa(self, db: Session) -> PortfolioMarkdownResponse:
        return self._generate_markdown_entry(
            db,
            title="Interview Q&A",
            section_name="面试讲解",
            prompt_style="interview",
        )

    def generate_project_review(self, db: Session) -> PortfolioMarkdownResponse:
        return self._generate_markdown_entry(
            db,
            title="Project Review",
            section_name="项目复盘",
            prompt_style="review",
        )

    def export_markdown(self, db: Session) -> PortfolioMarkdownResponse:
        summary = self.summary(db)
        return PortfolioMarkdownResponse(
            title="Portfolio Summary",
            markdown=self._summary_markdown(summary),
            message="已导出作品集摘要 Markdown。",
            source_branch=self._git_branch(),
            source_commit=self._git_commit(),
            evidence=self._summary_evidence(summary),
        )

    def _generate_markdown_entry(self, db: Session, *, title: str, section_name: str, prompt_style: str) -> PortfolioMarkdownResponse:
        if not self.llm_service.is_configured():
            raise ConfigurationError(
                "Portfolio markdown generation requires a real LLM provider.",
                code="LLM_NOT_CONFIGURED",
                details={"section": section_name, "prompt_style": prompt_style},
            )

        summary = self.summary(db)
        prompt = self._build_generation_prompt(summary, section_name=section_name, prompt_style=prompt_style)
        markdown = self.llm_service.complete(
            system_prompt=(
                "You write honest portfolio-grade markdown for AI Knowledge OS Pro. "
                "Only use supplied facts and boundaries. Do not invent features. "
                "When a capability is planned or requires providers, say so explicitly."
            ),
            user_prompt=prompt,
        ).strip()
        if not markdown:
            raise ConfigurationError(
                "Portfolio markdown generation returned empty content.",
                code="PORTFOLIO_GENERATION_FAILED",
                details={"section": section_name},
            )
        return PortfolioMarkdownResponse(
            title=title,
            markdown=markdown,
            message=f"已使用 {section_name} 真实名 LLM provider 生成。",
            source_branch=self._git_branch(),
            source_commit=self._git_commit(),
            evidence=self._summary_evidence(summary),
        )

    def _build_generation_prompt(self, summary: PortfolioSummary, *, section_name: str, prompt_style: str) -> str:
        payload = {
            "project_name": summary.project_name,
            "version": summary.version,
            "semantic_version": summary.semantic_version,
            "runtime_mode": summary.runtime_mode,
            "positioning": summary.positioning,
            "metrics": [metric.model_dump() for metric in summary.metrics],
            "capabilities": [cap.model_dump() for cap in summary.capabilities],
            "resume_bullets": summary.resume_bullets,
            "interview_talking_points": summary.interview_talking_points,
            "recommended_storyline": summary.recommended_storyline,
            "honest_boundaries": summary.honest_boundaries,
            "next_steps": summary.next_steps,
        }
        return (
            f"Write a {section_name} section for AI Knowledge OS Pro.\n"
            f"Style: {prompt_style}.\n"
            "Use only the following verified facts.\n"
            "Structure the answer with clear headings and concise bullets where helpful.\n"
            "If a feature is planned or requires providers, say that plainly.\n\n"
            f"FACTS:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _summary_markdown(summary: PortfolioSummary) -> str:
        lines = [
            f"# {summary.project_name} Portfolio Summary",
            "",
            f"- Version: {summary.version} / {summary.semantic_version}",
            f"- Runtime mode: {summary.runtime_mode}",
            "",
            "## Positioning",
            summary.positioning,
            "",
            "## Metrics",
        ]
        for metric in summary.metrics:
            lines.append(f"- {metric.label}: {metric.value} ({metric.description})")
        lines.extend(
            [
                "",
                "## Honest Boundaries",
                *[f"- {boundary}" for boundary in summary.honest_boundaries],
                "",
                "## Next Steps",
                *[f"- {step}" for step in summary.next_steps],
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _summary_evidence(summary: PortfolioSummary) -> list[str]:
        evidence = [f"{metric.label}={metric.value}" for metric in summary.metrics[:6]]
        evidence.extend([f"runtime_mode={summary.runtime_mode}", f"version={summary.version}/{summary.semantic_version}"])
        return evidence

    @staticmethod
    def _git_branch() -> str | None:
        for env_name in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
            value = os.getenv(env_name, "").strip()
            if value:
                return value
        try:
            output = subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=settings.project_root,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return None
        value = output.strip()
        if value:
            return value
        try:
            output = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=settings.project_root,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return None
        value = output.strip()
        if value and value != "HEAD":
            return value
        return "detached-head"

    @staticmethod
    def _git_commit() -> str | None:
        try:
            output = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=settings.project_root,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return None
        value = output.strip()
        return value or None


portfolio_service = PortfolioService()
