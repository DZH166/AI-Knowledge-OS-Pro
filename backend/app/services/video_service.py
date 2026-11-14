from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from uuid import uuid4

import imageio_ffmpeg
from PIL import Image


class VideoTooling:
    def __init__(self) -> None:
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        self.ffprobe_path = self._ffprobe_path(self.ffmpeg_path)

    def probe(self, path: Path) -> dict:
        command = [
            self.ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True, timeout=30)
        except Exception as exc:
            return self._probe_with_ffmpeg(path, exc)
        try:
            return json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("ffprobe 返回了无法解析的结果。") from exc

    def _probe_with_ffmpeg(self, path: Path, original_exc: Exception) -> dict:
        command = [self.ffmpeg_path, "-i", str(path)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        except Exception as exc:
            raise ValueError(f"无法读取视频元数据：{original_exc}; ffmpeg fallback failed: {exc}") from exc
        output = result.stderr + "\n" + result.stdout
        duration_ms = 0
        duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        if duration_match:
            hours, minutes, seconds = duration_match.groups()
            duration_ms = round((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)
        size_match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", output)
        streams = []
        if size_match:
            streams.append({"codec_type": "video", "width": int(size_match.group(1)), "height": int(size_match.group(2))})
        if re.search(r"Audio:", output):
            streams.append({"codec_type": "audio"})
        if not streams and duration_ms <= 0:
            raise ValueError(f"无法读取视频元数据：{original_exc}")
        return {"format": {"duration": duration_ms / 1000 if duration_ms else 0}, "streams": streams}

    def extract_audio(self, video_path: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{uuid4().hex}_audio.wav"
        command = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ]
        try:
            subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True, timeout=300)
        except Exception as exc:
            raise ValueError(f"无法从视频提取音频：{exc}") from exc
        return output_path

    def extract_keyframe(self, video_path: Path, output_dir: Path, timestamp_seconds: float = 1.0) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{uuid4().hex}_frame.jpg"
        command = [
            self.ffmpeg_path,
            "-y",
            "-ss",
            str(max(0.0, timestamp_seconds)),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(output_path),
        ]
        try:
            subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True, timeout=60)
        except Exception as exc:
            raise ValueError(f"无法提取视频关键帧：{exc}") from exc
        return output_path

    def extract_keyframes(
        self,
        video_path: Path,
        output_dir: Path,
        duration_ms: int,
        *,
        max_frames: int = 6,
    ) -> list[tuple[int, Path]]:
        frame_count = max(3, min(max_frames, 8))
        safe_duration = max(1, duration_ms)
        timestamps = [round(safe_duration * (index + 1) / (frame_count + 1)) for index in range(frame_count)]
        extracted: list[tuple[int, Path]] = []
        signatures: list[tuple[int, ...]] = []
        for timestamp_ms in timestamps:
            frame_path = self.extract_keyframe(video_path, output_dir, timestamp_ms / 1000)
            signature = self._image_signature(frame_path)
            if signature is not None and any(self._hamming_distance(signature, previous) <= 6 for previous in signatures):
                frame_path.unlink(missing_ok=True)
                continue
            if signature is not None:
                signatures.append(signature)
            extracted.append((timestamp_ms, frame_path))
        if not extracted:
            timestamp_ms = min(1000, safe_duration // 2)
            extracted.append((timestamp_ms, self.extract_keyframe(video_path, output_dir, timestamp_ms / 1000)))
        return extracted

    @staticmethod
    def _image_signature(path: Path) -> tuple[int, ...] | None:
        try:
            with Image.open(path) as image:
                grayscale = image.convert("L").resize((16, 16))
                pixels = list(grayscale.getdata())
        except Exception:
            return None
        average = sum(pixels) / len(pixels)
        return tuple(1 if pixel >= average else 0 for pixel in pixels)

    @staticmethod
    def _hamming_distance(left: tuple[int, ...], right: tuple[int, ...]) -> int:
        return sum(a != b for a, b in zip(left, right, strict=True))

    @staticmethod
    def video_metadata(probe_data: dict) -> tuple[int, int | None, int | None, bool]:
        duration = 0.0
        try:
            duration = float(probe_data.get("format", {}).get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        width = None
        height = None
        has_audio = False
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video" and width is None:
                width = int(stream.get("width") or 0) or None
                height = int(stream.get("height") or 0) or None
            if stream.get("codec_type") == "audio":
                has_audio = True
        return max(1, round(duration * 1000)), width, height, has_audio

    @staticmethod
    def _ffprobe_path(ffmpeg_path: str) -> str:
        candidate = Path(ffmpeg_path).with_name("ffprobe.exe")
        if candidate.exists():
            return str(candidate)
        return "ffprobe"


video_tooling = VideoTooling()
