import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SourceItem } from "@/types/api";
import { CodeSourceDetail } from "@/app/code/page";

describe("CodeSourceDetail", () => {
  it("turns a backend code_repository Source into a consumable code-viewer link", () => {
    const source = {
      id: 44,
      source_type: "code_repository",
      title: "Evidence Agent",
      original_filename: "Evidence Agent",
      language: "python",
      status: "active",
      active_revision_id: 51,
      latest_revision_id: 51,
      revisions: [{
        id: 51,
        chunks: [{
          id: 61,
          content_text: "def advance():\n    return True",
          locator_json: '{"kind":"code_range","file_path":"backend/app/worker.py","line_start":40,"line_end":41,"language":"python"}'
        }]
      }]
    } as SourceItem;

    const markup = renderToStaticMarkup(createElement(CodeSourceDetail, { source }));

    expect(markup).toContain("Evidence Agent");
    expect(markup).toContain("code_repository");
    expect(markup).toContain("backend/app/worker.py");
    expect(markup).toContain("/code?source=44&amp;file=backend%2Fapp%2Fworker.py&amp;line=40&amp;line_end=41");
  });
});
