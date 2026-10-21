from __future__ import annotations

from enum import StrEnum

from app.modules.evidence_agent.contracts import RunStatus


class RunSignal(StrEnum):
    DISPATCH = "dispatch"
    SELECT_QUICK = "select_quick"
    SELECT_AGENT = "select_agent"
    EXECUTE = "execute"
    NEED_INPUT = "need_input"
    PROVIDE_INPUT = "provide_input"
    NEED_APPROVAL = "need_approval"
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    PAUSE = "pause"
    RESUME = "resume"
    COMPLETE = "complete"
    INSUFFICIENT = "insufficient"
    FAIL = "fail"
    CANCEL = "cancel"


class InvalidRunTransition(ValueError):
    def __init__(self, status: RunStatus, signal: RunSignal) -> None:
        super().__init__(f"Run in '{status.value}' cannot accept '{signal.value}'.")
        self.status = status
        self.signal = signal


_TRANSITIONS: dict[tuple[RunStatus, RunSignal], RunStatus] = {
    (RunStatus.QUEUED, RunSignal.DISPATCH): RunStatus.ROUTING,
    (RunStatus.ROUTING, RunSignal.SELECT_QUICK): RunStatus.RUNNING,
    (RunStatus.ROUTING, RunSignal.SELECT_AGENT): RunStatus.PLANNED,
    (RunStatus.PLANNED, RunSignal.EXECUTE): RunStatus.RUNNING,
    (RunStatus.RUNNING, RunSignal.NEED_INPUT): RunStatus.AWAITING_INPUT,
    (RunStatus.AWAITING_INPUT, RunSignal.PROVIDE_INPUT): RunStatus.QUEUED,
    (RunStatus.RUNNING, RunSignal.NEED_APPROVAL): RunStatus.AWAITING_APPROVAL,
    (RunStatus.AWAITING_APPROVAL, RunSignal.APPROVE): RunStatus.QUEUED,
    (RunStatus.AWAITING_APPROVAL, RunSignal.REJECT): RunStatus.INSUFFICIENT_EVIDENCE,
    (RunStatus.AWAITING_APPROVAL, RunSignal.MODIFY): RunStatus.AWAITING_APPROVAL,
    (RunStatus.RUNNING, RunSignal.PAUSE): RunStatus.PAUSED,
    (RunStatus.PAUSED, RunSignal.RESUME): RunStatus.QUEUED,
    (RunStatus.RUNNING, RunSignal.COMPLETE): RunStatus.COMPLETED,
    (RunStatus.RUNNING, RunSignal.INSUFFICIENT): RunStatus.INSUFFICIENT_EVIDENCE,
}

_CANCELLABLE = {
    RunStatus.QUEUED,
    RunStatus.ROUTING,
    RunStatus.PLANNED,
    RunStatus.RUNNING,
    RunStatus.AWAITING_INPUT,
    RunStatus.AWAITING_APPROVAL,
    RunStatus.PAUSED,
}

_FAILABLE = {
    RunStatus.QUEUED,
    RunStatus.ROUTING,
    RunStatus.PLANNED,
    RunStatus.RUNNING,
}


def transition_run(status: RunStatus, signal: RunSignal) -> RunStatus:
    if signal is RunSignal.CANCEL and status in _CANCELLABLE:
        return RunStatus.CANCELLED
    if signal is RunSignal.FAIL and status in _FAILABLE:
        return RunStatus.FAILED
    try:
        return _TRANSITIONS[(status, signal)]
    except KeyError as exc:
        raise InvalidRunTransition(status, signal) from exc
