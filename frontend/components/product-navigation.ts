export type NavigationIcon =
  | "workbench"
  | "runs"
  | "library"
  | "artifacts"
  | "dashboard"
  | "upload"
  | "media"
  | "chat"
  | "learning"
  | "portfolio"
  | "system";

export type NavigationItem = { href: string; label: string; description?: string; icon: NavigationIcon };
export type NavigationGroup = {
  kind: "primary" | "developer";
  title: string;
  collapsedByDefault: boolean;
  items: NavigationItem[];
};

export const navigationGroups: NavigationGroup[] = [
  {
    kind: "primary",
    title: "研究",
    collapsedByDefault: false,
    items: [
      { href: "/workbench", label: "研究工作台", icon: "workbench" },
      { href: "/runs", label: "运行记录", icon: "runs" },
      { href: "/library", label: "证据资料库", icon: "library" },
      { href: "/artifacts", label: "研究成果", icon: "artifacts" }
    ]
  },
  {
    kind: "developer",
    title: "开发者模式",
    collapsedByDefault: true,
    items: [
      { href: "/dashboard", label: "旧版总览", icon: "dashboard" },
      { href: "/knowledge", label: "旧版知识库", icon: "library" },
      { href: "/upload", label: "摄取与上传", icon: "upload" },
      { href: "/media", label: "多模态来源", icon: "media" },
      { href: "/chat", label: "传统 RAG 问答", icon: "chat" },
      { href: "/learning", label: "学习资产", icon: "learning" },
      { href: "/portfolio", label: "作品集工具", icon: "portfolio" },
      { href: "/system", label: "系统与观测", icon: "system" }
    ]
  }
];

export function activeNavigationHref(pathname: string, items: NavigationItem[]): string | null {
  const activePathname = pathname === "/evaluations" || pathname.startsWith("/evaluations/") || pathname === "/policies" || pathname.startsWith("/policies/")
    ? "/system"
    : pathname;
  return (
    items
      .filter((item) => activePathname === item.href || activePathname.startsWith(`${item.href}/`))
      .sort((left, right) => right.href.length - left.href.length)[0]?.href ?? null
  );
}
