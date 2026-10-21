# V5 Fixed Evaluation Corpus

This corpus is synthetic, deterministic, and safe to publish. It exists to test
observable retrieval and Agent behavior without paid providers or private user
data. It must never be described as a real-model quality benchmark.

The 60 cases in `../cases.jsonl` cover:

- single-hop evidence lookup;
- multi-source decomposition;
- PDF, image, audio, video, and code locators;
- active-versus-retired revision safety;
- normal insufficient-evidence outcomes;
- prompt-injection/tool-policy isolation;
- cancellation, duplicate wake-up, stale wake-up, and pause/resume recovery.

Every reported metric is computed by `scripts/evaluate_agentic_rag.py`. Recording
mode uses deterministic local embedding/model adapters and is labelled as such.
Real-provider results require an explicit real mode and must be stored separately.
