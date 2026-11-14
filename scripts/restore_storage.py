from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402
from app.services.storage_backup import StorageBackupError, restore_backup  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify and restore a SQLite + uploads backup. Previous state is kept beside the target."
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument("--upload-dir", type=Path, default=settings.upload_dir)
    parser.add_argument("--force", action="store_true", help="Replace non-empty targets after keeping a sibling copy.")
    args = parser.parse_args()

    try:
        result = restore_backup(
            archive_path=args.archive,
            database_url=args.database_url,
            upload_dir=args.upload_dir,
            force=args.force,
        )
    except StorageBackupError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
