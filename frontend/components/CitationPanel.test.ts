import { describe, expect, it } from "vitest";

import type { Citation } from "@/types/api";
import { citationHref } from "./CitationPanel";

const citation: Citation = {
  citation_id: "[1]",
  document_name: "Architecture.pdf",
  chunk_id: 7,
  chunk_index: 2,
  content_preview: "traceable evidence",
  score: 0.91
};

describe("citationHref", () => {
  it("prefers a canonical document route when document and source ids are both present", () => {
    expect(citationHref({
      ...citation,
      source_type: "document",
      source_id: 41,
      document_id: 12,
      page_number: 6,
      heading_path: "Agent design"
    })).toBe("/documents/12?page=6&heading=Agent+design&chunk=7");
  });

  it("uses the unified source detail only for a media citation", () => {
    expect(citationHref({
      ...citation,
      source_type: "audio",
      source_id: 41,
      document_id: 12,
      start_ms: 6_000
    })).toBe("/media/sources/41?t=6000&chunk=7");
  });

  it("keeps code locators ahead of document and media fallbacks", () => {
    expect(citationHref({
      ...citation,
      source_type: "code_repository",
      source_id: 4,
      document_id: 12,
      file_path: "backend/app/api/router.py",
      line_start: 9,
      line_end: 12
    })).toBe("/code?file=backend%2Fapp%2Fapi%2Frouter.py&line=9&line_end=12&source=4");
  });
});
