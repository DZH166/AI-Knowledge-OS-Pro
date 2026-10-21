from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from threading import Barrier, BrokenBarrierError, Lock

import pytest
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base, create_database_engine
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import MultimodalChunk, Source
from app.modules.evidence_index import (
    ActiveEvidenceRef,
    ActiveScope,
    ActivateRevision,
    ActivationInvariantError,
    ChunkDraft,
    GetEvidenceChunk,
    GetEvidenceNeighbors,
    GetRevision,
    GetSourceState,
    PinnedEvidenceRef,
    PinnedScope,
    InvalidRevisionDraftError,
    InvalidEvidenceWindowError,
    RevisionLifecycleConflictError,
    RevisionDraft,
    SearchEvidence,
    SqlEvidenceIndex,
    StageRevision,
    VerifiedPoint,
)


def test_exact_chunk_and_bounded_neighbors_stay_inside_the_pinned_revision(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space, title="Bounded evidence window")
    evidence_index = SqlEvidenceIndex(db_session)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-bounded-window",
            draft=RevisionDraft(
                source_id=source.id,
                content_hash=sha256(b"bounded-window").hexdigest(),
                index_version="v5-test",
                collection_name="test-evidence",
                chunks=tuple(
                    ChunkDraft(
                        chunk_index=index,
                        modality="text",
                        content=f"bounded context chunk {index}",
                        locator={"kind": "pdf_page", "page": index + 1},
                    )
                    for index in range(5)
                ),
            ),
        )
    )
    staged_view = evidence_index.query(GetRevision(staged.revision_id))
    evidence_index.command(
        ActivateRevision(
            command_id="activate-bounded-window",
            revision_id=staged.revision_id,
            verified_points=tuple(
                VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                for point in staged_view.points
            ),
        )
    )
    chunks = list(
        db_session.scalars(
            select(MultimodalChunk)
            .where(MultimodalChunk.revision_id == staged.revision_id)
            .order_by(MultimodalChunk.chunk_index)
        )
    )

    opened = evidence_index.query(
        GetEvidenceChunk(revision_id=staged.revision_id, chunk_id=chunks[2].id)
    )
    neighbors = evidence_index.query(
        GetEvidenceNeighbors(
            revision_id=staged.revision_id,
            chunk_id=chunks[2].id,
            before=1,
            after=2,
        )
    )

    assert opened.chunk_id == chunks[2].id
    assert opened.revision_id == staged.revision_id
    assert opened.excerpt == "bounded context chunk 2"
    assert [item.chunk_id for item in neighbors.items] == [
        chunks[1].id,
        chunks[2].id,
        chunks[3].id,
        chunks[4].id,
    ]
    assert all(item.revision_id == staged.revision_id for item in neighbors.items)

    with pytest.raises(InvalidEvidenceWindowError):
        evidence_index.query(
            GetEvidenceNeighbors(
                revision_id=staged.revision_id,
                chunk_id=chunks[2].id,
                before=4,
                after=0,
            )
        )


def _synchronize_revision_number_reads(engine: Engine) -> None:
    barrier = Barrier(2, timeout=1)
    lock = Lock()
    synchronized_reads = 0

    @event.listens_for(engine, "after_cursor_execute")
    def _wait_after_revision_number_read(
        _connection,
        _cursor,
        statement: str,
        _parameters,
        _context,
        _executemany: bool,
    ) -> None:
        nonlocal synchronized_reads
        normalized = " ".join(statement.lower().split())
        if "max(source_revisions.revision_number)" not in normalized:
            return
        with lock:
            if synchronized_reads >= 2:
                return
            synchronized_reads += 1
        try:
            barrier.wait()
        except BrokenBarrierError:
            # A correct implementation may serialize before allocating the number.
            pass


def _synchronize_operation_reads(engine: Engine, command_id: str) -> None:
    barrier = Barrier(2, timeout=1)
    lock = Lock()
    synchronized_reads = 0

    @event.listens_for(engine, "after_cursor_execute")
    def _wait_after_operation_read(
        _connection,
        _cursor,
        statement: str,
        parameters,
        _context,
        _executemany: bool,
    ) -> None:
        nonlocal synchronized_reads
        normalized = " ".join(statement.lower().split())
        if "from index_operations" not in normalized or command_id not in parameters:
            return
        with lock:
            if synchronized_reads >= 2:
                return
            synchronized_reads += 1
        try:
            barrier.wait()
        except BrokenBarrierError:
            # A correct implementation may serialize before checking idempotency.
            pass


def _source(db: Session, space: KnowledgeSpace, *, title: str = "Evidence source") -> Source:
    source = Source(
        space_id=space.id,
        source_type="document",
        title=title,
        file_size=100,
        status="uploaded",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def _draft(source: Source, *, content: str, page: int) -> RevisionDraft:
    return RevisionDraft(
        source_id=source.id,
        content_hash=sha256(f"file:{content}".encode()).hexdigest(),
        parser_name="pytest-parser",
        parser_version="1",
        index_version="v5-test",
        embedding_provider="fixture",
        embedding_model="fixture-8d",
        embedding_dimensions=8,
        embedding_fingerprint="fixture::8d::v1",
        collection_name="test-evidence",
        chunks=(
            ChunkDraft(
                chunk_index=0,
                modality="text",
                content=content,
                locator={"kind": "pdf_page", "page": page},
            ),
        ),
    )


def test_staging_a_revision_is_idempotent_at_the_command_seam(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    evidence_index = SqlEvidenceIndex(db_session)
    command = StageRevision(
        command_id="stage-source-1-revision-1",
        draft=_draft(source, content="first immutable fact", page=3),
    )

    first = evidence_index.command(command)
    replay = evidence_index.command(command)
    revision = evidence_index.query(GetRevision(first.revision_id))
    source_state = evidence_index.query(GetSourceState(source.id))

    assert replay.operation_id == first.operation_id
    assert replay.replayed is True
    assert revision.status == "staging"
    assert revision.chunk_count == 1
    assert source_state.revision_ids == (first.revision_id,)


def test_concurrent_staging_for_one_source_never_leaks_a_database_conflict(
    tmp_path: Path,
) -> None:
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'concurrent-stage.db').as_posix()}")
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    with session_factory() as setup_session:
        space = KnowledgeSpace(name="Concurrent evidence", description="pytest")
        setup_session.add(space)
        setup_session.commit()
        source = _source(setup_session, space, title="Concurrent source")
    _synchronize_revision_number_reads(engine)
    start_barrier = Barrier(2, timeout=5)

    def stage(command: StageRevision):
        with session_factory() as worker_session:
            try:
                start_barrier.wait()
                return SqlEvidenceIndex(worker_session).command(command)
            except Exception as error:  # noqa: BLE001 - the assertion rejects raw DB errors
                return error

    commands = (
        StageRevision(
            command_id="concurrent-stage-a",
            draft=_draft(source, content="concurrent fact a", page=40),
        ),
        StageRevision(
            command_id="concurrent-stage-b",
            draft=_draft(source, content="concurrent fact b", page=41),
        ),
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(stage, commands))

        assert not any(
            isinstance(outcome, (IntegrityError, OperationalError)) for outcome in outcomes
        ), repr(outcomes)
        conflicts = tuple(
            outcome for outcome in outcomes if isinstance(outcome, RevisionLifecycleConflictError)
        )
        receipts = tuple(outcome for outcome in outcomes if not isinstance(outcome, Exception))
        assert len(receipts) + len(conflicts) == 2
        if conflicts:
            assert len(conflicts) == 1
            assert conflicts[0].retryable is True
        else:
            assert len({receipt.revision_id for receipt in receipts}) == 2
            with session_factory() as query_session:
                evidence_index = SqlEvidenceIndex(query_session)
                revision_numbers = sorted(
                    evidence_index.query(GetRevision(receipt.revision_id)).revision_number
                    for receipt in receipts
                )
            assert revision_numbers == [1, 2]
    finally:
        engine.dispose()


def test_concurrent_replay_of_one_stage_command_is_idempotent(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'concurrent-replay.db').as_posix()}")
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    with session_factory() as setup_session:
        space = KnowledgeSpace(name="Concurrent replay", description="pytest")
        setup_session.add(space)
        setup_session.commit()
        source = _source(setup_session, space, title="Replay source")

    command = StageRevision(
        command_id="concurrent-replay-command",
        draft=_draft(source, content="one immutable replay", page=42),
    )
    _synchronize_operation_reads(engine, command.command_id)
    start_barrier = Barrier(2, timeout=5)

    def stage_replay(_worker_number: int):
        with session_factory() as worker_session:
            try:
                start_barrier.wait()
                return SqlEvidenceIndex(worker_session).command(command)
            except Exception as error:  # noqa: BLE001 - the assertion rejects raw DB errors
                return error

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(stage_replay, range(2)))

        assert not any(isinstance(outcome, Exception) for outcome in outcomes), repr(outcomes)
        assert len({outcome.operation_id for outcome in outcomes}) == 1
        assert len({outcome.revision_id for outcome in outcomes}) == 1
        assert sorted(outcome.replayed for outcome in outcomes) == [False, True]
        with session_factory() as query_session:
            state = SqlEvidenceIndex(query_session).query(GetSourceState(source.id))
            revision = SqlEvidenceIndex(query_session).query(GetRevision(state.revision_ids[0]))
        assert state.revision_ids == (outcomes[0].revision_id,)
        assert revision.revision_number == 1
    finally:
        engine.dispose()


def test_activation_rejects_an_unverified_point_manifest(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    evidence_index = SqlEvidenceIndex(db_session)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-unverified-activation",
            draft=_draft(source, content="manifest must be verified", page=4),
        )
    )

    try:
        evidence_index.command(
            ActivateRevision(
                command_id="activate-without-verification",
                revision_id=staged.revision_id,
                verified_points=(),
            )
        )
    except ActivationInvariantError:
        pass
    else:
        raise AssertionError("Activation accepted an unverified point manifest.")

    revision = evidence_index.query(GetRevision(staged.revision_id))
    source_state = evidence_index.query(GetSourceState(source.id))
    assert (revision.status, revision.index_status) == ("staging", "staging")
    assert source_state.active_revision_id is None


def test_verified_revision_activation_is_atomic_and_idempotent(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    evidence_index = SqlEvidenceIndex(db_session)
    staged = evidence_index.command(
        StageRevision(
            command_id="stage-before-valid-activation",
            draft=_draft(source, content="verified immutable fact", page=5),
        )
    )
    staged_view = evidence_index.query(GetRevision(staged.revision_id))
    command = ActivateRevision(
        command_id="activate-valid-manifest",
        revision_id=staged.revision_id,
        verified_points=tuple(
            VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
            for point in staged_view.points
        ),
    )

    activated = evidence_index.command(command)
    replay = evidence_index.command(command)
    revision = evidence_index.query(GetRevision(staged.revision_id))
    source_state = evidence_index.query(GetSourceState(source.id))

    assert activated.status == "active"
    assert replay.operation_id == activated.operation_id
    assert replay.replayed is True
    assert (revision.status, revision.index_status) == ("active", "active")
    assert source_state.active_revision_id == staged.revision_id
    assert source_state.active_index_revision_id == staged.index_revision_id


def test_activating_a_new_revision_retires_the_old_active_evidence(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    evidence_index = SqlEvidenceIndex(db_session)

    first = evidence_index.command(
        StageRevision(
            command_id="stage-first-active",
            draft=_draft(source, content="obsolete evidence phrase", page=6),
        )
    )
    first_view = evidence_index.query(GetRevision(first.revision_id))
    evidence_index.command(
        ActivateRevision(
            command_id="activate-first",
            revision_id=first.revision_id,
            verified_points=tuple(
                VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                for point in first_view.points
            ),
        )
    )

    second = evidence_index.command(
        StageRevision(
            command_id="stage-second-active",
            draft=_draft(source, content="current evidence phrase", page=7),
        )
    )
    second_view = evidence_index.query(GetRevision(second.revision_id))
    evidence_index.command(
        ActivateRevision(
            command_id="activate-second",
            revision_id=second.revision_id,
            verified_points=tuple(
                VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                for point in second_view.points
            ),
        )
    )

    active_hits = evidence_index.search(
        SearchEvidence(
            text="evidence phrase",
            scope=ActiveScope(space_id=knowledge_space.id, source_ids=(source.id,)),
        )
    )
    first_after_swap = evidence_index.query(GetRevision(first.revision_id))
    second_after_swap = evidence_index.query(GetRevision(second.revision_id))

    assert (first_after_swap.status, first_after_swap.index_status) == ("retired", "retired")
    assert (second_after_swap.status, second_after_swap.index_status) == ("active", "active")
    assert len(active_hits.hits) == 1
    assert isinstance(active_hits.hits[0].evidence, ActiveEvidenceRef)
    assert active_hits.hits[0].evidence.revision_id == second.revision_id
    assert active_hits.hits[0].evidence.index_revision_id == second.index_revision_id
    assert active_hits.hits[0].evidence.excerpt == "current evidence phrase"


def test_pinned_search_can_resolve_retired_immutable_evidence(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    evidence_index = SqlEvidenceIndex(db_session)

    receipts = []
    for number, content in ((1, "historical pinned fact"), (2, "replacement fact")):
        staged = evidence_index.command(
            StageRevision(
                command_id=f"stage-pinned-{number}",
                draft=_draft(source, content=content, page=number + 10),
            )
        )
        staged_view = evidence_index.query(GetRevision(staged.revision_id))
        evidence_index.command(
            ActivateRevision(
                command_id=f"activate-pinned-{number}",
                revision_id=staged.revision_id,
                verified_points=tuple(
                    VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                    for point in staged_view.points
                ),
            )
        )
        receipts.append(staged)

    pinned_hits = evidence_index.search(
        SearchEvidence(
            text="historical pinned fact",
            scope=PinnedScope(
                space_id=knowledge_space.id,
                revision_ids=(receipts[0].revision_id,),
            ),
        )
    )

    assert len(pinned_hits.hits) == 1
    evidence = pinned_hits.hits[0].evidence
    assert isinstance(evidence, PinnedEvidenceRef)
    assert evidence.revision_id == receipts[0].revision_id
    assert evidence.index_revision_id == receipts[0].index_revision_id
    assert evidence.currently_active is False
    assert evidence.content_hash
    assert evidence.locator == {"kind": "pdf_page", "page": 11}


def test_invalid_revision_draft_is_rejected_before_lifecycle_state_is_created(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    evidence_index = SqlEvidenceIndex(db_session)
    duplicate_chunks = (
        ChunkDraft(
            chunk_index=0,
            modality="text",
            content="first duplicate",
            locator={"kind": "pdf_page", "page": 20},
        ),
        ChunkDraft(
            chunk_index=0,
            modality="text",
            content="second duplicate",
            locator={"kind": "pdf_page", "page": 21},
        ),
    )

    with pytest.raises(InvalidRevisionDraftError):
        evidence_index.command(
            StageRevision(
                command_id="stage-invalid-duplicate-indices",
                draft=RevisionDraft(
                    source_id=source.id,
                    content_hash=sha256(b"invalid fixture").hexdigest(),
                    index_version="v5-test",
                    collection_name="test-evidence",
                    chunks=duplicate_chunks,
                ),
            )
        )

    assert evidence_index.query(GetSourceState(source.id)).revision_ids == ()


def test_stale_activation_cannot_replace_a_revision_that_won_the_active_race(
    db_session: Session,
    knowledge_space: KnowledgeSpace,
) -> None:
    source = _source(db_session, knowledge_space)
    evidence_index = SqlEvidenceIndex(db_session)
    first = evidence_index.command(
        StageRevision(
            command_id="stage-racing-first",
            draft=_draft(source, content="first racing draft", page=30),
        )
    )
    second = evidence_index.command(
        StageRevision(
            command_id="stage-racing-second",
            draft=_draft(source, content="second racing draft", page=31),
        )
    )
    second_view = evidence_index.query(GetRevision(second.revision_id))
    evidence_index.command(
        ActivateRevision(
            command_id="activate-racing-second",
            revision_id=second.revision_id,
            verified_points=tuple(
                VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                for point in second_view.points
            ),
        )
    )
    first_view = evidence_index.query(GetRevision(first.revision_id))

    with pytest.raises(ActivationInvariantError):
        evidence_index.command(
            ActivateRevision(
                command_id="activate-stale-first",
                revision_id=first.revision_id,
                verified_points=tuple(
                    VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                    for point in first_view.points
                ),
            )
        )

    source_state = evidence_index.query(GetSourceState(source.id))
    assert source_state.active_revision_id == second.revision_id
    assert evidence_index.query(GetRevision(first.revision_id)).status == "staging"
