import { describe, expect, it } from "vitest";
import { libraryFiltersFromSearch, libraryFiltersHref } from "./library-filters";

describe("shareable library controls", () => {
  it("restores search, space, type and view while rejecting invalid space IDs", () => {
    expect(libraryFiltersFromSearch("?q=成本&space_id=7&type=video&view=cards")).toEqual({ query: "成本", spaceId: 7, sourceType: "video", view: "cards" });
    for (const space of ["-1", "Infinity", "1.5", "not-a-number"]) expect(libraryFiltersFromSearch(`?space_id=${space}`).spaceId).toBe(0);
    expect(libraryFiltersFromSearch(`?q=${"a".repeat(500)}`).query).toHaveLength(200);
  });

  it("changes display filters without discarding demo mode or an exact source deep link", () => {
    const href = libraryFiltersHref("?demo=1&source=9001", { query: "方案 A", spaceId: 7, sourceType: "document", view: "cards" });
    const params = new URLSearchParams(href.split("?")[1]);
    expect(params.get("demo")).toBe("1"); expect(params.get("source")).toBe("9001");
    expect(params.get("q")).toBe("方案 A"); expect(params.get("space_id")).toBe("7");
    const cleared = libraryFiltersHref(href.split("?")[1], { query: "", spaceId: 0, sourceType: "", view: "list" });
    expect(cleared).toBe("/library?demo=1&source=9001");
  });
});
