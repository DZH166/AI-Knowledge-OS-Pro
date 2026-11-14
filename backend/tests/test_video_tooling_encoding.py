from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.video_service import VideoTooling


def test_ffmpeg_subprocesses_force_utf8_decoding(monkeypatch, tmp_path: Path) -> None:
    """Windows defaults to the ANSI code page and crashes on ffmpeg byte output.

    The fallback probe and the audio/keyframe extractions must all request
    UTF-8 with replacement so binary-ish stderr never kills a reader thread.
    """

    calls: list[dict] = []

    def fake_run(command: list[str], **kwargs):
        calls.append(kwargs)
        if "-print_format" in command:
            raise FileNotFoundError("ffprobe is not bundled")
        return SimpleNamespace(
            stdout="",
            stderr="Duration: 00:00:02.00, start: 0.000000\nStream #0:0 Video: h264, 640x360\nStream #0:1 Audio: aac",
            returncode=1,
        )

    monkeypatch.setattr("app.services.video_service.subprocess.run", fake_run)
    tooling = VideoTooling()

    probe = tooling.probe(tmp_path / "sample.mp4")
    tooling.extract_audio(tmp_path / "sample.mp4", tmp_path / "audio")
    tooling.extract_keyframe(tmp_path / "sample.mp4", tmp_path / "frames", 1.0)

    assert probe["format"]["duration"] == 2.0
    assert probe["streams"][0]["width"] == 640
    assert len(calls) == 4
    assert all(call["encoding"] == "utf-8" for call in calls)
    assert all(call["errors"] == "replace" for call in calls)
