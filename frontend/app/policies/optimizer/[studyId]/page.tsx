import { OptimizerStudyView } from "@/components/optimizer/OptimizerStudyView";


export default async function OptimizerStudyPage({ params }: { params: Promise<{ studyId: string }> }) {
  const { studyId } = await params;
  return <OptimizerStudyView studyId={studyId} />;
}
