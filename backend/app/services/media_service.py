from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from fastapi import UploadFile
from mutagen import File as MutagenFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import ConfigurationError, DuplicateDocumentError
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
from app.services.embedding_service import EmbeddingService
from app.services.ocr_service import OCRProvider, get_ocr_provider
from app.services.transcription_service import TranscriptionProvider, get_transcription_provider
from app.services.vector_store import VectorStore
from app.services.video_service import video_tooling


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
    supported_video_mime_types = {"video/mp4", "video/quicktime", "application/octet-stream"}

    def __init__(
        self,
        ocr_provider: OCRProvider | None = None,
        transcription_provider: TranscriptionProvider | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.ocr_provider = ocr_provider or get_ocr_provider()
        self.transcription_provider = transcription_provider or get_transcription_provider()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def upload_image(self, db: Session, space_id: int, upload_file: UploadFile) -> Source:
        space = db.get(KnowledgeSpace, space_id)
        if space is None:
            raise ValueError("知识库不存在。")

        original_name = upload_file.filename or "image"
        suffix = Path(original_name).suffix.lower()
        if suffix not in self.supported_image_extensions:
            raise ValueError("当前图片接入支持 png、jpg、jpeg、webp、bmp。")
        if upload_file.content_type and upload_file.content_type not in self.supported_image_mime_types:
            raise ValueError("上传文件不是受支持的图片 MIME 类型。")

        storage_path, content_hash, file_size = self._save_upload(upload_file, original_name, "images")
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
                details={"source_id": duplicate.id, "filename": duplicate.original_filename},
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
            metadata_json=json.dumps({"image_format": image_format}, ensure_ascii=False),
        )
        db.add(asset)
        db.flush()

        source.active_revision_id = revision.id
        source.latest_revision_id = revision.id
        db.commit()
        return self.get_source(db, source.id)

    def upload_audio(self, db: Session, space_id: int, upload_file: UploadFile) -> Source:
        space = db.get(KnowledgeSpace, space_id)
        if space is None:
            raise ValueError("知识库不存在。")
        original_name = upload_file.filename or "audio"
        suffix = Path(original_name).suffix.lower()
        if suffix not in self.supported_audio_extensions:
            raise ValueError("当前音频接入支持 mp3、wav、m4a。")
        if upload_file.content_type and upload_file.content_type not in self.supported_audio_mime_types:
            raise ValueError("上传文件不是受支持的音频 MIME 类型。")

        storage_path, content_hash, file_size = self._save_upload(upload_file, original_name, "audio")
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
                details={"source_id": duplicate.id, "filename": duplicate.original_filename},
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

    def upload_video(self, db: Session, space_id: int, upload_file: UploadFile) -> Source:
        space = db.get(KnowledgeSpace, space_id)
        if space is None:
            raise ValueError("知识库不存在。")
        original_name = upload_file.filename or "video"
        suffix = Path(original_name).suffix.lower()
        if suffix not in self.supported_video_extensions:
            raise ValueError("当前视频接入支持 mp4、mov。")
        if upload_file.content_type and upload_file.content_type not in self.supported_video_mime_types:
            raise ValueError("上传文件不是受支持的视频 MIME 类型。")

        storage_path, content_hash, file_size = self._save_upload(upload_file, original_name, "video")
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
                details={"source_id": duplicate.id, "filename": duplicate.original_filename},
            )
        try:
            duration_ms, width, height, has_audio = video_tooling.video_metadata(video_tooling.probe(storage_path))
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
            self._add_video_keyframe(db=db, source=source, revision=revision, video_path=storage_path)
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
                media_path = video_tooling.extract_audio(media_path, settings.upload_dir / "video" / "derived")
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

        existing_video_frames = self._active_video_frames(source) if source.source_type == "video" else []
        latest_revision_number = max((revision.revision_number for revision in source.revisions), default=0)
        for old_revision in source.revisions:
            if old_revision.status == "active":
                old_revision.status = "superseded"
        revision = SourceRevision(
            source_id=source.id,
            revision_number=latest_revision_number + 1,
            status="active",
            parser_name=f"{source.source_type}_transcription_provider",
            parser_version="v3.5" if source.source_type == "video" else "v3.4",
            content_hash=source.content_hash,
            chunk_count=len(result.segments),
            vector_count=0,
            validation_status="passed" if result.segments else "empty",
            metadata_json=json.dumps(
                {"provider": result.provider, "model": result.model, "language": result.language},
                ensure_ascii=False,
            ),
            activated_at=datetime.now(timezone.utc),
        )
        db.add(revision)
        db.flush()

        if source.source_type == "video" and existing_video_frames:
            for frame_index, old_frame in enumerate(existing_video_frames):
                db.add(
                    VisualFrame(
                        source_id=source.id,
                        revision_id=revision.id,
                        frame_index=frame_index,
                        timestamp_ms=old_frame.timestamp_ms,
                        storage_path=old_frame.storage_path,
                        ocr_text=old_frame.ocr_text,
                        visual_description=old_frame.visual_description,
                        scene_score=old_frame.scene_score,
                        metadata_json=old_frame.metadata_json,
                    )
                )
        elif source.source_type == "video":
            self._add_video_keyframe(
                db=db,
                source=source,
                revision=revision,
                video_path=Path(source.storage_path),
                reuse_existing_asset=True,
            )

        chunks: list[MultimodalChunk] = []
        for segment in result.segments:
            transcript = TranscriptSegment(
                source_id=source.id,
                revision_id=revision.id,
                segment_index=segment.index,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                speaker=segment.speaker,
                language=result.language,
                text=segment.text,
                confidence=(round(segment.confidence * 100) if segment.confidence is not None else None),
                metadata_json="{}",
            )
            db.add(transcript)
            locator = {
                "source_id": source.id,
                "type": source.source_type,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "asset": "original_video" if source.source_type == "video" else "original_audio",
            }
            chunk = MultimodalChunk(
                source_id=source.id,
                revision_id=revision.id,
                chunk_index=segment.index,
                modality=f"{source.source_type}_transcript",
                source_type=source.source_type,
                content_text=segment.text,
                search_text=f"{'视频' if source.source_type == 'video' else '音频'}转写：{source.title or source.original_filename}\n{segment.text}",
                raw_payload_json=json.dumps({"transcript_segment_index": segment.index}, ensure_ascii=False),
                locator_json=json.dumps(locator, ensure_ascii=False),
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                speaker=segment.speaker,
                language=result.language,
                status="active",
            )
            db.add(chunk)
            db.flush()
            db.add(
                CitationLocator(
                    source_id=source.id,
                    revision_id=revision.id,
                    chunk_id=chunk.id,
                    locator_json=chunk.locator_json,
                    display_text=f"{'视频' if source.source_type == 'video' else '音频'} {self._format_timestamp(segment.start_ms)}",
                )
            )
            chunks.append(chunk)

        if chunks:
            index_revision = self._index_multimodal_chunks(db, source, revision, chunks)
            revision.vector_count = index_revision.point_count
        else:
            db.add(
                IndexRevision(
                    source_id=source.id,
                    revision_id=revision.id,
                    status="empty",
                    index_version=settings.index_version,
                    embedding_provider=self.embedding_service.provider.name,
                    embedding_model=self.embedding_service.provider.model,
                    embedding_dimensions=self.embedding_service.provider.dimensions,
                    embedding_fingerprint=self.embedding_service.fingerprint(),
                    qdrant_collection=settings.qdrant_collection,
                    point_count=0,
                    validation_status="empty",
                )
            )

        metadata = source.metadata_data
        metadata.update(
            {
                "ingestion_mode": f"{source.source_type}_transcription",
                "transcription_status": "completed" if chunks else "empty",
                "transcription_provider": result.provider,
                "transcription_model": result.model,
                "transcript_segment_count": len(chunks),
                "language": result.language,
                "capability_note": f"{'视频' if source.source_type == 'video' else '音频'}已完成真实转写并生成带时间戳的可检索片段。" if chunks else "转写已执行，但没有识别到可用文字。",
            }
        )
        if source.source_type == "video":
            metadata.update(
                {
                    "extracted_audio_status": "completed",
                    "keyframe_status": "completed",
                }
            )
        source.language = result.language
        source.duration_ms = result.duration_ms or source.duration_ms
        source.active_revision_id = revision.id
        source.latest_revision_id = revision.id
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.commit()
        return self.get_source(db, source.id)

    def process_image_visual_description(self, db: Session, source_id: int) -> Source:
        source = self.get_source(db, source_id)
        if source.source_type != "image":
            raise ValueError("视觉描述当前只支持图片或视频关键帧。")
        if not source.storage_path:
            raise ValueError("图片文件路径不存在，无法执行视觉描述。")
        result = self.ocr_provider.describe_image(Path(source.storage_path), source.mime_type)
        revision = self._active_revision(source)
        self._supersede_chunks(db, source.id, "image_description")
        chunks: list[MultimodalChunk] = []
        if result.description.strip():
            content = self._description_content(result.description, result.learning_points)
            chunk = MultimodalChunk(
                source_id=source.id,
                revision_id=revision.id,
                chunk_index=self._next_chunk_index(revision),
                modality="image_description",
                source_type="image",
                content_text=content,
                search_text=f"图片视觉描述：{source.title or source.original_filename}\n{content}",
                raw_payload_json=json.dumps(
                    {"content_type": result.content_type, "learning_points": result.learning_points},
                    ensure_ascii=False,
                ),
                locator_json=json.dumps(
                    {"source_id": source.id, "type": "image", "asset": "original_image"},
                    ensure_ascii=False,
                ),
                status="active",
            )
            db.add(chunk)
            db.flush()
            self._add_citation_locator(db, source, revision, chunk, "图片视觉描述")
            chunks.append(chunk)
        if chunks:
            self._index_multimodal_chunks(db, source, revision, chunks)
        metadata = source.metadata_data
        metadata.update(
            {
                "vision_description_status": "completed" if chunks else "empty",
                "vision_description": result.description,
                "vision_content_type": result.content_type,
                "vision_learning_points": result.learning_points,
                "vision_provider": result.provider,
                "vision_model": result.model,
            }
        )
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        self._refresh_revision_counts(db, revision)
        db.commit()
        return self.get_source(db, source.id)

    def process_video_keyframes(self, db: Session, source_id: int, *, max_frames: int = 6) -> Source:
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
                    {"asset_type": "keyframe", "batch_id": batch_id, "superseded": False},
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
        revision = self._active_revision(source)
        frames = self._active_video_frames(source)
        if not frames:
            raise ValueError("视频还没有可用关键帧，请先执行关键帧抽取。")
        chunks: list[MultimodalChunk] = []
        next_chunk_index = self._next_chunk_index(revision)
        for frame in frames:
            if not frame.storage_path:
                continue
            result = self.ocr_provider.extract_text(Path(frame.storage_path), "image/jpeg")
            frame.ocr_text = result.text.strip() or None
            self._supersede_chunks(db, source.id, "video_frame_text", frame_id=frame.id)
            if not frame.ocr_text:
                continue
            chunk = self._frame_chunk(
                source=source,
                revision=revision,
                frame=frame,
                modality="video_frame_text",
                content=frame.ocr_text,
                raw_payload={"ocr_provider": result.provider, "ocr_model": result.model},
                chunk_index=next_chunk_index + len(chunks),
            )
            db.add(chunk)
            db.flush()
            self._add_citation_locator(db, source, revision, chunk, f"视频关键帧 {self._format_timestamp(frame.timestamp_ms or 0)}")
            chunks.append(chunk)
        if chunks:
            self._index_multimodal_chunks(db, source, revision, chunks)
        metadata = source.metadata_data
        metadata.update(
            {
                "keyframe_ocr_status": "completed" if chunks else "empty",
                "keyframe_ocr_count": len(chunks),
                "keyframe_ocr_provider": self.ocr_provider.name,
                "keyframe_ocr_model": self.ocr_provider.model,
            }
        )
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        self._refresh_revision_counts(db, revision)
        db.commit()
        return self.get_source(db, source.id)

    def process_video_visual_description(self, db: Session, source_id: int) -> Source:
        source = self.get_source(db, source_id)
        if source.source_type != "video":
            raise ValueError("关键帧视觉描述只支持视频资料。")
        revision = self._active_revision(source)
        frames = self._active_video_frames(source)
        if not frames:
            raise ValueError("视频还没有可用关键帧，请先执行关键帧抽取。")
        chunks: list[MultimodalChunk] = []
        categories: list[str] = []
        next_chunk_index = self._next_chunk_index(revision)
        for frame in frames:
            if not frame.storage_path:
                continue
            result = self.ocr_provider.describe_image(Path(frame.storage_path), "image/jpeg")
            frame.visual_description = result.description.strip() or None
            categories.append(result.content_type)
            self._supersede_chunks(db, source.id, "video_frame_description", frame_id=frame.id)
            if not frame.visual_description:
                continue
            content = self._description_content(frame.visual_description, result.learning_points)
            chunk = self._frame_chunk(
                source=source,
                revision=revision,
                frame=frame,
                modality="video_frame_description",
                content=content,
                raw_payload={
                    "content_type": result.content_type,
                    "learning_points": result.learning_points,
                    "provider": result.provider,
                    "model": result.model,
                },
                chunk_index=next_chunk_index + len(chunks),
            )
            db.add(chunk)
            db.flush()
            self._add_citation_locator(db, source, revision, chunk, f"视频画面 {self._format_timestamp(frame.timestamp_ms or 0)}")
            chunks.append(chunk)
        if chunks:
            self._index_multimodal_chunks(db, source, revision, chunks)
        metadata = source.metadata_data
        metadata.update(
            {
                "visual_description_status": "completed" if chunks else "empty",
                "visual_description_count": len(chunks),
                "visual_content_types": sorted(set(categories)),
                "vision_provider": self.ocr_provider.name,
                "vision_model": self.ocr_provider.model,
            }
        )
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        self._refresh_revision_counts(db, revision)
        db.commit()
        return self.get_source(db, source.id)

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
            result = self.ocr_provider.extract_text(Path(source.storage_path), source.mime_type)
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

        latest_revision_number = max((revision.revision_number for revision in source.revisions), default=0)
        for revision in source.revisions:
            if revision.status == "active":
                revision.status = "superseded"

        revision = SourceRevision(
            source_id=source.id,
            revision_number=latest_revision_number + 1,
            status="active",
            parser_name="image_ocr_provider",
            parser_version="v3.2",
            content_hash=source.content_hash,
            chunk_count=1 if text else 0,
            vector_count=0,
            validation_status="passed" if text else "empty",
            metadata_json=json.dumps({"ocr_provider": result.provider, "ocr_model": result.model}, ensure_ascii=False),
            activated_at=datetime.now(timezone.utc),
        )
        db.add(revision)
        db.flush()

        if text:
            chunk = MultimodalChunk(
                source_id=source.id,
                revision_id=revision.id,
                chunk_index=0,
                modality="image_text",
                source_type="image",
                content_text=text,
                search_text=f"图片 OCR：{source.title or source.original_filename}\n{text}",
                raw_payload_json=json.dumps({"ocr_text": text}, ensure_ascii=False),
                locator_json=json.dumps({"source_id": source.id, "type": "image", "asset": "original_image"}, ensure_ascii=False),
                status="active",
            )
            db.add(chunk)
            db.flush()
            db.add(
                CitationLocator(
                    source_id=source.id,
                    revision_id=revision.id,
                    chunk_id=chunk.id,
                    locator_json=chunk.locator_json,
                    display_text=f"图片：{source.original_filename or source.title or source.id}",
                )
            )
            index_revision = self._index_multimodal_chunks(db, source, revision, [chunk])
            revision.vector_count = index_revision.point_count
        else:
            db.add(
                IndexRevision(
                    source_id=source.id,
                    revision_id=revision.id,
                    status="empty",
                    index_version=settings.index_version,
                    embedding_provider=self.embedding_service.provider.name,
                    embedding_model=self.embedding_service.provider.model,
                    embedding_dimensions=self.embedding_service.provider.dimensions,
                    embedding_fingerprint=self.embedding_service.fingerprint(),
                    qdrant_collection=settings.qdrant_collection,
                    point_count=0,
                    validation_status="empty",
                )
            )

        source.status = "ready"
        source.active_revision_id = revision.id
        source.latest_revision_id = revision.id
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.commit()
        return self.get_source(db, source.id)

    def list_sources(self, db: Session, space_id: int | None = None, source_type: str | None = None) -> list[Source]:
        stmt = (
            select(Source)
            .options(
                selectinload(Source.media_assets),
                selectinload(Source.revisions).selectinload(SourceRevision.chunks),
                selectinload(Source.revisions).selectinload(SourceRevision.transcript_segments),
                selectinload(Source.revisions).selectinload(SourceRevision.visual_frames),
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
                selectinload(Source.revisions).selectinload(SourceRevision.transcript_segments),
                selectinload(Source.revisions).selectinload(SourceRevision.visual_frames),
            )
        )
        if source is None:
            raise ValueError("资料来源不存在。")
        return source

    def _index_multimodal_chunks(
        self,
        db: Session,
        source: Source,
        revision: SourceRevision,
        chunks: list[MultimodalChunk],
    ) -> IndexRevision:
        vectors = self.embedding_service.embed_texts([chunk.search_text for chunk in chunks])
        point_ids = [f"mm-{uuid4()}" for _ in chunks]
        fingerprint = self.embedding_service.fingerprint()
        payloads = [
            {
                "space_id": source.space_id,
                "source_id": source.id,
                "source_type": source.source_type,
                "document_name": source.original_filename or source.title or f"source-{source.id}",
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "modality": chunk.modality,
                "content": chunk.content_text,
                "content_preview": self._preview(chunk.content_text),
                "locator_json": chunk.locator_json,
                "start_ms": chunk.start_ms,
                "end_ms": chunk.end_ms,
                "speaker": chunk.speaker,
                "embedding_fingerprint": fingerprint,
                "index_version": settings.index_version,
            }
            for chunk in chunks
        ]
        self.vector_store.upsert_chunks(point_ids=point_ids, vectors=vectors, payloads=payloads)
        for chunk, point_id in zip(chunks, point_ids, strict=True):
            chunk.qdrant_point_id = point_id

        index_revision = IndexRevision(
            source_id=source.id,
            revision_id=revision.id,
            status="active",
            index_version=settings.index_version,
            embedding_provider=self.embedding_service.provider.name,
            embedding_model=self.embedding_service.provider.model,
            embedding_dimensions=self.embedding_service.provider.dimensions,
            embedding_fingerprint=fingerprint,
            qdrant_collection=settings.qdrant_collection,
            point_count=len(chunks),
            validation_status="passed",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(index_revision)
        return index_revision

    def _save_upload(self, upload_file: UploadFile, original_name: str, subdirectory: str) -> tuple[Path, str, int]:
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
                    raise ValueError(f"文件超过上传限制：{settings.max_upload_size_mb} MB。")
                hasher.update(chunk)
                buffer.write(chunk)

        return storage_path, hasher.hexdigest(), total_size

    @staticmethod
    def _active_revision(source: Source) -> SourceRevision:
        revision = next((item for item in source.revisions if item.id == source.active_revision_id), None)
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
        return sorted(frames, key=lambda frame: (frame.timestamp_ms or 0, frame.frame_index, frame.id))

    def _supersede_chunks(
        self,
        db: Session,
        source_id: int,
        modality: str,
        *,
        frame_id: int | None = None,
    ) -> None:
        stmt = select(MultimodalChunk).where(
            MultimodalChunk.source_id == source_id,
            MultimodalChunk.modality == modality,
            MultimodalChunk.status == "active",
        )
        if frame_id is not None:
            stmt = stmt.where(MultimodalChunk.frame_id == frame_id)
        chunks = list(db.scalars(stmt))
        point_ids = [chunk.qdrant_point_id for chunk in chunks if chunk.qdrant_point_id]
        if point_ids:
            self.vector_store.delete_points(point_ids)
        for chunk in chunks:
            chunk.status = "superseded"
            chunk.qdrant_point_id = None
        db.flush()

    @staticmethod
    def _next_chunk_index(revision: SourceRevision) -> int:
        return max((chunk.chunk_index for chunk in revision.chunks), default=-1) + 1

    def _frame_chunk(
        self,
        *,
        source: Source,
        revision: SourceRevision,
        frame: VisualFrame,
        modality: str,
        content: str,
        raw_payload: dict,
        chunk_index: int,
    ) -> MultimodalChunk:
        timestamp_ms = frame.timestamp_ms or 0
        return MultimodalChunk(
            source_id=source.id,
            revision_id=revision.id,
            chunk_index=chunk_index,
            modality=modality,
            source_type="video",
            content_text=content,
            search_text=f"视频画面 {self._format_timestamp(timestamp_ms)}：{source.title or source.original_filename}\n{content}",
            raw_payload_json=json.dumps(raw_payload, ensure_ascii=False),
            locator_json=json.dumps(
                {
                    "source_id": source.id,
                    "type": "video",
                    "asset": "keyframe",
                    "frame_id": frame.id,
                    "start_ms": timestamp_ms,
                    "end_ms": timestamp_ms,
                },
                ensure_ascii=False,
            ),
            frame_id=frame.id,
            start_ms=timestamp_ms,
            end_ms=timestamp_ms,
            status="active",
        )

    @staticmethod
    def _add_citation_locator(
        db: Session,
        source: Source,
        revision: SourceRevision,
        chunk: MultimodalChunk,
        display_text: str,
    ) -> None:
        db.add(
            CitationLocator(
                source_id=source.id,
                revision_id=revision.id,
                chunk_id=chunk.id,
                locator_json=chunk.locator_json,
                display_text=display_text,
            )
        )

    @staticmethod
    def _description_content(description: str, learning_points: list[str]) -> str:
        parts = [description.strip()]
        if learning_points:
            parts.append("学习重点：\n" + "\n".join(f"- {point}" for point in learning_points))
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _json_dict(value: str | None) -> dict:
        try:
            parsed = json.loads(value or "{}")
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _refresh_revision_counts(db: Session, revision: SourceRevision) -> None:
        db.flush()
        active_chunks = list(
            db.scalars(
                select(MultimodalChunk).where(
                    MultimodalChunk.revision_id == revision.id,
                    MultimodalChunk.status == "active",
                )
            )
        )
        revision.chunk_count = len(active_chunks)
        revision.vector_count = sum(1 for chunk in active_chunks if chunk.qdrant_point_id)

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
        keyframe_asset = self._latest_keyframe_asset(source) if reuse_existing_asset else None
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
                    metadata_json=json.dumps({"timestamp_ms": timestamp_ms}, ensure_ascii=False),
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
        keyframes = [asset for asset in source.media_assets if asset.asset_type == "keyframe"]
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
            length = float(audio.info.length) if audio is not None and getattr(audio, "info", None) else 0
        except Exception as exc:
            raise ValueError("无法读取音频元数据，请上传有效的 mp3、wav 或 m4a 文件。") from exc
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
