from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from uuid import uuid4

from qdrant_client import QdrantClient
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402
from app.modules.evidence_index import ReconcileIndex, SqlEvidenceIndex  # noqa: E402
from app.modules.evidence_index.vector_adapter import QdrantVectorAdapter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit SQL vector manifests against Qdrant. Dry-run is the default."
    )
    parser.add_argument("--apply", action="store_true", help="Apply safe repairs after reporting issues.")
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument("--collection", default=settings.qdrant_collection)
    args = parser.parse_args()

    engine = create_database_engine(args.database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=settings.qdrant_timeout_seconds,
        check_compatibility=False,
    )
    try:
        with factory() as session:
            report = SqlEvidenceIndex(session, QdrantVectorAdapter(client)).command(
                ReconcileIndex(
                    command_id=f"cli-reconcile-{uuid4().hex}",
                    collection_name=args.collection,
                    apply=args.apply,
                )
            )
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
        return 0 if not report.issues or report.applied else 2
    finally:
        client.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
