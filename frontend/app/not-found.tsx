import Link from "next/link";

export default function NotFound() {
  return (
    <main className="page" style={{ paddingTop: 48 }}>
      <section className="panel stack">
        <span className="pill gray">404</span>
        <h1 style={{ margin: 0 }}>没有找到这个页面</h1>
        <p className="muted" style={{ margin: 0 }}>
          地址可能已经变化，或者这条记录属于另一个知识空间。回到工作台或证据资料库继续。
        </p>
        <div className="row wrap" style={{ gap: 10 }}>
          <Link className="button" href="/workbench">研究工作台</Link>
          <Link className="button secondary" href="/library">证据资料库</Link>
        </div>
      </section>
    </main>
  );
}
