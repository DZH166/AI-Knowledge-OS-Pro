import { Suspense } from "react";
import { FeedbackWorkbench } from "@/components/feedback/FeedbackWorkbench";

export default function FeedbackPage() {
  return <Suspense fallback={<p role="status">正在打开反馈审阅…</p>}><FeedbackWorkbench /></Suspense>;
}
