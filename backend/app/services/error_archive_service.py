from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.error_archive import ErrorArchive
from app.models.source import MultimodalChunk, Source


class ErrorArchiveService:
    exception_pattern = re.compile(
        r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning))\b(?:\s*:\s*([^\n]+))?"
    )
    http_pattern = re.compile(r"\bHTTP(?:/\d(?:\.\d)?)?\s*(?:status\s*)?(\d{3})\b", re.IGNORECASE)
    generic_pattern = re.compile(r"(?im)^\s*(?:error|fatal|failed)\s*[:\-]\s*(.+)$")

    def extract_from_source(self, db: Session, source_id: int) -> tuple[ErrorArchive, bool]:
        source = db.get(Source, source_id)
        if source is None:
            raise ValueError("图片资料不存在。")
        if source.source_type != "image":
            raise ValueError("当前只支持从图片 OCR 结果中识别报错。")

        chunks = list(
            db.scalars(
                select(MultimodalChunk)
                .where(
                    MultimodalChunk.source_id == source.id,
                    MultimodalChunk.revision_id == source.active_revision_id,
                    MultimodalChunk.modality == "image_text",
                    MultimodalChunk.status == "active",
                )
                .order_by(MultimodalChunk.chunk_index)
            )
        )
        if not chunks:
            raise ValueError("当前图片还没有可用 OCR 文本，请先执行真实 OCR。")

        text = "\n".join(chunk.content_text for chunk in chunks).strip()
        detection = self._detect(text)
        if detection is None:
            raise ValueError("OCR 文本中没有识别到明确报错标记，系统不会强行生成报错记录。")

        error_type, error_message, confidence, match_start = detection
        fingerprint = hashlib.sha256(
            f"{source.id}\n{error_type}\n{error_message}".lower().encode("utf-8")
        ).hexdigest()
        existing = db.scalar(
            select(ErrorArchive).where(
                ErrorArchive.source_id == source.id,
                ErrorArchive.fingerprint == fingerprint,
            )
        )
        if existing is not None:
            return existing, False

        language = self._detect_language(text)
        severity = self._severity(error_type)
        archive = ErrorArchive(
            space_id=source.space_id,
            source_id=source.id,
            chunk_id=chunks[0].id,
            title=f"{error_type} · {source.original_filename or source.title or source.id}",
            error_type=error_type,
            error_message=error_message,
            stack_excerpt=self._excerpt(text, match_start),
            language=language,
            severity=severity,
            status="open",
            detection_method="ocr_pattern",
            confidence=confidence,
            suggested_actions_json=json.dumps(self._suggested_actions(error_type), ensure_ascii=False),
            tags_json=json.dumps(["截图报错", language or "未识别语言"], ensure_ascii=False),
            fingerprint=fingerprint,
        )
        db.add(archive)
        db.commit()
        db.refresh(archive)
        return archive, True

    def list_archives(
        self,
        db: Session,
        *,
        space_id: int | None = None,
        source_id: int | None = None,
        status: str | None = None,
    ) -> list[ErrorArchive]:
        stmt = select(ErrorArchive).order_by(ErrorArchive.created_at.desc())
        if space_id is not None:
            stmt = stmt.where(ErrorArchive.space_id == space_id)
        if source_id is not None:
            stmt = stmt.where(ErrorArchive.source_id == source_id)
        if status:
            stmt = stmt.where(ErrorArchive.status == status)
        return list(db.scalars(stmt).all())

    def get_archive(self, db: Session, archive_id: int) -> ErrorArchive:
        archive = db.get(ErrorArchive, archive_id)
        if archive is None:
            raise ValueError("报错档案不存在。")
        return archive

    def update_archive(
        self,
        db: Session,
        archive_id: int,
        *,
        status: str | None = None,
        resolution_notes: str | None = None,
        tags: list[str] | None = None,
    ) -> ErrorArchive:
        archive = self.get_archive(db, archive_id)
        if status is not None:
            archive.status = status
            archive.resolved_at = datetime.now(timezone.utc) if status == "resolved" else None
        if resolution_notes is not None:
            archive.resolution_notes = resolution_notes.strip() or None
        if tags is not None:
            archive.tags_json = json.dumps([tag.strip() for tag in tags if tag.strip()], ensure_ascii=False)
        db.commit()
        db.refresh(archive)
        return archive

    def _detect(self, text: str) -> tuple[str, str, int, int] | None:
        match = self.exception_pattern.search(text)
        if match:
            return match.group(1), (match.group(2) or match.group(0)).strip(), 95, match.start()
        match = self.http_pattern.search(text)
        if match:
            code = int(match.group(1))
            return f"HTTP {code}", self._line_at(text, match.start()), 85, match.start()
        match = self.generic_pattern.search(text)
        if match:
            return "Error", match.group(1).strip(), 65, match.start()
        return None

    @staticmethod
    def _line_at(text: str, position: int) -> str:
        start = text.rfind("\n", 0, position) + 1
        end = text.find("\n", position)
        return text[start : end if end >= 0 else len(text)].strip()

    @staticmethod
    def _excerpt(text: str, position: int, radius: int = 900) -> str:
        start = max(0, position - radius)
        end = min(len(text), position + radius)
        return text[start:end].strip()

    @staticmethod
    def _detect_language(text: str) -> str | None:
        lowered = text.lower()
        if "traceback (most recent call last)" in lowered or re.search(r"\b[a-z_]+\.py:\d+", lowered):
            return "python"
        if "node_modules" in lowered or "npm err" in lowered or re.search(r"\bat .+\(.+\.(?:js|ts):\d+", text):
            return "javascript"
        if "java.lang." in lowered or re.search(r"\bat [\w.$]+\([\w.]+\.java:\d+", text):
            return "java"
        if "sqlstate" in lowered or "syntax error at or near" in lowered:
            return "sql"
        return None

    @staticmethod
    def _severity(error_type: str) -> str:
        if error_type in {"MemoryError", "SystemError"} or error_type.startswith("HTTP 5"):
            return "high"
        if error_type.startswith("HTTP 4") or error_type.endswith(("Error", "Exception")):
            return "medium"
        return "unknown"

    @staticmethod
    def _suggested_actions(error_type: str) -> list[str]:
        mapping = {
            "ModuleNotFoundError": ["确认当前 Python 虚拟环境", "检查 requirements.txt", "安装缺失依赖后重新运行"],
            "ImportError": ["检查包版本和导入路径", "确认虚拟环境与运行解释器一致", "查看依赖冲突"],
            "TypeError": ["定位堆栈中首个项目代码位置", "检查传入参数类型", "补充边界输入测试"],
            "ConnectionError": ["检查目标服务是否启动", "核对服务地址和端口", "检查网络与代理配置"],
            "TimeoutError": ["确认下游服务状态", "检查超时配置", "只对临时错误增加有限重试"],
            "HTTP 401": ["检查凭证是否配置", "确认 token 是否过期", "检查请求权限范围"],
            "HTTP 403": ["确认当前账号权限", "检查资源访问策略", "核对 API 权限范围"],
            "HTTP 404": ["核对请求 URL", "确认资源标识存在", "检查路由和环境配置"],
            "HTTP 429": ["查看限流响应头", "降低请求并发", "使用退避重试"],
        }
        if error_type in mapping:
            return mapping[error_type]
        if error_type.startswith("HTTP 5"):
            return ["查看服务端日志", "确认依赖服务健康状态", "保留 request id 后重试"]
        return ["保留完整堆栈并稳定复现", "定位首个项目代码位置", "记录修复过程和回归测试"]


error_archive_service = ErrorArchiveService()
