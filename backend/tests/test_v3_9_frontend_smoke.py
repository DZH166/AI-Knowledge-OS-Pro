import subprocess
import sys

from scripts import check_frontend_smoke


def test_report_code_blocks_do_not_allow_debug_dumps_or_unrelated_pre_views(tmp_path, monkeypatch) -> None:
    frontend = tmp_path / "frontend"
    components = frontend / "components"
    artifact = components / "evidence-agent" / "ArtifactBody.tsx"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('<pre aria-label="研究正文代码">{children}</pre>', encoding="utf-8")
    other = components / "OtherView.tsx"
    other.write_text("<pre>unrelated raw dump</pre>", encoding="utf-8")
    monkeypatch.setattr(check_frontend_smoke, "ROOT", tmp_path)
    monkeypatch.setattr(check_frontend_smoke, "FRONTEND", frontend)
    monkeypatch.setattr(check_frontend_smoke, "APP_DIR", frontend / "app")

    failures = check_frontend_smoke.scan_forbidden_ui_patterns()
    assert failures == ["frontend/components/OtherView.tsx contains <pre> outside the approved evidence/code views"]

    artifact.write_text("<pre>{JSON.stringify(payload)}</pre>", encoding="utf-8")
    failures = check_frontend_smoke.scan_forbidden_ui_patterns()
    assert any("ArtifactBody.tsx contains forbidden UI pattern: JSON.stringify(" in failure for failure in failures)


def test_frontend_smoke_check_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_frontend_smoke.py"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "frontend_smoke=checked" in completed.stdout
    assert "result=passed" in completed.stdout
    assert "required_routes=31" in completed.stdout
    assert "nav_targets=12" in completed.stdout
    assert "warnings=0" in completed.stdout
