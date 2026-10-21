from __future__ import annotations

import argparse
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
NODE_CAPTURE = ROOT / "frontend" / "e2e" / "capture-showcase.mjs"
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "screenshots"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture the synthetic V5 Evidence Agent GitHub showcase."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    subprocess.run(
        [
            "node",
            str(NODE_CAPTURE),
            "--base-url",
            args.base_url,
            "--output",
            str(args.output.resolve()),
        ],
        cwd=ROOT / "frontend",
        check=True,
    )


if __name__ == "__main__":
    main()
