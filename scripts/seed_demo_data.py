from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts.seed_showcase import BACKEND, seed
except ModuleNotFoundError:
    from seed_showcase import BACKEND, seed


DEFAULT_DATABASE = BACKEND / "data" / "demo_showcase.db"


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed an isolated synthetic V4.2 demo database.")
    parser.add_argument("--database-path", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--reset", action="store_true", help="Replace the existing demo database.")
    args = parser.parse_args()
    seed(args.database_path, reset=args.reset)
    print("Demo seed data is synthetic and labelled; it is not real OCR, transcription or LLM output.")


if __name__ == "__main__":
    main()
