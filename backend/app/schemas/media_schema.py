from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.document_schema import IngestionJobRead


class MediaAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    asset_type: str
    storage_path: str
    mime_type: str | None = None
    file_size: int
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    metadata_json: str
    created_at: datetime


class MultimodalChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    revision_id: int
    chunk_index: int
    modality: str
    source_type: str
    content_text: str
    search_text: str
    locator_json: str
    start_ms: int | None = None
    end_ms: int | None = None
    page_number: int | None = None
    slide_number: int | None = None
    frame_id: int | None = None
    status: str
    qdrant_point_id: str | None = None
    created_at: datetime


class TranscriptSegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    revision_id: int
    segment_index: int
    start_ms: int
    end_ms: int
    speaker: str | None = None
    language: str | None = None
    text: str
    confidence: int | None = None
    created_at: datetime


class VisualFrameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    revision_id: int
    frame_index: int
    timestamp_ms: int | None = None
    storage_path: str | None = None
    ocr_text: str | None = None
    visual_description: str | None = None
    scene_score: int | None = None
    metadata_json: str
    created_at: datetime


class SourceRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    revision_number: int
    status: str
    parser_name: str | None = None
    parser_version: str | None = None
    chunk_count: int
    vector_count: int
    validation_status: str
    error_message: str | None = None
    metadata_json: str
    activated_at: datetime | None = None
    chunks: list[MultimodalChunkRead] = []
    transcript_segments: list[TranscriptSegmentRead] = []
    visual_frames: list[VisualFrameRead] = []


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    document_id: int | None = None
    source_type: str
    title: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int
    storage_path: str | None = None
    content_hash: str | None = None
    status: str
    language: str | None = None
    duration_ms: int | None = None
    page_count: int | None = None
    width: int | None = None
    height: int | None = None
    metadata_json: str
    active_revision_id: int | None = None
    latest_revision_id: int | None = None
    created_at: datetime
    updated_at: datetime


class SourceDetail(SourceRead):
    media_assets: list[MediaAssetRead] = []
    revisions: list[SourceRevisionRead] = []


class ImageUploadResponse(BaseModel):
    source: SourceDetail
    message: str
    job_id: int | None = None


class ImageOCRResponse(BaseModel):
    source: SourceDetail
    message: str


class AudioUploadResponse(BaseModel):
    source: SourceDetail
    message: str
    job_id: int | None = None


class AudioTranscriptionResponse(BaseModel):
    source: SourceDetail
    message: str


class VideoUploadResponse(BaseModel):
    source: SourceDetail
    message: str
    job_id: int | None = None


MediaOperation = Literal[
    "image_ocr",
    "image_visual_description",
    "image_screenshot_analysis",
    "image_full_analysis",
    "audio_transcription",
    "video_transcription",
    "video_keyframes",
    "video_keyframe_ocr",
    "video_visual_description",
    "video_full_pipeline",
]


class MediaProcessRequest(BaseModel):
    operation: MediaOperation


class MediaTaskResponse(BaseModel):
    source: SourceDetail
    job: IngestionJobRead
    message: str
