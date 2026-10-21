# Citation Locator

Citation locators describe where evidence lives.

## Implemented Locator Types

- Document chunk locator.
- Page or heading-style document context where available.
- Image source detail locator.
- Audio timestamp locator.
- Video timestamp and frame locator.
- Code repository file and line locator.

## Why It Matters

RAG answers are only useful when the user can return to the evidence. A locator connects generated text back to a real source, chunk, transcript segment or media frame.

## Current Limitations

- V4.4 adds API/contract validation and optional browser E2E scaffolding for document, media and code citation jumps.
- Browser execution is optional and reports `skipped` when Playwright or browser binaries are not installed.
- Very rich document anchors still depend on parser metadata such as page number or Markdown heading path.

## Code Locator

```text
file_path
line_start
line_end
symbol_name
```
