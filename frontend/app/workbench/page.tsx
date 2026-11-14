import { Workbench } from "@/components/evidence-agent/Workbench";

// The workbench reads scenario/space/demo query parameters and must render the
// real disabled draft on the server. A static prerender would emit only the
// Suspense fallback, leaving no editable form until client JavaScript arrives.
export const dynamic = "force-dynamic";

export default function WorkbenchPage() {
  return <Workbench />;
}
