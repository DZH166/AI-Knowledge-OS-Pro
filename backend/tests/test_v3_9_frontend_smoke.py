import subprocess
import sys


def test_frontend_smoke_check_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_frontend_smoke.py"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "frontend_smoke=checked" in completed.stdout
    assert "result=passed" in completed.stdout
    assert "required_routes=24" in completed.stdout
    assert "warnings=0" in completed.stdout
