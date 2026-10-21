import { describe, expect, it } from "vitest";

import { activeNavigationHref, navigationGroups } from "./product-navigation";

describe("product navigation", () => {
  it("selects exactly one active destination for nested product routes", () => {
    const destinations = navigationGroups.flatMap((group) => group.items);

    for (const [pathname, expected] of [
      ["/workbench", "/workbench"],
      ["/runs/run-42", "/runs"],
      ["/artifacts/artifact-9", "/artifacts"],
      ["/media/sources/3", "/media"]
    ] as const) {
      const active = activeNavigationHref(pathname, destinations);
      expect(active).toBe(expected);
      expect(destinations.filter((item) => item.href === active)).toHaveLength(1);
    }
  });

  it("keeps the default product IA to four visible destinations", () => {
    expect(navigationGroups.find((group) => group.kind === "primary")?.items.map((item) => item.href)).toEqual([
      "/workbench",
      "/runs",
      "/library",
      "/artifacts"
    ]);
    expect(navigationGroups.find((group) => group.kind === "developer")?.collapsedByDefault).toBe(true);
  });
});
