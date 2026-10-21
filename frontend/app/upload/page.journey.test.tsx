import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams("scenario=compare&space_id=7") }));

import UploadPage from "./page";

describe("research journey upload return", () => {
  it("offers a return to the same comparison space and explains processing is not evidence yet", () => {
    const markup = renderToStaticMarkup(createElement(UploadPage));

    expect(markup).toContain('href="/workbench?scenario=compare&amp;space_id=7"');
    expect(markup).toContain("处理完成并建立有效版本后");
  });

});
