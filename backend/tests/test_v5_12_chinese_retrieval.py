from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.modules.evidence_index import (
    ActivateRevision,
    ActiveScope,
    ChunkDraft,
    CommandReceipt,
    GetRevision,
    PinnedScope,
    RevisionDraft,
    SearchEvidence,
    SqlEvidenceIndex,
    StageRevision,
    VerifiedPoint,
)
from app.services.hybrid_retriever import HybridRetriever
from app.services.rerank_provider import DisabledRerankProvider
from app.services.vector_store import VectorSearchResult


class _EmptyVectorStore:
    def search(self, **_kwargs):
        return []


def _hybrid() -> HybridRetriever:
    return HybridRetriever(vector_store=_EmptyVectorStore(), rerank_provider=DisabledRerankProvider())


def _activate(
    db: Session,
    space: KnowledgeSpace,
    *texts: str,
    source: Source | None = None,
) -> tuple[Source, CommandReceipt]:
    if source is None:
        source = Source(space_id=space.id, source_type="document", title="Chinese evidence", status="uploaded")
        db.add(source)
        db.commit()
    index = SqlEvidenceIndex(db)
    receipt = index.command(StageRevision(
        command_id=str(uuid4()),
        draft=RevisionDraft(
            source_id=source.id,
            content_hash=sha256("\n".join(texts).encode()).hexdigest(),
            index_version="v512-public-search-tests",
            collection_name="offline-no-vector-service",
            chunks=tuple(ChunkDraft(ordinal, "text", text, {"kind": "pdf_page", "page": ordinal + 1}) for ordinal, text in enumerate(texts)),
        ),
    ))
    revision = index.query(GetRevision(receipt.revision_id))
    index.command(ActivateRevision(
        command_id=str(uuid4()),
        revision_id=receipt.revision_id,
        verified_points=tuple(VerifiedPoint(point.point_id, point.payload_digest) for point in revision.points),
    ))
    return source, receipt


def test_natural_chinese_question_finds_literal_evidence_without_spaces(db_session, knowledge_space) -> None:
    content = "系统采用混合检索结合向量与关键词，减少术语漏召回。"
    _activate(db_session, knowledge_space, content)

    hits = SqlEvidenceIndex(db_session).search(SearchEvidence(
        text="为什么混合检索能减少漏召回？", scope=ActiveScope(knowledge_space.id),
    )).hits

    assert [hit.evidence.excerpt for hit in hits] == [content]


def test_hybrid_preserves_natural_chinese_keyword_recall(db_session, knowledge_space) -> None:
    content = "系统采用混合检索结合向量与关键词，减少术语漏召回。"
    _activate(db_session, knowledge_space, content)

    hits = _hybrid().search(db_session, space_id=knowledge_space.id,
                          query="为什么混合检索能减少漏召回？", query_vector=[], limit=5, score_threshold=0.0)

    assert [hit.payload["content"] for hit in hits] == [content]


def test_keyword_coverage_beats_repeated_generic_words(db_session, knowledge_space) -> None:
    specific = "检索请求发生超时后执行重试。"
    _activate(db_session, knowledge_space, "检索 超时 " * 50, specific)

    hits = _hybrid().search(db_session, space_id=knowledge_space.id, query="检索 超时 重试",
                          query_vector=[], limit=2, score_threshold=0.0)

    assert hits[0].payload["content"] == specific


def test_pinned_hybrid_source_filter_precedes_the_canonical_candidate_cap(db_session, knowledge_space) -> None:
    content = "检索请求发生超时后执行重试。"
    _, excluded = _activate(db_session, knowledge_space, *([content] * 101))
    selected_source, selected = _activate(db_session, knowledge_space,
                                        *(["与问题无关的索引占位内容。"] * 100), content)

    hits = _hybrid().search(db_session, space_id=knowledge_space.id, query="检索 超时 重试",
                          query_vector=[], limit=1, score_threshold=0.0,
                          source_ids=(selected_source.id,), revision_ids=(excluded.revision_id, selected.revision_id))

    assert [(hit.source_id, hit.payload["revision_id"], hit.payload["content"]) for hit in hits] == [
        (selected_source.id, selected.revision_id, content),
    ]


@pytest.mark.parametrize("query", [
    "ＲＡＧ：检索预算最多８次？",
    "RAG 8 次",
    "rag budget 8",
    "检索预算，8：RAG",
])
@pytest.mark.parametrize("path", ["sql", "hybrid"])
def test_width_punctuation_ascii_and_numeric_literals_remain_searchable(db_session, knowledge_space, query, path) -> None:
    content = "RAG budget 最多允许 8 次检索调用，超过预算后停止。"
    _activate(db_session, knowledge_space, content)

    if path == "sql":
        result = SqlEvidenceIndex(db_session).search(SearchEvidence(query, ActiveScope(knowledge_space.id)))
        contents = [hit.evidence.excerpt for hit in result.hits]
    else:
        contents = [hit.payload["content"] for hit in _hybrid().search(
            db_session, space_id=knowledge_space.id, query=query, query_vector=[], score_threshold=0.0,
        )]

    assert contents == [content]


@pytest.mark.parametrize("path", ["sql", "hybrid"])
def test_chinese_search_keeps_active_and_pinned_evidence_identity(db_session, knowledge_space, path) -> None:
    old_text = "旧版缓存设置为 5 分钟，超时后允许一次重试。"
    new_text = "新版缓存设置为 10 分钟，超时后允许两次重试。"
    source, old = _activate(db_session, knowledge_space, old_text)
    _, new = _activate(db_session, knowledge_space, new_text, source=source)
    query = "缓存超时以后怎么重试？"

    if path == "sql":
        index = SqlEvidenceIndex(db_session)
        active = index.search(SearchEvidence(query, ActiveScope(knowledge_space.id))).hits
        pinned = index.search(SearchEvidence(query, PinnedScope(knowledge_space.id, (old.revision_id,)))).hits
        assert [hit.evidence.revision_id for hit in active] == [new.revision_id]
        assert len(pinned) == 1
        evidence = pinned[0].evidence
        assert (evidence.source_id, evidence.revision_id, evidence.index_revision_id, evidence.content_hash,
                evidence.excerpt, evidence.locator, evidence.currently_active) == (
            source.id, old.revision_id, old.index_revision_id, sha256(old_text.encode()).hexdigest(),
            old_text, {"kind": "pdf_page", "page": 1}, False,
        )
    else:
        retriever = _hybrid()
        active = retriever.search(db_session, space_id=knowledge_space.id, query=query, query_vector=[], score_threshold=0.0)
        pinned = retriever.search(db_session, space_id=knowledge_space.id, query=query, query_vector=[],
                                  revision_ids=(old.revision_id,), score_threshold=0.0)
        assert [hit.payload["revision_id"] for hit in active] == [new.revision_id]
        assert len(pinned) == 1
        payload = pinned[0].payload
        assert (payload["source_id"], payload["revision_id"], payload["index_revision_id"], payload["content_hash"],
                payload["content"], payload["locator"]) == (
            source.id, old.revision_id, old.index_revision_id, sha256(old_text.encode()).hexdigest(),
            old_text, {"kind": "pdf_page", "page": 1},
        )


@pytest.mark.parametrize("path", ["sql", "hybrid"])
def test_chinese_search_never_crosses_space_or_explicit_source_scope(db_session, knowledge_space, path) -> None:
    content = "检索请求发生超时后执行重试。"
    selected, _ = _activate(db_session, knowledge_space, content)
    _activate(db_session, knowledge_space, content)
    other_space = KnowledgeSpace(name="Private other space")
    db_session.add(other_space)
    db_session.commit()
    _, other_revision = _activate(db_session, other_space, content)

    if path == "sql":
        index = SqlEvidenceIndex(db_session)
        active = index.search(SearchEvidence("检索超时怎么重试？", ActiveScope(knowledge_space.id, (selected.id,)))).hits
        forbidden = index.search(SearchEvidence("检索超时怎么重试？", PinnedScope(knowledge_space.id, (other_revision.revision_id,)))).hits
        assert [hit.evidence.source_id for hit in active] == [selected.id]
    else:
        retriever = _hybrid()
        active = retriever.search(db_session, space_id=knowledge_space.id, query="检索超时怎么重试？", query_vector=[],
                                 source_ids=(selected.id,), score_threshold=0.0)
        forbidden = retriever.search(db_session, space_id=knowledge_space.id, query="检索超时怎么重试？", query_vector=[],
                                    revision_ids=(other_revision.revision_id,), score_threshold=0.0)
        assert [hit.source_id for hit in active] == [selected.id]
    assert forbidden == [] or forbidden == ()


@pytest.mark.parametrize("legacy", ["document", "canonical_without_index_pointer"])
def test_legacy_hybrid_keyword_paths_share_chinese_analysis(db_session, knowledge_space, legacy) -> None:
    content = "系统采用混合检索结合向量与关键词，减少术语漏召回。"
    if legacy == "document":
        document = Document(space_id=knowledge_space.id, filename="legacy.md", original_filename="legacy.md", file_type="md",
                            file_size=10, storage_path="legacy.md", status="ready", vector_status="indexed")
        db_session.add(document)
        db_session.flush()
        db_session.add(Chunk(document_id=document.id, space_id=knowledge_space.id, chunk_index=0, content=content,
                             content_preview=content, char_count=len(content)))
        db_session.commit()
    else:
        source, _ = _activate(db_session, knowledge_space, content)
        source.active_index_revision_id = None
        db_session.commit()

    hits = _hybrid().search(db_session, space_id=knowledge_space.id, query="为什么混合检索能减少漏召回？",
                          query_vector=[], score_threshold=0.0)

    assert [hit.payload["content"] for hit in hits] == [content]


@pytest.mark.parametrize("path", ["sql", "hybrid"])
def test_mixed_identifier_query_does_not_turn_generic_suffix_into_keyword_corroboration(db_session, knowledge_space, path) -> None:
    selected, _ = _activate(db_session, knowledge_space, "Zeta 样本量事实是 2400 个。")
    unrelated, _ = _activate(db_session, knowledge_space, "Omega1 当前版本事实是新版 1。")
    query = "Zeta 样本量事实"
    index = SqlEvidenceIndex(db_session)

    if path == "sql":
        hits = index.search(SearchEvidence(query, ActiveScope(knowledge_space.id))).hits
        assert [hit.evidence.source_id for hit in hits] == [selected.id]
    else:
        # Real vector providers can return weak semantic candidates. A shared
        # generic Chinese suffix must not manufacture a second retrieval signal.
        candidates = index.search(SearchEvidence("事实", ActiveScope(knowledge_space.id))).hits
        vector_hits = []
        for hit in candidates:
            evidence = hit.evidence
            vector_hits.append(VectorSearchResult(
                score=0.9 if evidence.source_id == selected.id else 0.28,
                payload={"space_id": knowledge_space.id, "source_id": evidence.source_id,
                         "revision_id": evidence.revision_id, "index_revision_id": evidence.index_revision_id,
                         "chunk_id": evidence.chunk_id, "content_hash": evidence.content_hash,
                         "content": evidence.excerpt, "source_type": evidence.source_type,
                         "modality": evidence.modality, "locator": evidence.locator},
            ))

        class FixedVectorStore:
            def search(self, **_kwargs):
                return vector_hits

        hits = HybridRetriever(vector_store=FixedVectorStore(), rerank_provider=DisabledRerankProvider()).search(
            db_session, space_id=knowledge_space.id, query=query, query_vector=[], limit=5, score_threshold=0.0,
        )
        unrelated_hit = next(hit for hit in hits if hit.source_id == unrelated.id)
        assert unrelated_hit.keyword_score is None


@pytest.mark.parametrize("path", ["sql", "hybrid"])
def test_mixed_question_can_match_multiple_chinese_fragments_without_english_label(db_session, knowledge_space, path) -> None:
    content = "每条引用绑定版本和内容指纹，确保结果可追溯。"
    _activate(db_session, knowledge_space, content)
    query = "RAG 里怎么保持引用可追溯？"

    if path == "sql":
        hits = SqlEvidenceIndex(db_session).search(SearchEvidence(query, ActiveScope(knowledge_space.id))).hits
        assert [hit.evidence.excerpt for hit in hits] == [content]
    else:
        hits = _hybrid().search(db_session, space_id=knowledge_space.id, query=query, query_vector=[], score_threshold=0.0)
        assert [hit.payload["content"] for hit in hits] == [content]
