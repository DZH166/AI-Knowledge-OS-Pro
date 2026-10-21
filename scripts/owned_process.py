"""Start a command inside an owned process tree before it can spawn children."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import BinaryIO


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits), ("IoInfo", ctypes.c_uint64 * 6),
        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _Accounting(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
        ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
        ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD),
    ]


class _WindowsJob:
    def __init__(self) -> None:
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            "QueryInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
            "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimits()
        # KILL_ON_JOB_CLOSE, without either breakaway flag. The handle is not
        # inheritable, so an abruptly terminated runner also reaps its children.
        limits.BasicLimitInformation.LimitFlags = 0x2000
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process: subprocess.Popen) -> None:
        # CPython retains the CreateProcess handle for this exact child. Keep
        # assignment tied to that handle even if startup exits unexpectedly;
        # reopening by PID could identify a reused process instead.
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def terminate(self, timeout: float = 5) -> None:
        if not self.api.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        deadline = time.monotonic() + timeout
        while True:
            accounting = _Accounting()
            if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if accounting.ActiveProcesses == 0:
                return
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired("owned Windows job cleanup", timeout)
            time.sleep(0.02)

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def _require_posix_ownership() -> None:
    required = ("P_PID", "WEXITED", "WNOWAIT", "WNOHANG", "CLD_EXITED", "CLD_KILLED", "CLD_DUMPED")
    if (any(not hasattr(os, name) for name in required)
            or not callable(getattr(os, "waitid", None))
            or not callable(getattr(os, "killpg", None))):
        raise OSError("posix_owned_process_not_supported: waitid WNOWAIT and killpg are required")
    if not hasattr(signal, "SIGCHLD") or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        raise OSError("posix_owned_process_requires_default_sigchld")


class OwnedProcess:
    """Single-owner lifecycle; do not reap its Popen or install another reaper.

    POSIX requires default SIGCHLD handling throughout ownership. Native code
    changing sigaction/SA_NOCLDWAIT or another thread calling waitpid is outside
    this boundary; Python cannot introspect those native flags portably.
    """
    def __init__(self, process: subprocess.Popen, job: _WindowsJob | None = None):
        self.process = process
        self.job = job
        self.pid = process.pid
        self.closed = False
        self._exit_code: int | None = None
        self._ownership_lost = False

    def poll(self) -> int | None:
        if self.job is not None:
            return self.process.poll()
        if self.closed:
            return self._exit_code
        if self._ownership_lost or self.process.returncode is not None:
            self._ownership_lost = True
            raise OSError("posix_process_ownership_lost")
        try:
            _require_posix_ownership()
            result = os.waitid(os.P_PID, self.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        except OSError as exc:
            self._ownership_lost = True
            raise OSError("posix_process_ownership_lost") from exc
        if result is not None:
            if result.si_pid != self.pid or result.si_code not in (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED):
                self._ownership_lost = True
                raise OSError("posix_process_ownership_lost")
            self._exit_code = result.si_status if result.si_code == os.CLD_EXITED else -result.si_status
        return self._exit_code

    def wait(self, timeout: float | None = None) -> int:
        if self.job is not None:
            return self.process.wait(timeout=timeout)
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            exit_code = self.poll()
            if exit_code is not None:
                return exit_code
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise subprocess.TimeoutExpired(self.process.args, timeout)
            time.sleep(0.02 if remaining is None else min(0.02, remaining))

    def stop(self) -> None:
        if self.closed:
            return
        if self.job is not None:
            try:
                # Job membership survives the launcher and target parent exits.
                self.job.terminate()
                self.process.wait(timeout=5)
            finally:
                self.job.close()
                self.closed = True
        else:
            # Only observe here: reaping the leader would allow the numeric
            # process-group identity to be reused before the last signal.
            self.poll()
            try:
                os.killpg(self.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            self.poll()
            try:
                os.killpg(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self._exit_code = self.process.wait(timeout=5)
            self.closed = True


def launch_owned(command: list[str], *, cwd: Path, env: dict[str, str], stdout: BinaryIO) -> OwnedProcess:
    if os.name != "nt":
        _require_posix_ownership()
        return OwnedProcess(subprocess.Popen(
            command, cwd=cwd, env=env, stdout=stdout, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True,
        ))
    job = _WindowsJob()
    process = None
    try:
        # This isolated stdlib launcher blocks on stdin before executing command.
        # Never open the gate until AssignProcessToJobObject has succeeded.
        process = subprocess.Popen(
            [sys.executable, "-I", "-S", str(Path(__file__).resolve()), *command],
            cwd=cwd, env=env, stdout=stdout, stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        job.assign(process)
        process.stdin.write(b"1")
        process.stdin.flush()
        process.stdin.close()
        return OwnedProcess(process, job)
    except BaseException:
        # Before assignment the launcher cannot run command. After assignment,
        # closing the job reaps the entire tree, including a just-released target.
        job.close()
        if process is not None:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        raise


if __name__ == "__main__":
    if sys.stdin.buffer.read(1) != b"1":
        raise SystemExit(1)
    child = subprocess.Popen(sys.argv[1:], stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    raise SystemExit(child.wait())
