"use client";

import type { ComponentType, ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  Briefcase,
  Brain,
  Bug,
  Code2,
  ClipboardList,
  FileQuestion,
  FileText,
  GitBranch,
  GraduationCap,
  Home,
  Images,
  Layers,
  Menu,
  MessageSquare,
  NotebookPen,
  Route,
  ServerCog,
  Settings,
  TimerReset,
  UploadCloud,
  Workflow
} from "lucide-react";
import { useState } from "react";

type NavItem = { href: string; label: string; icon: ComponentType<{ size?: number }> };
type NavGroup = { title: string; items: NavItem[] };

const groups: NavGroup[] = [
  { title: "开始", items: [{ href: "/dashboard", label: "学习工作台", icon: Home }] },
  {
    title: "知识管理",
    items: [
      { href: "/knowledge", label: "知识库", icon: BookOpen },
      { href: "/upload", label: "资料上传", icon: UploadCloud },
      { href: "/documents", label: "文档管理", icon: FileText },
      { href: "/media", label: "媒体资料库", icon: Images },
      { href: "/code", label: "代码仓库", icon: Code2 },
      { href: "/errors", label: "报错档案", icon: Bug },
      { href: "/tasks", label: "任务中心", icon: TimerReset }
    ]
  },
  {
    title: "AI 助手",
    items: [
      { href: "/chat", label: "知识问答", icon: MessageSquare },
      { href: "/chat/history", label: "会话记录", icon: FileQuestion }
    ]
  },
  {
    title: "学习成长",
    items: [
      { href: "/learning/roadmap", label: "学习路线", icon: Route },
      { href: "/learning/knowledge-graph", label: "知识关系", icon: GitBranch },
      { href: "/learning/knowledge-points", label: "知识点", icon: ClipboardList },
      { href: "/learning/cards", label: "学习卡片", icon: Layers },
      { href: "/learning/quizzes", label: "练习中心", icon: Workflow },
      { href: "/learning/notes", label: "学习笔记", icon: NotebookPen },
      { href: "/learning", label: "版本档案", icon: GraduationCap }
    ]
  },
  {
    title: "作品集求职",
    items: [
      { href: "/portfolio", label: "项目复盘", icon: Briefcase },
      { href: "/portfolio/resume", label: "简历表达", icon: FileText },
      { href: "/portfolio/interview", label: "面试讲解", icon: FileQuestion },
      { href: "/portfolio/project-review", label: "讲解路线", icon: Workflow }
    ]
  },
  {
    title: "系统",
    items: [
      { href: "/system", label: "模型与服务", icon: ServerCog },
      { href: "/system/observability", label: "可观测性", icon: TimerReset },
      { href: "/system/settings", label: "设置", icon: Settings }
    ]
  }
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const crumbs = pathname
    .split("/")
    .filter(Boolean)
    .map((part) => decodeURIComponent(part));

  return (
    <div className="app-shell">
      <button className="mobile-menu-button" onClick={() => setMobileOpen(true)} type="button">
        <Menu size={18} />
        菜单
      </button>
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <Link className="brand" href="/dashboard" onClick={() => setMobileOpen(false)}>
          <span className="brand-mark">
            <Brain size={22} />
          </span>
          <span>
            <strong>AI Knowledge OS Pro</strong>
            <small>V4.2 回归 Demo 中枢</small>
          </span>
        </Link>
        <nav className="nav-list" aria-label="主导航">
          {groups.map((group) => (
            <section className="nav-group" key={group.title}>
              <button className="nav-group-title" onClick={() => setCollapsed((old) => ({ ...old, [group.title]: !old[group.title] }))} type="button">
                {group.title}
              </button>
              {!collapsed[group.title] &&
                group.items.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"));
                  return (
                    <Link className={`nav-item ${active ? "active" : ""}`} href={item.href} key={`${group.title}-${item.label}`} onClick={() => setMobileOpen(false)}>
                      <Icon size={18} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
            </section>
          ))}
        </nav>
      </aside>
      {mobileOpen && <button aria-label="关闭菜单" className="mobile-backdrop" onClick={() => setMobileOpen(false)} type="button" />}
      <main className="main-content">
        <div className="breadcrumb">
          <Link href="/dashboard">首页</Link>
          {crumbs.map((crumb, index) => (
            <span key={`${crumb}-${index}`}>/ {crumbLabel(crumb)}</span>
          ))}
        </div>
        {children}
      </main>
    </div>
  );
}

function crumbLabel(value: string) {
  const map: Record<string, string> = {
    dashboard: "学习工作台",
    knowledge: "知识库",
    upload: "资料上传",
    documents: "文档管理",
    media: "媒体资料库",
    code: "代码仓库",
    errors: "报错档案",
    sources: "资料来源",
    tasks: "任务中心",
    chat: "知识问答",
    learning: "学习成长",
    roadmap: "学习路线",
    "knowledge-graph": "知识关系",
    history: "会话记录",
    quizzes: "练习中心",
    notes: "学习笔记",
    cards: "学习卡片",
    portfolio: "作品集求职",
    resume: "简历表达",
    interview: "面试讲解",
    "project-review": "讲解路线",
    system: "系统状态",
    observability: "可观测性",
    settings: "设置"
  };
  return map[value] || value;
}
