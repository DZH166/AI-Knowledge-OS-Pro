import subprocess
import sys


def test_v4_8_request_cache_static_gate_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_request_cache.py"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "request_cache=checked" in completed.stdout
    assert "ttl_methods=6" in completed.stdout
    assert "result=passed" in completed.stdout
