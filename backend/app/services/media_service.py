from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from uuid import uuid4

from fastapi import UploadFile
from mutagen import File as MutagenFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import ConfigurationError, DuplicateDocumentError
from app.models.evidence_index import VectorPointManifest
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import (
    CitationLocator,
    IndexRevision,
    MediaAsset,
    MultimodalChunk,
    Source,
    SourceRevision,
    TranscriptSegment,
    VisualFrame,
)
from app.modules.evidence_index import (
    ActivateRevision,
    CancelRevision,
    ChunkDraft,
    GetRevision,
    PointEmbedding,
    RevisionDraft,
    SqlEvidenceIndex,
    StageRevision,
    UpsertRevisionVectors,
    VerifiedPoint,
)
from app.services.embedding_service import EmbeddingService
from app.services.ingestion_service import LegacyVectorStoreEvidenceAdapter
from app.services.ocr_service import OCRProvider, get_ocr_provider
from app.services.transcription_service import (
    TranscriptionProvider,
    get_transcription_provider,
)
from app.services.vector_store import VectorStore
from app.services.video_service import video_tooling


@dataclass(slots=True)
class _StagedMediaRevision:
    evidence_index: SqlEvidenceIndex
    command_prefix: str
    revision: SourceRevision
    chunks: tuple[MultimodalChunk, ...]
    previous_point_ids: tuple[str, ...]


@dataclass(slots=True)
class _MediaChunkSeed:
    draft: ChunkDraft
    raw_payload_json: str = "{}"
    start_ms: int | None = None
    end_ms: int | None = None
    page_number: int | None = None
    slide_number: int | None = None
    speaker: str | None = None
    language: str | None = None
    previous_frame_id: int | None = None
    display_text: str | None = None


_NOT_PROVIDED = object()


class MediaService:
    supported_image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    supported_image_mime_types = {"image/png", "image/jpeg", "image/webp", "image/bmp"}
    supported_audio_extensions = {".mp3", ".wav", ".m4a"}
    supported_audio_mime_types = {
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/mp4",
        "audio/x-m4a",
        "application/octet-stream",
    }
    supported_video_extensions = {".mp4", ".mov"}
    supported_video_mime_types = {
        "video/mp4",
        "video/quicktime",
        "application/octet-stream",
    }

    def __init__(
        self,
        ocr_provider: OCRProvider | None = None,
        transcription_provider: TranscriptionProvider | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.ocr_provider = ocr_provider or get_ocr_provider()
        self.transcription_provider = (
            transcription_provider or get_transcription_provider()
        )
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def upload_image(
        self, db: Session, space_id: int, upload_file: UploadFile
    ) -> Source:
        space = db.get(KnowledgeSpace, space_id)
        if space is None:
            raise ValueError("知识库不存在。")

        original_name = upload_file.filename or "image"
        suffix = Path(original_name).suffix.lower()
        if suffix not in self.supported_image_extensions:
            raise ValueError("当前图片接入支持 png、jpg、jpeg、webp、bmp。")
        if (
            upload_file.content_type
            and upload_file.content_type not in self.supported_image_mime_types
        ):
            raise ValueError("上传文件不是受支持的图片 MIME 类型。")

        storage_path, content_hash, file_size = self._save_upload(
            upload_file, original_name, "images"
        )
        duplicate = db.scalar(
            select(Source).where(
                Source.space_id == space_id,
                Source.content_hash == content_hash,
                Source.status != "deleted",
            )
        )
        if duplicate is not None:
            storage_path.unlink(missing_ok=True)
            raise DuplicateDocumentError(
                "同一知识库中已经存在内容相同的图片。",
                details={
                    "source_id": duplicate.id,
                    "filename": duplicate.original_filename,
                },
            )

        try:
            width, height, image_format = self._inspect_image(storage_path)
        except ValueError:
            storage_path.unlink(missing_ok=True)
            raise

        metadata = {
            "ingestion_mode": "image_metadata_only",
            "ocr_status": "not_configured",
            "vision_description_status": "not_configured",
            "capability_note": "V3 当前保存图片和真实尺寸元数据；未配置真实 OCR/视觉模型时不会生成伪识别结果。",
            "image_format": image_format,
        }
        source = Source(
            space_id=space.id,
            source_type="image",
            title=Path(original_name).stem,
            original_filename=original_name,
            mime_type=upload_file.content_type,
            file_size=file_size,
            storage_path=str(storage_path),
            content_hash=content_hash,
            status="ready",
            width=width,
            height=height,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        db.add(source)
        db.flush()

        revision = SourceRevision(
            source_id=source.id,
            revision_number=1,
            status="active",
            parser_name="image_metadata_parser",
            parser_version="v3",
            content_hash=content_hash,
            chunk_count=0,
            vector_count=0,
            validation_status="metadata_only",
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            activated_at=datetime.now(timezone.utc),
        )
        db.add(revision)
        db.flush()

        asset = MediaAsset(
            source_id=source.id,
            asset_type="original_image",
            storage_path=str(storage_path),
            mime_type=upload_file.content_type,
            file_size=file_size,
            width=width,
            height=height,
            metadata_json=json.dumps(
                {"image_format": image_format}, ensure_ascii=False
            ),
        )
        db.add(asset)
        db.flush()

        source.active_revision_id = revision.id
        source.latest_revision_id = revision.id
        db.commit()
        return self.get_source(db, source.id)

    def upload_audio(
        self, db: Session, space_id: int, upload_file: UploadFile
    ) -> Source:
        space = db.get(KnowledgeSpace, space_id)
        if space is None:
            raise ValueError("知识库不存在。")
        original_name = upload_file.filename or "audio"
        suffix = Path(original_name).suffix.lower()
        if suffix not in self.supported_audio_extensions:
            raise ValueError("当前音频接入支持 mp3、wav、m4a。")
        if (
            upload_file.content_type
            and upload_file.content_type not in self.supported_audio_mime_types
        ):
            raise ValueError("上传文件不是受支持的音频 MIME 类型。")

        storage_path, content_hash, file_size = self._save_upload(
            upload_file, original_name, "audio"
        )
        duplicate = db.scalar(
            select(Source).where(
                Source.space_id == space_id,
                Source.content_hash == content_hash,
                Source.status != "deleted",
            )
        )
        if duplicate is not None:
            storage_path.unlink(missing_ok=True)
            raise DuplicateDocumentError(
                "同一知识库中已经存在内容相同的音频。",
                details={
                    "source_id": duplicate.id,
                    "filename": duplicate.original_filename,
                },
            )
        try:
            duration_ms = self._inspect_audio_duration(storage_path)
        except ValueError:
            storage_path.unlink(missing_ok=True)
            raise

        metadata = {
            "ingestion_mode": "audio_metadata_only",
            "transcription_status": "not_configured",
            "capability_note": "音频已保存真实时长和来源；未配置真实转写 provider 时不会生成伪转写。",
        }
        source = Source(
            space_id=space.id,
            source_type="audio",
            title=Path(original_name).stem,
            original_filename=original_name,
            mime_type=upload_file.content_type,
            file_size=file_size,
            storage_path=str(storage_path),
            content_hash=content_hash,
            status="ready",
            duration_ms=duration_ms,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        db.add(source)
        db.flush()
        revision = SourceRevision(
            source_id=source.id,
            revision_number=1,
            status="active",
            parser_name="audio_metadata_parser",
            parser_version="v3.4",
            content_hash=content_hash,
            chunk_count=0,
            vector_count=0,
            validation_status="metadata_only",
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            activated_at=datetime.now(timezone.utc),
        )
        db.add(revision)
        db.flush()
        db.add(
            MediaAsset(
                source_id=source.id,
                asset_type="original_audio",
                storage_path=str(storage_path),
                mime_type=upload_file.content_type,
                file_size=file_size,
                duration_ms=duration_ms,
                metadata_json="{}",
            )
        )
        source.active_revision_id = revision.id
        source.latest_revision_id = revision.id
        db.commit()
        return self.get_source(db, source.id)

    def upload_video(
        self, db: Session, space_id: int, upload_file: UploadFile
    ) -> Source:
        space = db.get(KnowledgeSpace, space_id)
        if space is None:
            raise ValueError("知识库不存在。")
        original_name = upload_file.filename or "video"
        suffix = Path(original_name).suffix.lower()
        if suffix not in self.supported_video_extensions:
            raise ValueError("当前视频接入支持 mp4、mov。")
        if (
            upload_file.content_type
            and upload_file.content_type not in self.supported_video_mime_types
        ):
            raise ValueError("上传文件不是受支持的视频 MIME 类型。")

        storage_path, content_hash, file_size = self._save_upload(
            upload_file, original_name, "video"
        )
        duplicate = db.scalar(
            select(Source).where(
                Source.space_id == space_id,
                Source.content_hash == content_hash,
                Source.status != "deleted",
            )
        )
        if duplicate is not None:
            storage_path.unlink(missing_ok=True)
            raise DuplicateDocumentError(
                "同一知识库中已经存在内容相同的视频。",
                details={
                    "source_id": duplicate.id,
                    "filename": duplicate.original_filename,
                },
            )
        try:
            duration_ms, width, height, has_audio = video_tooling.video_metadata(
                video_tooling.probe(storage_path)
            )
        except ValueError:
            storage_path.unlink(missing_ok=True)
            raise

        metadata = {
            "ingestion_mode": "video_metadata_only",
            "transcription_status": "not_configured",
            "keyframe_status": "pending",
            "has_audio": has_audio,
            "capability_note": "视频已保存真实元数据；未配置真实转写 provider 时不会生成伪字幕。",
        }
        source = Source(
            space_id=space.id,
            source_type="video",
            title=Path(original_name).stem,
            original_filename=original_name,
            mime_type=upload_file.content_type,
            file_size=file_size,
            storage_path=str(storage_path),
            content_hash=content_hash,
            status="ready",
            duration_ms=duration_ms,
            width=width,
            height=height,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        db.add(source)
        db.flush()
        revision = SourceRevision(
            source_id=source.id,
            revision_number=1,
            status="active",
            parser_name="video_metadata_parser",
            parser_version="v3.5",
            content_hash=content_hash,
            chunk_count=0,
            vector_count=0,
            validation_status="metadata_only",
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            activated_at=datetime.now(timezone.utc),
        )
        db.add(revision)
        db.flush()
        db.add(
            MediaAsset(
                source_id=source.id,
                asset_type="original_video",
                storage_path=str(storage_path),
                mime_type=upload_file.content_type,
                file_size=file_size,
                width=width,
                height=height,
                duration_ms=duration_ms,
                metadata_json="{}",
            )
        )
        try:
            self._add_video_keyframe(
                db=db, source=source, revision=revision, video_path=storage_path
            )
        except ValueError:
            db.rollback()
            storage_path.unlink(missing_ok=True)
            raise
        metadata.update({"keyframe_status": "completed", "keyframe_count": 1})
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        revision.metadata_json = json.dumps(metadata, ensure_ascii=False)
        source.active_revision_id = revision.id
        source.latest_revision_id = revision.id
        db.commit()
        return self.get_source(db, source.id)

    def process_audio_transcription(self, db: Session, source_id: int) -> Source:
        source = self.get_source(db, source_id)
        if source.source_type not in {"audio", "video"}:
            raise ValueError("当前转写只支持音频或视频资料。")
        if not source.storage_path:
            raise ValueError("媒体文件路径不存在，无法执行转写。")
        self._ensure_transcription_provider_configured(source.source_type)

        metadata = source.metadata_data
        if source.source_type == "video" and metadata.get("has_audio") is False:
            raise ValueError("当前视频没有可提取的音轨，无法执行转写。")
        metadata.update(
            {
                "transcription_status": "running",
                "transcription_provider": self.transcription_provider.name,
                "transcription_model": self.transcription_provider.model,
            }
        )
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.commit()
        extracted_audio_path: Path | None = None
        try:
            media_path = Path(source.storage_path)
            media_mime = source.mime_type
            if source.source_type == "video":
                media_path = video_tooling.extract_audio(
                    media_path, settings.upload_dir / "video" / "derived"
                )
                extracted_audio_path = media_path
                media_mime = "audio/wav"
                db.add(
                    MediaAsset(
                        source_id=source.id,
                        asset_type="extracted_audio",
                        storage_path=str(media_path),
                        mime_type="audio/wav",
                        file_size=media_path.stat().st_size,
                        duration_ms=source.duration_ms,
                        metadata_json="{}",
                    )
                )
            result = self.transcription_provider.transcribe(media_path, media_mime)
        except Exception:
            db.rollback()
            if extracted_audio_path is not None:
                extracted_audio_path.unlink(missing_ok=True)
            source = self.get_source(db, source_id)
            metadata = source.metadata_data
            metadata["transcription_status"] = "failed"
            source.metadata_json = json.dumps(metadata, ensure_ascii=False)
            db.commit()
            raise

        metadata = source.metadata_data
        metadata.update(
            {
                "ingestion_mode": f"{source.source_type}_transcription",
                "transcription_status": "completed" if result.segments else "empty",
                "transcription_provider": result.provider,
                "transcription_model": result.model,
                "transcript_segment_count": len(result.segments),
                "language": result.language,
                "capability_note": f"{'视频' if source.source_type == 'video' else '音频'}已完成真实转写并生成带时间戳的可检索片段。"
                if result.segments
                else "转写已执行，但没有识别到可用文字。",
            }
        )
        if source.source_type == "video":
            metadata.update(
                {
                    "extracted_audio_status": "completed",
                    "keyframe_status": "completed",
                }
            )

        existing_video_frames = (
            self._active_video_frames(source) if source.source_type == "video" else []
        )
        staged: _StagedMediaRevision | None = None
        try:
            if not result.segments:
                return self._activate_empty_media_revision(
                    db,
                    source,
                    parser_name=f"{source.source_type}_transcription_provider",
                    parser_version="v3.5" if source.source_type == "video" else "v3.4",
                    revision_metadata={
                        "provider": result.provider,
                        "model": result.model,
                        "language": result.language,
                    },
                    source_metadata=metadata,
                    existing_video_frames=existing_video_frames,
                    language=result.language,
                    duration_ms=result.duration_ms,
                )

            staged = self._stage_media_revision(
                db,
                source,
                parser_name=f"{source.source_type}_transcription_provider",
                parser_version="v3.5" if source.source_type == "video" else "v3.4",
                revision_metadata={
                    "provider": result.provider,
                    "model": result.model,
                    "language": result.language,
                },
                chunks=tuple(
                    ChunkDraft(
                        chunk_index=segment.index,
                        modality=f"{source.source_type}_transcript",
                        content=segment.text,
                        search_text=(
                            f"{'视频' if source.source_type == 'video' else '音频'}转写："
                            f"{source.title or source.original_filename}\n{segment.text}"
                        ),
                        locator={
                            "source_id": source.id,
                            "kind": "media_time",
                            "type": source.source_type,
                            "start_ms": segment.start_ms,
                            "end_ms": segment.end_ms,
                            "asset": (
                                "original_video"
                                if source.source_type == "video"
                                else "original_audio"
                            ),
                        },
                    )
                    for segment in result.segments
                ),
            )
            revision = staged.revision
            chunks_by_index = {chunk.chunk_index: chunk for chunk in staged.chunks}
            for segment in result.segments:
                chunk = chunks_by_index[segment.index]
                chunk.raw_payload_json = json.dumps(
                    {"transcript_segment_index": segment.index},
                    ensure_ascii=False,
                )
                chunk.start_ms = segment.start_ms
                chunk.end_ms = segment.end_ms
                chunk.speaker = segment.speaker
                chunk.language = result.language
                db.add(
                    TranscriptSegment(
                        source_id=source.id,
                        revision_id=revision.id,
                        segment_index=segment.index,
                        start_ms=segment.start_ms,
                        end_ms=segment.end_ms,
                        speaker=segment.speaker,
                        language=result.language,
                        text=segment.text,
                        confidence=(
                            round(segment.confidence * 100)
                            if segment.confidence is not None
                            else None
                        ),
                        metadata_json="{}",
                    )
                )
                db.add(
                    CitationLocator(
                        source_id=source.id,
                        revision_id=revision.id,
                        chunk_id=chunk.id,
                        locator_json=chunk.locator_json,
                        display_text=(
                            f"{'视频' if source.source_type == 'video' else '音频'} "
                            f"{self._format_timestamp(segment.start_ms)}"
                        ),
                    )
                )

            self._copy_video_frames_to_revision(
                db,
                source=source,
                revision=revision,
                existing_frames=existing_video_frames,
            )
            return self._store_and_activate_media_revision(
                db,
                source,
                staged,
                source_metadata=metadata,
                language=result.language,
                duration_ms=result.duration_ms,
            )
        except Exception:
            db.rollback()
            self._cancel_staged_media_revision(db, staged)
            self._record_media_failure(db, source.id, "transcription_status")
            raise

    def process_image_visual_description(self, db: Session, source_id: int) -> Source:
        source = self.get_source(db, source_id)
        if source.source_type != "image":
            raise ValueError("视觉描述当前只支持图片或视频关键帧。")
        if not source.storage_path:
            raise ValueError("图片文件路径不存在，无法执行视觉描述。")
        metadata = source.metadata_data
        metadata.update(
            {
                "vision_description_status": "running",
                "vision_provider": self.ocr_provider.name,
                "vision_model": self.ocr_provider.model,
            }
        )
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.commit()
        try:
            result = self.ocr_provider.describe_image(
                Path(source.storage_path), source.mime_type
            )
        except Exception:
            self._record_media_failure(db, source.id, "vision_description_status")
            raise

        description = result.description.strip()
        content = (
            self._description_content(description, result.learning_points)
            if description
            else ""
        )
        previous_revision = self._active_revision(source)
        seeds = self._carried_chunk_seeds(
            db,
            source,
            previous_revision,
            excluded_modalities={"image_description"},
        )
        if content:
            seeds.append(
                _MediaChunkSeed(
                    draft=ChunkDraft(
                        chunk_index=len(seeds),
                        modality="image_description",
                        content=content,
                        search_text=(
                            f"图片视觉描述：{source.title or source.original_filename}\n"
                            f"{content}"
                        ),
                        locator={
                            "source_id": source.id,
                            "kind": "image_region",
                            "type": "image",
                            "asset": "original_image",
                        },
                    ),
                    raw_payload_json=json.dumps(
                        {
                            "content_type": result.content_type,
                            "learning_points": result.learning_points,
                            "provider": result.provider,
                            "model": result.model,
                        },
                        ensure_ascii=False,
                    ),
                    display_text="图片视觉描述",
                )
            )

        metadata.update(
            {
                "vision_description_status": "completed" if content else "empty",
                "vision_description": result.description,
                "vision_content_type": result.content_type,
                "vision_learning_points": result.learning_points,
                "vision_provider": result.provider,
                "vision_model": result.model,
            }
        )
        staged: _StagedMediaRevision | None = None
        try:
            if not seeds:
                return self._activate_empty_media_revision(
                    db,
                    source,
                    parser_name="image_visual_description_provider",
                    parser_version="v5",
                    revision_metadata={
                        "provider": result.provider,
                        "model": result.model,
                        "content_type": result.content_type,
                    },
                    source_metadata=metadata,
                )
            staged = self._stage_seeded_media_revision(
                db,
                source,
                parser_name="image_visual_description_provider",
                parser_version="v5",
                revision_metadata={
                    "provider": result.provider,
                    "model": result.model,
                    "content_type": result.content_type,
                },
                seeds=seeds,
            )
            return self._store_and_activate_media_revision(
                db,
                source,
                staged,
                source_metadata=metadata,
            )
        except Exception:
            db.rollback()
            self._cancel_staged_media_revision(db, staged)
            self._record_media_failure(db, source.id, "vision_description_status")
            raise

    def process_video_keyframes(
        self, db: Session, source_id: int, *, max_frames: int = 6
    ) -> Source:
        source = self.get_source(db, source_id)
        if source.source_type != "video":
            raise ValueError("关键帧抽取只支持视频资料。")
        if not source.storage_path:
            raise ValueError("视频文件路径不存在，无法提取关键帧。")
        revision = self._active_revision(source)
        batch_id = uuid4().hex
        for frame in revision.visual_frames:
            metadata = self._json_dict(frame.metadata_json)
            metadata["superseded"] = True
            frame.metadata_json = json.dumps(metadata, ensure_ascii=False)
        for asset in source.media_assets:
            if asset.asset_type != "keyframe":
                continue
            metadata = self._json_dict(asset.metadata_json)
            metadata["superseded"] = True
            asset.metadata_json = json.dumps(metadata, ensure_ascii=False)

        extracted = video_tooling.extract_keyframes(
            Path(source.storage_path),
            settings.upload_dir / "video" / "frames",
            source.duration_ms or 1,
            max_frames=max_frames,
        )
        for frame_index, (timestamp_ms, frame_path) in enumerate(extracted):
            width, height = self._inspect_optional_image_size(frame_path)
            frame = VisualFrame(
                source_id=source.id,
                revision_id=revision.id,
                frame_index=frame_index,
                timestamp_ms=timestamp_ms,
                storage_path=str(frame_path),
                metadata_json=json.dumps(
                    {
                        "asset_type": "keyframe",
                        "batch_id": batch_id,
                        "superseded": False,
                    },
                    ensure_ascii=False,
                ),
            )
            db.add(frame)
            db.flush()
            db.add(
                MediaAsset(
                    source_id=source.id,
                    asset_type="keyframe",
                    storage_path=str(frame_path),
                    mime_type="image/jpeg",
                    file_size=frame_path.stat().st_size,
                    width=width,
                    height=height,
                    metadata_json=json.dumps(
                        {
                            "timestamp_ms": timestamp_ms,
                            "frame_id": frame.id,
                            "batch_id": batch_id,
                            "superseded": False,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        metadata = source.metadata_data
        metadata.update(
            {
                "keyframe_status": "completed",
                "keyframe_count": len(extracted),
                "keyframe_batch_id": batch_id,
                "keyframe_strategy": "evenly_spaced_perceptual_dedup",
            }
        )
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.commit()
        return self.get_source(db, source.id)

    def process_video_keyframe_ocr(self, db: Session, source_id: int) -> Source:
        source = self.get_source(db, source_id)
        if source.source_type != "video":
            raise ValueError("关键帧 OCR 只支持视频资料。")
        frames = self._active_video_frames(source)
        if not frames:
            raise ValueError("视频还没有可用关键帧，请先执行关键帧抽取。")
        metadata = source.metadata_data
        metadata.update(
            {
                "keyframe_ocr_status": "running",
                "keyframe_ocr_provider": self.ocr_provider.name,
                "keyframe_ocr_model": self.ocr_provider.model,
            }
        )
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.commit()

        results: list[tuple[VisualFrame, Any, str]] = []
        try:
            for frame in frames:
                if not frame.storage_path:
                    continue
                result = self.ocr_provider.extract_text(
                    Path(frame.storage_path), "image/jpeg"
                )
                results.append((frame, result, result.text.strip()))
        except Exception:
            self._record_media_failure(db, source.id, "keyframe_ocr_status")
            raise

        previous_revision = self._active_revision(source)
        seeds = self._carried_chunk_seeds(
            db,
            source,
            previous_revision,
            excluded_modalities={"video_frame_text"},
        )
        for frame, result, text in results:
            if not text:
                continue
            timestamp_ms = frame.timestamp_ms or 0
            seeds.append(
                _MediaChunkSeed(
                    draft=ChunkDraft(
                        chunk_index=len(seeds),
                        modality="video_frame_text",
                        content=text,
                        search_text=(
                            f"视频画面 {self._format_timestamp(timestamp_ms)}："
                            f"{source.title or source.original_filename}\n{text}"
                        ),
                        locator={
                            "source_id": source.id,
                            "kind": "media_time",
                            "type": "video",
                            "asset": "keyframe",
                            "frame_index": frame.frame_index,
                            "start_ms": timestamp_ms,
                            "end_ms": timestamp_ms,
                        },
                    ),
                    raw_payload_json=json.dumps(
                        {
                            "ocr_provider": result.provider,
                            "ocr_model": result.model,
                        },
                        ensure_ascii=False,
                    ),
                    start_ms=timestamp_ms,
                    end_ms=timestamp_ms,
                    previous_frame_id=frame.id,
                    display_text=(
                        f"视频关键帧 {self._format_timestamp(timestamp_ms)}"
                    ),
                )
            )
        metadata.update(
            {
                "keyframe_ocr_status": (
                    "completed" if any(text for _frame, _result, text in results) else "empty"
                ),
                "keyframe_ocr_count": sum(
                    1 for _frame, _result, text in results if text
                ),
                "keyframe_ocr_provider": self.ocr_provider.name,
                "keyframe_ocr_model": self.ocr_provider.model,
            }
        )
        frame_ocr = {frame.id: text or None for frame, _result, text in results}
        staged: _StagedMediaRevision | None = None
        try:
            if not seeds:
                return self._activate_empty_media_revision(
                    db,
                    source,
                    parser_name="video_keyframe_ocr_provider",
                    parser_version="v5",
                    revision_metadata={
                        "provider": self.ocr_provider.name,
                        "model": self.ocr_provider.model,
                    },
                    source_metadata=metadata,
                    existing_video_frames=frames,
                    frame_ocr_overrides=frame_ocr,
                )
            staged = self._stage_seeded_media_revision(
                db,
                source,
                parser_name="video_keyframe_ocr_provider",
                parser_version="v5",
                revision_metadata={
                    "provider": self.ocr_provider.name,
                    "model": self.ocr_provider.model,
                },
                seeds=seeds,
            )
            self._copy_transcript_segments_to_revision(
                db,
                previous_revision=previous_revision,
                revision=staged.revision,
            )
            frame_map = self._copy_video_frames_to_revision(
                db,
                source=source,
                revision=staged.revision,
                existing_frames=frames,
                ocr_overrides=frame_ocr,
            )
            self._bind_staged_frame_ids(staged, seeds, frame_map)
            return self._store_and_activate_media_revision(
                db,
                source,
                staged,
                source_metadata=metadata,
            )
        except Exception:
            db.rollback()
            self._cancel_staged_media_revision(db, staged)
            self._record_media_failure(db, source.id, "keyframe_ocr_status")
            raise

    def process_video_visual_description(self, db: Session, source_id: int) -> Source:
        source = self.get_source(db, source_id)
        if source.source_type != "video":
            raise ValueError("关键帧视觉描述只支持视频资料。")
        frames = self._active_video_frames(source)
        if not frames:
            raise ValueError("视频还没有可用关键帧，请先执行关键帧抽取。")
        metadata = source.metadata_data
        metadata.update(
            {
                "visual_description_status": "running",
                "vision_provider": self.ocr_provider.name,
                "vision_model": self.ocr_provider.model,
            }
        )
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.commit()

        results: list[tuple[VisualFrame, Any, str]] = []
        try:
            for frame in frames:
                if not frame.storage_path:
                    continue
                result = self.ocr_provider.describe_image(
                    Path(frame.storage_path), "image/jpeg"
                )
                results.append((frame, result, result.description.strip()))
        except Exception:
            self._record_media_failure(db, source.id, "visual_description_status")
            raise

        previous_revision = self._active_revision(source)
        seeds = self._carried_chunk_seeds(
            db,
            source,
            previous_revision,
            excluded_modalities={"video_frame_description"},
        )
        for frame, result, description in results:
            if not description:
                continue
            timestamp_ms = frame.timestamp_ms or 0
            content = self._description_content(
                description, result.learning_points
            )
            seeds.append(
                _MediaChunkSeed(
                    draft=ChunkDraft(
                        chunk_index=len(seeds),
                        modality="video_frame_description",
                        content=content,
                        search_text=(
                            f"视频画面 {self._format_timestamp(timestamp_ms)}："
                            f"{source.title or source.original_filename}\n{content}"
                        ),
                        locator={
                            "source_id": source.id,
                            "kind": "media_time",
                            "type": "video",
                            "asset": "keyframe",
                            "frame_index": frame.frame_index,
                            "start_ms": timestamp_ms,
                            "end_ms": timestamp_ms,
                        },
                    ),
                    raw_payload_json=json.dumps(
                        {
                            "content_type": result.content_type,
                            "learning_points": result.learning_points,
                            "provider": result.provider,
                            "model": result.model,
                        },
                        ensure_ascii=False,
                    ),
                    start_ms=timestamp_ms,
                    end_ms=timestamp_ms,
                    previous_frame_id=frame.id,
                    display_text=(
                        f"视频画面 {self._format_timestamp(timestamp_ms)}"
                    ),
                )
            )
        categories = [result.content_type for _frame, result, _description in results]
        metadata.update(
            {
                "visual_description_status": (
                    "completed"
                    if any(description for _frame, _result, description in results)
                    else "empty"
                ),
                "visual_description_count": sum(
                    1 for _frame, _result, description in results if description
                ),
                "visual_content_types": sorted(set(categories)),
                "vision_provider": self.ocr_provider.name,
                "vision_model": self.ocr_provider.model,
            }
        )
        frame_descriptions = {
            frame.id: description or None
            for frame, _result, description in results
        }
        staged: _StagedMediaRevision | None = None
        try:
            if not seeds:
                return self._activate_empty_media_revision(
                    db,
                    source,
                    parser_name="video_visual_description_provider",
                    parser_version="v5",
                    revision_metadata={
                        "provider": self.ocr_provider.name,
                        "model": self.ocr_provider.model,
                        "content_types": sorted(set(categories)),
                    },
                    source_metadata=metadata,
                    existing_video_frames=frames,
                    frame_description_overrides=frame_descriptions,
                )
            staged = self._stage_seeded_media_revision(
                db,
                source,
                parser_name="video_visual_description_provider",
                parser_version="v5",
                revision_metadata={
                    "provider": self.ocr_provider.name,
                    "model": self.ocr_provider.model,
                    "content_types": sorted(set(categories)),
                },
                seeds=seeds,
            )
            self._copy_transcript_segments_to_revision(
                db,
                previous_revision=previous_revision,
                revision=staged.revision,
            )
            frame_map = self._copy_video_frames_to_revision(
                db,
                source=source,
                revision=staged.revision,
                existing_frames=frames,
                description_overrides=frame_descriptions,
            )
            self._bind_staged_frame_ids(staged, seeds, frame_map)
            return self._store_and_activate_media_revision(
                db,
                source,
                staged,
                source_metadata=metadata,
            )
        except Exception:
            db.rollback()
            self._cancel_staged_media_revision(db, staged)
            self._record_media_failure(db, source.id, "visual_description_status")
            raise

    def process_image_ocr(self, db: Session, source_id: int) -> Source:
        source = self.get_source(db, source_id)
        if source.source_type != "image":
            raise ValueError("当前 OCR 只支持图片资料。")
        if not source.storage_path:
            raise ValueError("图片文件路径不存在，无法执行 OCR。")

        metadata = source.metadata_data
        metadata["ocr_status"] = "running"
        metadata["ocr_provider"] = self.ocr_provider.name
        metadata["ocr_model"] = self.ocr_provider.model
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.commit()

        try:
            result = self.ocr_provider.extract_text(
                Path(source.storage_path), source.mime_type
            )
        except Exception:
            metadata = source.metadata_data
            metadata["ocr_status"] = "failed"
            source.metadata_json = json.dumps(metadata, ensure_ascii=False)
            db.commit()
            raise

        text = result.text.strip()
        metadata = source.metadata_data
        metadata.update(
            {
                "ingestion_mode": "image_ocr",
                "ocr_status": "completed" if text else "empty",
                "ocr_provider": result.provider,
                "ocr_model": result.model,
                "ocr_text_length": len(text),
                "capability_note": (
                    "图片已完成真实 OCR，并已生成可检索的多模态片段。"
                    if text
                    else "OCR 已执行，但没有识别到可用文字。"
                ),
            }
        )

        staged: _StagedMediaRevision | None = None
        try:
            if not text:
                return self._activate_empty_media_revision(
                    db,
                    source,
                    parser_name="image_ocr_provider",
                    parser_version="v3.2",
                    revision_metadata={
                        "ocr_provider": result.provider,
                        "ocr_model": result.model,
                    },
                    source_metadata=metadata,
                )

            staged = self._stage_media_revision(
                db,
                source,
                parser_name="image_ocr_provider",
                parser_version="v3.2",
                revision_metadata={
                    "ocr_provider": result.provider,
                    "ocr_model": result.model,
                },
                chunks=(
                    ChunkDraft(
                        chunk_index=0,
                        modality="image_text",
                        content=text,
                        search_text=f"图片 OCR：{source.title or source.original_filename}\n{text}",
                        locator={
                            "source_id": source.id,
                            "kind": "image_region",
                            "type": "image",
                            "asset": "original_image",
                        },
                    ),
                ),
            )
            chunk = staged.chunks[0]
            chunk.raw_payload_json = json.dumps({"ocr_text": text}, ensure_ascii=False)
            db.add(
                CitationLocator(
                    source_id=source.id,
                    revision_id=staged.revision.id,
                    chunk_id=chunk.id,
                    locator_json=chunk.locator_json,
                    display_text=f"图片：{source.original_filename or source.title or source.id}",
                )
            )
            return self._store_and_activate_media_revision(
                db,
                source,
                staged,
                source_metadata=metadata,
            )
        except Exception:
            db.rollback()
            self._cancel_staged_media_revision(db, staged)
            self._record_media_failure(db, source.id, "ocr_status")
            raise

    def list_sources(
        self, db: Session, space_id: int | None = None, source_type: str | None = None
    ) -> list[Source]:
        stmt = (
            select(Source)
            .options(
                selectinload(Source.media_assets),
                selectinload(Source.revisions).selectinload(SourceRevision.chunks),
                selectinload(Source.revisions).selectinload(
                    SourceRevision.transcript_segments
                ),
                selectinload(Source.revisions).selectinload(
                    SourceRevision.visual_frames
                ),
            )
            .order_by(Source.created_at.desc())
        )
        if space_id is not None:
            stmt = stmt.where(Source.space_id == space_id)
        if source_type is not None:
            stmt = stmt.where(Source.source_type == source_type)
        return list(db.scalars(stmt).all())

    def get_source(self, db: Session, source_id: int) -> Source:
        source = db.scalar(
            select(Source)
            .where(Source.id == source_id)
            .options(
                selectinload(Source.media_assets),
                selectinload(Source.revisions).selectinload(SourceRevision.chunks),
                selectinload(Source.revisions).selectinload(
                    SourceRevision.transcript_segments
                ),
                selectinload(Source.revisions).selectinload(
                    SourceRevision.visual_frames
                ),
            )
        )
        if source is None:
            raise ValueError("资料来源不存在。")
        return source

    def _carried_chunk_seeds(
        self,
        db: Session,
        source: Source,
        revision: SourceRevision,
        *,
        excluded_modalities: set[str],
    ) -> list[_MediaChunkSeed]:
        seeds: list[_MediaChunkSeed] = []
        for chunk in sorted(revision.chunks, key=lambda item: (item.chunk_index, item.id)):
            if chunk.status != "active" or chunk.modality in excluded_modalities:
                continue
            locator = self._json_dict(chunk.locator_json)
            locator.setdefault("kind", self._locator_kind(chunk))
            locator.setdefault("source_id", source.id)
            previous_frame_id = chunk.frame_id
            if previous_frame_id is not None:
                frame = db.get(VisualFrame, previous_frame_id)
                locator.pop("frame_id", None)
                if frame is not None:
                    locator.setdefault("frame_index", frame.frame_index)
                    locator.setdefault("start_ms", frame.timestamp_ms or 0)
                    locator.setdefault("end_ms", frame.timestamp_ms or 0)
            display_text = db.scalar(
                select(CitationLocator.display_text)
                .where(CitationLocator.chunk_id == chunk.id)
                .order_by(CitationLocator.id.desc())
                .limit(1)
            )
            seeds.append(
                _MediaChunkSeed(
                    draft=ChunkDraft(
                        chunk_index=len(seeds),
                        modality=chunk.modality,
                        content=chunk.content_text,
                        search_text=chunk.search_text,
                        locator=locator,
                    ),
                    raw_payload_json=chunk.raw_payload_json,
                    start_ms=chunk.start_ms,
                    end_ms=chunk.end_ms,
                    page_number=chunk.page_number,
                    slide_number=chunk.slide_number,
                    speaker=chunk.speaker,
                    language=chunk.language,
                    previous_frame_id=previous_frame_id,
                    display_text=display_text,
                )
            )
        return seeds

    def _stage_seeded_media_revision(
        self,
        db: Session,
        source: Source,
        *,
        parser_name: str,
        parser_version: str,
        revision_metadata: Mapping[str, Any],
        seeds: list[_MediaChunkSeed],
    ) -> _StagedMediaRevision:
        staged = self._stage_media_revision(
            db,
            source,
            parser_name=parser_name,
            parser_version=parser_version,
            revision_metadata=revision_metadata,
            chunks=tuple(seed.draft for seed in seeds),
        )
        for seed, chunk in zip(seeds, staged.chunks, strict=True):
            chunk.raw_payload_json = seed.raw_payload_json
            chunk.start_ms = seed.start_ms
            chunk.end_ms = seed.end_ms
            chunk.page_number = seed.page_number
            chunk.slide_number = seed.slide_number
            chunk.speaker = seed.speaker
            chunk.language = seed.language
            db.add(
                CitationLocator(
                    source_id=source.id,
                    revision_id=staged.revision.id,
                    chunk_id=chunk.id,
                    locator_json=chunk.locator_json,
                    display_text=seed.display_text,
                )
            )
        return staged

    def _stage_media_revision(
        self,
        db: Session,
        source: Source,
        *,
        parser_name: str,
        parser_version: str,
        revision_metadata: Mapping[str, Any],
        chunks: tuple[ChunkDraft, ...],
    ) -> _StagedMediaRevision:
        next_revision_number = (
            max(
                (revision.revision_number for revision in source.revisions),
                default=0,
            )
            + 1
        )
        command_prefix = (
            f"media:{source.id}:{parser_name}:revision:{next_revision_number}"
        )
        evidence_index = SqlEvidenceIndex(
            db,
            vector_adapter=LegacyVectorStoreEvidenceAdapter(self.vector_store),
        )
        previous_point_ids = self._active_point_ids(db, source)
        content_hash = (
            source.content_hash
            or hashlib.sha256(
                "\n".join(chunk.content for chunk in chunks).encode("utf-8")
            ).hexdigest()
        )
        staged = evidence_index.command(
            StageRevision(
                command_id=f"{command_prefix}:stage",
                draft=RevisionDraft(
                    source_id=source.id,
                    content_hash=content_hash,
                    index_version=settings.index_version,
                    collection_name=settings.qdrant_collection,
                    chunks=chunks,
                    parser_name=parser_name,
                    parser_version=parser_version,
                    embedding_provider=self.embedding_service.provider.name,
                    embedding_model=self.embedding_service.provider.model,
                    embedding_dimensions=self.embedding_service.provider.dimensions,
                    embedding_fingerprint=self.embedding_service.fingerprint(),
                    metadata=dict(revision_metadata),
                ),
            )
        )
        revision = db.get(SourceRevision, staged.revision_id)
        canonical_chunks = tuple(
            db.scalars(
                select(MultimodalChunk)
                .where(MultimodalChunk.revision_id == staged.revision_id)
                .order_by(MultimodalChunk.chunk_index, MultimodalChunk.id)
            )
        )
        if revision is None or len(canonical_chunks) != len(chunks):
            db.rollback()
            try:
                evidence_index.command(
                    CancelRevision(
                        command_id=f"{command_prefix}:cancel-invalid-stage",
                        revision_id=staged.revision_id,
                        reason="Canonical media revision was incomplete after staging.",
                    )
                )
            except Exception:
                db.rollback()
            raise RuntimeError("Canonical media revision was incomplete after staging.")
        return _StagedMediaRevision(
            evidence_index=evidence_index,
            command_prefix=command_prefix,
            revision=revision,
            chunks=canonical_chunks,
            previous_point_ids=previous_point_ids,
        )

    def _store_and_activate_media_revision(
        self,
        db: Session,
        source: Source,
        staged: _StagedMediaRevision,
        *,
        source_metadata: Mapping[str, Any],
        language: str | None | object = _NOT_PROVIDED,
        duration_ms: int | None = None,
    ) -> Source:
        vectors = self.embedding_service.embed_texts(
            [chunk.search_text for chunk in staged.chunks]
        )
        staged.evidence_index.command(
            UpsertRevisionVectors(
                command_id=f"{staged.command_prefix}:upsert",
                revision_id=staged.revision.id,
                points=tuple(
                    PointEmbedding(
                        point_id=chunk.qdrant_point_id or "",
                        vector=tuple(float(value) for value in vector),
                    )
                    for chunk, vector in zip(staged.chunks, vectors, strict=True)
                ),
            )
        )
        revision_view = staged.evidence_index.query(
            GetRevision(revision_id=staged.revision.id)
        )

        source.status = "ready"
        source.metadata_json = json.dumps(dict(source_metadata), ensure_ascii=False)
        if language is not _NOT_PROVIDED:
            source.language = language if isinstance(language, str) else None
        if duration_ms:
            source.duration_ms = duration_ms
        staged.evidence_index.command(
            ActivateRevision(
                command_id=f"{staged.command_prefix}:activate",
                revision_id=staged.revision.id,
                verified_points=tuple(
                    VerifiedPoint(
                        point_id=point.point_id,
                        payload_digest=point.payload_digest,
                    )
                    for point in revision_view.points
                ),
            )
        )

        active_point_ids = {
            chunk.qdrant_point_id for chunk in staged.chunks if chunk.qdrant_point_id
        }
        self._best_effort_delete_points(
            point_id
            for point_id in staged.previous_point_ids
            if point_id not in active_point_ids
        )
        return self.get_source(db, source.id)

    def _activate_empty_media_revision(
        self,
        db: Session,
        source: Source,
        *,
        parser_name: str,
        parser_version: str,
        revision_metadata: Mapping[str, Any],
        source_metadata: Mapping[str, Any],
        existing_video_frames: list[VisualFrame] | None = None,
        frame_ocr_overrides: Mapping[int, str | None] | None = None,
        frame_description_overrides: Mapping[int, str | None] | None = None,
        language: str | None | object = _NOT_PROVIDED,
        duration_ms: int | None = None,
    ) -> Source:
        previous_revision_id = source.active_revision_id
        previous_index_revision_id = source.active_index_revision_id
        previous_point_ids = self._active_point_ids(db, source)
        now = datetime.now(timezone.utc)
        revision = SourceRevision(
            source_id=source.id,
            revision_number=max(
                (item.revision_number for item in source.revisions),
                default=0,
            )
            + 1,
            status="staging",
            parser_name=parser_name,
            parser_version=parser_version,
            content_hash=source.content_hash,
            chunk_count=0,
            vector_count=0,
            validation_status="empty",
            metadata_json=json.dumps(dict(revision_metadata), ensure_ascii=False),
            supersedes_revision_id=previous_revision_id,
        )
        db.add(revision)
        db.flush()
        index_revision = IndexRevision(
            source_id=source.id,
            revision_id=revision.id,
            status="staging",
            index_version=settings.index_version,
            embedding_provider=self.embedding_service.provider.name,
            embedding_model=self.embedding_service.provider.model,
            embedding_dimensions=self.embedding_service.provider.dimensions,
            embedding_fingerprint=self.embedding_service.fingerprint(),
            qdrant_collection=settings.qdrant_collection,
            point_count=0,
            validation_status="empty",
        )
        db.add(index_revision)
        db.flush()
        self._copy_video_frames_to_revision(
            db,
            source=source,
            revision=revision,
            existing_frames=existing_video_frames or [],
            ocr_overrides=frame_ocr_overrides,
            description_overrides=frame_description_overrides,
        )

        previous_revision = (
            db.get(SourceRevision, previous_revision_id)
            if previous_revision_id is not None
            else None
        )
        previous_index = (
            db.get(IndexRevision, previous_index_revision_id)
            if previous_index_revision_id is not None
            else None
        )
        if previous_revision is not None:
            previous_revision.status = "retired"
            previous_revision.retired_at = now
            for chunk in db.scalars(
                select(MultimodalChunk).where(
                    MultimodalChunk.revision_id == previous_revision.id
                )
            ):
                chunk.status = "retired"
                chunk.retired_at = now
        if previous_index is not None:
            previous_index.status = "retired"
            previous_index.retired_at = now
            for manifest in db.scalars(
                select(VectorPointManifest).where(
                    VectorPointManifest.index_revision_id == previous_index.id
                )
            ):
                manifest.status = "retired"

        revision.status = "active"
        revision.activated_at = now
        index_revision.status = "empty"
        index_revision.activated_at = now
        source.status = "ready"
        source.active_revision_id = revision.id
        source.latest_revision_id = revision.id
        source.active_index_revision_id = index_revision.id
        source.metadata_json = json.dumps(dict(source_metadata), ensure_ascii=False)
        if language is not _NOT_PROVIDED:
            source.language = language if isinstance(language, str) else None
        if duration_ms:
            source.duration_ms = duration_ms
        db.commit()

        self._best_effort_delete_points(previous_point_ids)
        return self.get_source(db, source.id)

    def _copy_video_frames_to_revision(
        self,
        db: Session,
        *,
        source: Source,
        revision: SourceRevision,
        existing_frames: list[VisualFrame],
        ocr_overrides: Mapping[int, str | None] | None = None,
        description_overrides: Mapping[int, str | None] | None = None,
    ) -> dict[int, VisualFrame]:
        if source.source_type != "video":
            return {}
        frame_map: dict[int, VisualFrame] = {}
        if existing_frames:
            for frame_index, old_frame in enumerate(existing_frames):
                frame = VisualFrame(
                    source_id=source.id,
                    revision_id=revision.id,
                    frame_index=frame_index,
                    timestamp_ms=old_frame.timestamp_ms,
                    storage_path=old_frame.storage_path,
                    ocr_text=(
                        ocr_overrides[old_frame.id]
                        if ocr_overrides is not None
                        and old_frame.id in ocr_overrides
                        else old_frame.ocr_text
                    ),
                    visual_description=(
                        description_overrides[old_frame.id]
                        if description_overrides is not None
                        and old_frame.id in description_overrides
                        else old_frame.visual_description
                    ),
                    scene_score=old_frame.scene_score,
                    metadata_json=old_frame.metadata_json,
                )
                db.add(frame)
                db.flush()
                frame_map[old_frame.id] = frame
            return frame_map
        if not source.storage_path:
            raise ValueError("媒体文件路径不存在，无法复制视频关键帧。")
        self._add_video_keyframe(
            db=db,
            source=source,
            revision=revision,
            video_path=Path(source.storage_path),
            reuse_existing_asset=True,
        )
        return frame_map

    @staticmethod
    def _copy_transcript_segments_to_revision(
        db: Session,
        *,
        previous_revision: SourceRevision,
        revision: SourceRevision,
    ) -> None:
        for segment in sorted(
            previous_revision.transcript_segments,
            key=lambda item: (item.segment_index, item.id),
        ):
            db.add(
                TranscriptSegment(
                    source_id=segment.source_id,
                    revision_id=revision.id,
                    segment_index=segment.segment_index,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    speaker=segment.speaker,
                    language=segment.language,
                    text=segment.text,
                    confidence=segment.confidence,
                    metadata_json=segment.metadata_json,
                )
            )

    @staticmethod
    def _bind_staged_frame_ids(
        staged: _StagedMediaRevision,
        seeds: list[_MediaChunkSeed],
        frame_map: Mapping[int, VisualFrame],
    ) -> None:
        for seed, chunk in zip(seeds, staged.chunks, strict=True):
            if seed.previous_frame_id is None:
                continue
            frame = frame_map.get(seed.previous_frame_id)
            if frame is None:
                raise RuntimeError(
                    "A staged frame evidence chunk has no frame in its replacement revision."
                )
            chunk.frame_id = frame.id

    def _cancel_staged_media_revision(
        self,
        db: Session,
        staged: _StagedMediaRevision | None,
    ) -> None:
        if staged is None:
            return
        revision = db.get(SourceRevision, staged.revision.id)
        if revision is None or revision.status in {"active", "cancelled"}:
            return
        try:
            staged.evidence_index.command(
                CancelRevision(
                    command_id=f"{staged.command_prefix}:cancel",
                    revision_id=staged.revision.id,
                    reason="Media evidence replacement failed before activation.",
                )
            )
        except Exception:
            db.rollback()

    def _record_media_failure(
        self,
        db: Session,
        source_id: int,
        status_key: str,
    ) -> None:
        try:
            source = self.get_source(db, source_id)
            metadata = source.metadata_data
            metadata[status_key] = "failed"
            source.metadata_json = json.dumps(metadata, ensure_ascii=False)
            db.commit()
        except Exception:
            db.rollback()

    @staticmethod
    def _active_point_ids(db: Session, source: Source) -> tuple[str, ...]:
        if source.active_revision_id is None:
            return ()
        return tuple(
            point_id
            for point_id in db.scalars(
                select(MultimodalChunk.qdrant_point_id)
                .where(
                    MultimodalChunk.source_id == source.id,
                    MultimodalChunk.revision_id == source.active_revision_id,
                    MultimodalChunk.status == "active",
                    MultimodalChunk.qdrant_point_id.is_not(None),
                )
                .order_by(MultimodalChunk.id)
            )
            if point_id
        )

    def _best_effort_delete_points(self, point_ids: Iterable[str]) -> None:
        unique_point_ids = list(
            dict.fromkeys(point_id for point_id in point_ids if point_id)
        )
        if not unique_point_ids:
            return
        try:
            self.vector_store.delete_points(unique_point_ids)
        except Exception:
            # Activation already made the old revision query-invisible. The
            # EvidenceIndex manifest keeps reconciliation deterministic.
            return

    def _save_upload(
        self, upload_file: UploadFile, original_name: str, subdirectory: str
    ) -> tuple[Path, str, int]:
        upload_dir = settings.upload_dir / subdirectory
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_filename(original_name)
        storage_path = upload_dir / f"{uuid4().hex}_{safe_name}"
        hasher = hashlib.sha256()
        total_size = 0

        upload_file.file.seek(0)
        with storage_path.open("wb") as buffer:
            while True:
                chunk = upload_file.file.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > settings.max_upload_size_bytes:
                    buffer.close()
                    storage_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"文件超过上传限制：{settings.max_upload_size_mb} MB。"
                    )
                hasher.update(chunk)
                buffer.write(chunk)

        return storage_path, hasher.hexdigest(), total_size

    @staticmethod
    def _active_revision(source: Source) -> SourceRevision:
        revision = next(
            (item for item in source.revisions if item.id == source.active_revision_id),
            None,
        )
        if revision is None:
            raise ValueError("资料没有活动修订，无法继续处理。")
        return revision

    def _active_video_frames(self, source: Source) -> list[VisualFrame]:
        revision = self._active_revision(source)
        frames = [
            frame
            for frame in revision.visual_frames
            if not self._json_dict(frame.metadata_json).get("superseded", False)
        ]
        return sorted(
            frames,
            key=lambda frame: (frame.timestamp_ms or 0, frame.frame_index, frame.id),
        )

    @staticmethod
    def _locator_kind(chunk: MultimodalChunk) -> str:
        modality = chunk.modality.lower()
        if any(token in modality for token in ("transcript", "audio", "video")):
            return "media_time"
        if any(token in modality for token in ("image", "frame", "visual")):
            return "image_region"
        if "code" in modality:
            return "code_span"
        return "text"

    @staticmethod
    def _description_content(description: str, learning_points: list[str]) -> str:
        parts = [description.strip()]
        if learning_points:
            parts.append(
                "学习重点：\n" + "\n".join(f"- {point}" for point in learning_points)
            )
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _json_dict(value: str | None) -> dict:
        try:
            parsed = json.loads(value or "{}")
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _ensure_transcription_provider_configured(self, source_type: str) -> None:
        if self.transcription_provider.is_configured():
            return
        label = "视频" if source_type == "video" else "音频"
        raise ConfigurationError(
            f"真实{label}转写需要配置 TRANSCRIPTION_API_KEY 或 OPENAI_API_KEY。当前不会生成伪转写。",
            code="TRANSCRIPTION_NOT_CONFIGURED",
            details={
                "provider": self.transcription_provider.name,
                "model": self.transcription_provider.model,
                "source_type": source_type,
            },
        )

    def _add_video_keyframe(
        self,
        db: Session,
        source: Source,
        revision: SourceRevision,
        video_path: Path,
        *,
        reuse_existing_asset: bool = False,
    ) -> VisualFrame:
        timestamp_ms = self._keyframe_timestamp_ms(source.duration_ms)
        keyframe_asset = (
            self._latest_keyframe_asset(source) if reuse_existing_asset else None
        )
        if keyframe_asset is not None and Path(keyframe_asset.storage_path).exists():
            frame_path = Path(keyframe_asset.storage_path)
        else:
            frame_path = video_tooling.extract_keyframe(
                video_path,
                settings.upload_dir / "video" / "frames",
                timestamp_seconds=timestamp_ms / 1000,
            )
            width, height = self._inspect_optional_image_size(frame_path)
            db.add(
                MediaAsset(
                    source_id=source.id,
                    asset_type="keyframe",
                    storage_path=str(frame_path),
                    mime_type="image/jpeg",
                    file_size=frame_path.stat().st_size,
                    width=width,
                    height=height,
                    metadata_json=json.dumps(
                        {"timestamp_ms": timestamp_ms}, ensure_ascii=False
                    ),
                )
            )
        frame = VisualFrame(
            source_id=source.id,
            revision_id=revision.id,
            frame_index=0,
            timestamp_ms=timestamp_ms,
            storage_path=str(frame_path),
            metadata_json=json.dumps({"asset_type": "keyframe"}, ensure_ascii=False),
        )
        db.add(frame)
        db.flush()
        return frame

    @staticmethod
    def _latest_keyframe_asset(source: Source) -> MediaAsset | None:
        keyframes = [
            asset for asset in source.media_assets if asset.asset_type == "keyframe"
        ]
        if not keyframes:
            return None
        return sorted(keyframes, key=lambda asset: asset.id or 0, reverse=True)[0]

    @staticmethod
    def _keyframe_timestamp_ms(duration_ms: int | None) -> int:
        if not duration_ms or duration_ms <= 0:
            return 0
        return min(1000, max(0, duration_ms // 2))

    @staticmethod
    def _inspect_image(path: Path) -> tuple[int, int, str | None]:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
                return width, height, image.format
        except UnidentifiedImageError as exc:
            raise ValueError("无法识别图片内容，请上传有效图片。") from exc

    @staticmethod
    def _inspect_optional_image_size(path: Path) -> tuple[int | None, int | None]:
        try:
            with Image.open(path) as image:
                return image.size
        except Exception:
            return None, None

    @staticmethod
    def _inspect_audio_duration(path: Path) -> int:
        try:
            audio = MutagenFile(path)
            length = (
                float(audio.info.length)
                if audio is not None and getattr(audio, "info", None)
                else 0
            )
        except Exception as exc:
            raise ValueError(
                "无法读取音频元数据，请上传有效的 mp3、wav 或 m4a 文件。"
            ) from exc
        if length <= 0:
            raise ValueError("音频时长无效，请上传包含有效音频内容的文件。")
        return max(1, round(length * 1000))

    @staticmethod
    def _format_timestamp(milliseconds: int) -> str:
        total_seconds = max(0, milliseconds // 1000)
        return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", filename).strip("._")
        return cleaned or "image"

    @staticmethod
    def _preview(text: str, limit: int = 220) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "..."


media_service = MediaService()
