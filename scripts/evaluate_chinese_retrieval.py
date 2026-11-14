"""Offline, labeled retrieval evaluation; never calls a model or vector service."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app import models  # noqa: E402,F401 - register all related SQL tables
from app.db.session import Base  # noqa: E402
from app.models.knowledge_space import KnowledgeSpace  # noqa: E402
from app.models.source import MultimodalChunk, Source  # noqa: E402
from app.modules.evidence_index import (  # noqa: E402
    ActivateRevision,
    ActiveScope,
    ChunkDraft,
    GetRevision,
    PinnedScope,
    RevisionDraft,
    SearchEvidence,
    SqlEvidenceIndex,
    StageRevision,
    VerifiedPoint,
)
from app.services.hybrid_retriever import HybridRetriever  # noqa: E402
from app.services.rerank_provider import DisabledRerankProvider  # noqa: E402

DATASET_PATH = ROOT / "evaluation" / "chinese_retrieval" / "v1.json"
IMPLEMENTATION_FILES = (
    "backend/app/modules/evidence_index/sql.py",
    "backend/app/services/hybrid_retriever.py",
    "backend/app/services/lexical_retrieval.py",
)
TOP_K = 5


def _text_hash(path: Path) -> str:
    return sha256(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def _fields(value: Any, required: set[str], optional: set[str], label: str) -> None:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError(f"{label}: unknown or missing fields; required={sorted(required)}")


def _text(value: Any, label: str, *, key: bool = False) -> str:
    if not isinstance(value, str) or not value.strip() or (key and ("/" in value or value != value.strip())):
        raise ValueError(f"{label}: expected non-empty text" + (" without '/' or surrounding whitespace" if key else ""))
    return value


def _positive_int(value: Any, label: str, maximum: int | None = None) -> None:
    if type(value) is not int or value < 1 or (maximum is not None and value > maximum):
        raise ValueError(f"{label}: expected a positive integer" + (f" <= {maximum}" if maximum else ""))


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{label}: expected a list of non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label}: duplicate references")
    return value


def _load(path: Path) -> dict[str, Any]:
    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Dataset must be readable UTF-8 JSON: {path}") from exc
    _fields(dataset, {"schema_version", "dataset_id", "sources", "queries"}, set(), "dataset")
    if type(dataset["schema_version"]) is not int or dataset["schema_version"] != 1:
        raise ValueError("dataset.schema_version must be 1")
    _text(dataset["dataset_id"], "dataset.dataset_id")
    for name in ("sources", "queries"):
        if not isinstance(dataset[name], list) or not dataset[name]:
            raise ValueError(f"dataset.{name}: expected a non-empty list")
    sources: dict[str, dict[str, Any]] = {}
    revisions: dict[str, str] = {}
    chunks: dict[str, tuple[str, str]] = {}
    for source in dataset["sources"]:
        _fields(source, {"key", "space_id", "versions"}, set(), "source")
        source_key = _text(source["key"], "source.key", key=True)
        if source_key in sources:
            raise ValueError(f"Duplicate source key: {source_key}")
        sources[source_key] = source
        _positive_int(source["space_id"], f"{source_key}.space_id")
        if not isinstance(source["versions"], list) or not source["versions"]:
            raise ValueError(f"{source_key}.versions: expected a non-empty list")
        for version in source["versions"]:
            _fields(version, {"key", "chunks"}, set(), f"{source_key}.version")
            version_key = f"{source_key}/{_text(version['key'], 'version.key', key=True)}"
            if version_key in revisions:
                raise ValueError(f"Duplicate revision key: {version_key}")
            revisions[version_key] = source_key
            if not isinstance(version["chunks"], list) or not version["chunks"]:
                raise ValueError(f"{version_key}.chunks: expected a non-empty list")
            for chunk in version["chunks"]:
                _fields(chunk, {"key", "text"}, {"repeat"}, f"{version_key}.chunk")
                chunk_key = f"{version_key}/{_text(chunk['key'], 'chunk.key', key=True)}"
                if chunk_key in chunks:
                    raise ValueError(f"Duplicate chunk key: {chunk_key}")
                chunks[chunk_key] = (source_key, version_key)
                _text(chunk["text"], f"{chunk_key}.text")
                _positive_int(chunk.get("repeat", 1), f"{chunk_key}.repeat", 1000)
    query_ids: set[str] = set()
    for query in dataset["queries"]:
        _fields(query, {"id", "category", "space_id", "text", "expected"}, {"source_keys", "revision_keys"}, "query")
        query_id = _text(query["id"], "query.id", key=True)
        if query_id in query_ids:
            raise ValueError(f"Duplicate query id: {query_id}")
        query_ids.add(query_id)
        _text(query["category"], f"{query_id}.category")
        _text(query["text"], f"{query_id}.text")
        if type(query["space_id"]) is not int:
            raise ValueError(f"{query_id}.space_id: expected an integer")
        if "source_keys" in query and "revision_keys" in query:
            raise ValueError(f"{query_id}: source_keys and revision_keys cannot be combined in this evaluator")
        for field, known in (("source_keys", sources), ("revision_keys", revisions), ("expected", chunks)):
            for ref in _strings(query.get(field, []), f"{query_id}.{field}"):
                if ref not in known:
                    raise ValueError(f"{query_id}.{field}: unknown reference {ref!r}")
        for expected in query["expected"]:
            source_key, revision_key = chunks[expected]
            source = sources[source_key]
            active = f"{source_key}/{source['versions'][-1]['key']}"
            if (
                source["space_id"] != query["space_id"]
                or (query.get("source_keys") and source_key not in query["source_keys"])
                or ("revision_keys" in query and revision_key not in query["revision_keys"])
                or ("revision_keys" not in query and revision_key != active)
            ):
                raise ValueError(f"{query_id}.expected: reference {expected!r} lies outside the query scope")
    return dataset


@dataclass(frozen=True)
class _Fixture:
    case_key: str
    source_key: str
    revision_key: str
    space_id: int
    source_id: int
    revision_id: int
    index_revision_id: int
    chunk_id: int
    content_hash: str
    content: str
    locator: dict[str, Any]
    active: bool


class _EmptyVectorStore:
    """Explicitly empty external-vector boundary, not simulated model quality."""

    def __init__(self) -> None:
        self.calls = 0

    def search(self, **_kwargs: Any) -> list[Any]:
        self.calls += 1
        return []


def _build(db: Session, dataset: dict[str, Any]) -> tuple[list[_Fixture], dict[str, int], dict[str, int]]:
    spaces = {item["space_id"] for item in dataset["sources"] + dataset["queries"]}
    db.add_all(KnowledgeSpace(id=space_id, name=f"Chinese evaluation {space_id}") for space_id in sorted(spaces))
    db.commit()
    index = SqlEvidenceIndex(db)
    fixtures: list[_Fixture] = []
    source_ids: dict[str, int] = {}
    revision_ids: dict[str, int] = {}
    for source_spec in dataset["sources"]:
        source_key = source_spec["key"]
        source = Source(space_id=source_spec["space_id"], source_type="document", title=source_key, status="uploaded")
        db.add(source)
        db.commit()
        source_ids[source_key] = source.id
        for number, version in enumerate(source_spec["versions"], start=1):
            revision_key = f"{source_key}/{version['key']}"
            drafts = tuple(
                ChunkDraft(
                    chunk_index=ordinal,
                    modality="text",
                    content=chunk["text"] * chunk.get("repeat", 1),
                    locator={"kind": "pdf_page", "page": ordinal + 1, "case_key": f"{revision_key}/{chunk['key']}"},
                )
                for ordinal, chunk in enumerate(version["chunks"])
            )
            content_hash = sha256(json.dumps([draft.content for draft in drafts], ensure_ascii=False).encode()).hexdigest()
            receipt = index.command(StageRevision(
                command_id=f"chinese-eval-stage:{revision_key}",
                draft=RevisionDraft(source_id=source.id, content_hash=content_hash, index_version="chinese-retrieval-v1", collection_name="offline-no-vectors", chunks=drafts),
            ))
            view = index.query(GetRevision(receipt.revision_id))
            index.command(ActivateRevision(
                command_id=f"chinese-eval-activate:{revision_key}",
                revision_id=receipt.revision_id,
                verified_points=tuple(VerifiedPoint(point.point_id, point.payload_digest) for point in view.points),
            ))
            revision_ids[revision_key] = receipt.revision_id
            stored = list(db.scalars(select(MultimodalChunk).where(MultimodalChunk.revision_id == receipt.revision_id).order_by(MultimodalChunk.chunk_index)))
            for draft, chunk in zip(drafts, stored, strict=True):
                fixtures.append(_Fixture(
                    case_key=draft.locator["case_key"], source_key=source_key, revision_key=revision_key,
                    space_id=source.space_id, source_id=source.id, revision_id=receipt.revision_id,
                    index_revision_id=receipt.index_revision_id, chunk_id=chunk.id,
                    content_hash=sha256(draft.content.encode()).hexdigest(), content=draft.content,
                    locator=dict(draft.locator), active=number == len(source_spec["versions"]),
                ))
    return fixtures, source_ids, revision_ids


def _path_result(rows: list[dict[str, Any]], query: dict[str, Any], fixtures: list[_Fixture]) -> dict[str, Any]:
    by_chunk = {item.chunk_id: item for item in fixtures}
    ranking: list[dict[str, Any]] = []
    for rank, row in enumerate(rows, start=1):
        fixture = by_chunk.get(row.get("chunk_id"))
        scope_valid = bool(fixture and fixture.space_id == query["space_id"] and (
            fixture.revision_key in query["revision_keys"] if "revision_keys" in query
            else fixture.active and (not query.get("source_keys") or fixture.source_key in query["source_keys"])
        ))
        identity_valid = bool(fixture and all(row.get(name) == getattr(fixture, name) for name in (
            "source_id", "revision_id", "index_revision_id", "chunk_id", "content_hash", "content", "locator",
        )))
        ranking.append({"rank": rank, "case_key": fixture.case_key if fixture else None, **row,
                        "scope_valid": scope_valid, "identity_valid": identity_valid})
    expected = set(query["expected"])
    relevant_ranks = [item["rank"] for item in ranking if item["scope_valid"] and item["identity_valid"] and item["case_key"] in expected]
    return {
        "expected": query["expected"], "ranking": ranking,
        "hit1": 1 in relevant_ranks, "hit5": any(rank <= TOP_K for rank in relevant_ranks),
        "rr": round(1 / relevant_ranks[0], 6) if relevant_ranks else 0.0,
        "empty_success": not ranking if not expected else None,
        "scope_violations": sum(not item["scope_valid"] for item in ranking),
        "identity_violations": sum(not item["identity_valid"] for item in ranking),
    }


def evaluate(path: Path = DATASET_PATH) -> dict[str, Any]:
    """Evaluate public SQL and sparse-only hybrid paths against immutable labels."""
    path = Path(path).resolve()
    dataset = _load(path)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    vector_store = _EmptyVectorStore()
    try:
        with Session(engine, expire_on_commit=False) as db:
            fixtures, source_ids, revision_ids = _build(db, dataset)
            index = SqlEvidenceIndex(db)
            hybrid = HybridRetriever(vector_store=vector_store, rerank_provider=DisabledRerankProvider())
            cases: list[dict[str, Any]] = []
            for query in dataset["queries"]:
                selected_sources = tuple(source_ids[key] for key in query.get("source_keys", []))
                selected_revisions = tuple(revision_ids[key] for key in query["revision_keys"]) if "revision_keys" in query else None
                scope = PinnedScope(query["space_id"], selected_revisions) if selected_revisions is not None else ActiveScope(query["space_id"], selected_sources)
                sql_hits = index.search(SearchEvidence(text=query["text"], scope=scope, limit=100)).hits
                sql_rows = [{"source_id": hit.evidence.source_id, "revision_id": hit.evidence.revision_id,
                             "index_revision_id": hit.evidence.index_revision_id, "chunk_id": hit.evidence.chunk_id,
                             "content_hash": hit.evidence.content_hash, "content": hit.evidence.excerpt,
                             "locator": dict(hit.evidence.locator), "score": hit.score} for hit in sql_hits]
                hybrid_hits = hybrid.search(db, space_id=query["space_id"], query=query["text"], query_vector=[],
                                            source_ids=selected_sources, revision_ids=selected_revisions,
                                            limit=100, score_threshold=0.0, dense_score_threshold=0.0)
                hybrid_rows = [{name: hit.payload.get(name) for name in (
                    "source_id", "revision_id", "index_revision_id", "chunk_id", "content_hash", "content", "locator",
                )} | {"score": hit.final_score, "keyword_score": hit.keyword_score, "reason": hit.reason} for hit in hybrid_hits]
                cases.append({**query, "paths": {
                    "evidence_index": _path_result(sql_rows, query, fixtures),
                    "hybrid_sparse_only": _path_result(hybrid_rows, query, fixtures),
                }})
        metrics: dict[str, Any] = {}
        for name in ("evidence_index", "hybrid_sparse_only"):
            positive = [item["paths"][name] for item in cases if item["expected"]]
            negative = [item["paths"][name] for item in cases if not item["expected"]]
            metrics[name] = {
                "positive_queries": len(positive), "negative_queries": len(negative),
                "hit_at_1": round(sum(item["hit1"] for item in positive) / len(positive), 6) if positive else None,
                "hit_at_5": round(sum(item["hit5"] for item in positive) / len(positive), 6) if positive else None,
                "mrr": round(sum(item["rr"] for item in positive) / len(positive), 6) if positive else None,
                "negative_empty_successes": sum(item["empty_success"] for item in negative),
                "scope_violations": sum(item["scope_violations"] for item in positive + negative),
                "identity_violations": sum(item["identity_violations"] for item in positive + negative),
            }
        strict_passed = all(item["scope_violations"] == item["identity_violations"] == 0 and item["negative_empty_successes"] == item["negative_queries"] for item in metrics.values())
        return {
            "schema_version": 1, "dataset_id": dataset["dataset_id"], "dataset_sha256": _text_hash(path),
            "dataset_path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "implementation_sha256": {name: _text_hash(ROOT / name) if (ROOT / name).is_file() else None for name in IMPLEMENTATION_FILES},
            "evaluator_sha256": _text_hash(Path(__file__)),
            "boundary": "Retrieval-only synthetic fixtures; no model, embedding, external vector or rerank calls. Does not measure real-model answer quality.",
            "providers": {"model": "not_used", "embedding": "not_used", "vector": "explicit_empty_adapter", "rerank": "disabled", "external_calls": 0, "local_empty_vector_searches": vector_store.calls},
            "top_k": TOP_K, "retrieval_limit": 100, "strict_passed": strict_passed,
            "category_counts": dict(sorted(Counter(item["category"] for item in cases).items())),
            "fixtures": [asdict(item) for item in fixtures], "metrics": metrics, "queries": cases,
        }
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true", help="Fail on scope/identity/negative-case errors; positive retrieval scores stay visible.")
    args = parser.parse_args()
    if args.output and args.output.resolve() == args.dataset.resolve():
        parser.error("--output must not overwrite the dataset")
    try:
        report = evaluate(args.dataset)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "strict_passed": report["strict_passed"], "metrics": report["metrics"]}))
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if args.strict and not report["strict_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
