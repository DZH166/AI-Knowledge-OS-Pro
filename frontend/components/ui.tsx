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

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state">
      <AlertTriangle size={20} />
      <span>{message}</span>
      {onRetry && (
        <button className="button secondary small" onClick={onRetry} type="button">
          重试
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
