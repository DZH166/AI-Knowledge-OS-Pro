from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402
from app.services.storage_integrity import storage_integrity_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit SQLite, uploaded files and evidence bookkeeping. Read-only unless --deep-hash reads file bytes."
    )
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument("--upload-dir", type=Path, default=settings.upload_dir)
    parser.add_argument("--deep-hash", action="store_true", help="Hash every referenced file and compare content fingerprints.")
    parser.add_argument("--no-orphans", action="store_true", help="Skip scanning uploads that no row references.")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path as well as stdout.")
    args = parser.parse_args()

    engine = create_database_engine(args.database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            report = storage_integrity_service.check(
                session,
                upload_dir=args.upload_dir,
                deep_hash=args.deep_hash,
                scan_orphans=not args.no_orphans,
            )
        payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        print(payload)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
        return 0 if report.ok else 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
