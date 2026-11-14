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
from app.services.storage_backup import (  # noqa: E402
    StorageBackupError,
    create_backup,
    summary_dict,
    verify_backup,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or verify a consistent SQLite + uploads backup for Evidence OS."
    )
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument("--upload-dir", type=Path, default=settings.upload_dir)
    parser.add_argument("--output", type=Path, help="Archive path for a new backup.")
    parser.add_argument("--label", default=None, help="Optional label stored in the manifest.")
    parser.add_argument("--verify", type=Path, help="Verify an existing archive instead of creating one.")
    args = parser.parse_args()

    try:
        if args.verify:
            result = verify_backup(args.verify)
            print(json.dumps(summary_dict(result), ensure_ascii=False, indent=2))
            return 0 if result.ok else 2
        if not args.output:
            parser.error("--output is required when creating a backup")
        summary = create_backup(
            database_url=args.database_url,
            upload_dir=args.upload_dir,
            output=args.output,
            label=args.label,
        )
        print(json.dumps(summary_dict(summary), ensure_ascii=False, indent=2))
        return 0
    except StorageBackupError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
