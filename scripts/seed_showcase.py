from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import wave

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import models as _models  # noqa: E402,F401
from app.db.session import Base  # noqa: E402
from app.models.chat_session import ChatMessage, ChatSession  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.ingestion_job import IngestionJob  # noqa: E402
from app.models.knowledge_space import KnowledgeSpace  # noqa: E402
from app.models.learning_log import LearningLog  # noqa: E402
from app.models.learning_note import LearningNote  # noqa: E402
from app.models.learning_system import KnowledgePoint, LearningCard, QuizQuestion, VersionLearningPackage  # noqa: E402
from app.models.qa_log import QALog  # noqa: E402
from app.models.source import (  # noqa: E402
    CitationLocator,
    IndexRevision,
    MediaAsset,
    MultimodalChunk,
    Source,
    SourceRevision,
    TranscriptSegment,
    VisualFrame,
)
from app.models.task_event import JobEvent  # noqa: E402

DEMO_INDEX_VERSION = "v2-openai-compatible-1536"
DEMO_EMBEDDING_PROVIDER = "demo_hash"
DEMO_EMBEDDING_MODEL = "local-hash-embedding"
DEMO_EMBEDDING_DIMENSIONS = 1536
DEMO_EMBEDDING_FINGERPRINT = (
    f"{DEMO_EMBEDDING_PROVIDER}::demo::{DEMO_EMBEDDING_MODEL}::"
    f"{DEMO_EMBEDDING_DIMENSIONS}::{DEMO_INDEX_VERSION}::cosine-normalized"
)


def font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def make_frame(path: Path, title: str, subtitle: str, accent: str) -> None:
    image = Image.new("RGB", (1280, 720), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1280, 92), fill="#0f172a")
    draw.rectangle((70, 150, 1210, 610), fill="#ffffff", outline="#cbd5e1", width=3)
    draw.rectangle((70, 150, 92, 610), fill=accent)
    draw.text((70, 30), "AI Knowledge OS Pro", fill="#ffffff", font=font(38))
    draw.text((130, 230), title, fill="#0f172a", font=font(52))
    draw.text((130, 325), subtitle, fill="#475569", font=font(30))
    draw.text((130, 510), "Synthetic showcase evidence / V4.5", fill=accent, font=font(24))
    image.save(path, format="PNG")


def make_silent_wav(path: Path, duration_seconds: int = 18) -> None:
    sample_rate = 16_000
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * sample_rate * duration_seconds)


def make_video(path: Path, cover: Path) -> None:
    try:
        import imageio_ffmpeg

        executable = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run(
            [
                executable,
                "-y",
                "-loop",
                "1",
                "-i",
                str(cover),
                "-t",
                "18",
                "-vf",
                "format=yuv420p",
                "-c:v",
                "libx264",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
    except Exception as exc:
        print(f"Video fixture skipped: {exc}")


def seed(database_path: Path, reset: bool) -> None:
    resolved = database_path.resolve()
    if "showcase" not in resolved.name.lower():
        raise SystemExit("Refusing to write: the database filename must contain 'showcase'.")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if reset and resolved.exists():
        resolved.unlink()

    storage = BACKEND / "storage" / "showcase"
    storage.mkdir(parents=True, exist_ok=True)
    frame_paths = [storage / f"video-frame-{index}.png" for index in range(1, 4)]
    make_frame(frame_paths[0], "Durable media tasks", "Queue, progress, retry and evidence links", "#0f766e")
    make_frame(frame_paths[1], "Timestamp citations", "Seek from an answer to the exact video segment", "#2563eb")
    make_frame(frame_paths[2], "Source-based learning", "Turn persisted evidence into review material", "#7c3aed")
    image_path = storage / "architecture-board.png"
    make_frame(image_path, "Multimodal RAG architecture", "FastAPI + Next.js + Qdrant + Redis/RQ", "#dc2626")
    audio_path = storage / "rag-review.wav"
    make_silent_wav(audio_path)
    video_path = storage / "multimodal-rag-walkthrough.mp4"
    make_video(video_path, frame_paths[0])
    document_path = storage / "rag-evidence-guide.md"
    document_path.write_text("# RAG evidence guide\n\nEvery answer should link back to persisted source evidence.\n", encoding="utf-8")

    engine = create_engine(f"sqlite:///{resolved.as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        if db.query(KnowledgeSpace).count() > 0:
            print(f"Showcase database already contains data: {resolved}")
            return

        space = KnowledgeSpace(name="Multimodal RAG Learning Lab", description="Synthetic GitHub showcase workspace")
        db.add(space)
        db.flush()

        documents = [
            Document(
                space_id=space.id,
                filename="rag-evidence-guide.md",
                original_filename="rag-evidence-guide.md",
                file_type="md",
                content_type="text/markdown",
                file_size=document_path.stat().st_size,
                storage_path=str(document_path),
                status="ready",
                parse_status="parsed",
                chunk_status="chunked",
                vector_status="indexed",
                processing_status="completed",
                processing_progress=100,
                title="RAG Evidence Guide",
                tags_json=json.dumps(["RAG", "citations", "portfolio"]),
                summary="How traceable chunks, retrieval and citation validation form a reliable RAG workflow.",
                chunk_count=6,
                embedding_provider=DEMO_EMBEDDING_PROVIDER,
                embedding_model=DEMO_EMBEDDING_MODEL,
                embedding_dimensions=DEMO_EMBEDDING_DIMENSIONS,
                embedding_fingerprint=DEMO_EMBEDDING_FINGERPRINT,
                index_version=DEMO_INDEX_VERSION,
            ),
            Document(
                space_id=space.id,
                filename="media-task-design.txt",
                original_filename="media-task-design.txt",
                file_type="txt",
                content_type="text/plain",
                file_size=2048,
                storage_path=str(document_path),
                status="ready",
                parse_status="parsed",
                chunk_status="chunked",
                vector_status="indexed",
                processing_status="completed",
                processing_progress=100,
                title="Durable Media Task Design",
                tags_json=json.dumps(["Redis", "RQ", "multimodal"]),
                summary="Task states, event timelines, retries and provider failure boundaries.",
                chunk_count=4,
                embedding_provider=DEMO_EMBEDDING_PROVIDER,
                embedding_model=DEMO_EMBEDDING_MODEL,
                embedding_dimensions=DEMO_EMBEDDING_DIMENSIONS,
                embedding_fingerprint=DEMO_EMBEDDING_FINGERPRINT,
                index_version=DEMO_INDEX_VERSION,
            ),
        ]
        db.add_all(documents)
        db.flush()

        image_source = Source(
            space_id=space.id,
            source_type="image",
            title="Architecture Whiteboard",
            original_filename=image_path.name,
            mime_type="image/png",
            file_size=image_path.stat().st_size,
            storage_path=str(image_path),
            content_hash="showcase-image",
            status="ready",
            width=1280,
            height=720,
            metadata_json=json.dumps(
                {
                    "ocr_status": "completed",
                    "visual_description_status": "completed",
                    "capability_note": "Synthetic screenshot with persisted OCR and visual evidence.",
                }
            ),
        )
        audio_source = Source(
            space_id=space.id,
            source_type="audio",
            title="RAG Review Session",
            original_filename=audio_path.name,
            mime_type="audio/wav",
            file_size=audio_path.stat().st_size,
            storage_path=str(audio_path),
            content_hash="showcase-audio",
            status="ready",
            language="en",
            duration_ms=18_000,
            metadata_json=json.dumps(
                {
                    "transcription_status": "completed",
                    "capability_note": "Synthetic timeline used to demonstrate timestamp navigation.",
                }
            ),
        )
        video_source = Source(
            space_id=space.id,
            source_type="video",
            title="Multimodal RAG Walkthrough",
            original_filename=video_path.name,
            mime_type="video/mp4",
            file_size=video_path.stat().st_size if video_path.exists() else 0,
            storage_path=str(video_path),
            content_hash="showcase-video",
            status="ready",
            language="en",
            duration_ms=18_000,
            width=1280,
            height=720,
            metadata_json=json.dumps(
                {
                    "has_audio": False,
                    "keyframe_status": "completed",
                    "transcription_status": "completed",
                    "processing_status": "completed",
                    "capability_note": "Synthetic demo source with traceable keyframes and transcript segments.",
                }
            ),
        )
        code_source = Source(
            space_id=space.id,
            source_type="code_repository",
            title="AI Knowledge OS Pro Code Walkthrough",
            original_filename="ai-knowledge-os-pro",
            mime_type="text/x-code-repository",
            file_size=4096,
            storage_path="synthetic://ai-knowledge-os-pro",
            content_hash="showcase-code-repository",
            status="ready",
            metadata_json=json.dumps(
                {
                    "ingestion_mode": "code_repository",
                    "file_count": 2,
                    "chunk_count": 2,
                    "skipped_count": 0,
                    "safety_note": "Synthetic code evidence only; no local private path or secret content is stored.",
                }
            ),
        )
        db.add_all([image_source, audio_source, video_source, code_source])
        db.flush()

        video_citation_chunk_id: int | None = None
        for source, parser_name in [
            (image_source, "showcase_ocr"),
            (audio_source, "showcase_transcript"),
            (video_source, "showcase_video_pipeline"),
        ]:
            revision = SourceRevision(
                source_id=source.id,
                revision_number=1,
                status="active",
                parser_name=parser_name,
                parser_version="4.5.0",
                content_hash=source.content_hash,
                chunk_count=3 if source.source_type != "image" else 1,
                vector_count=3 if source.source_type != "image" else 1,
                validation_status="passed",
                metadata_json=json.dumps({"showcase": True}),
                activated_at=now,
            )
            db.add(revision)
            db.flush()
            source.active_revision_id = revision.id
            source.latest_revision_id = revision.id

            if source.source_type == "image":
                chunk = MultimodalChunk(
                    source_id=source.id,
                    revision_id=revision.id,
                    chunk_index=0,
                    modality="image_text",
                    source_type="image",
                    content_text="Architecture: Upload -> durable task -> evidence chunk -> citation -> learning artifact.",
                    search_text="multimodal RAG architecture durable task citation learning artifact",
                    locator_json=json.dumps({"source_id": source.id, "region": "full_image"}),
                    status="active",
                )
                db.add(chunk)
                db.flush()
                db.add(CitationLocator(source_id=source.id, revision_id=revision.id, chunk_id=chunk.id, locator_json=chunk.locator_json, display_text="Architecture whiteboard"))
                db.add(MediaAsset(source_id=source.id, asset_type="original", storage_path=str(image_path), mime_type="image/png", file_size=image_path.stat().st_size, width=1280, height=720, metadata_json=json.dumps({"showcase": True})))
            else:
                segment_texts = [
                    "A durable task records progress and provider failures instead of hiding work in one request.",
                    "Timestamp citations return the learner to the exact evidence used by the answer.",
                    "Learning artifacts are created only from persisted source chunks.",
                ]
                for index, text in enumerate(segment_texts):
                    start_ms = index * 6_000
                    end_ms = start_ms + 5_500
                    segment = TranscriptSegment(
                        source_id=source.id,
                        revision_id=revision.id,
                        segment_index=index,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        speaker="Narrator",
                        language="en",
                        text=text,
                        confidence=96,
                        metadata_json=json.dumps({"showcase": True}),
                    )
                    chunk = MultimodalChunk(
                        source_id=source.id,
                        revision_id=revision.id,
                        chunk_index=index,
                        modality=f"{source.source_type}_transcript",
                        source_type=source.source_type,
                        content_text=text,
                        search_text=text,
                        locator_json=json.dumps({"source_id": source.id, "start_ms": start_ms, "end_ms": end_ms}),
                        start_ms=start_ms,
                        end_ms=end_ms,
                        speaker="Narrator",
                        language="en",
                        status="active",
                    )
                    db.add_all([segment, chunk])
                    db.flush()
                    if source.source_type == "video" and index == 1:
                        video_citation_chunk_id = chunk.id
                    db.add(CitationLocator(source_id=source.id, revision_id=revision.id, chunk_id=chunk.id, locator_json=chunk.locator_json, display_text=f"{source.title} at {start_ms // 1000}s"))

                db.add(MediaAsset(source_id=source.id, asset_type="original", storage_path=source.storage_path or "", mime_type=source.mime_type, file_size=source.file_size, duration_ms=source.duration_ms, metadata_json=json.dumps({"showcase": True})))

                if source.source_type == "video":
                    for index, frame_path in enumerate(frame_paths):
                        timestamp_ms = index * 6_000
                        frame = VisualFrame(
                            source_id=source.id,
                            revision_id=revision.id,
                            frame_index=index,
                            timestamp_ms=timestamp_ms,
                            storage_path=str(frame_path),
                            ocr_text=["Durable tasks", "Timestamp citations", "Source-based learning"][index],
                            visual_description="Synthetic product walkthrough frame with a labelled engineering concept.",
                            scene_score=90 - index * 4,
                            metadata_json=json.dumps({"showcase": True}),
                        )
                        db.add(frame)
                        db.flush()
                        db.add(
                            MediaAsset(
                                source_id=source.id,
                                asset_type="keyframe",
                                storage_path=str(frame_path),
                                mime_type="image/png",
                                file_size=frame_path.stat().st_size,
                                width=1280,
                                height=720,
                                metadata_json=json.dumps({"timestamp_ms": timestamp_ms, "frame_id": frame.id, "showcase": True}),
                            )
                        )

        code_revision = SourceRevision(
            source_id=code_source.id,
            revision_number=1,
            status="active",
            parser_name="showcase_code_repository",
            parser_version="4.5.0",
            content_hash=code_source.content_hash,
            chunk_count=2,
            vector_count=2,
            validation_status="passed",
            metadata_json=json.dumps({"showcase": True, "source_type": "code_repository"}),
            activated_at=now,
        )
        db.add(code_revision)
        db.flush()
        code_source.active_revision_id = code_revision.id
        code_source.latest_revision_id = code_revision.id
        code_chunks = [
            (
                "backend/app/api/router.py",
                1,
                31,
                "api_router",
                "api_router includes dashboard, documents, media, chat, learning, portfolio, system and task routes.",
            ),
            (
                "frontend/components/AppShell.tsx",
                1,
                90,
                "navigationGroups",
                "AppShell exposes the demo navigation path across Dashboard, Upload, Tasks, Chat, Learning and Portfolio.",
            ),
        ]
        for index, (file_path, line_start, line_end, symbol_name, text) in enumerate(code_chunks):
            locator = {
                "source_type": "code_repository",
                "source_id": code_source.id,
                "file_path": file_path,
                "line_start": line_start,
                "line_end": line_end,
                "symbol_name": symbol_name,
                "github_url": "https://github.com/DZH166/AI-Knowledge-OS-Pro",
            }
            chunk = MultimodalChunk(
                source_id=code_source.id,
                revision_id=code_revision.id,
                chunk_index=index,
                modality="code_file",
                source_type="code_repository",
                content_text=f"File: {file_path}\nLines: {line_start}-{line_end}\n\n{text}",
                search_text=f"{file_path} {symbol_name} {text}",
                raw_payload_json=json.dumps({"language": "python" if file_path.endswith(".py") else "typescript-react"}),
                locator_json=json.dumps(locator),
                language="python" if file_path.endswith(".py") else "typescript-react",
                status="active",
                qdrant_point_id=f"showcase-code-{index}",
            )
            db.add(chunk)
            db.flush()
            db.add(
                CitationLocator(
                    source_id=code_source.id,
                    revision_id=code_revision.id,
                    chunk_id=chunk.id,
                    locator_json=chunk.locator_json,
                    display_text=f"{file_path}:{line_start}-{line_end}",
                )
            )
        db.add(
            IndexRevision(
                source_id=code_source.id,
                revision_id=code_revision.id,
                status="active",
                index_version=DEMO_INDEX_VERSION,
                embedding_provider=DEMO_EMBEDDING_PROVIDER,
                embedding_model=DEMO_EMBEDDING_MODEL,
                embedding_dimensions=DEMO_EMBEDDING_DIMENSIONS,
                embedding_fingerprint=DEMO_EMBEDDING_FINGERPRINT,
                qdrant_collection="ai_knowledge_os_v2_openai_compatible_1536_chunks",
                point_count=2,
                validation_status="passed",
                activated_at=now,
            )
        )

        if video_citation_chunk_id is None:
            raise RuntimeError("Showcase video citation chunk was not created.")
        citations = [
            {
                "citation_id": "1",
                "document_name": video_source.title,
                "source_type": "video",
                "source_id": video_source.id,
                "document_id": None,
                "chunk_id": video_citation_chunk_id,
                "chunk_index": 1,
                "start_ms": 6_000,
                "end_ms": 11_500,
                "content_preview": "Timestamp citations return the learner to the exact evidence used by the answer.",
                "score": 0.94,
            }
        ]
        related_chunks = [
            {
                "chunk_id": video_citation_chunk_id,
                "document_name": video_source.title,
                "content": "Timestamp citations return the learner to the exact evidence used by the answer.",
                "score": 0.94,
                "source_type": "video",
                "source_id": video_source.id,
                "document_id": None,
                "start_ms": 6_000,
                "end_ms": 11_500,
            }
        ]
        qa = QALog(
            space_id=space.id,
            question="How does the system keep multimodal RAG answers traceable?",
            answer="Each persisted chunk carries a source locator. Video evidence stores start/end timestamps, so a citation can seek the player and highlight the supporting transcript [1].",
            answer_mode="normal",
            citations_json=json.dumps(citations),
            used_citation_ids_json=json.dumps(["1"]),
            related_chunks_json=json.dumps(related_chunks),
            answer_confidence="high",
            retrieval_score=0.94,
            retrieval_status="grounded",
            runtime_mode="demo",
        )
        db.add(qa)
        db.flush()
        refusal_qa = QALog(
            space_id=space.id,
            question="What private API key is configured in the project?",
            answer=(
                "I do not have enough source evidence to answer that. "
                "The demo data intentionally excludes secrets and real provider keys."
            ),
            answer_mode="normal",
            citations_json="[]",
            used_citation_ids_json="[]",
            related_chunks_json="[]",
            answer_confidence="low",
            retrieval_score=0.0,
            retrieval_status="insufficient_context",
            runtime_mode="demo",
        )
        db.add(refusal_qa)
        db.flush()
        session = ChatSession(space_id=space.id, title="Traceable multimodal RAG", answer_mode="normal")
        db.add(session)
        db.flush()
        db.add_all(
            [
                ChatMessage(session_id=session.id, role="user", content=refusal_qa.question, answer_mode="normal", created_at=now - timedelta(seconds=40)),
                ChatMessage(session_id=session.id, qa_log_id=refusal_qa.id, role="assistant", content=refusal_qa.answer, answer_mode="normal", citations_json="[]", used_citation_ids_json="[]", related_chunks_json="[]", retrieval_status="insufficient_context", answer_confidence="low", created_at=now - timedelta(seconds=30)),
                ChatMessage(session_id=session.id, role="user", content=qa.question, answer_mode="normal", created_at=now - timedelta(seconds=20)),
                ChatMessage(session_id=session.id, qa_log_id=qa.id, role="assistant", content=qa.answer, answer_mode="normal", citations_json=json.dumps(citations), used_citation_ids_json=json.dumps(["1"]), related_chunks_json=json.dumps(related_chunks), retrieval_status="grounded", answer_confidence="high", is_favorite=True, created_at=now - timedelta(seconds=10)),
            ]
        )

        package = VersionLearningPackage(
            version_name="V4.5 / 4.5.0 Live Demo E2E Hardening",
            slug="v3-7-github-showcase-demo",
            status="confirmed",
            summary="A traceable multimodal RAG learning system with durable tasks, evidence navigation and source-derived study assets.",
            implemented_features_json=json.dumps(["Unified media tasks", "Timestamp citations", "Multi-keyframe video", "GitHub CI"]),
            major_files_json=json.dumps([{"path": "backend/app/services/media_task_service.py", "responsibility": "Durable media orchestration"}, {"path": "frontend/app/media/sources/[id]/page.tsx", "responsibility": "Evidence-linked media learning UI"}]),
            focus="Explain how task state, source locators and learning artifacts form one auditable workflow.",
            review_suggestions="Review provider boundaries, retry/cancel semantics and citation deep links.",
            interview_expression="I unified document and media processing under a durable task model and made RAG evidence navigable from answer to source timestamp.",
            next_version_suggestion="Add subtitle export and richer scene segmentation.",
            markdown_content="## V4.5 Live Demo E2E Hardening\n\nTraceable multimodal RAG, durable tasks, citation deep links, runtime observability, provider dry-run evaluation, strict browser E2E, refusals, source-based learning and release-ready quality gates.",
            confirmed_at=now,
        )
        db.add(package)
        db.flush()
        point_names = ["Durable multimodal tasks", "Evidence-linked RAG", "Source-derived learning"]
        points: list[KnowledgePoint] = []
        for index, name in enumerate(point_names):
            point = KnowledgePoint(
                package_id=package.id,
                name=name,
                beginner_explanation="Long-running AI work should be observable and every generated result should point back to evidence.",
                project_usage="V4.5 connects persistent jobs, multimodal chunks, citation locators, demo readiness, observability, provider readiness checks, strict browser E2E, learning artifacts and docs/release quality gates.",
                code_locations_json=json.dumps(["backend/app/services/media_task_service.py", "frontend/app/media/sources/[id]/page.tsx"]),
                review_suggestion="Review the task state machine and timestamp locator contract.",
                interview_expression="I designed an auditable multimodal RAG workflow instead of a synchronous upload-and-chat demo.",
                mastery_status=["mastered", "learning", "review_needed"][index],
            )
            db.add(point)
            db.flush()
            points.append(point)
            db.add(LearningCard(package_id=package.id, knowledge_point_id=point.id, front=f"Why does {name} matter?", back=point.project_usage, mastery_status="reviewing"))
            db.add(QuizQuestion(package_id=package.id, knowledge_point_id=point.id, question=f"Which statement best describes {name}?", options_json=json.dumps(["It preserves evidence and state", "It decorates the UI", "It bypasses providers"]), correct_answer="It preserves evidence and state", explanation=point.project_usage))

        db.add(LearningNote(title="Portfolio explanation", content="Lead with the user workflow, then explain the durable task model, source locators and real-mode provider boundaries.", tags_json=json.dumps(["portfolio", "interview"]), knowledge_point_id=points[0].id, qa_log_id=qa.id, version_slug=package.slug))
        learning_log_points = [
            {
                "name": point.name,
                "beginner_explanation": point.beginner_explanation,
                "project_usage": point.project_usage,
                "code_locations": json.loads(point.code_locations_json or "[]"),
                "review_suggestion": point.review_suggestion,
                "interview_expression": point.interview_expression,
            }
            for point in points
        ]
        db.add(LearningLog(version_name=package.version_name, slug=package.slug, summary=package.summary, implemented_features_json=package.implemented_features_json, major_files_json=package.major_files_json, knowledge_points_json=json.dumps(learning_log_points), focus=package.focus, review_suggestions=package.review_suggestions, interview_expression=package.interview_expression, next_version_suggestion=package.next_version_suggestion, markdown_content=package.markdown_content))

        job_specs = [
            (video_source, "video_full_pipeline", "completed", "completed", 100, "Video keyframes, visual evidence and transcript are ready."),
            (audio_source, "audio_transcription", "running", "transcription", 68, "Worker is transcribing timestamped audio segments."),
            (image_source, "image_ocr", "failed", "ocr", 22, "OCR provider is not configured; no fake text was generated."),
            (code_source, "code_repository_ingestion", "completed", "indexing", 100, "Synthetic code repository evidence is indexed for locator regression."),
        ]
        for offset, (source, job_type, status, step, progress, message) in enumerate(job_specs):
            created = now - timedelta(minutes=offset * 7)
            job = IngestionJob(
                document_id=None,
                source_id=source.id,
                space_id=space.id,
                target_type="media",
                job_type=job_type,
                status=status,
                current_step=step,
                step_index=4 if status == "completed" else 2,
                step_total=4,
                progress=progress,
                worker_id="showcase-worker" if status != "failed" else None,
                queue_name="default",
                priority=100,
                attempt=1,
                max_attempts=3,
                message=message,
                error_code="OCR_NOT_CONFIGURED" if status == "failed" else None,
                error_message="Configure a real OCR provider before retrying." if status == "failed" else None,
                error_details_json=json.dumps({"showcase": True, "retryable": status == "failed"}),
                result_json=json.dumps({"detail_url": f"/media/sources/{source.id}", "source_id": source.id}),
                started_at=created,
                heartbeat_at=now if status == "running" else created,
                finished_at=now if status in {"completed", "failed"} else None,
                duration_ms=12_400 if status == "completed" else None,
                created_at=created,
            )
            db.add(job)
            db.flush()
            events = [
                ("queued", "queued", 0, "Task entered the durable queue."),
                ("running", "preflight", 5, "Worker validated source metadata."),
                (status, step, progress, message),
            ]
            for event_type, event_step, event_progress, event_message in events:
                db.add(JobEvent(job_id=job.id, event_type=event_type, step=event_step, progress=event_progress, message=event_message))

        db.commit()
        space_id = space.id
        video_source_id = video_source.id
    print(f"Showcase database seeded: {resolved}")
    print(f"Knowledge space id: {space_id}; video source id: {video_source_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an isolated synthetic database for GitHub screenshots.")
    parser.add_argument("--database-path", type=Path, default=BACKEND / "data" / "showcase.db")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed(args.database_path, args.reset)


if __name__ == "__main__":
    main()
