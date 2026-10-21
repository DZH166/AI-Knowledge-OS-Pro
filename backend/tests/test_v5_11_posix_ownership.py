from __future__ import annotations

import errno
from io import BytesIO
import os
import signal
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import owned_process as runtime


class PosixSystem:
    """OS boundary fixture: reaping immediately releases the simulated PGID."""

    def __init__(self, monkeypatch, *, exit_code=7):
        self.pid = 40001
        self.exit_code = exit_code
        self.owned = True
        self.events = []
        self.now = 0.0
        self.sigchld = 0
        self.os = SimpleNamespace(
            name="posix", P_PID=1, WEXITED=4, WNOWAIT=0x100, WNOHANG=1,
            CLD_EXITED=1, CLD_KILLED=2, CLD_DUMPED=3,
            waitid=self.waitid, killpg=self.killpg,
        )
        monkeypatch.setattr(runtime, "os", self.os)
        monkeypatch.setattr(runtime, "signal", SimpleNamespace(
            SIGCHLD=17, SIG_DFL=0, SIG_IGN=1, SIGTERM=15, SIGKILL=9,
            getsignal=lambda _sig: self.sigchld,
        ))
        monkeypatch.setattr(runtime, "time", SimpleNamespace(
            monotonic=lambda: self.now, sleep=self.sleep,
        ))

        system = self

        class Process:
            pid = system.pid
            args = ["fixture"]
            returncode = None

            def poll(self):
                if system.exit_code is not None:
                    return self.wait()
                return None

            def wait(self, timeout=None):
                if system.exit_code is None:
                    raise subprocess.TimeoutExpired(self.args, timeout)
                if self.returncode is None:
                    system.events.append("reap")
                    system.owned = False
                    self.returncode = system.exit_code
                return self.returncode

        self.process = Process()

    def sleep(self, duration):
        self.now += duration

    def waitid(self, idtype, pid, flags):
        assert idtype == self.os.P_PID and pid == self.pid
        assert flags & self.os.WNOWAIT, "Observation consumed the child identity."
        self.events.append("observe")
        if not self.owned:
            raise ChildProcessError(errno.ECHILD, "Child was reaped externally")
        if self.exit_code is None:
            return None
        return SimpleNamespace(
            si_pid=self.pid,
            si_code=self.os.CLD_EXITED if self.exit_code >= 0 else self.os.CLD_KILLED,
            si_status=abs(self.exit_code),
        )

    def killpg(self, pid, sig):
        assert pid == self.pid
        self.events.append(("signal", sig, self.owned))
        if self.exit_code is None:
            self.exit_code = -sig


@pytest.mark.parametrize("observation", ["poll", "wait"])
@pytest.mark.parametrize("exit_code", [0, 7, -9])
def test_posix_observation_keeps_identity_until_all_group_signals_are_sent(monkeypatch, observation, exit_code):
    system = PosixSystem(monkeypatch, exit_code=exit_code)
    owned = runtime.OwnedProcess(system.process)
    assert getattr(owned, observation)() == exit_code
    assert system.owned, "Public observation reaped the leader and released its process-group identity."
    owned.stop()
    signals = [event for event in system.events if isinstance(event, tuple)]
    assert signals == [("signal", 15, True), ("signal", 9, True)]
    assert system.events[-1] == "reap"
    assert owned.poll() == exit_code and owned.wait(timeout=0) == exit_code


@pytest.mark.parametrize("loss_at", ["before_stop", "after_cached_exit", "after_sigterm"])
def test_posix_lost_ownership_never_signals_a_reused_group_even_on_retry(monkeypatch, loss_at):
    system = PosixSystem(monkeypatch)
    owned = runtime.OwnedProcess(system.process)
    if loss_at == "after_cached_exit":
        assert owned.wait(timeout=0) == 7
    if loss_at == "after_sigterm":
        signal_group = system.os.killpg

        def external_reap_after_sigterm(pid, sig):
            signal_group(pid, sig)
            system.owned = False

        system.os.killpg = external_reap_after_sigterm
    else:
        system.owned = False
    with pytest.raises(OSError):
        owned.stop()
    signals_before_retry = [event for event in system.events if isinstance(event, tuple)]
    assert signals_before_retry == ([("signal", 15, True)] if loss_at == "after_sigterm" else [])

    # A newly-created child could later receive the same numeric PID/PGID.
    system.owned = True
    for operation in (owned.poll, owned.wait, owned.stop, owned.stop):
        with pytest.raises(OSError, match="posix_process_ownership_lost"):
            operation()
    assert [event for event in system.events if isinstance(event, tuple)] == signals_before_retry
    assert "reap" not in system.events


@pytest.mark.parametrize("unsupported", ["waitid", "WNOWAIT", "SIGCHLD", "ignored", "handler"])
def test_posix_launch_rejects_unsupported_ownership_before_spawning(monkeypatch, tmp_path, unsupported):
    system = PosixSystem(monkeypatch)
    if unsupported in ("waitid", "WNOWAIT"):
        delattr(system.os, unsupported)
    elif unsupported == "SIGCHLD":
        delattr(runtime.signal, "SIGCHLD")
    else:
        system.sigchld = 1 if unsupported == "ignored" else lambda *_args: None
    starts = []

    def spawn(*args, **kwargs):
        starts.append((args, kwargs))
        return system.process

    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)
    with pytest.raises(OSError, match="posix_owned_process"):
        runtime.launch_owned(["fixture"], cwd=tmp_path, env={}, stdout=BytesIO())
    assert starts == [], "Unsupported ownership must be rejected before executing the target."


def test_posix_sigchld_handler_change_invalidates_ownership_before_signaling(monkeypatch):
    system = PosixSystem(monkeypatch)
    owned = runtime.OwnedProcess(system.process)
    assert owned.poll() == 7
    system.sigchld = 1
    with pytest.raises(OSError, match="posix_process_ownership_lost"):
        owned.stop()
    system.sigchld = 0
    with pytest.raises(OSError, match="posix_process_ownership_lost"):
        owned.stop()
    assert not [event for event in system.events if isinstance(event, tuple)]


def test_posix_timeout_escalation_keeps_identity_and_stop_is_idempotent(monkeypatch):
    system = PosixSystem(monkeypatch, exit_code=None)
    owned = runtime.OwnedProcess(system.process)
    signal_group = system.os.killpg

    def ignore_sigterm(pid, sig):
        signal_group(pid, sig)
        if sig == 15:
            system.exit_code = None

    system.os.killpg = ignore_sigterm
    with pytest.raises(subprocess.TimeoutExpired):
        owned.wait(timeout=0.05)
    assert system.owned and system.now == pytest.approx(0.05)
    owned.stop()
    assert system.now == pytest.approx(5.05)
    assert [event for event in system.events if isinstance(event, tuple)] == [
        ("signal", 15, True), ("signal", 9, True),
    ]
    assert system.events[-1] == "reap"
    events = list(system.events)
    system.owned = True  # Numeric identity has now been reused.
    owned.stop()
    owned.stop()
    assert owned.poll() == -9 and owned.wait(timeout=0) == -9
    assert system.events == events


def test_posix_successful_launch_uses_a_separate_session(monkeypatch, tmp_path):
    system = PosixSystem(monkeypatch)
    starts = []

    def spawn(command, **kwargs):
        starts.append((command, kwargs))
        return system.process

    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)
    owned = runtime.launch_owned(["fixture"], cwd=tmp_path, env={}, stdout=BytesIO())
    assert len(starts) == 1 and starts[0][1]["start_new_session"] is True
    assert owned.wait(timeout=0) == 7 and system.owned
    owned.stop()


@pytest.mark.skipif(sys.platform != "linux", reason="Requires a real Linux waitid/zombie lifecycle; OS-adapter tests are separate.")
def test_linux_public_wait_preserves_zombie_until_group_cleanup(tmp_path):
    assert signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL
    with (tmp_path / "linux.log").open("wb") as output:
        owned = runtime.launch_owned(
            [sys.executable, "-c", "raise SystemExit(7)"], cwd=tmp_path,
            env=dict(os.environ), stdout=output,
        )
    try:
        assert owned.wait(timeout=5) == 7
        for _ in range(3):
            assert owned.poll() == 7
            status = os.waitid(os.P_PID, owned.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
            assert status is not None and status.si_pid == owned.pid and status.si_status == 7
            assert os.getpgid(owned.pid) == owned.pid
        owned.stop()
        with pytest.raises(ChildProcessError):
            os.waitid(os.P_PID, owned.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        owned.stop()
        assert owned.wait(timeout=0) == 7
    finally:
        owned.stop()


@pytest.mark.skipif(sys.platform != "linux", reason="Requires a real Linux external-reaper lifecycle; OS-adapter tests are separate.")
def test_linux_external_reaper_prevents_any_further_group_signals(tmp_path, monkeypatch):
    with (tmp_path / "external-reaper.log").open("wb") as output:
        owned = runtime.launch_owned(
            [sys.executable, "-c", "raise SystemExit(0)"], cwd=tmp_path,
            env=dict(os.environ), stdout=output,
        )
    try:
        assert owned.wait(timeout=5) == 0
    except BaseException:
        owned.stop()
        raise
    assert os.waitpid(owned.pid, 0)[0] == owned.pid

    def forbidden_signal(*_args):
        pytest.fail("The kernel reported this child reaped; its numeric group ID is no longer owned.")

    monkeypatch.setattr(runtime.os, "killpg", forbidden_signal)
    for operation in (owned.stop, owned.stop, owned.poll):
        with pytest.raises(OSError, match="posix_process_ownership_lost"):
            operation()
