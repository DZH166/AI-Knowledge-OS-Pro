import sys

import pytest

from scripts import check_encoding


def test_encoding_scans_sources_not_generated_browser_vendor_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(check_encoding, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["check_encoding.py"])
    vendor = tmp_path / "frontend/playwright-report/trace/assets/vendor.js"
    vendor.parent.mkdir(parents=True)
    vendor.write_bytes(b"third party fixture: \xff")
    result = tmp_path / "frontend/test-results/error-context.md"
    result.parent.mkdir(parents=True)
    result.write_bytes(b"external error output: \xff")
    source = tmp_path / "frontend/components/test-results/source.ts"
    source.parent.mkdir(parents=True)
    source.write_text("export const enabled = true;", encoding="utf-8")
    check_encoding.main()
    assert source in check_encoding.iter_text_files()


def test_encoding_includes_maintained_powershell_scripts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_encoding, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["check_encoding.py"])
    source = tmp_path / "start.ps1"
    source.write_bytes(b"invalid source: \xff")
    with pytest.raises(SystemExit):
        check_encoding.main()
    assert "start.ps1: invalid UTF-8" in capsys.readouterr().out
