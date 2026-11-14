"use client";

import type { ComponentType, KeyboardEvent as ReactKeyboardEvent, ReactNode, SVGProps } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  Archive,
  Blocks,
  BookOpen,
  BriefcaseBusiness,
  ChevronRight,
  CircleGauge,
  FileArchive,
  FlaskConical,
  Images,
  LibraryBig,
  Menu,
  MessageSquareText,
  UploadCloud,
  X
} from "lucide-react";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { activeNavigationHref, navigationGroups, type NavigationIcon, type NavigationItem } from "./product-navigation";
import { markRouteTransitionStart, recordRouteReady } from "@/services/page-metrics";

type IconComponent = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string }>;

const ICONS: Record<NavigationIcon, IconComponent> = {
  workbench: FlaskConical,
  runs: CircleGauge,
  library: LibraryBig,
  artifacts: FileArchive,
  dashboard: Blocks,
  upload: UploadCloud,
  media: Images,
  chat: MessageSquareText,
  learning: BookOpen,
  portfolio: BriefcaseBusiness,
  system: Archive
};

export function AppShell({ children }: { children: ReactNode }) {
  return <Suspense fallback={<main className="main-content" id="main-content">{children}</main>}><ShellContent>{children}</ShellContent></Suspense>;
}

function ShellContent({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const recording = useSearchParams().get("demo") === "1";
  const workbenchHref = recording ? "/workbench?demo=1" : "/workbench";
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileOpenButtonRef = useRef<HTMLButtonElement>(null);
  const mobileCloseButtonRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const destinations = navigationGroups.flatMap((group) => group.items);
  const activeHref = activeNavigationHref(pathname, destinations);
  const developer = navigationGroups.find((group) => group.kind === "developer");
  const primary = navigationGroups.find((group) => group.kind === "primary");
  const productIsActive = primary?.items.some((item) => item.href === activeHref) ?? false;
  const developerIsActive = developer?.items.some((item) => item.href === activeHref) ?? false;
  const crumbs = pathname.split("/").filter(Boolean).map((part) => decodeURIComponent(part));

  useEffect(() => recordRouteReady(pathname), [pathname]);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 981px)");
    const closeOnDesktop = () => { if (desktop.matches) setMobileOpen(false); };
    desktop.addEventListener("change", closeOnDesktop);
    return () => desktop.removeEventListener("change", closeOnDesktop);
  }, []);

  useEffect(() => {
    if (mobileOpen) mobileCloseButtonRef.current?.focus();
  }, [mobileOpen]);

  const dismissMobileNavigation = useCallback(() => {
    setMobileOpen(false);
    requestAnimationFrame(() => mobileOpenButtonRef.current?.focus());
  }, []);

  const navigate = (href: string) => {
    markRouteTransitionStart(href);
    setMobileOpen(false);
  };

  function handleSidebarKeyDown(event: ReactKeyboardEvent<HTMLElement>) {
    if (!mobileOpen) return;
    if (event.key === "Escape") {
      event.preventDefault();
      dismissMobileNavigation();
    } else if (event.key === "Tab") {
      const elements = sidebarRef.current?.querySelectorAll<HTMLElement>('a, button, summary');
      const visible = Array.from(elements ?? []).filter((element) =>
        element.tabIndex >= 0 &&
        !element.closest('details:not([open]) > :not(summary)') &&
        element.getClientRects().length > 0
      );
      const first = visible[0];
      const last = visible[visible.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }

  return (
    <div className="app-shell" data-product-mode={productIsActive}>
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      {!mobileOpen && (
        <button aria-label="打开导航" className="mobile-menu-button" onClick={() => setMobileOpen(true)} ref={mobileOpenButtonRef} title="打开导航" type="button">
          <Menu aria-hidden="true" size={18} />
        </button>
      )}
      <aside aria-label="产品导航" aria-modal={mobileOpen || undefined} className={`sidebar ${mobileOpen ? "open" : ""}`} onKeyDown={handleSidebarKeyDown} ref={sidebarRef} role={mobileOpen ? "dialog" : undefined}>
        <button aria-label="关闭导航" className="sidebar-close" onClick={dismissMobileNavigation} ref={mobileCloseButtonRef} title="关闭导航" type="button">
          <X aria-hidden="true" size={18} />
        </button>
        <Link className="brand" href={workbenchHref} onClick={() => navigate(workbenchHref)}>
          <span aria-hidden="true" className="brand-mark">
            <svg aria-hidden="true" fill="none" height="20" viewBox="0 0 24 24" width="20"><path d="M6 3h12v18l-6-4-6 4V3Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.6" /><path d="M9 7h6m-6 4h4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" /></svg>
          </span>
          <span className="min-w-0">
            <strong>溯知</strong>
            <small>证据研究工作台</small>
          </span>
        </Link>

        <nav aria-label="主导航" className="nav-list">
          <section aria-labelledby="primary-navigation-title" className="nav-group">
            <p className="nav-section-label" id="primary-navigation-title">
              {primary?.title}
            </p>
            {primary?.items.map((item) => (
              <NavigationLink activeHref={activeHref} item={item} key={item.href} onNavigate={navigate} recording={recording} />
            ))}
          </section>

          {developer && (
            <details className="developer-nav" open={developerIsActive || undefined}>
              <summary>{developer.title}</summary>
              <div className="developer-nav-items">
                {developer.items.map((item) => (
                  <NavigationLink activeHref={activeHref} item={item} key={item.href} onNavigate={navigate} />
                ))}
              </div>
            </details>
          )}
        </nav>
        <div className="sidebar-footer">
          <span className="workspace-monogram" aria-hidden="true">溯</span>
          <div><strong>个人研究空间</strong><small>{recording ? "演示模式 · 非真实执行" : "资料 · 证据 · 结论"}</small></div>
        </div>
      </aside>

      {mobileOpen && <button aria-label="关闭菜单" className="mobile-backdrop" onClick={dismissMobileNavigation} tabIndex={-1} type="button" />}

      <main className="main-content" id="main-content" inert={mobileOpen || undefined} tabIndex={-1}>
        <nav aria-label="面包屑" className="breadcrumb">
          <Link href={workbenchHref} onClick={() => navigate(workbenchHref)}>
            溯知
          </Link>
          {crumbs.map((crumb, index) => (
            <span key={`${crumb}-${index}`}>
              <ChevronRight aria-hidden="true" size={13} />
              <span aria-current={index === crumbs.length - 1 ? "page" : undefined}>{crumbLabel(crumb)}</span>
            </span>
          ))}
        </nav>
        {children}
      </main>
    </div>
  );
}

function NavigationLink({
  activeHref,
  item,
  onNavigate,
  recording = false
}: {
  activeHref: string | null;
  item: NavigationItem;
  onNavigate: (href: string) => void;
  recording?: boolean;
}) {
  const Icon = ICONS[item.icon];
  const active = item.href === activeHref;
  const href = recording ? `${item.href}?demo=1` : item.href;
  return (
    <Link
      aria-current={active ? "page" : undefined}
      className={`nav-item ${active ? "active" : ""}`}
      href={href}
      onClick={() => onNavigate(href)}
    >
      <Icon aria-hidden="true" size={18} />
      <span className="nav-item-copy">
        <strong>{item.label}</strong>
        {item.description && <small>{item.description}</small>}
      </span>
    </Link>
  );
}

function crumbLabel(value: string) {
  const labels: Record<string, string> = {
    workbench: "研究工作台",
    runs: "运行记录",
    library: "证据资料库",
    artifacts: "研究成果",
    evaluations: "智能体评测",
    policies: "策略实验室",
    optimize: "优化实验",
    optimizer: "优化实验",
    error: "错误诊断",
    feedback: "反馈审阅",
    dashboard: "旧版总览",
    knowledge: "旧版知识库",
    upload: "摄取与上传",
    media: "多模态来源",
    sources: "来源详情",
    documents: "文档",
    chat: "传统 RAG 问答",
    learning: "学习资产",
    portfolio: "作品集工具",
    system: "系统与观测",
    tasks: "任务中心",
    trace: "运行轨迹"
  };
  if (/^\d+$/.test(value)) return `#${value}`;
  if (value.length > 24 || /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(value)) return "详情";
  return labels[value] ?? value;
}
