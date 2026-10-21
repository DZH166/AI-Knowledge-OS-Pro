from __future__ import annotations

import platform
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ServiceError
from app.models.ingestion_job import IngestionJob
from app.schemas.system_schema import ComponentStatus, RuntimeStatus, SystemStatusResponse, SystemTestResponse
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.ocr_service import get_ocr_provider
from app.services.transcription_service import get_transcription_provider
from app.services.vector_store import VectorStore


class SystemService:
    def __init__(self) -> None:
        self.vector_store = VectorStore()
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()
        self.ocr_provider = get_ocr_provider()
        self.transcription_provider = get_transcription_provider()

    def status(self, db: Session) -> SystemStatusResponse:
        warnings: list[str] = []
        db_status = self._db_status(db)
        qdrant_status = self._qdrant_status()
        collection_status = self._collection_status(qdrant_status)
        redis_status = self._redis_status()
        worker_status = self._worker_status(db)
        llm_status = self._llm_status()
        embedding_status = self._embedding_status()
        ocr_status = self._ocr_status()
        transcription_status = self._transcription_status()
        index_status = ComponentStatus(
            ok=True,
            status="ready",
            message="索引配置已加载。",
            details={"fingerprint": self.embedding_service.fingerprint()},
        )

        if settings.demo_mode:
            warnings.append("当前 DEMO_MODE=true：系统会使用本地 hash embedding 和演示回答，不代表真实模型效果。")
        else:
            if not self.llm_service.is_configured():
                warnings.append("真实模式未配置 LLM_API_KEY/OPENAI_API_KEY，问答生成会被阻止。")
            if not self.embedding_service.is_configured():
                warnings.append("真实模式未配置 EMBEDDING_API_KEY/OPENAI_API_KEY，上传索引和检索会被阻止。")
            if not self.ocr_provider.is_configured():
                warnings.append("真实模式未配置 OCR_API_KEY/OPENAI_API_KEY，图片 OCR 会被阻止，但不会生成伪 OCR。")
            if not self.transcription_provider.is_configured():
                warnings.append("真实模式未配置 TRANSCRIPTION_API_KEY/OPENAI_API_KEY，音频转写会被阻止，但不会生成伪转写。")
        if not qdrant_status.ok:
            warnings.append("Qdrant 当前不可用，请启动 Qdrant Server 后再上传或提问。")
        if not redis_status.ok:
            warnings.append("Redis 当前不可用，V3 后台任务无法入队。")
        if not worker_status.ok:
            warnings.append("没有检测到活跃 Worker 心跳；上传任务可能会停留在等待处理状态。")

        return SystemStatusResponse(
            runtime=RuntimeStatus(
                app_name=settings.app_name,
                app_version=settings.app_version,
                semantic_version=settings.app_semver,
                app_env=settings.app_env,
                runtime_mode=settings.runtime_mode,
                python_version=platform.python_version(),
                database_url=self._safe_database_url(settings.database_url),
                qdrant_url=settings.qdrant_url,
                qdrant_collection=settings.qdrant_collection,
                redis_url=self._safe_redis_url(settings.redis_url),
                task_queue_name=settings.task_queue_name,
                worker_queues=settings.worker_queues,
                llm_provider=settings.llm_provider if not settings.demo_mode else "demo_answer",
                llm_model=self.llm_service.provider.model,
                embedding_provider=settings.embedding_provider if not settings.demo_mode else "demo_hash",
                embedding_model=self.embedding_service.provider.model,
                embedding_dimensions=self.embedding_service.provider.dimensions,
                ocr_provider=settings.ocr_provider,
                ocr_model=self.ocr_provider.model,
                transcription_provider=settings.transcription_provider,
                transcription_model=self.transcription_provider.model,
                index_version=settings.index_version,
                retrieval_top_k=settings.retrieval_top_k,
                retrieval_score_threshold=settings.retrieval_score_threshold,
            ),
            db=db_status,
            qdrant=qdrant_status,
            collection=collection_status,
            redis=redis_status,
            worker=worker_status,
            llm=llm_status,
            embedding=embedding_status,
            ocr=ocr_status,
            transcription=transcription_status,
            index=index_status,
            warnings=warnings,
        )

    def test_llm(self) -> SystemTestResponse:
        try:
            answer = self.llm_service.complete(
                system_prompt="你是系统健康检查助手，只需要回答 OK。",
                user_prompt="请回答 OK。",
            )
        except ServiceError as exc:
            return SystemTestResponse(ok=False, status=exc.code, message=exc.message, details=exc.details or {})
        except Exception as exc:
            return SystemTestResponse(ok=False, status="LLM_TEST_FAILED", message=str(exc))
        return SystemTestResponse(ok=True, status="ready", message="LLM 测试成功。", details={"preview": answer[:120]})

    def test_embedding(self) -> SystemTestResponse:
        try:
            vector = self.embedding_service.embed_query("AI Knowledge OS Pro health check")
        except ServiceError as exc:
            return SystemTestResponse(ok=False, status=exc.code, message=exc.message, details=exc.details or {})
        except Exception as exc:
            return SystemTestResponse(ok=False, status="EMBEDDING_TEST_FAILED", message=str(exc))
        return SystemTestResponse(
            ok=True,
            status="ready",
            message="Embedding 测试成功。",
            details={"dimensions": len(vector), "fingerprint": self.embedding_service.fingerprint()},
        )

    def test_qdrant(self) -> SystemTestResponse:
        status = self.vector_store.status()
        return SystemTestResponse(
            ok=bool(status["ok"]),
            status=str(status["status"]),
            message=str(status["message"]),
            details={key: value for key, value in status.items() if key not in {"ok", "status", "message"}},
        )

    def _db_status(self, db: Session) -> ComponentStatus:
        try:
            db.execute(text("select 1"))
        except Exception as exc:
            return ComponentStatus(ok=False, status="unavailable", message=f"数据库不可用：{exc}")
        return ComponentStatus(ok=True, status="ready", message="数据库连接正常。")

    def _redis_status(self) -> ComponentStatus:
        try:
            from redis import Redis
            from rq import Queue

            connection = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
            ping = connection.ping()
            queues = [name.strip() for name in settings.worker_queues.split(",") if name.strip()]
            queue_lengths = {name: len(Queue(name, connection=connection)) for name in queues}
            return ComponentStatus(
                ok=bool(ping),
                status="ready",
                message="Redis 连接正常，任务可以入队。",
                details={"queues": queue_lengths},
            )
        except Exception as exc:
            return ComponentStatus(
                ok=False,
                status="unavailable",
                message="Redis 不可用，后台任务无法入队。",
                details={"error": exc.__class__.__name__},
            )

    def _worker_status(self, db: Session) -> ComponentStatus:
        active_statuses = ["queued", "claimed", "running", "cancelling", "retry_scheduled", "interrupted"]
        counts = dict(
            db.execute(
                select(IngestionJob.status, func.count(IngestionJob.id))
                .where(IngestionJob.status.in_(active_statuses))
                .group_by(IngestionJob.status)
            ).all()
        )
        heartbeat_cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.task_heartbeat_timeout_seconds)
        active_workers = db.scalar(
            select(func.count(func.distinct(IngestionJob.worker_id))).where(
                IngestionJob.worker_id.is_not(None),
                IngestionJob.heartbeat_at.is_not(None),
                IngestionJob.heartbeat_at >= heartbeat_cutoff,
            )
        ) or 0
        queued = int(counts.get("queued", 0) or 0)
        running = int(counts.get("running", 0) or 0) + int(counts.get("claimed", 0) or 0)
        ok = active_workers > 0 or (queued == 0 and running == 0)
        message = "任务队列当前没有待处理任务。" if ok and active_workers == 0 else f"检测到 {active_workers} 个活跃 Worker。"
        if not ok:
            message = "存在待处理任务，但没有检测到活跃 Worker 心跳。"
        return ComponentStatus(
            ok=ok,
            status="ready" if ok else "no_active_worker",
            message=message,
            details={
                "active_workers": active_workers,
                "queued": queued,
                "running": running,
                "status_counts": counts,
                "heartbeat_timeout_seconds": settings.task_heartbeat_timeout_seconds,
            },
        )

    def _qdrant_status(self) -> ComponentStatus:
        status = self.vector_store.status()
        return ComponentStatus(
            ok=bool(status["ok"]),
            status=str(status["status"]),
            message=str(status["message"]),
            details={key: value for key, value in status.items() if key not in {"ok", "status", "message"}},
        )

    def _collection_status(self, qdrant_status: ComponentStatus) -> ComponentStatus:
        if not qdrant_status.ok:
            return ComponentStatus(ok=False, status="unknown", message="Qdrant 不可用，暂不能检查 collection。")
        exists = bool(qdrant_status.details.get("collection_exists"))
        count = self.vector_store.count_points()
        return ComponentStatus(
            ok=exists,
            status="ready" if exists else "missing",
            message="collection 已存在。" if exists else "collection 尚未创建，首次索引时会自动创建。",
            details={"collection": settings.qdrant_collection, "point_count": count},
        )

    def _llm_status(self) -> ComponentStatus:
        if settings.demo_mode:
            return ComponentStatus(ok=True, status="demo", message="DEMO_MODE=true，使用演示回答。")
        if not self.llm_service.is_configured():
            return ComponentStatus(ok=False, status="not_configured", message="真实模式未配置 LLM API key。")
        return ComponentStatus(ok=True, status="configured", message="LLM 已配置，尚未执行调用测试。")

    def _embedding_status(self) -> ComponentStatus:
        if settings.demo_mode:
            return ComponentStatus(ok=True, status="demo", message="DEMO_MODE=true，使用本地 hash embedding。")
        if not self.embedding_service.is_configured():
            return ComponentStatus(ok=False, status="not_configured", message="真实模式未配置 Embedding API key。")
        return ComponentStatus(ok=True, status="configured", message="Embedding 已配置，尚未执行调用测试。")

    def _ocr_status(self) -> ComponentStatus:
        if not self.ocr_provider.is_configured():
            return ComponentStatus(
                ok=False,
                status="not_configured",
                message="未配置真实 OCR provider。图片不会生成伪识别文本。",
                details={"provider": settings.ocr_provider, "model": self.ocr_provider.model},
            )
        return ComponentStatus(
            ok=True,
            status="configured",
            message="OCR provider 已配置，图片可执行真实 OCR。",
            details={"provider": settings.ocr_provider, "model": self.ocr_provider.model},
        )

    def _transcription_status(self) -> ComponentStatus:
        if not self.transcription_provider.is_configured():
            return ComponentStatus(
                ok=False,
                status="not_configured",
                message="未配置真实音频转写 provider。系统不会生成伪转写。",
                details={"provider": settings.transcription_provider, "model": self.transcription_provider.model},
            )
        return ComponentStatus(
            ok=True,
            status="configured",
            message="音频转写 provider 已配置。",
            details={"provider": settings.transcription_provider, "model": self.transcription_provider.model},
        )

    @staticmethod
    def _safe_database_url(database_url: str) -> str:
        if "@" not in database_url:
            return database_url
        prefix, rest = database_url.split("@", 1)
        scheme = prefix.split("://", 1)[0]
        return f"{scheme}://***:***@{rest}"

    @staticmethod
    def _safe_redis_url(redis_url: str) -> str:
        if "@" not in redis_url:
            return redis_url
        prefix, rest = redis_url.split("@", 1)
        scheme = prefix.split("://", 1)[0]
        return f"{scheme}://***:***@{rest}"


system_service = SystemService()
