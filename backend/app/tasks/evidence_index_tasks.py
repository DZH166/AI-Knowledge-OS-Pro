from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from qdrant_client import QdrantClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.evidence_index import ReconcileIndex, SqlEvidenceIndex
from app.modules.evidence_index.vector_adapter import QdrantVectorAdapter


def reconcile_evidence_index(apply: bool = False) -> dict[str, object]:
    """Run one bounded reconciliation pass; RQ retries are safe and idempotent."""

    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=settings.qdrant_timeout_seconds,
        check_compatibility=False,
    )
    try:
        with SessionLocal() as session:
            report = SqlEvidenceIndex(
                session,
                QdrantVectorAdapter(client),
            ).command(
                ReconcileIndex(
                    command_id=f"rq-reconcile-{uuid4().hex}",
                    collection_name=settings.qdrant_collection,
                    apply=apply,
                )
            )
            return asdict(report)
    finally:
        client.close()
