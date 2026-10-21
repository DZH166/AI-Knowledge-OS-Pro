"use client";

import type { ComponentType, KeyboardEvent as ReactKeyboardEvent, ReactNode, SVGProps } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Archive,
  Blocks,
  BookOpen,
  BrainCircuit,
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
import { useCallback, useEffect, useRef, useState } from "react";

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
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileOpenButtonRef = useRef<HTMLButtonElement>(null);
  const mobileCloseButtonRef = useRef<HTMLButtonElement>(null);
  const destinations = navigationGroups.flatMap((group) => group.items);
  const activeHref = activeNavigationHref(pathname, destinations);
  const developer = navigationGroups.find((group) => group.kind === "developer");
  const primary = navigationGroups.find((group) => group.kind === "primary");
  const productIsActive = primary?.items.some((item) => item.href === activeHref) ?? false;
  const developerIsActive = developer?.items.some((item) => item.href === activeHref) ?? false;
  const crumbs = pathname.split("/").filter(Boolean).map((part) => decodeURIComponent(part));

  useEffect(() => recordRouteReady(pathname), [pathname]);

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
    if (event.key !== "Escape" || !mobileOpen) return;
    event.preventDefault();
    dismissMobileNavigation();
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
      <aside aria-label="产品导航" className={`sidebar ${mobileOpen ? "open" : ""}`} onKeyDown={handleSidebarKeyDown}>
        <button aria-label="关闭导航" className="sidebar-close" onClick={dismissMobileNavigation} ref={mobileCloseButtonRef} title="关闭导航" type="button">
          <X aria-hidden="true" size={18} />
        </button>
        <Link className="brand" href="/workbench" onClick={() => navigate("/workbench")}>
          <span aria-hidden="true" className="brand-mark">
            <BrainCircuit size={22} />
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
              <NavigationLink activeHref={activeHref} item={item} key={item.href} onNavigate={navigate} />
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
      </aside>

      {mobileOpen && <button aria-label="关闭菜单" className="mobile-backdrop" onClick={dismissMobileNavigation} type="button" />}

      <main className="main-content" id="main-content" tabIndex={-1}>
        <nav aria-label="面包屑" className="breadcrumb">
          <Link href="/workbench" onClick={() => navigate("/workbench")}>
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
  onNavigate
}: {
  activeHref: string | null;
  item: NavigationItem;
  onNavigate: (href: string) => void;
}) {
  const Icon = ICONS[item.icon];
  const active = item.href === activeHref;
  return (
    <Link
      aria-current={active ? "page" : undefined}
      className={`nav-item ${active ? "active" : ""}`}
      href={item.href}
      onClick={() => onNavigate(item.href)}
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
    dashboard: "旧版总览",
    knowledge: "旧版知识库",
    upload: "摄取与上传",
    media: "多模态来源",
    chat: "传统 RAG 问答",
    learning: "学习资产",
    portfolio: "作品集工具",
    system: "系统与观测"
  };
  return labels[value] ?? value;
}
