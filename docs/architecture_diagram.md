# Architecture Diagrams

These Mermaid diagrams are intentionally interview-friendly. They show the product boundary, not every implementation class.

## 1. System Architecture

```mermaid
flowchart LR
    Learner["Learner / AI app builder"] --> UI["Next.js product UI"]
    UI --> API["FastAPI API"]
    API --> DB["SQLite / SQLAlchemy"]
    API --> Qdrant["Qdrant vector store"]
    API --> Redis["Redis / RQ queue"]
    Redis --> Worker["Worker process"]
    Worker --> DB
    Worker --> Qdrant
    Worker --> Providers["OpenAI-compatible providers"]
    Providers --> LLM["LLM"]
    Providers --> Embed["Embedding"]
    Providers --> OCR["OCR / vision"]
    Providers --> Speech["Speech-to-text"]
```

## 2. RAG Flow

```mermaid
flowchart TD
    Upload["Document or media source"] --> Parse["Parse / OCR / transcribe"]
    Parse --> Chunk["Chunk with source locator"]
    Chunk --> Embed["Embedding provider"]
    Embed --> Index["Qdrant index"]
    Question["User question"] --> Retrieve["Vector retrieval"]
    Index --> Retrieve
    Retrieve --> Prompt["Grounded prompt"]
    Prompt --> Answer["LLM answer"]
    Answer --> Cite["Validated citations"]
    Cite --> Jump["Document section / image detail / media timestamp"]
```

## 3. Multimodal Processing Flow

```mermaid
flowchart TD
    Source["Source"] --> Revision["SourceRevision"]
    Revision --> Image["Image OCR / visual task"]
    Revision --> Audio["Audio transcription"]
    Revision --> Video["Video metadata / keyframes / transcription"]
    Image --> Chunk["MultimodalChunk"]
    Audio --> Segment["TranscriptSegment"]
    Video --> Frame["VisualFrame timestamp_ms"]
    Segment --> Chunk
    Frame --> Asset["MediaAsset"]
    Chunk --> Locator["CitationLocator"]
    Asset --> Locator
```

## 4. Task Queue Flow

```mermaid
flowchart LR
    UI["Upload or process action"] --> Job["IngestionJob"]
    Job --> Event1["JobEvent queued"]
    Job --> Broker["Redis / RQ"]
    Broker --> Worker["Worker claims job"]
    Worker --> Step["Parse/OCR/transcribe/keyframes"]
    Step --> Event2["Progress events"]
    Step --> Result["Result JSON + source state"]
    Result --> UI2["Task Center retry/cancel/result link"]
```

## 5. Learning Loop Flow

```mermaid
flowchart TD
    Evidence["Persisted chunk or media segment"] --> Artifact["LearningArtifact"]
    Artifact --> Point["Knowledge point"]
    Artifact --> Card["Learning card"]
    Artifact --> Quiz["Practice question"]
    Artifact --> Note["Learning note"]
    Artifact --> Pitch["Interview expression"]
    Point --> Archive["Version learning archive"]
    Archive --> Review["Review and explain project evolution"]
```

## 6. Citation Jump Flow

```mermaid
flowchart TD
    Citation["RAG citation payload"] --> Kind{"source type"}
    Kind -->|document_id| Doc["/documents/{id}?chunk=..."]
    Kind -->|image source_id| Image["/media/sources/{id}"]
    Kind -->|audio start_ms| Audio["/media/sources/{id}?t=..."]
    Kind -->|video start_ms| Video["/media/sources/{id}?t=...&chunk=..."]
    Video --> Highlight["Seek player and highlight transcript"]
    Audio --> Highlight
```

## 7. Portfolio Generation Flow

```mermaid
flowchart TD
    Code["Codebase + Git history"] --> Summary["Portfolio summary service"]
    Docs["README + architecture + learning logs"] --> Summary
    Tests["Test/build/release evidence"] --> Summary
    Summary --> Resume["Resume entry draft"]
    Summary --> Interview["Interview Q&A draft"]
    Summary --> Review["Project review narrative"]
    Providers["Configured LLM provider"] --> Resume
    Providers --> Interview
    Providers --> Review
    Resume --> Export["Markdown export"]
    Interview --> Export
    Review --> Export
    Export --> Portfolio["GitHub portfolio evidence"]
```
