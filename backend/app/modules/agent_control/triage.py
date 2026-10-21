from __future__ import annotations

from app.modules.agent_control.contracts import FailureCategory, FailureTriage
from app.modules.agent_control.sanitization import sanitize_fact


def triage_run_failure(
    *,
    status: str,
    termination_reason: str | None,
    tool_error_codes: tuple[str, ...] = (),
    dispatch_dead_letter: bool = False,
) -> FailureTriage:
    reason = (termination_reason or "").lower()
    if dispatch_dead_letter or "dispatch_dead_letter" in reason:
        return _triage(
            FailureCategory.DISPATCH_FAILED,
            "后台任务未能进入执行队列。",
            True,
            (_fact("termination_reason", termination_reason or "none"),),
            "检查 Redis/RQ 和 Outbox 后重新唤醒该 Run。",
        )
    if "worker_interrupted" in reason or "worker" in reason and "interrupt" in reason:
        return _triage(
            FailureCategory.WORKER_INTERRUPTED,
            "后台任务进程在完成当前步骤前中断。",
            True,
            (_fact("termination_reason", termination_reason or "none"),),
            "恢复 Worker 后从最近检查点继续。",
        )
    if "budget" in reason:
        return _triage(
            FailureCategory.BUDGET_EXHAUSTED,
            "Run 达到了预设执行预算。",
            False,
            (_fact("termination_reason", termination_reason or "none"),),
            "缩小研究范围，或由用户明确提高预算后创建续跑。",
        )
    if status == "insufficient_evidence" or "evidence" in reason and "insufficient" in reason:
        return _triage(
            FailureCategory.EVIDENCE_INSUFFICIENT,
            "现有固定证据不足以支持结论。",
            False,
            (_fact("status", status), _fact("termination_reason", termination_reason or "none")),
            "补充可信来源后，从 Evidence Gap Report 创建续跑。",
        )
    if status == "cancelled":
        return _triage(
            FailureCategory.USER_CANCELLED,
            "Run 由用户取消。",
            False,
            (_fact("status", "cancelled"),),
            "如果仍需研究，请创建新的 Run。",
        )
    if tool_error_codes:
        return _triage(
            FailureCategory.TOOL_FAILED,
            "至少一个工具调用失败。",
            True,
            tuple(_fact("tool_error", code) for code in sorted(set(tool_error_codes))),
            "检查失败工具的输入、权限与依赖后重试。",
        )
    if "provider" in reason or "model" in reason:
        return _triage(
            FailureCategory.PROVIDER_UNAVAILABLE,
            "模型提供方不可用或未配置。",
            True,
            (_fact("termination_reason", termination_reason or "none"),),
            "检查 Provider 配置；不要把未配置状态当作成功。",
        )
    if status == "failed":
        return _triage(
            FailureCategory.UNKNOWN,
            "Run 已失败，但现有事实不足以安全归类。",
            False,
            (_fact("termination_reason", termination_reason or "none"),),
            "查看已脱敏轨迹与后台日志后再决定是否重试。",
        )
    return _triage(
        FailureCategory.NONE,
        "当前 Run 没有需要归因的失败。",
        False,
        (_fact("status", status),),
        "无需处理。",
    )


def triage_evaluation_failure(
    *,
    status: str,
    error_code: str | None = None,
    hard_gate_failed: bool = False,
) -> FailureTriage:
    code = (error_code or "").upper()
    if code == "EVALUATION_DISPATCH_DEAD_LETTER":
        return _triage(
            FailureCategory.DISPATCH_FAILED,
            "评测任务未能进入后台队列。",
            True,
            (_fact("error_code", code),),
            "恢复 Redis/RQ 后创建一次新的评测快照。",
        )
    if code == "EVALUATION_WORKER_INTERRUPTED":
        return _triage(
            FailureCategory.WORKER_INTERRUPTED,
            "评测 Worker 在租约到期前中断。",
            True,
            (_fact("error_code", code),),
            "确认 Worker 稳定后重新运行固定评测。",
        )
    if code == "EVALUATION_TIMEOUT":
        return _triage(
            FailureCategory.EXECUTOR_TIMEOUT,
            "固定评测超过允许时间。",
            True,
            (_fact("error_code", code),),
            "检查本机负载与评测日志后重新运行。",
        )
    if code in {"EVALUATION_REPORT_INVALID", "EVALUATION_REPORT_DISHONEST"}:
        return _triage(
            FailureCategory.MALFORMED_REPORT,
            "评测报告结构或 Provider 边界不可信。",
            False,
            (_fact("error_code", code),),
            "修复评测器或报告校验，不要发布该快照。",
        )
    if hard_gate_failed or code == "EVALUATION_GATE_FAILED":
        return _triage(
            FailureCategory.EVALUATION_GATE_FAILED,
            "评测完成，但至少一个质量门禁失败。",
            False,
            ((_fact("error_code", code) if code else _fact("hard_gate_failed", True)),),
            "打开失败案例和指标差异，修复回退后再评测。",
        )
    if status == "failed":
        return _triage(
            FailureCategory.EXECUTOR_FAILED if code else FailureCategory.UNKNOWN,
            "评测执行失败。" if code else "评测失败但无法安全归类。",
            bool(code),
            ((_fact("error_code", code) if code else _fact("status", "failed")),),
            "检查经过脱敏的错误记录后重新运行。" if code else "先检查 Worker 日志，再决定是否重试。",
        )
    return _triage(
        FailureCategory.NONE,
        "当前评测没有执行失败。",
        False,
        (_fact("status", status),),
        "无需处理。",
    )


def _triage(
    category: FailureCategory,
    summary: str,
    retryable: bool,
    facts: tuple[str, ...],
    action: str,
) -> FailureTriage:
    return FailureTriage(
        category=category,
        summary=summary,
        retryable=retryable,
        supporting_facts=facts,
        suggested_action=action,
    )


def _fact(key: str, value: object) -> str:
    return f"{key}={sanitize_fact(value)}"
