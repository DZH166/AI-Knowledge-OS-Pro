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
    title: "Evidence Research",
    collapsedByDefault: false,
    items: [
      { href: "/workbench", label: "研究工作台", description: "定义目标与边界", icon: "workbench" },
      { href: "/runs", label: "运行记录", description: "追踪计划与执行", icon: "runs" },
      { href: "/library", label: "证据资料库", description: "管理可检索来源", icon: "library" },
      { href: "/artifacts", label: "研究成果", description: "交付可核验结论", icon: "artifacts" }
    ]
  },
  {
    kind: "developer",
    title: "Developer Mode",
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
  return (
    items
      .filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`))
      .sort((left, right) => right.href.length - left.href.length)[0]?.href ?? null
  );
}
