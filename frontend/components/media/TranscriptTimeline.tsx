import { Play } from "lucide-react";

import { EmptyState, StatusBadge } from "@/components/ui";
import { formatDuration } from "@/services/api";
import type { MultimodalChunk, TranscriptSegment } from "@/types/api";

type TranscriptTimelineProps = {
  sourceType: string;
  transcriptSegments: TranscriptSegment[];
  transcriptChunks: MultimodalChunk[];
  chapters: TranscriptSegment[];
  activeSegmentId: number | null;
  onSeek: (milliseconds: number) => void;
  onSelectChunk: (chunkId: number | null) => void;
};

export function TranscriptTimeline({
  sourceType,
  transcriptSegments,
  transcriptChunks,
  chapters,
  activeSegmentId,
  onSeek,
  onSelectChunk
}: TranscriptTimelineProps) {
  return (
    <section className="panel stack" data-testid="transcript-timeline">
      <div className="row between wrap">
        <h2>{sourceType === "video" ? "Video" : "Audio"} transcript timeline</h2>
        {transcriptChunks.length > 0 && <span className="pill">{transcriptChunks.length} chunks indexed</span>}
      </div>
      {chapters.length > 1 && (
        <div className="chapter-list">
          {chapters.map((segment) => (
            <button className="button secondary small" key={segment.id} onClick={() => onSeek(segment.start_ms)} type="button">
              <Play size={14} />
              {formatDuration(segment.start_ms)}
            </button>
          ))}
        </div>
      )}
      {transcriptSegments.length === 0 ? (
        <EmptyState
          description="Configure a real transcription provider and run transcription. The system returns an explicit NOT_CONFIGURED error instead of fake subtitles."
          title="No transcript segments"
        />
      ) : (
        <div className="list">
          {transcriptSegments.map((segment) => {
            const chunk = transcriptChunks.find((item) => item.start_ms === segment.start_ms);
            return (
              <button
                className={`list-item transcript-segment ${segment.id === activeSegmentId ? "active" : ""}`}
                data-active={segment.id === activeSegmentId ? "true" : "false"}
                data-testid="transcript-segment"
                id={`segment-${segment.id}`}
                key={segment.id}
                onClick={() => {
                  onSelectChunk(chunk?.id || null);
                  onSeek(segment.start_ms);
                }}
                type="button"
              >
                <div className="row between">
                  <strong>
                    {formatDuration(segment.start_ms)} - {formatDuration(segment.end_ms)}
                  </strong>
                  <StatusBadge status="ready" label={segment.language || "language unknown"} />
                </div>
                <p className="pre-wrap">{segment.text}</p>
                {segment.confidence !== null && <span className="muted">Confidence {segment.confidence}%</span>}
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
