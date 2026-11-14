from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.services.chunker import Chunker  # noqa: E402


def make_document(index: int) -> str:
    body = (
        f"# Synthetic document {index}\n\n"
        "## Evidence\n\n"
        "Every answer should point back to a source revision and a locator. "
        "This paragraph is intentionally repeated to create predictable chunks.\n\n"
        "```python\n"
        "def retrieve(query):\n"
        "    return evidence_index.search(query)\n"
        "```\n\n"
        "## Notes\n\n"
        "中文段落用于检查混合语言切片，不应依赖外部模型或网络。"
    )
    return (body + "\n\n") * 8


def benchmark(count: int) -> dict[str, object]:
    chunker = Chunker()
    tracemalloc.start()
    started = time.perf_counter()
    chunks = 0
    for index in range(count):
        chunks += len(chunker.split(make_document(index)))
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "documents": count,
        "chunks": chunks,
        "elapsed_seconds": round(elapsed, 3),
        "documents_per_second": round(count / elapsed, 1) if elapsed else None,
        "chunks_per_second": round(chunks / elapsed, 1) if elapsed else None,
        "peak_memory_mb": round(peak / (1024 * 1024), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark deterministic text chunking without providers or Qdrant.")
    parser.add_argument("--documents", default="1000,10000", help="Comma-separated document counts.")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence path.")
    args = parser.parse_args()

    counts = [int(value.strip()) for value in args.documents.split(",") if value.strip()]
    results = [benchmark(count) for count in counts]
    payload = {
        "mode": "synthetic_chunking",
        "note": "Component benchmark only: measures Chunker CPU/memory, not end-to-end ingestion or retrieval.",
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
