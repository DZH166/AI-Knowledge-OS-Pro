from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from tempfile import mkdtemp
import time
from urllib.error import URLError
from urllib.request import urlopen

if __package__:
    from .owned_process import OwnedProcess, launch_owned
else:
    from owned_process import OwnedProcess, launch_owned


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ALLOWED_SPECS = (
    "workbench-retry.spec.ts",
    "v5-9-research-journey.spec.ts",
    "v5-10-research-recovery.spec.ts",
    "v5-11-artifact-upload.spec.ts",
    "v5-11-connection-recovery.spec.ts",
)


class BrowserBoundaryError(RuntimeError):
    def __init__(self, boundary: str, *, missing_runtime: bool = False):
        super().__init__(boundary)
        self.missing_runtime = missing_runtime


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def print_console(message: str) -> None:
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        # Some embedded consoles cannot be reconfigured. Keep their diagnostics
        # ASCII-safe without letting display failures interrupt durable evidence.
        try:
            print(message.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except (UnicodeError, OSError, ValueError):
            pass
    except (OSError, ValueError):
        pass


def existing_node(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit.resolve() if explicit.is_file() else None
    available = shutil.which("node")
    if available:
        return Path(available)
    bundled = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node"
    return next((path for path in (bundled / "bin" / "node.exe", bundled / "bin" / "node", bundled / "node.exe", bundled / "node") if path.is_file()), None)


def start_owned(command: list[str], env: dict[str, str], log_path: Path) -> OwnedProcess:
    # A regular file drains both streams even while the parent waits for exit.
    # The child inherits its own handle; the parent's handle can close after spawn.
    with log_path.open("wb") as output:
        return launch_owned(command, cwd=FRONTEND, env=env, stdout=output)


def print_log_tail(label: str, path: Path) -> None:
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - 8192))
            tail = stream.read(8192).decode("utf-8", errors="replace")
        if size > 8192:
            # Do not display a partial line, which could contain a cut-off secret.
            tail = tail.partition("\n")[2]
        tail = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", tail)
        secrets = {
            value for key, value in os.environ.items()
            if value and re.search(r"(?i)key|secret|token|password|credential", key)
        }
        for value in sorted(secrets, key=len, reverse=True):
            tail = tail.replace(value, "[REDACTED]")
        tail = re.sub(
            r"(?i)\b(api[_-]?key|secret|token|password)(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,}]+)",
            r"\1\2[REDACTED]", tail,
        )
        tail = "\n".join(tail.splitlines()[-80:])[-4000:]
    except OSError:
        tail = "Log could not be read; inspect the retained log path."
    print_console(f"controlled_log_tail={label} path={path} max_bytes=8192 max_chars=4000")
    for line in tail.splitlines():
        print_console(f"[{label}] {line}")


def stop_owned(process: OwnedProcess) -> None:
    process.stop()
    print_console(f"controlled_cleanup=owned_process pid={process.pid}")


def wait_frontend(origin: str, process: OwnedProcess, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise BrowserBoundaryError("frontend_exited_before_ready")
        try:
            with urlopen(f"{origin}/workbench", timeout=min(3, max(0.01, deadline - time.monotonic()))) as response:
                if response.status == 200:
                    return
        except (URLError, OSError):
            pass
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))
    raise BrowserBoundaryError("frontend_startup_timeout")


def main(argv: list[str] | None = None) -> int:
    configure_console()
    parser = argparse.ArgumentParser(description="Run controlled browser regression without Docker or provider calls.")
    parser.add_argument("--node", type=Path, help="Existing Node executable; never downloads runtimes.")
    parser.add_argument("--strict", action="store_true", help="Fail when browser prerequisites are missing.")
    parser.add_argument("--browser-channel", choices=("chrome", "msedge"), help="Use an already installed browser channel; default is bundled Chromium. Never downloads a browser.")
    parser.add_argument("--spec", action="append", choices=ALLOWED_SPECS, help="Select an allowed controlled spec; defaults to all allowed specs.")
    parser.add_argument("--port", type=int, default=0, help="Unused loopback port; 0 allocates a fresh port.")
    parser.add_argument("--startup-timeout", type=float, default=120)
    parser.add_argument("--test-timeout", type=float, default=900, help="Bound the entire browser run in seconds (maximum 1800).")
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535 or not 0 < args.startup_timeout <= 120 or not 0 < args.test_timeout <= 1800:
        parser.error("Port must be 0-65535; startup timeout 0-120 and test timeout 0-1800, excluding zero.")
    specs = list(dict.fromkeys(args.spec or ALLOWED_SPECS))
    report: dict[str, object] = {
        "verification_mode": "controlled", "integration_services": "not_run",
        "real_providers": "not_run", "specs": specs, "status": "failed", "exit_code": 1,
        "browser_channel": args.browser_channel or "chromium",
        "preflight_log": None, "frontend_log": None, "browser_log": None,
    }
    print_console("verification_mode=controlled integration_services=not_run real_providers=not_run")
    owned: list[OwnedProcess] = []
    try:
        node = existing_node(args.node)
        if node is None:
            raise BrowserBoundaryError("NODE_NOT_AVAILABLE", missing_runtime=True)
        next_cli = FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next"
        playwright_cli = FRONTEND / "node_modules" / "@playwright" / "test" / "cli.js"
        if not next_cli.is_file() or not playwright_cli.is_file():
            raise BrowserBoundaryError("FRONTEND_BROWSER_DEPENDENCIES_NOT_AVAILABLE", missing_runtime=True)
        if any(not (FRONTEND / "e2e" / spec).is_file() for spec in specs):
            raise BrowserBoundaryError("CONTROLLED_SPEC_MISSING")
        log_root = ROOT / ".controlled_browser_logs"
        log_root.mkdir(parents=True, exist_ok=True)
        log_directory = Path(mkdtemp(prefix="controlled-browser-", dir=log_root))
        preflight_log = log_directory / "preflight.log"
        frontend_log = log_directory / "frontend.log"
        browser_log = log_directory / "browser.log"
        env = {
            **os.environ, "E2E_BROWSER_CHANNEL": args.browser_channel or "",
            "E2E_SKIP_WEBSERVER": "1", "E2E_TEST_TIMEOUT_MS": "60000", "E2E_WORKERS": "1",
            "NEXT_TELEMETRY_DISABLED": "1", "API_PROXY_TARGET": "",
        }
        report["boundary"] = "browser_preflight"
        report["preflight_log"] = str(preflight_log)
        probe = start_owned(
            [str(node), "-e", "const {chromium}=require('@playwright/test');"
             "chromium.launch({headless:true,channel:process.env.E2E_BROWSER_CHANNEL||undefined,timeout:10000})"
             ".then(browser=>browser.close()).catch(error=>{console.error(error);process.exitCode=1;});"],
            env, preflight_log,
        )
        owned.append(probe)
        probe_exit = probe.wait(timeout=15)
        stop_owned(probe)
        owned.remove(probe)
        if probe_exit != 0:
            raise BrowserBoundaryError(f"{(args.browser_channel or 'chromium').upper()}_NOT_AVAILABLE", missing_runtime=True)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(("127.0.0.1", args.port))
            port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        env = {**env, "NEXT_PUBLIC_API_BASE_URL": origin, "E2E_BASE_URL": origin}
        report["frontend_url"] = origin
        report["frontend_log"] = str(frontend_log)
        frontend = start_owned([str(node), str(next_cli), "dev", "--hostname", "127.0.0.1", "--port", str(port)], env, frontend_log)
        owned.append(frontend)
        wait_frontend(origin, frontend, args.startup_timeout)
        filters = [rf"(?:^|[\\/]){re.escape(spec)}$" for spec in specs]
        report["browser_log"] = str(browser_log)
        browser = start_owned(
            [str(node), str(playwright_cli), "test", "--config=playwright.config.ts", "--project=chromium", "--workers=1", "--retries=0", *filters],
            env, browser_log,
        )
        owned.append(browser)
        report["boundary"] = "browser_tests"
        exit_code = browser.wait(timeout=args.test_timeout)
        report.update(status="passed" if exit_code == 0 else "failed", exit_code=exit_code, boundary="browser_tests")
    except BrowserBoundaryError as exc:
        skipped = exc.missing_runtime and not args.strict
        report.update(status="skipped" if skipped else "failed", exit_code=0 if skipped else 1, boundary=str(exc))
    except subprocess.TimeoutExpired:
        report.update(status="failed", exit_code=1, boundary=f"{report.get('boundary', 'owned_process')}_timeout")
    except OSError:
        report.update(status="failed", exit_code=1, boundary="local_runtime_unavailable")
    except KeyboardInterrupt:
        report.update(status="failed", exit_code=130, boundary="interrupted")
    finally:
        for process in reversed(owned):
            try:
                stop_owned(process)
            except (BrowserBoundaryError, subprocess.TimeoutExpired, OSError):
                report.update(status="failed", exit_code=1, boundary="owned_process_tree_cleanup_failed")
        if args.json_report:
            args.json_report.parent.mkdir(parents=True, exist_ok=True)
            args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for label in ("preflight", "frontend", "browser"):
            log_path = report[f"{label}_log"]
            if isinstance(log_path, str):
                print_log_tail(label, Path(log_path))
        print_console(f"controlled_browser_status={report['status']} reason={report.get('boundary', 'unknown')} exit_code={report['exit_code']}")
        print_console(f"controlled_browser_report={json.dumps(report, ensure_ascii=False, sort_keys=True)}")
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
