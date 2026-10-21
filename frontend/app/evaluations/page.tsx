import { Suspense } from "react";

import { EvaluationIndex } from "@/components/agent-control/EvaluationIndex";


export default function EvaluationsPage() {
  return <Suspense fallback={<div aria-live="polite" role="status">正在打开评测中心…</div>}><EvaluationIndex /></Suspense>;
}
