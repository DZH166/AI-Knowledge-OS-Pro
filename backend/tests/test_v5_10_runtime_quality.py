from __future__ import annotations

from io import BytesIO, TextIOWrapper
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import smoke_test_real_services as smoke
from scripts import check_all as gates


class HttpReply:
    status = 200

    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def ready_system():
    return {
        "runtime": {"runtime_mode": "real"},
        **{name: {"ok": True, "status": "ready"} for name in (
            "db", "qdrant", "collection", "redis", "worker", "llm", "embedding",
        )},
    }


def test_real_service_command_reports_http_failure(monkeypatch, capsys) -> None:
    def unavailable(req, **_kwargs):
        raise HTTPError(req.full_url, 503, "Unavailable", {}, BytesIO(b'{"ok":false}'))

    monkeypatch.setattr(smoke.request, "urlopen", unavailable)
    monkeypatch.setattr("sys.argv", ["smoke_test_real_services.py"])

    assert smoke.main() == 1
    assert "real_services_status=failed" in capsys.readouterr().out


def test_default_real_service_preflight_does_not_call_providers(monkeypatch, capsys) -> None:
    def read_only(req, **_kwargs):
        assert req.get_method() == "GET", "Default preflight must never initiate provider probes."
        return HttpReply({"status": "ok", "runtime_mode": "real"}
                         if req.full_url.endswith("/health") else ready_system())

    monkeypatch.setattr(smoke.request, "urlopen", read_only)
    monkeypatch.setattr("sys.argv", ["smoke_test_real_services.py"])

    assert smoke.main() == 0
    output = capsys.readouterr().out
    assert "mode=preflight" in output
    assert "provider_probes=not_run" in output


@pytest.mark.parametrize("failure", ["business", "demo", "invalid_json", "invalid_shape"])
def test_preflight_rejects_unhealthy_or_unverifiable_replies(monkeypatch, capsys, failure) -> None:
    def respond(req, **_kwargs):
        if req.full_url.endswith("/health"):
            return HttpReply({"status": "ok", "runtime_mode": "real"})
        payload = ready_system()
        if failure == "business":
            payload["redis"] = {"ok": False, "status": "unavailable"}
        elif failure == "demo":
            payload["runtime"]["runtime_mode"] = "demo"
        elif failure == "invalid_shape":
            payload = []
        reply = HttpReply(payload)
        if failure == "invalid_json":
            reply.body = b"<html>gateway failure</html>"
        return reply

    monkeypatch.setattr(smoke.request, "urlopen", respond)
    assert smoke.main([]) == 1
    output = capsys.readouterr().out
    assert "real_services_status=failed" in output
    assert "real_provider_success=not_claimed" in output


@pytest.mark.parametrize("outcome", ["failed", "demo_before_probe", "success"])
def test_explicit_provider_probes_require_real_preflight_and_business_success(monkeypatch, capsys, outcome) -> None:
    def respond(req, **_kwargs):
        if req.full_url.endswith("/health"):
            return HttpReply({"status": "ok", "runtime_mode": "demo" if outcome == "demo_before_probe" else "real"})
        if req.get_method() == "GET":
            return HttpReply(ready_system())
        assert outcome != "demo_before_probe", "A demo preflight must prevent provider calls."
        return HttpReply({"ok": outcome == "success", "status": "ready" if outcome == "success" else "LLM_TEST_FAILED"})

    monkeypatch.setattr(smoke.request, "urlopen", respond)
    assert smoke.main(["--probe-providers"]) == (0 if outcome == "success" else 1)
    output = capsys.readouterr().out
    assert f"provider_probes={'not_run' if outcome == 'demo_before_probe' else outcome if outcome == 'failed' else 'passed'}" in output
    assert f"real_provider_success={'verified' if outcome == 'success' else 'not_claimed'}" in output


def test_total_check_reports_optional_browser_skip_without_claiming_pass(monkeypatch, tmp_path, capsys) -> None:
    def execute(command, **_kwargs):
        output = "demo_e2e_status=skipped reason=PLAYWRIGHT_NOT_INSTALLED\n" if "scripts/run_demo_e2e.py" in command else ""
        return subprocess.CompletedProcess(command, 0, output, "")

    report = tmp_path / "quality.json"
    monkeypatch.setattr(gates.subprocess, "run", execute)
    monkeypatch.setattr("sys.argv", ["check_all.py", "--e2e", "--json-report", str(report)])
    gates.main()

    payload = json.loads(report.read_text(encoding="utf-8"))
    browser = next(gate for gate in payload["gates"] if gate["name"] == "optional demo browser E2E")
    assert browser["status"] == "skipped"
    assert "PLAYWRIGHT_NOT_INSTALLED" in browser["failure_reason"]
    assert payload["skipped_gate_count"] == 1
    assert "status=skipped" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["skip_zero", "failed_exit", "missing_executable"])
def test_strict_browser_check_returns_failure_and_writes_failed_gate(monkeypatch, tmp_path, capsys, failure) -> None:
    def execute(command, **_kwargs):
        if "scripts/check_e2e.py" not in command:
            return subprocess.CompletedProcess(command, 0, "", "")
        assert "--strict" in command
        if failure == "missing_executable":
            raise FileNotFoundError("Node unavailable")
        if failure == "failed_exit":
            raise subprocess.CalledProcessError(1, command, output="e2e_status=failed reason=NO_NODE_OR_NPM\n")
        return subprocess.CompletedProcess(command, 0, "e2e_status=skipped reason=NO_NODE_OR_NPM\n", "")

    report = tmp_path / "strict.json"
    monkeypatch.setattr(gates.subprocess, "run", execute)
    monkeypatch.setattr("sys.argv", ["check_all.py", "--live-e2e", "--json-report", str(report)])
    assert gates.main() == 1

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["gates"][0]["status"] == "failed"
    assert "result=failed" in capsys.readouterr().out


@pytest.mark.parametrize("strict, expected_status, exit_code", [(False, "skipped", 0), (True, "failed", 1)])
def test_controlled_browser_missing_node_is_never_a_pass(monkeypatch, tmp_path, capsys, strict, expected_status, exit_code) -> None:
    from scripts import run_controlled_browser as controlled

    def forbidden_start(*_args, **_kwargs):
        pytest.fail("Missing runtime must not start any process or service.")

    monkeypatch.setattr(controlled.subprocess, "Popen", forbidden_start)
    args = ["--node", str(tmp_path / "missing-node.exe")]
    if strict:
        args.append("--strict")
    assert controlled.main(args) == exit_code
    output = capsys.readouterr().out
    assert f"controlled_browser_status={expected_status}" in output
    assert "integration_services=not_run" in output


def test_controlled_browser_runs_only_allowlisted_specs_against_owned_frontend(monkeypatch, tmp_path, capsys) -> None:
    from scripts import run_controlled_browser as controlled

    frontend = tmp_path / "frontend"
    specs = ("workbench-retry.spec.ts", "v5-9-research-journey.spec.ts", "v5-10-research-recovery.spec.ts",
             "v5-11-artifact-upload.spec.ts", "v5-11-connection-recovery.spec.ts")
    for filename in (*[f"e2e/{name}" for name in specs], "node_modules/next/dist/bin/next", "node_modules/@playwright/test/cli.js"):
        target = frontend / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture", encoding="utf-8")
    launches = []

    class OwnedProcess:
        pid = 900001

        def __init__(self, command, **kwargs):
            launches.append((command, kwargs))
            self.returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            self.returncode = 0
            return 0

        def stop(self):
            self.returncode = 0

    def execute(command, **_kwargs):
        assert command[0] != "docker"
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(controlled, "FRONTEND", frontend, raising=False)
    monkeypatch.setattr(controlled, "launch_owned", OwnedProcess)
    monkeypatch.setattr(controlled.subprocess, "run", execute)
    monkeypatch.setattr(controlled.os, "killpg", lambda *_args: None, raising=False)
    monkeypatch.setattr(controlled, "urlopen", lambda *_args, **_kwargs: HttpReply({}), raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "https://paid-provider.invalid")
    monkeypatch.setenv("API_PROXY_TARGET", "https://paid-provider.invalid")
    report = tmp_path / "controlled.json"

    assert controlled.main(["--node", sys.executable, "--strict", "--json-report", str(report)]) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["verification_mode"] == "controlled"
    assert payload["specs"] == list(specs)
    assert payload["integration_services"] == "not_run"
    assert len(launches) == 3
    assert launches[1][1]["env"]["API_PROXY_TARGET"] == "", "An explicit empty value prevents Next dotenv from restoring a remote proxy."
    assert launches[1][1]["env"]["NEXT_PUBLIC_API_BASE_URL"] == payload["frontend_url"]
    assert "test" in launches[2][0]
    filters = launches[2][0][launches[2][0].index("--retries=0") + 1:]
    selected = {name for name in (*specs, "v5-8-feedback.spec.ts", "v5-10-research-recoveryXspecXts")
                if any(re.search(pattern, f"/project/frontend/e2e/{name}") for pattern in filters)}
    assert selected == set(specs)
    assert "controlled_browser_status=passed" in capsys.readouterr().out


def test_controlled_browser_deadline_fails_and_cleans_both_owned_process_trees(monkeypatch, tmp_path, capsys) -> None:
    from scripts import run_controlled_browser as controlled

    frontend = tmp_path / "frontend"
    for filename in ("e2e/workbench-retry.spec.ts", "node_modules/next/dist/bin/next", "node_modules/@playwright/test/cli.js"):
        target = frontend / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture", encoding="utf-8")
    processes = []

    class OwnedProcess:
        def __init__(self, command, **_kwargs):
            self.command = command
            self.pid = 900011 + len(processes)
            self.returncode = None
            self.timed_out = False
            processes.append(self)

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            if "test" in self.command and not self.timed_out:
                self.timed_out = True
                raise subprocess.TimeoutExpired(self.command, timeout)
            self.returncode = 0
            return 0

        def stop(self):
            self.returncode = 0

    monkeypatch.setattr(controlled, "FRONTEND", frontend)
    monkeypatch.setattr(controlled, "launch_owned", OwnedProcess)
    monkeypatch.setattr(controlled.subprocess, "run", lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "", ""))
    monkeypatch.setattr(controlled.os, "killpg", lambda *_args: None, raising=False)
    monkeypatch.setattr(controlled, "urlopen", lambda *_args, **_kwargs: HttpReply({}))
    report = tmp_path / "timeout.json"

    assert controlled.main(["--node", sys.executable, "--strict", "--spec", "workbench-retry.spec.ts",
                            "--test-timeout", "1", "--json-report", str(report)]) == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["boundary"] == "browser_tests_timeout"
    output = capsys.readouterr().out
    assert "controlled_cleanup=owned_process pid=900011" in output
    assert "controlled_cleanup=owned_process pid=900012" in output
    assert "controlled_cleanup=owned_process pid=900013" in output


def test_controlled_browser_cli_rejects_live_specs_before_starting_services(tmp_path) -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_controlled_browser.py", "--spec", "v5-8-feedback.spec.ts"],
        cwd=gates.ROOT, capture_output=True, text=True, timeout=10,
    )
    assert completed.returncode == 2
    assert "invalid choice" in completed.stderr


def test_controlled_browser_cli_missing_runtime_writes_failed_evidence(tmp_path) -> None:
    report = tmp_path / "missing.json"
    completed = subprocess.run(
        [sys.executable, "scripts/run_controlled_browser.py", "--strict", "--node", str(tmp_path / "absent-node.exe"),
         "--json-report", str(report)],
        cwd=gates.ROOT, capture_output=True, text=True, timeout=10,
    )
    assert completed.returncode == 1
    assert "controlled_browser_status=failed" in completed.stdout
    assert json.loads(report.read_text(encoding="utf-8"))["boundary"] == "NODE_NOT_AVAILABLE"


def test_total_check_can_report_controlled_browser_separately_from_service_acceptance(monkeypatch, tmp_path, capsys) -> None:
    def execute(command, **_kwargs):
        if command[0] == "git":
            return subprocess.CompletedProcess(command, 0, "", "")
        assert command[1:3] == ["scripts/run_controlled_browser.py", "--strict"]
        return subprocess.CompletedProcess(command, 0, "controlled_browser_status=passed reason=browser_tests\n", "")

    report = tmp_path / "controlled_gate.json"
    monkeypatch.setattr(gates.subprocess, "run", execute)
    monkeypatch.setattr("sys.argv", ["check_all.py", "--controlled-browser", "--json-report", str(report)])
    assert gates.main() == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["mode"] == "controlled-browser"
    assert payload["gates"][0]["name"] == "controlled browser regression"
    assert "check_all=controlled-browser" in capsys.readouterr().out


def test_smoke_cli_returns_nonzero_for_failed_http_adapter() -> None:
    source = """
import runpy
import sys
from io import BytesIO
from urllib import request
from urllib.error import HTTPError
def unavailable(req, **kwargs):
    raise HTTPError(req.full_url, 503, 'Unavailable', {}, BytesIO(b'{"ok":false}'))
request.urlopen = unavailable
sys.argv = ['smoke_test_real_services.py']
runpy.run_path('scripts/smoke_test_real_services.py', run_name='__main__')
"""
    completed = subprocess.run([sys.executable, "-c", source], cwd=gates.ROOT, capture_output=True, text=True, timeout=10)
    assert completed.returncode == 1
    assert "real_services_status=failed mode=preflight provider_probes=not_run" in completed.stdout


def test_controlled_browser_failure_keeps_logs_and_shows_bounded_redacted_errors(monkeypatch, tmp_path, capsys) -> None:
    from scripts import run_controlled_browser as controlled

    run_pytest = subprocess.run
    frontend = tmp_path / "frontend"
    for filename in ("e2e/workbench-retry.spec.ts", "node_modules/next/dist/bin/next", "node_modules/@playwright/test/cli.js"):
        target = frontend / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture", encoding="utf-8")

    class LoggingProcess:
        pid = 900099

        def __init__(self, command, **kwargs):
            self.is_browser = "test" in command
            self.returncode = None
            output = kwargs.get("stdout")
            if output is not None:
                assert output != subprocess.PIPE, "Logs must drain directly to files, not wait-bound pipes."
                if self.is_browser:
                    output.write(("old-noisy-log-line\n" * 1000 +
                                  "Error: expected draft recovery to preserve the question\n"
                                  "fixture-sensitive-value\n4 failed\n3 passed\n").encode("utf-8"))
                else:
                    output.write(b"Next ready on the isolated loopback port\n")
                output.flush()

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            self.returncode = 1 if self.is_browser else 0
            return self.returncode

        def stop(self):
            self.returncode = 0

    monkeypatch.setattr(controlled, "ROOT", tmp_path)
    monkeypatch.setattr(controlled, "FRONTEND", frontend)
    monkeypatch.setattr(controlled, "launch_owned", LoggingProcess)
    monkeypatch.setattr(controlled.subprocess, "run", lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "", ""))
    monkeypatch.setattr(controlled.os, "killpg", lambda *_args: None, raising=False)
    monkeypatch.setattr(controlled, "urlopen", lambda *_args, **_kwargs: HttpReply({}))
    monkeypatch.setenv("CONTROLLED_TEST_SECRET", "fixture-sensitive-value")
    report = tmp_path / "failed-browser.json"

    assert controlled.main(["--node", sys.executable, "--strict", "--spec", "workbench-retry.spec.ts",
                            "--json-report", str(report)]) == 1
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert Path(evidence["frontend_log"]).is_file()
    assert Path(evidence["browser_log"]).is_file()
    assert Path(evidence["browser_log"]).parent == Path(evidence["frontend_log"]).parent
    output = capsys.readouterr().out
    assert "expected draft recovery to preserve the question" in output
    assert "4 failed" in output and "3 passed" in output
    assert "fixture-sensitive-value" not in output
    assert "[REDACTED]" in output
    assert len(output) < 12_000

    # Run the same basetemp deletion a subsequent standard pytest invocation
    # performs, but only inside this test's isolated project directory.
    later_test = tmp_path / "test_later.py"
    later_test.write_text("def test_later(tmp_path):\n    assert tmp_path.is_dir()\n", encoding="utf-8")
    later_config = tmp_path / "pytest.ini"
    later_config.write_text("[pytest]\naddopts = --basetemp=.pytest_tmp\n", encoding="utf-8")
    wiped = tmp_path / ".pytest_tmp" / "old-pytest-marker"
    wiped.parent.mkdir(exist_ok=True)
    wiped.write_text("old test data", encoding="utf-8")
    result = run_pytest(
        [sys.executable, "-m", "pytest", "-c", str(later_config), str(later_test), "-q"],
        cwd=tmp_path, capture_output=True, text=True, timeout=15,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not wiped.exists(), "The simulated later pytest run must really clear its basetemp."
    assert Path(evidence["browser_log"]).is_file(), "Retained browser evidence was deleted by pytest."
    assert Path(evidence["frontend_log"]).is_file()


@pytest.mark.parametrize("reconfigurable", [True, False])
def test_controlled_browser_gbk_console_preserves_failed_status_and_json_report(monkeypatch, tmp_path, reconfigurable) -> None:
    from scripts import run_controlled_browser as controlled

    frontend = tmp_path / "frontend"
    for filename in ("e2e/workbench-retry.spec.ts", "node_modules/next/dist/bin/next", "node_modules/@playwright/test/cli.js"):
        target = frontend / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture", encoding="utf-8")

    class LoggingProcess:
        pid = 900199

        def __init__(self, command, **kwargs):
            self.is_browser = "test" in command
            self.returncode = None
            log = "✓ frontend ready\n" if not self.is_browser else "✓ 19 passed\nError: saved source is unchecked\n1 failed\n"
            kwargs["stdout"].write(log.encode("utf-8"))
            kwargs["stdout"].flush()

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            self.returncode = 1 if self.is_browser else 0
            return self.returncode

        def stop(self):
            self.returncode = 0

    console_bytes = BytesIO()
    gbk_console = TextIOWrapper(console_bytes, encoding="gbk", errors="strict")

    class FixedEncodingConsole:
        encoding = "gbk"

        def write(self, value):
            return gbk_console.write(value)

        def flush(self):
            return gbk_console.flush()

    monkeypatch.setattr(sys, "stdout", gbk_console if reconfigurable else FixedEncodingConsole())
    monkeypatch.setattr(controlled, "ROOT", tmp_path)
    monkeypatch.setattr(controlled, "FRONTEND", frontend)
    monkeypatch.setattr(controlled, "launch_owned", LoggingProcess)
    monkeypatch.setattr(controlled.subprocess, "run", lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "", ""))
    monkeypatch.setattr(controlled.os, "killpg", lambda *_args: None, raising=False)
    monkeypatch.setattr(controlled, "urlopen", lambda *_args, **_kwargs: HttpReply({}))
    report = tmp_path / "gbk-console.json"

    assert controlled.main(["--node", sys.executable, "--strict", "--spec", "workbench-retry.spec.ts",
                            "--json-report", str(report)]) == 1
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["status"] == "failed"
    assert evidence["exit_code"] == 1
    assert evidence["boundary"] == "browser_tests"
    assert "✓ 19 passed" in Path(evidence["browser_log"]).read_text(encoding="utf-8")
    gbk_console.flush()
    output = console_bytes.getvalue().decode(gbk_console.encoding)
    assert "controlled_browser_status=failed" in output
    assert "controlled_browser_report=" in output
    assert "Error: saved source is unchecked" in output
    assert "19 passed" in output and "1 failed" in output


@pytest.mark.parametrize("reconfigurable", [True, False])
@pytest.mark.parametrize("outcome", ["passed", "failed_exit", "failed_marker", "skipped", "strict_skipped"])
def test_total_check_gbk_console_preserves_browser_verdict_in_json(monkeypatch, tmp_path, reconfigurable, outcome) -> None:
    strict = outcome == "strict_skipped"
    expected_gate = "failed" if outcome.startswith("failed") or strict else outcome
    expected_status = "failed" if expected_gate == "failed" else "passed"
    expected_exit = 1 if expected_gate == "failed" else 0
    marker = "controlled_browser_status" if strict else "demo_e2e_status"
    child_status = "skipped" if strict else "failed" if outcome.startswith("failed") else outcome
    child_output = f"✓ browser diagnostic\n{marker}={child_status} reason=CONTROLLED_FIXTURE\n"

    def execute(command, **_kwargs):
        if "scripts/run_demo_e2e.py" in command or "scripts/run_controlled_browser.py" in command:
            if outcome == "failed_exit":
                raise subprocess.CalledProcessError(1, command, output=child_output)
            return subprocess.CompletedProcess(command, 0, child_output, "")
        return subprocess.CompletedProcess(command, 0, "", "")

    console_bytes = BytesIO()
    gbk_console = TextIOWrapper(console_bytes, encoding="gbk", errors="strict")

    class FixedEncodingConsole:
        encoding = "gbk"

        def write(self, value):
            return gbk_console.write(value)

        def flush(self):
            return gbk_console.flush()

    report = tmp_path / "browser-gbk.json"
    monkeypatch.setattr(sys, "stdout", gbk_console if reconfigurable else FixedEncodingConsole())
    monkeypatch.setattr(gates.subprocess, "run", execute)
    monkeypatch.setattr(sys, "argv", ["check_all.py", "--controlled-browser" if strict else "--e2e", "--json-report", str(report)])
    # The running parent's output must be safe without a startup-env workaround.
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)

    assert gates.main() == expected_exit
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["status"] == expected_status
    assert evidence["gate_count"] >= 1
    browser_gate = next(gate for gate in evidence["gates"] if "browser" in gate["name"])
    assert browser_gate["status"] == expected_gate
    assert evidence["skipped_gate_count"] == (1 if expected_gate == "skipped" else 0)
    gbk_console.flush()
    output = console_bytes.getvalue().decode(gbk_console.encoding)
    assert "browser diagnostic" in output
    assert f"result={expected_status}" in output
    assert f"status={expected_gate}" in output
