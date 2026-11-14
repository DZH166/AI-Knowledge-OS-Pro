"use client";

import { useEffect } from "react";

export default function ErrorBoundary({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Route error", error);
  }, [error]);

  return (
    <main className="page" style={{ paddingTop: 48 }}>
      <section className="panel stack" role="alert">
        <span className="pill gray">页面出错</span>
        <h1 style={{ margin: 0 }}>这一页没有完成加载</h1>
        <p className="muted" style={{ margin: 0 }}>
          你的资料和已保存的运行不会因为这次页面错误丢失。可以先重试；如果仍然失败，回到工作台重新进入。
        </p>
        {error.digest ? <p className="muted">错误编号：{error.digest}</p> : null}
        <div className="row wrap" style={{ gap: 10 }}>
          <button className="button" onClick={reset} type="button">重试当前页</button>
          <a className="button secondary" href="/workbench">回到工作台</a>
        </div>
      </section>
    </main>
  );
}
