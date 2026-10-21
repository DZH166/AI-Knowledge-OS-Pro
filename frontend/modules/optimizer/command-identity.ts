type StudyCreationIntent = {
  label: string;
  policyId: string;
  template: string;
  seed: number;
  candidates: number;
  evaluations: number;
};

/** Match repeated submissions of unchanged user intent, regardless of response loss. */
export function studyIntentKey(intent: StudyCreationIntent): string {
  return JSON.stringify([
    intent.label.trim(), intent.policyId, intent.template,
    intent.seed, intent.candidates, intent.evaluations
  ]);
}
