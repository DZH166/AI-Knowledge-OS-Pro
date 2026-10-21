from __future__ import annotations

import subprocess
import zipfile

import pytest

from scripts import release


@pytest.mark.parametrize("source_mode", ["git", "extracted_zip"])
def test_release_analysis_excludes_retained_browser_diagnostics_from_source_archives(tmp_path, monkeypatch, source_mode):
    root = tmp_path / "source"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("Maintained source\n", encoding="utf-8")
    diagnostics = root / ".controlled_browser_logs" / "run-1"
    diagnostics.mkdir(parents=True)
    retained = [diagnostics / name for name in ("frontend.log", "report.json", "error-context.md")]
    for path in retained:
        path.write_text("Local browser diagnostic\n", encoding="utf-8")
    sibling = root / ".controlled_browser_logs-guide.md"
    sibling.write_text("Maintained documentation\n", encoding="utf-8")
    monkeypatch.setattr(release, "ROOT", root)

    def git_files(*_args, **_kwargs):
        if source_mode == "extracted_zip":
            raise subprocess.CalledProcessError(128, ["git", "ls-files", "-z"])
        # Even a diagnostic accidentally force-added to Git remains excluded.
        return b"\0".join(path.relative_to(root).as_posix().encode() for path in [readme, sibling, *retained])

    monkeypatch.setattr(release.subprocess, "check_output", git_files)
    analysis = release.analyze_release()
    assert analysis.included == sorted([readme, sibling]), "Local browser reports must not become release payload."
    assert set(retained) <= set(analysis.excluded)
    archive_path = tmp_path / "release.zip"
    release.create_release_archive(archive_path, version="TEST", root=root, files=analysis.included)
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {
            "README.md", ".controlled_browser_logs-guide.md",
            release.RELEASE_MANIFEST, release.RELEASE_MANIFEST_DIGEST,
        }
