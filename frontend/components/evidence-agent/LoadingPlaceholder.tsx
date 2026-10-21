import styles from "./EvidenceAgent.module.css";

export function LoadingPlaceholder({ label }: { label: string }) {
  return <div aria-live="polite" className={styles.loadingState} role="status"><span>{label}</span><div aria-hidden="true" className={styles.skeletonGrid}><i /><i /><i /></div></div>;
}
