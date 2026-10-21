from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from scripts import run_controlled_browser as controlled


CHILD = """
import json, os, pathlib, socket, sys, time
ready, finish = map(pathlib.Path, sys.argv[1:])
with socket.socket() as server:
    server.bind(('127.0.0.1', 0))
    server.listen()
    server.settimeout(0.02)
    ready.write_text(json.dumps({'port': server.getsockname()[1], 'pid': os.getpid()}))
    deadline = time.monotonic() + 20
    while not finish.exists() and time.monotonic() < deadline:
        try:
            connection, _ = server.accept()
            connection.close()
        except socket.timeout:
            pass
"""
PARENT = """
import pathlib, subprocess, sys, time
child, ready, finish, mode = sys.argv[1:]
subprocess.Popen([sys.executable, '-c', child, ready, finish], stdin=subprocess.DEVNULL)
deadline = time.monotonic() + 5
while not pathlib.Path(ready).exists() and time.monotonic() < deadline:
    time.sleep(0.01)
if mode == 'timeout':
    time.sleep(20)
sys.exit(7 if mode == 'failure' else 0)
"""


def wait_ready(path: Path) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.02)
    pytest.fail(f"Child did not publish its listening socket: {path}")


def listening(port: int) -> bool:
    with socket.socket() as client:
        client.settimeout(0.1)
        return client.connect_ex(("127.0.0.1", port)) == 0


@pytest.mark.parametrize("mode", ["parent_first", "failure", "timeout"])
def test_owned_cleanup_reaps_descendants_after_parent_exit_or_timeout_without_touching_unrelated_processes(tmp_path, mode):
    ready, finish = tmp_path / "owned.json", tmp_path / "finish-owned"
    other_ready, other_finish = tmp_path / "other.json", tmp_path / "finish-other"
    unrelated = subprocess.Popen(
        [sys.executable, "-c", CHILD, str(other_ready), str(other_finish)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}),
    )
    owned = None
    try:
        other = wait_ready(other_ready)
        owned = controlled.start_owned(
            [sys.executable, "-c", PARENT, CHILD, str(ready), str(finish), mode],
            dict(os.environ), tmp_path / "owned.log",
        )
        child = wait_ready(ready)
        if mode == "timeout":
            with pytest.raises(subprocess.TimeoutExpired):
                owned.wait(timeout=0.05)
        else:
            assert owned.wait(timeout=5) == (7 if mode == "failure" else 0)
        assert listening(child["port"]), "The descendant must still be live when cleanup begins."
        controlled.stop_owned(owned)
        deadline = time.monotonic() + 2
        while listening(child["port"]) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not listening(child["port"]), "An owned child survived after the parent exited."
        assert unrelated.poll() is None and listening(other["port"])
    finally:
        # Cooperative shutdown plus bounded lifetimes also clean the red case,
        # where the runner under test cannot yet reap its orphaned descendant.
        finish.touch()
        other_finish.touch()
        if owned is not None:
            controlled.stop_owned(owned)
        unrelated.wait(timeout=5)
        if ready.exists():
            child = json.loads(ready.read_text())
            deadline = time.monotonic() + 5
            while listening(child["port"]) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not listening(child["port"]), "Test fixture failed to clean up its child."


@pytest.mark.parametrize("channel", ["chrome", None])
@pytest.mark.parametrize("available", [True, False])
def test_browser_channel_is_launched_and_closed_before_frontend_start(monkeypatch, tmp_path, channel, available):
    node = controlled.existing_node(None)
    assert node is not None, "This executable browser adapter regression requires the existing Node runtime."
    frontend = tmp_path / "frontend"
    module = frontend / "node_modules/@playwright/test"
    module.mkdir(parents=True)
    next_cli = frontend / "node_modules/next/dist/bin/next"
    next_cli.parent.mkdir(parents=True)
    next_cli.write_text("require('node:fs').writeFileSync('frontend-started', 'yes'); setInterval(() => {}, 1000);", encoding="utf-8")
    expected = channel or ""
    module.joinpath("index.js").write_text(
        "const fs=require('node:fs'); exports.chromium={"
        "executablePath:()=>process.execPath,"
        "launch:async options=>{"
        f"if((options.channel || '') !== {json.dumps(expected)}) throw Error('wrong channel');"
        "fs.writeFileSync('browser-launched', 'yes');"
        + ("throw Error('browser cannot execute');" if not available else "")
        + "return {close:async()=>fs.writeFileSync('browser-closed', 'yes')};}};",
        encoding="utf-8",
    )
    module.joinpath("cli.js").write_text(
        "const fs=require('node:fs');"
        "if(!fs.existsSync('browser-closed')) process.exit(8);"
        f"if(process.env.E2E_BROWSER_CHANNEL !== {json.dumps(expected)}) process.exit(9);",
        encoding="utf-8",
    )
    specs = frontend / "e2e"
    specs.mkdir()
    specs.joinpath("workbench-retry.spec.ts").write_text("// Controlled fixture", encoding="utf-8")
    monkeypatch.setattr(controlled, "ROOT", tmp_path)
    monkeypatch.setattr(controlled, "FRONTEND", frontend)
    monkeypatch.setenv("E2E_BROWSER_CHANNEL", "msedge")

    class Ready:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(controlled, "urlopen", lambda *_args, **_kwargs: Ready())
    report = tmp_path / "report.json"
    args = ["--node", str(node), "--strict", "--spec", "workbench-retry.spec.ts", "--json-report", str(report)]
    if channel:
        args += ["--browser-channel", channel]
    assert controlled.main(args) == (0 if available else 1)
    result = json.loads(report.read_text(encoding="utf-8"))
    assert frontend.joinpath("browser-launched").is_file(), "Checking executable existence is not an executable preflight."
    assert result["browser_channel"] == (channel or "chromium")
    if available:
        assert frontend.joinpath("browser-closed").is_file()
        assert result["status"] == "passed"
    else:
        assert not frontend.joinpath("frontend-started").exists()
        assert result["status"] == "failed"
        assert result["boundary"] == ("CHROME_NOT_AVAILABLE" if channel else "CHROMIUM_NOT_AVAILABLE")
