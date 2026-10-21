"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Info,
  Loader2,
  MoreHorizontal,
  Search,
  X
} from "lucide-react";

import { statusLabel, statusTone } from "@/services/api";
import { finishInteractionMetric, getInteractionMetricsSnapshot, startInteractionMetric } from "@/services/interaction-metrics";
import type { InteractionMetric } from "@/services/interaction-metrics";

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="lead">{description}</p>}
      </div>
      {action && <div className="page-header-action">{action}</div>}
    </header>
  );
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <span className={`status-badge ${statusTone(status)}`}>{label || statusLabel(status)}</span>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <CheckCircle2 size={22} />
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({
  message,
  reason,
  impact,
  nextStep,
  technicalDetails,
  providerRequired = false,
  onRetry
}: {
  message: string;
  reason?: string;
  impact?: string;
  nextStep?: string;
  technicalDetails?: ReactNode;
  providerRequired?: boolean;
  onRetry?: () => void | Promise<void>;
}) {
  const [retrying, setRetrying] = useState(false);
  const reasonLabel = "\u53ef\u80fd\u539f\u56e0";
  const nextStepLabel = "\u4e0b\u4e00\u6b65";

  async function handleRetry() {
    if (!onRetry || retrying) return;
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div className="error-state">
      <AlertTriangle size={20} />
      <div className="stack compact">
        <strong>{message}</strong>
        {reason && <span>{reasonLabel}: {reason}</span>}
        {impact && <span>影响: {impact}</span>}
        {nextStep && <span>{nextStepLabel}: {nextStep}</span>}
        {providerRequired && <StatusBadge status="not_configured" label={statusLabel("not_configured")} />}
        {technicalDetails && <TechnicalDetails>{technicalDetails}</TechnicalDetails>}
      </div>
      {onRetry && (
        <button className="button secondary small" disabled={retrying} onClick={handleRetry} type="button">
          {retrying ? <ButtonLoading label="重试中" /> : "重试"}
        </button>
      )}
    </div>
  );
}

export function Toast({ message, tone = "success", onClose }: { message: string; tone?: "success" | "warning" | "danger" | "info"; onClose?: () => void }) {
  if (!message) return null;
  return (
    <div className={`toast ${tone}`} role="status">
      <CheckCircle2 size={18} />
      <span>{message}</span>
      {onClose && (
        <button aria-label="关闭提示" className="icon-button compact" onClick={onClose} type="button">
          <X size={14} />
        </button>
      )}
    </div>
  );
}

export function Modal({
  open,
  title,
  description,
  children,
  footer,
  onClose
}: {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="presentation">
      <section aria-modal="true" className="modal-panel" role="dialog">
        <header className="row between">
          <div>
            <h2>{title}</h2>
            {description && <p className="muted">{description}</p>}
          </div>
          <button aria-label="关闭" className="icon-button" onClick={onClose} type="button">
            <X size={16} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-footer">{footer}</footer>}
      </section>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "确认",
  cancelLabel = "取消",
  tone = "danger",
  busy = false,
  onConfirm,
  onCancel
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "primary";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      description={description}
      footer={
        <div className="row wrap">
          <button className="button secondary" disabled={busy} onClick={onCancel} type="button">
            {cancelLabel}
          </button>
          <button className={`button ${tone === "danger" ? "danger" : ""}`} disabled={busy} onClick={onConfirm} type="button">
            {busy ? <ButtonLoading label="处理中" /> : confirmLabel}
          </button>
        </div>
      }
      onClose={onCancel}
      open={open}
      title={title}
    >
      <p className="muted">这个操作会立即执行，请确认后继续。</p>
    </Modal>
  );
}

export function LoadingSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton-list">
      {Array.from({ length: lines }).map((_, index) => (
        <span className="skeleton-line" key={index} />
      ))}
    </div>
  );
}

export function ProgressSteps({ steps, active }: { steps: string[]; active: number }) {
  return (
    <ol className="progress-steps">
      {steps.map((step, index) => (
        <li className={index < active ? "done" : index === active ? "active" : ""} key={step}>
          <span>{index + 1}</span>
          {step}
        </li>
      ))}
    </ol>
  );
}

export function SearchInput({ value, onChange, placeholder = "搜索" }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="search-input">
      <Search size={16} />
      <input onChange={(event) => onChange(event.target.value)} placeholder={placeholder} value={value} />
    </label>
  );
}

export function TechnicalDetails({ children, title = "技术详情" }: { children: ReactNode; title?: string }) {
  return (
    <details className="technical-details">
      <summary>
        <ChevronDown size={16} />
        {title}
      </summary>
      <div>{children}</div>
    </details>
  );
}

export function CopyButton({ value, label = "复制" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }
  return (
    <button className="button secondary small" onClick={copy} type="button">
      {copied ? <Check size={15} /> : <Copy size={15} />}
      {copied ? "已复制" : label}
    </button>
  );
}

export function CodeBlock({ value }: { value: string }) {
  return (
    <div className="code-block">
      <button className="icon-button" onClick={() => navigator.clipboard.writeText(value)} title="复制代码" type="button">
        <Copy size={15} />
      </button>
      <pre>{value}</pre>
    </div>
  );
}

export function Drawer({ title, open = true, children, onClose }: { title?: string; open?: boolean; children: ReactNode; onClose?: () => void }) {
  if (!open) return null;
  return (
    <aside className="drawer stack">
      {(title || onClose) && (
        <div className="row between">
          {title && <h2>{title}</h2>}
          {onClose && (
            <button aria-label="关闭抽屉" className="icon-button" onClick={onClose} type="button">
              <X size={16} />
            </button>
          )}
        </div>
      )}
      {children}
    </aside>
  );
}

export type DataTableColumn<T> = {
  key: string;
  header: ReactNode;
  cell: (row: T, index: number) => ReactNode;
  className?: string;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty
}: {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  empty?: ReactNode;
}) {
  if (rows.length === 0) {
    return <>{empty || <EmptyState title="没有匹配内容" description="调整筛选条件后再试，或先新增一条记录。" />}</>;
  }
  return (
    <div className="table-scroll">
      <table className="table data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th className={column.className} key={column.key}>{column.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowKey(row, rowIndex)}>
              {columns.map((column) => (
                <td className={column.className} key={column.key}>{column.cell(row, rowIndex)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="filter-bar">{children}</div>;
}

export function Pagination({ page, pageCount, onPageChange }: { page: number; pageCount: number; onPageChange: (page: number) => void }) {
  return (
    <nav aria-label="分页" className="pagination">
      <button className="button secondary small" disabled={page <= 1} onClick={() => onPageChange(page - 1)} type="button">
        <ChevronLeft size={15} />
        上一页
      </button>
      <span className="muted">第 {page} / {Math.max(pageCount, 1)} 页</span>
      <button className="button secondary small" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)} type="button">
        下一页
        <ChevronRight size={15} />
      </button>
    </nav>
  );
}

export function ActionMenu({ label = "操作", children }: { label?: string; children: ReactNode }) {
  return (
    <details className="action-menu">
      <summary>
        <MoreHorizontal size={16} />
        {label}
      </summary>
      <div className="action-menu-panel">{children}</div>
    </details>
  );
}

export function FormField({ label, htmlFor, error, help, children }: { label: string; htmlFor?: string; error?: string; help?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {help && <span className="field-help">{help}</span>}
      {error && <span className="field-error">{error}</span>}
    </div>
  );
}

export function HelpTooltip({ text }: { text: string }) {
  return (
    <span className="help-tooltip" title={text}>
      <Info size={14} />
    </span>
  );
}

export function ButtonLoading({ label }: { label: string }) {
  return (
    <>
      <Loader2 className="spin" size={16} />
      {label}
    </>
  );
}

export function PendingButton({
  children,
  pendingLabel = "处理中",
  className = "button",
  disabled = false,
  type = "button",
  metricName,
  onClick
}: {
  children: ReactNode;
  pendingLabel?: string;
  className?: string;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  metricName?: string;
  onClick: () => void | Promise<void>;
}) {
  const [pending, setPending] = useState(false);
  const [slowLevel, setSlowLevel] = useState(0);

  useEffect(() => {
    if (!pending) {
      setSlowLevel(0);
      return;
    }
    const first = window.setTimeout(() => setSlowLevel(1), 800);
    const second = window.setTimeout(() => setSlowLevel(2), 3000);
    const third = window.setTimeout(() => setSlowLevel(3), 10000);
    return () => {
      window.clearTimeout(first);
      window.clearTimeout(second);
      window.clearTimeout(third);
    };
  }, [pending]);

  async function handleClick() {
    if (pending || disabled) return;
    setPending(true);
    const metricId = startInteractionMetric(metricName || textFromChildren(children) || "button_action");
    try {
      await onClick();
      finishInteractionMetric(metricId, "completed");
    } catch (error) {
      finishInteractionMetric(metricId, "failed", error);
      throw error;
    } finally {
      setPending(false);
    }
  }

  return (
    <button className={className} disabled={disabled || pending} onClick={handleClick} type={type}>
      {pending ? <ButtonLoading label={slowActionLabel(slowLevel, pendingLabel)} /> : children}
    </button>
  );
}

function slowActionLabel(level: number, pendingLabel: string) {
  if (level >= 3) return "耗时较长，可稍后重试";
  if (level >= 2) return "仍在处理中，请稍候";
  if (level >= 1) return "处理中";
  return pendingLabel;
}

function textFromChildren(children: ReactNode): string {
  if (typeof children === "string") return children;
  if (Array.isArray(children)) return children.map(textFromChildren).join("").trim();
  return "";
}

export function SlowActionNotice({ active, level }: { active: boolean; level: number }) {
  if (!active || level <= 0) return null;
  return (
    <div className={`notice ${level >= 3 ? "warning" : ""}`} role="status">
      <Loader2 className="spin" size={16} />
      <span>{slowActionLabel(level, "处理中")}</span>
    </div>
  );
}

export function InteractionTimeline({ actions }: { actions: InteractionMetric[] }) {
  if (!actions.length) return <EmptyState description="执行异步按钮后，这里会显示最近操作耗时。" title="暂无交互耗时" />;
  return (
    <ol className="timeline">
      {actions.map((action) => (
        <li key={action.id}>
          <div className="row wrap">
            <StatusBadge status={action.status === "failed" ? "failed" : action.status === "running" ? "running" : "completed"} />
            <strong>{action.label}</strong>
            <span className="muted">{action.duration_ms === null ? "进行中" : `${action.duration_ms} ms`}</span>
          </div>
          {action.message && <p className="muted">{action.message}</p>}
        </li>
      ))}
    </ol>
  );
}

export function RecentActionsPanel() {
  const [snapshot, setSnapshot] = useState(() => getInteractionMetricsSnapshot());
  useEffect(() => {
    const timer = window.setInterval(() => setSnapshot(getInteractionMetricsSnapshot()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <article className="panel stack" data-testid="recent-actions-panel">
      <div className="row between wrap">
        <h2>最近按钮耗时</h2>
        <span className="pill gray">{snapshot.recent.length} 条</span>
      </div>
      <div className="grid cols-4">
        <MetricPill label="进行中" value={snapshot.running} />
        <MetricPill label="已完成" value={snapshot.completed} />
        <MetricPill label="失败" value={snapshot.failed} />
        <MetricPill label="慢操作" value={snapshot.slow_actions} />
      </div>
      <InteractionTimeline actions={snapshot.recent.slice(0, 8)} />
    </article>
  );
}

function MetricPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="card compact">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function ActionToast({ message, tone = "success", onClose }: { message: string; tone?: "success" | "warning" | "danger" | "info"; onClose?: () => void }) {
  return <Toast message={message} onClose={onClose} tone={tone} />;
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <article className="card stack">
      <LoadingSkeleton lines={lines} />
    </article>
  );
}

export function LoadingOverlay({ show, label = "加载中" }: { show: boolean; label?: string }) {
  if (!show) return null;
  return (
    <div className="loading-overlay" role="status">
      <Loader2 className="spin" size={18} />
      <span>{label}</span>
    </div>
  );
}

export function AsyncActionBoundary({ busy, error, children, onRetry }: { busy?: boolean; error?: string; children: ReactNode; onRetry?: () => void }) {
  return (
    <div className="async-boundary">
      {busy && <LoadingOverlay show label="正在处理" />}
      {error && <ErrorState message={error} onRetry={onRetry} />}
      {children}
    </div>
  );
}

export function SectionTabs({ tabs, active, onChange }: { tabs: { key: string; label: string }[]; active: string; onChange: (key: string) => void }) {
  return (
    <div className="section-tabs" role="tablist">
      {tabs.map((tab) => (
        <button aria-selected={active === tab.key} className={active === tab.key ? "active" : ""} key={tab.key} onClick={() => onChange(tab.key)} role="tab" type="button">
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function ProgressivePanel({ title, summary, children, defaultOpen = false }: { title: string; summary: string; children: ReactNode; defaultOpen?: boolean }) {
  return (
    <details className="progressive-panel" open={defaultOpen}>
      <summary>
        <strong>{title}</strong>
        <span>{summary}</span>
      </summary>
      <div>{children}</div>
    </details>
  );
}

export function CollapsibleTechnicalDetails({ title = "技术细节", children }: { title?: string; children: ReactNode }) {
  return <TechnicalDetails title={title}>{children}</TechnicalDetails>;
}

export function LoadingState({ title = "加载中", description }: { title?: string; description?: string }) {
  return (
    <div className="empty-state">
      <Loader2 className="spin" size={22} />
      <strong>{title}</strong>
      {description && <p>{description}</p>}
    </div>
  );
}

export function DemoModeBanner({ mode = "demo" }: { mode?: "demo" | "real" | string }) {
  if (mode !== "demo") return null;
  return (
    <div className="notice">
      <StatusBadge status="demo" />
      <span>当前使用合成示例数据，不代表真实 Provider 输出。</span>
    </div>
  );
}

export function CapabilityWarning({ capability, status, message, action }: { capability: string; status: string; message: string; action?: ReactNode }) {
  return (
    <div className="notice warning">
      <StatusBadge status={status} />
      <div className="stack compact">
        <strong>{capability}</strong>
        <span>{message}</span>
      </div>
      {action}
    </div>
  );
}

export function ProviderMissingWarning({ provider, code = "NOT_CONFIGURED", setupHint, onRetry }: { provider: string; code?: string; setupHint?: string; onRetry?: () => void }) {
  return (
    <ErrorState
      impact="需要该 Provider 的 OCR、转写、向量或 LLM 功能会明确拒绝。"
      message={`${provider} ${statusLabel("not_configured")}`}
      nextStep={setupHint || "配置对应 API Key 后重试，Demo 模式不会伪造真实 AI 输出。"}
      onRetry={onRetry}
      providerRequired
      reason="当前环境没有检测到可用的真实 Provider 凭据。"
      technicalDetails={<code>{code}</code>}
    />
  );
}

export function TaskStatusBadge({ status }: { status: string }) {
  return <StatusBadge status={status} />;
}

export function LearningActionBar({ children }: { children: ReactNode }) {
  return <div className="row wrap">{children}</div>;
}

export function SourceLocatorButton({ label = "查看来源", href, testId, onClick }: { label?: string; href?: string; testId?: string; onClick?: () => void }) {
  if (href) {
    return (
      <a className="button secondary small" data-testid={testId} href={href}>
        {label}
        <ChevronRight size={15} />
      </a>
    );
  }
  return (
    <button className="button secondary small" data-testid={testId} onClick={onClick} type="button">
      {label}
      <ChevronRight size={15} />
    </button>
  );
}

export type TaskLogEvent = {
  id?: number | string;
  stage?: string | null;
  status?: string | null;
  message?: string | null;
  progress?: number | null;
  created_at?: string | null;
};

export function TaskLogDrawer({ title = "任务日志", open = true, events, onClose }: { title?: string; open?: boolean; events: TaskLogEvent[]; onClose?: () => void }) {
  return (
    <Drawer onClose={onClose} open={open} title={title}>
      {events.length === 0 ? (
        <EmptyState description="任务开始后会在这里显示阶段、进度和错误信息。" title="暂无任务事件" />
      ) : (
        <ol className="timeline">
          {events.map((event, index) => (
            <li key={event.id ?? index}>
              <div className="row wrap">
                {event.status && <TaskStatusBadge status={event.status} />}
                <strong>{event.stage || "任务事件"}</strong>
                {typeof event.progress === "number" && <span className="muted">{Math.round(event.progress)}%</span>}
              </div>
              {event.message && <p className="muted">{event.message}</p>}
              {event.created_at && <time className="muted">{formatDisplayTime(event.created_at)}</time>}
            </li>
          ))}
        </ol>
      )}
    </Drawer>
  );
}

function formatDisplayTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}
