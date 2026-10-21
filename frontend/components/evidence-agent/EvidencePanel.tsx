"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";

import styles from "./EvidencePresentation.module.css";

export type EvidencePanelProps = {
  open: boolean; onClose: () => void; returnFocusRef: RefObject<HTMLElement | null>;
  children: ReactNode; title?: string; busy?: boolean; className?: string;
};

export function EvidencePanel({ open, onClose, returnFocusRef, children, title = "证据详情", busy = false, className }: EvidencePanelProps) {
  const [narrow, setNarrow] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  useEffect(() => {
    const media = window.matchMedia("(max-width: 820px)");
    const update = () => setNarrow(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || !narrow) return;
    if (open && !dialog.open) { dialog.showModal(); closeRef.current?.focus(); }
    else if (!open && dialog.open) dialog.close();
    return () => { if (dialog.open) dialog.close(); };
  }, [narrow, open]);

  function dismiss() {
    dialogRef.current?.close();
    onClose();
    requestAnimationFrame(() => {
      const target = returnFocusRef.current;
      if (target?.isConnected) target.focus({ preventScroll: true });
    });
  }

  const content = <>
    <div className={styles.panelHeader}>
      <h2 id={titleId}>{title}</h2>
      {open && <button aria-label="关闭证据详情" className={styles.closeButton} onClick={dismiss} ref={closeRef} type="button">
        <X aria-hidden="true" size={18} />
      </button>}
    </div>
    <div aria-busy={busy} aria-live="polite" className={styles.panelContent}>{children}</div>
  </>;

  return narrow ? <dialog aria-busy={busy} aria-labelledby={titleId} aria-modal="true" className={styles.dialog}
    data-testid="evidence-inspector" onCancel={(event) => { event.preventDefault(); dismiss(); }} ref={dialogRef}>
    {open && content}
  </dialog> : <aside aria-busy={busy} aria-labelledby={titleId} className={`${styles.panel} ${className ?? ""}`} data-testid="evidence-inspector">{content}</aside>;
}
