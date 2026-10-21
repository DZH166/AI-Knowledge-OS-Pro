import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "溯知 Evidence OS", template: "%s · 溯知" },
  description: "以可核验证据为核心的个人研究 Agent"
};

export const viewport: Viewport = { themeColor: "#f3f5f3" };

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
