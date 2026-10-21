"use client";

import { useState } from "react";
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

export function PageHeader({
  eyebrow,
  title,
  description,
  action
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="lead">{description}</p>}
      </div>
      {action}
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
        {reason && (
          <span>
            {"\u53ef\u80fd\u539f\u56e0\uff1a"}
            {reason}
          </span>
        )}
        {impact && (
          <span>
            {"\u5f71\u54cd\uff1a"}
            {impact}
          </span>
        )}
        {nextStep && (
          <span>
            {"\u4e0b\u4e00\u6b65\uff1a"}
            {nextStep}
          </span>
        )}
        {providerRequired && <StatusBadge status="not_configured" label={statusLabel("not_configured")} />}
        {technicalDetails && <TechnicalDetails>{technicalDetails}</TechnicalDetails>}
      </div>
      {onRetry && (
        <button className="button secondary small" disabled={retrying} onClick={handleRetry} type="button">
          {retrying ? <ButtonLoading label="重试中" /> : "\u91cd\u8bd5"}
        </button>
      )}
    </div>
  );
}

export function Toast({
  message,
  tone = "success",
  onClose
}: {
  message: string;
  tone?: "success" | "warning" | "danger" | "info";
  onClose?: () => void;
}) {
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
              <th className={column.className} key={column.key}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowKey(row, rowIndex)}>
              {columns.map((column) => (
                <td className={column.className} key={column.key}>
                  {column.cell(row, rowIndex)}
                </td>
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

export function Pagination({
  page,
  pageCount,
  onPageChange
}: {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <nav aria-label="分页" className="pagination">
      <button className="button secondary small" disabled={page <= 1} onClick={() => onPageChange(page - 1)} type="button">
        <ChevronLeft size={15} />
        上一页
      </button>
      <span className="muted">
        第 {page} / {Math.max(pageCount, 1)} 页
      </span>
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

export function FormField({
  label,
  htmlFor,
  error,
  help,
  children
}: {
  label: string;
  htmlFor?: string;
  error?: string;
  help?: string;
  children: ReactNode;
}) {
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
  onClick
}: {
  children: ReactNode;
  pendingLabel?: string;
  className?: string;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  onClick: () => void | Promise<void>;
}) {
  const [pending, setPending] = useState(false);

  async function handleClick() {
    if (pending || disabled) return;
    setPending(true);
    try {
      await onClick();
    } finally {
      setPending(false);
    }
  }

  return (
    <button className={className} disabled={disabled || pending} onClick={handleClick} type={type}>
      {pending ? <ButtonLoading label={pendingLabel} /> : children}
    </button>
  );
}

export function ActionToast({
  message,
  tone = "success",
  onClose
}: {
  message: string;
  tone?: "success" | "warning" | "danger" | "info";
  onClose?: () => void;
}) {
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

export function AsyncActionBoundary({
  busy,
  error,
  children,
  onRetry
}: {
  busy?: boolean;
  error?: string;
  children: ReactNode;
  onRetry?: () => void;
}) {
  return (
    <div className="async-boundary">
      {busy && <LoadingOverlay show label="正在处理" />}
      {error && <ErrorState message={error} onRetry={onRetry} />}
      {children}
    </div>
  );
}

export function SectionTabs({
  tabs,
  active,
  onChange
}: {
  tabs: { key: string; label: string }[];
  active: string;
  onChange: (key: string) => void;
}) {
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

export function ProgressivePanel({
  title,
  summary,
  children,
  defaultOpen = false
}: {
  title: string;
  summary: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
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


export function LoadingState({
  title = "\u52a0\u8f7d\u4e2d",
  description
}: {
  title?: string;
  description?: string;
}) {
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
      <span>{"\u5f53\u524d\u4f7f\u7528\u5408\u6210\u793a\u4f8b\u6570\u636e\uff0c\u4e0d\u4ee3\u8868\u771f\u5b9e Provider \u8f93\u51fa\u3002"}</span>
    </div>
  );
}

export function CapabilityWarning({
  capability,
  status,
  message,
  action
}: {
  capability: string;
  status: string;
  message: string;
  action?: ReactNode;
}) {
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

export function ProviderMissingWarning({
  provider,
  code = "NOT_CONFIGURED",
  setupHint,
  onRetry
}: {
  provider: string;
  code?: string;
  setupHint?: string;
  onRetry?: () => void;
}) {
  return (
    <ErrorState
      impact={"\u9700\u8981\u8be5 Provider \u7684 OCR\u3001\u8f6c\u5199\u3001\u5411\u91cf\u6216 LLM \u529f\u80fd\u4f1a\u660e\u786e\u62d2\u7edd\u3002"}
      message={`${provider} ${statusLabel("not_configured")}`}
      nextStep={setupHint || "\u914d\u7f6e\u5bf9\u5e94 API Key \u540e\u91cd\u8bd5\uff0cDemo \u6a21\u5f0f\u4e0d\u4f1a\u4f2a\u9020\u771f\u5b9e AI \u8f93\u51fa\u3002"}
      onRetry={onRetry}
      providerRequired
      reason={"\u5f53\u524d\u73af\u5883\u6ca1\u6709\u68c0\u6d4b\u5230\u53ef\u7528\u7684\u771f\u5b9e Provider \u51ed\u636e\u3002"}
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

export function SourceLocatorButton({
  label = "\u67e5\u770b\u6765\u6e90",
  href,
  testId,
  onClick
}: {
  label?: string;
  href?: string;
  testId?: string;
  onClick?: () => void;
}) {
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

export function TaskLogDrawer({
  title = "\u4efb\u52a1\u65e5\u5fd7",
  open = true,
  events,
  onClose
}: {
  title?: string;
  open?: boolean;
  events: TaskLogEvent[];
  onClose?: () => void;
}) {
  return (
    <Drawer onClose={onClose} open={open} title={title}>
      {events.length === 0 ? (
        <EmptyState description={"\u4efb\u52a1\u5f00\u59cb\u540e\u4f1a\u5728\u8fd9\u91cc\u663e\u793a\u9636\u6bb5\u3001\u8fdb\u5ea6\u548c\u9519\u8bef\u4fe1\u606f\u3002"} title={"\u6682\u65e0\u4efb\u52a1\u4e8b\u4ef6"} />
      ) : (
        <ol className="timeline">
          {events.map((event, index) => (
            <li key={event.id ?? index}>
              <div className="row wrap">
                {event.status && <TaskStatusBadge status={event.status} />}
                <strong>{event.stage || "\u4efb\u52a1\u4e8b\u4ef6"}</strong>
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
