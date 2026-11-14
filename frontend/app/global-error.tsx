"use client";

export default function GlobalError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <main style={{ maxWidth: 720, margin: "10vh auto", padding: 24, fontFamily: "system-ui, sans-serif" }}>
          <p style={{ color: "#0f766e", fontWeight: 700 }}>溯知 · 页面恢复</p>
          <h1>应用遇到未处理的错误</h1>
          <p style={{ color: "#52606d", lineHeight: 1.7 }}>
            本地资料和已提交的任务不会因为这次错误被删除。可以重试；如果问题持续，重启应用后再打开。
          </p>
          {error.digest ? <p style={{ color: "#7b8794" }}>错误编号：{error.digest}</p> : null}
          <button
            onClick={reset}
            style={{ padding: "10px 18px", borderRadius: 8, border: 0, background: "#0f766e", color: "#fff", cursor: "pointer" }}
            type="button"
          >
            重试
          </button>
        </main>
      </body>
    </html>
  );
}
