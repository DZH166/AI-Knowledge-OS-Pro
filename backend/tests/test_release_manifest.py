from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable
import zipfile

import pytest

from scripts import check_release as check_release_module
from scripts import release as release_module
from scripts.check_release import ReleaseValidationError, validate_release_archive
from scripts.release import (
    RELEASE_MANIFEST,
    RELEASE_MANIFEST_DIGEST,
    create_release_archive,
)


ROOT = Path(__file__).resolve().parents[2]


def _write_archive_sidecar(archive: Path, content: bytes | None = None) -> Path:
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    if content is None:
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        content = f"{digest}  {archive.name}\n".encode("ascii")
    sidecar.write_bytes(content)
    return sidecar


def test_release_check_cli_is_directly_executable() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_release.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Inspect an AI Knowledge OS Pro release archive" in completed.stdout


def _release_fixture(tmp_path: Path) -> tuple[Path, Path, list[Path]]:
    root = tmp_path / "repo"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("packaged snapshot\n", encoding="utf-8")
    source = root / "src" / "agent.py"
    source.parent.mkdir()
    source.write_text("answer = 42\n", encoding="utf-8")
    archive = tmp_path / "release.zip"
    files = [readme, source]
    create_release_archive(archive, version="TEST", root=root, files=files)
    _write_archive_sidecar(archive)
    return root, archive, files


def _rewrite_archive(
    archive: Path,
    transform: Callable[[str, bytes], bytes | None],
    *,
    additions: dict[str, bytes] | None = None,
) -> None:
    rewritten = archive.with_name("rewritten.zip")
    with (
        zipfile.ZipFile(archive) as source,
        zipfile.ZipFile(
            rewritten,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as destination,
    ):
        for info in source.infolist():
            content = transform(info.filename, source.read(info))
            if content is not None:
                destination.writestr(info.filename, content)
        for name, content in (additions or {}).items():
            destination.writestr(name, content)
    rewritten.replace(archive)
    _write_archive_sidecar(archive)


def _validate(archive: Path, root: Path, files: list[Path]) -> None:
    validate_release_archive(
        archive,
        version="TEST",
        root=root,
        expected_files=files,
        required_entries=set(),
    )


def test_release_manifest_accepts_exact_archive_and_worktree_snapshot(
    tmp_path: Path,
) -> None:
    root, archive, files = _release_fixture(tmp_path)

    result = validate_release_archive(
        archive,
        version="TEST",
        root=root,
        expected_files=files,
        required_entries={"README.md"},
    )

    assert result.payload_files == 2
    assert result.archive_sha256 == hashlib.sha256(archive.read_bytes()).hexdigest()


@pytest.mark.parametrize("mutation", ["missing", "stale", "truncated"])
def test_release_check_requires_an_exact_checksum_sidecar(
    tmp_path: Path, mutation: str
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    if mutation == "missing":
        sidecar.unlink()
    elif mutation == "stale":
        _write_archive_sidecar(archive, f"{'0' * 64}  {archive.name}\n".encode("ascii"))
    else:
        _write_archive_sidecar(archive, b"1234")

    with pytest.raises(ReleaseValidationError, match="checksum sidecar"):
        _validate(archive, root, files)


def test_release_check_rejects_archive_path_replaced_during_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    replacement = tmp_path / "unverified-replacement.zip"
    replacement.write_bytes(archive.read_bytes())
    with zipfile.ZipFile(replacement, "a") as unverified:
        unverified.writestr("UNVERIFIED.txt", b"this entry was never validated\n")
    replacement_digest = hashlib.sha256(replacement.read_bytes()).hexdigest()
    replacement_sidecar = f"{replacement_digest}  {archive.name}\n".encode("ascii")
    original_current_source_records = check_release_module._current_source_records
    replaced = False

    def replace_path_during_validation(
        current_root: Path,
        current_files: list[Path],
        source_stack: ExitStack,
    ) -> tuple[
        dict[str, tuple[str, int]],
        list[check_release_module._CurrentSourceSnapshot],
        list[str],
    ]:
        nonlocal replaced
        records = original_current_source_records(
            current_root, current_files, source_stack
        )
        if not replaced:
            replacement.replace(archive)
            _write_archive_sidecar(archive, replacement_sidecar)
            replaced = True
        return records

    monkeypatch.setattr(
        check_release_module,
        "_current_source_records",
        replace_path_during_validation,
    )

    with pytest.raises(ReleaseValidationError, match="path changed during validation"):
        _validate(archive, root, files)


def test_release_build_failure_preserves_existing_archive(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "README.md"
    source.write_text("valid\n", encoding="utf-8")
    invalid_source = root / "not-a-file"
    invalid_source.mkdir()
    archive = tmp_path / "release.zip"
    previous_archive = b"previous verified release"
    archive.write_bytes(previous_archive)

    with pytest.raises(ValueError, match="regular file"):
        create_release_archive(
            archive,
            version="TEST",
            root=root,
            files=[source, invalid_source],
        )

    assert archive.read_bytes() == previous_archive


def test_release_pair_publish_failure_preserves_the_previous_verified_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "README.md"
    source.write_text("new verified release\n", encoding="utf-8")
    releases = tmp_path / "releases"
    releases.mkdir()
    date = release_module.datetime.now().strftime("%Y%m%d")
    archive = releases / f"AI-Knowledge-OS-Pro-TEST-{date}.zip"
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    previous_archive = b"previous verified archive"
    previous_sidecar = b"previous verified sidecar"
    archive.write_bytes(previous_archive)
    sidecar.write_bytes(previous_sidecar)
    real_replace = release_module.os.replace
    injected = False

    def fail_sidecar_publication(
        source_path: str | bytes, destination_path: str | bytes
    ) -> None:
        nonlocal injected
        destination = Path(destination_path)
        source_parent = Path(source_path).parent.name
        if (
            destination == sidecar
            and source_parent.startswith(".release-stage-")
            and not injected
        ):
            injected = True
            raise OSError("injected sidecar publication failure")
        real_replace(source_path, destination_path)

    monkeypatch.setattr(release_module.os, "replace", fail_sidecar_publication)

    with pytest.raises(OSError, match="injected sidecar publication failure"):
        release_module.make_release(
            "TEST",
            root=root,
            releases=releases,
            files=[source],
            required_entries=set(),
        )

    assert injected
    assert archive.read_bytes() == previous_archive
    assert sidecar.read_bytes() == previous_sidecar
    assert not list(releases.glob(".release-stage-*"))


def test_release_builder_rejects_tracked_like_symlink_without_following_its_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    untracked_target = root / "untracked-secret.txt"
    untracked_target.write_text("must never be packaged\n", encoding="utf-8")
    tracked_link = root / "tracked-link.txt"
    try:
        tracked_link.symlink_to(untracked_target.name)
    except OSError as exc:
        pytest.skip(f"This platform cannot create an unprivileged test symlink: {exc}")
    archive = tmp_path / "release.zip"

    with pytest.raises(ValueError, match="symbolic link|reparse point"):
        create_release_archive(
            archive,
            version="TEST",
            root=root,
            files=[tracked_link],
        )

    assert not archive.exists()


@pytest.mark.skipif(
    sys.platform != "win32", reason="NTFS reparse-point coverage is Windows-specific"
)
def test_release_builder_rejects_source_beneath_a_windows_junction(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    untracked_directory = root / "untracked-directory"
    untracked_directory.mkdir()
    untracked_source = untracked_directory / "secret.txt"
    untracked_source.write_text("must never be packaged\n", encoding="utf-8")
    tracked_junction = root / "tracked-junction"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(tracked_junction), str(untracked_directory)],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        pytest.skip(
            f"This filesystem cannot create a junction: {completed.stderr or completed.stdout}"
        )
    archive = tmp_path / "release.zip"

    with pytest.raises(ValueError, match="symbolic link|reparse point"):
        create_release_archive(
            archive,
            version="TEST",
            root=root,
            files=[tracked_junction / "secret.txt"],
        )

    assert not archive.exists()


def test_release_check_rejects_source_changed_after_packaging(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "README.md"
    source.write_text("packaged snapshot\n", encoding="utf-8")
    archive = tmp_path / "release.zip"

    create_release_archive(archive, version="TEST", root=root, files=[source])
    _write_archive_sidecar(archive)
    source.write_text("newer worktree content\n", encoding="utf-8")

    with pytest.raises(
        ReleaseValidationError, match=r"stale worktree content.*README\.md"
    ):
        validate_release_archive(
            archive,
            version="TEST",
            root=root,
            expected_files=[source],
            required_entries=set(),
        )


def test_release_check_rejects_tampered_payload_bytes(tmp_path: Path) -> None:
    root, archive, files = _release_fixture(tmp_path)
    _rewrite_archive(
        archive,
        lambda name, content: b"answer = 99\n" if name == "src/agent.py" else content,
    )

    with pytest.raises(
        ReleaseValidationError, match=r"archive content hash mismatch: src/agent\.py"
    ):
        _validate(archive, root, files)


def test_release_check_reports_raw_zip_corruption_as_validation_failure(
    tmp_path: Path,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    with zipfile.ZipFile(archive) as source:
        central_offset = source.start_dir
    raw = bytearray(archive.read_bytes())
    while raw[central_offset : central_offset + 4] == b"PK\x01\x02":
        name_length = int.from_bytes(
            raw[central_offset + 28 : central_offset + 30], "little"
        )
        extra_length = int.from_bytes(
            raw[central_offset + 30 : central_offset + 32], "little"
        )
        comment_length = int.from_bytes(
            raw[central_offset + 32 : central_offset + 34], "little"
        )
        name_start = central_offset + 46
        name = raw[name_start : name_start + name_length].decode()
        if name == "src/agent.py":
            raw[central_offset + 16] ^= 0x01
            break
        central_offset = name_start + name_length + extra_length + comment_length
    else:
        raise AssertionError("src/agent.py central directory entry was not found")
    archive.write_bytes(raw)
    _write_archive_sidecar(archive)

    with pytest.raises(
        ReleaseValidationError, match="cannot read archive entry: src/agent.py"
    ):
        _validate(archive, root, files)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("extra", "archive entries absent from manifest: EXTRA.txt"),
        ("missing", "manifest entries absent from archive: src/agent.py"),
    ],
)
def test_release_check_rejects_entries_not_in_one_to_one_manifest_correspondence(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    if mutation == "extra":
        _rewrite_archive(
            archive, lambda _name, content: content, additions={"EXTRA.txt": b"extra\n"}
        )
    else:
        _rewrite_archive(
            archive,
            lambda name, content: None if name == "src/agent.py" else content,
        )

    with pytest.raises(ReleaseValidationError, match=re.escape(message)):
        _validate(archive, root, files)


def test_release_check_rejects_manifest_self_tampering(tmp_path: Path) -> None:
    root, archive, files = _release_fixture(tmp_path)
    _rewrite_archive(
        archive,
        lambda name, content: content.replace(b'"version":"TEST"', b'"version":"EVIL"')
        if name == RELEASE_MANIFEST
        else content,
    )

    with pytest.raises(
        ReleaseValidationError, match="release manifest self-digest mismatch"
    ):
        _validate(archive, root, files)


def test_release_check_rejects_duplicate_manifest_records_even_with_updated_digest(
    tmp_path: Path,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    with zipfile.ZipFile(archive) as source:
        manifest = json.loads(source.read(RELEASE_MANIFEST))
    manifest["files"].append(dict(manifest["files"][0]))
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    digest_bytes = (
        f"{hashlib.sha256(manifest_bytes).hexdigest()}  {RELEASE_MANIFEST}\n".encode()
    )
    _rewrite_archive(
        archive,
        lambda name, content: manifest_bytes
        if name == RELEASE_MANIFEST
        else digest_bytes
        if name == RELEASE_MANIFEST_DIGEST
        else content,
    )

    with pytest.raises(
        ReleaseValidationError, match="duplicate paths in release manifest"
    ):
        _validate(archive, root, files)


def test_release_check_rejects_duplicate_and_unsafe_archive_paths(
    tmp_path: Path,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(archive, "a") as destination:
            destination.writestr("README.md", b"duplicate\n")
            destination.writestr("../escape.txt", b"escape\n")
    _write_archive_sidecar(archive)

    with pytest.raises(ReleaseValidationError) as caught:
        _validate(archive, root, files)

    assert "duplicate archive entries: README.md" in str(caught.value)
    assert "unsafe archive path '../escape.txt'" in str(caught.value)


def test_release_check_preserves_forbidden_and_missing_entry_findings(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    forbidden_source = root / ".env"
    forbidden_source.write_text("SAFE_PLACEHOLDER=yes\n", encoding="utf-8")
    archive = tmp_path / "release.zip"
    create_release_archive(
        archive,
        version="TEST",
        root=root,
        files=[forbidden_source],
    )
    _write_archive_sidecar(archive)

    with pytest.raises(ReleaseValidationError) as caught:
        validate_release_archive(
            archive,
            version="TEST",
            root=root,
            expected_files=[forbidden_source],
            required_entries={"REQUIRED.md"},
        )

    assert caught.value.forbidden == (".env",)
    assert caught.value.missing == ("REQUIRED.md",)


def test_release_check_rejects_source_changed_after_freshness_hash_before_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    source = root / "src" / "agent.py"
    original_stat = source.stat()
    original_current_source_records = check_release_module._current_source_records
    injected = False

    def mutate_after_freshness_hash(
        current_root: Path,
        current_files: list[Path],
        source_stack: ExitStack,
    ) -> tuple[
        dict[str, tuple[str, int]],
        list[check_release_module._CurrentSourceSnapshot],
        list[str],
    ]:
        nonlocal injected
        records = original_current_source_records(
            current_root, current_files, source_stack
        )
        source.write_bytes(b"answer = 99\n")
        os.utime(
            source,
            ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
        )
        injected = True
        return records

    monkeypatch.setattr(
        check_release_module,
        "_current_source_records",
        mutate_after_freshness_hash,
    )

    with pytest.raises(
        ReleaseValidationError, match=r"worktree source changed.*src/agent\.py"
    ):
        _validate(archive, root, files)

    assert injected


def test_release_check_has_a_final_all_source_metadata_fence_after_rehash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    readme = root / "README.md"
    original_validate_source = release_module.validate_release_source
    readme_validations = 0
    injected = False

    def mutate_after_readme_rehash(
        current_root: Path,
        source: Path,
    ) -> release_module.ValidatedReleaseSource:
        nonlocal injected, readme_validations
        validated = original_validate_source(current_root, source)
        if source == readme:
            readme_validations += 1
            if readme_validations == 4:
                readme.write_bytes(b"tampered snapshot\n")
                injected = True
        return validated

    monkeypatch.setattr(
        release_module,
        "validate_release_source",
        mutate_after_readme_rehash,
    )

    with pytest.raises(
        ReleaseValidationError, match=r"worktree source changed.*README\.md"
    ):
        _validate(archive, root, files)

    assert injected


@pytest.mark.parametrize(
    "metadata_directory",
    ["RELEASE-MANIFEST.json", "release-manifest.JSON"],
)
def test_release_builder_rejects_payload_beneath_reserved_metadata_file_path(
    tmp_path: Path,
    metadata_directory: str,
) -> None:
    root = tmp_path / "repo"
    payload = root / metadata_directory / "payload.txt"
    payload.parent.mkdir(parents=True)
    payload.write_text("must not shadow release metadata\n", encoding="utf-8")
    archive = tmp_path / "release.zip"

    with pytest.raises(ValueError, match="portable extraction path ancestor conflict"):
        create_release_archive(
            archive,
            version="TEST",
            root=root,
            files=[payload],
        )

    assert not archive.exists()


def test_release_builder_rejects_casefold_collision_with_reserved_metadata_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    payload = root / "release-manifest.JSON"
    payload.write_text("must not replace release metadata\n", encoding="utf-8")
    archive = tmp_path / "release.zip"

    with pytest.raises(ValueError, match="reserved metadata path collision"):
        create_release_archive(
            archive,
            version="TEST",
            root=root,
            files=[payload],
        )

    assert not archive.exists()


@pytest.mark.parametrize(
    "nested_name",
    [
        "README.md/payload.txt",
        "readme.MD/payload.txt",
        "RELEASE-MANIFEST.json/payload.txt",
        "release-manifest.JSON/payload.txt",
    ],
)
def test_release_check_rejects_portable_archive_path_ancestor_conflicts(
    tmp_path: Path,
    nested_name: str,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    _rewrite_archive(
        archive,
        lambda _name, content: content,
        additions={nested_name: b"ambiguous portable extraction\n"},
    )

    with pytest.raises(ReleaseValidationError) as caught:
        _validate(archive, root, files)

    assert "portable archive path ancestor conflict" in str(caught.value)


def test_release_check_rejects_portable_manifest_path_ancestor_conflicts(
    tmp_path: Path,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    with zipfile.ZipFile(archive) as source:
        manifest = json.loads(source.read(RELEASE_MANIFEST))
    manifest["files"][1]["path"] = "readme.MD/payload.txt"
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    digest_bytes = (
        f"{hashlib.sha256(manifest_bytes).hexdigest()}  {RELEASE_MANIFEST}\n".encode()
    )
    _rewrite_archive(
        archive,
        lambda name, content: manifest_bytes
        if name == RELEASE_MANIFEST
        else digest_bytes
        if name == RELEASE_MANIFEST_DIGEST
        else content,
    )

    with pytest.raises(ReleaseValidationError) as caught:
        _validate(archive, root, files)

    assert "portable manifest path ancestor conflict" in str(caught.value)


def test_release_check_rejects_manifest_casefold_collision_with_metadata_file(
    tmp_path: Path,
) -> None:
    root, archive, files = _release_fixture(tmp_path)
    with zipfile.ZipFile(archive) as source:
        manifest = json.loads(source.read(RELEASE_MANIFEST))
    manifest["files"][1]["path"] = "release-manifest.JSON"
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    digest_bytes = (
        f"{hashlib.sha256(manifest_bytes).hexdigest()}  {RELEASE_MANIFEST}\n".encode()
    )
    _rewrite_archive(
        archive,
        lambda name, content: manifest_bytes
        if name == RELEASE_MANIFEST
        else digest_bytes
        if name == RELEASE_MANIFEST_DIGEST
        else content,
    )

    with pytest.raises(ReleaseValidationError) as caught:
        _validate(archive, root, files)

    assert "portable manifest path collision" in str(caught.value)


def test_release_check_rejects_portable_worktree_source_path_ancestor_conflicts(
    tmp_path: Path,
) -> None:
    root, archive, _files = _release_fixture(tmp_path)
    payload = root / "release-manifest.JSON" / "payload.txt"
    payload.parent.mkdir()
    payload.write_text("must not shadow release metadata\n", encoding="utf-8")

    with pytest.raises(ReleaseValidationError) as caught:
        validate_release_archive(
            archive,
            version="TEST",
            root=root,
            expected_files=[payload],
            required_entries=set(),
        )

    assert "portable worktree source path ancestor conflict" in str(caught.value)
