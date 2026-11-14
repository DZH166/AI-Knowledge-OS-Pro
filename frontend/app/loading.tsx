export default function Loading() {
  return (
    <main className="page" aria-busy="true" aria-live="polite">
      <div className="skeleton-line" style={{ height: 20, width: 180 }} />
      <div className="skeleton-line" style={{ height: 42, width: "55%" }} />
      <div className="panel stack">
        <div className="skeleton-line" style={{ height: 16, width: "78%" }} />
        <div className="skeleton-line" style={{ height: 16, width: "64%" }} />
        <div className="skeleton-line" style={{ height: 120 }} />
      </div>
      <span className="muted">正在加载页面…</span>
    </main>
  );
}
