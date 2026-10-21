export type LibraryFilters = { query: string; spaceId: number; sourceType: string; view: "list" | "cards" };

export function libraryFiltersFromSearch(search: string): LibraryFilters {
  const params = new URLSearchParams(search);
  const space = Number(params.get("space_id"));
  return {
    query: (params.get("q") ?? "").slice(0, 200),
    spaceId: Number.isSafeInteger(space) && space > 0 ? space : 0,
    sourceType: params.get("type") ?? "",
    view: params.get("view") === "cards" ? "cards" : "list"
  };
}

export function libraryFiltersHref(search: string, filters: LibraryFilters): string {
  const params = new URLSearchParams(search);
  for (const [key, value] of [["q", filters.query], ["space_id", filters.spaceId ? String(filters.spaceId) : ""], ["type", filters.sourceType], ["view", filters.view === "cards" ? "cards" : ""]]) {
    if (value) params.set(key, value); else params.delete(key);
  }
  const query = params.toString();
  return `/library${query ? `?${query}` : ""}`;
}
