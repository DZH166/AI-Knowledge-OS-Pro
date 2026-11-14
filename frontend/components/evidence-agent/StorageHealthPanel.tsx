"use client";

import { AlertTriangle, CheckCircle2, Database, FileWarning, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/services/api";
import type { StorageHealth, StorageHealthFinding } from "@/types/api";
import styles from "./EvidenceAgent.module.css";

const SEVERITY_LABEL: Record<StorageHealthFinding["severity"], string> = {
  error: "阻断",
  warning: "提醒",
  info: "信息"
};

function formatBytes(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "—";
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value} B`;
}

export function StorageHealthPanel({ autoCheck = true }: { autoCheck?: boolean }) {
  const [report, setReport] = useState<StorageHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [deep, setDeep] = useState(false);
  const [error, setError] = useState("");

  const check = useCallback(async (deepHash: boolean) => {
    setLoading(true);
    setError("");
    try {
      setReport(await api.storageHealth({ deepHash }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "存储自检失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (autoCheck) void check(false);
  }, [autoCheck, check]);

  const errors = report?.findings.filter((finding) => finding.severity === "error") ?? [];
  const warnings = report?.findings.filter((finding) => finding.severity === "warning") ?? [];
  const visible = [...errors, ...warnings].slice(0, 6);
  const hidden = Math.max(0, errors.length + warnings.length - visible.length);

  return (
    <section aria-label="存储完整性" className={styles.storagePanel}>
      <div className={styles.storageHeader}>
        <div className={styles.storageTitle}>
          <span aria-hidden="true" className={report?.ok === false ? styles.storageBadgeBad : styles.storageBadgeGood}>
            {report?.ok === false ? <AlertTriangle size={18} /> : <ShieldCheck size={18} />}
          </span>
          <div>
            <h2>存储完整性</h2>
            <p aria-live="polite">
              {report
                ? report.ok
                  ? `数据库、上传文件与证据版本自检通过${warnings.length ? `，有 ${warnings.length} 条提醒` : ""}。`
                  : `发现 ${errors.length} 个阻断问题；先修复再继续写入，避免证据无法回放。`
                : "核对 SQLite、上传文件与活动证据版本是否一致。"}
            </p>
          </div>
        </div>
        <div className={styles.storageActions}>
          <label className={styles.storageToggle}>
            <input checked={deep} onChange={(event) => setDeep(event.target.checked)} type="checkbox" />
            核对内容指纹
          </label>
          <button className={styles.quietAction} disabled={loading} onClick={() => void check(deep)} type="button">
            <RefreshCw aria-hidden="true" size={14} /> {loading ? "检查中" : "重新检查"}
          </button>
        </div>
      </div>

      {error && (
        <p className={styles.storageError} role="alert">
          <FileWarning aria-hidden="true" size={15} /> {error}
        </p>
      )}

      {report && (
        <div aria-live="polite">
          <dl className={styles.storageMetrics}>
            <div><dt>引用文件</dt><dd>{String(report.files.referenced ?? "—")}</dd></div>
            <div><dt>缺失文件</dt><dd>{String(report.files.missing ?? "—")}</dd></div>
            <div><dt>活跃来源</dt><dd>{String(report.evidence.active_sources ?? "—")}</dd></div>
            <div><dt>数据库体积</dt><dd>{formatBytes(report.database.file_bytes ?? report.database.bytes)}</dd></div>
            <div><dt>Journal</dt><dd>{String(report.database.journal_mode ?? "—")}</dd></div>
          </dl>

          {visible.length > 0 ? (
            <ul className={styles.storageFindings}>
              {visible.map((finding) => (
                <li className={finding.severity === "error" ? styles.findingError : styles.findingWarning} key={`${finding.code}-${finding.entity}-${finding.message}`}>
                  <span>{SEVERITY_LABEL[finding.severity]}</span>
                  <strong>{finding.entity}</strong>
                  <p>{finding.message}</p>
                </li>
              ))}
              {hidden > 0 && <li className={styles.findingMore}>另有 {hidden} 条同类提醒，可运行命令行自检查看完整报告。</li>}
            </ul>
          ) : (
            <p className={styles.storageClear}>
              <CheckCircle2 aria-hidden="true" size={16} /> 未发现文件缺失、版本错位或索引悬空。
            </p>
          )}

          <details className={styles.storageDetails}>
            <summary><Database aria-hidden="true" size={14} /> 检查范围与数据口径</summary>
            {report.notes.map((note) => <p key={note}>{note}</p>)}
            <p>检查时间：{new Date(report.checked_at).toLocaleString("zh-CN")}；内容指纹默认为存在性检查，不替代外部备份。</p>
            <p>备份：<code>python scripts/backup_storage.py --output backups/evidence.zip</code>；恢复前会先验证归档并保留旧副本。</p>
          </details>
        </div>
      )}
    </section>
  );
}
