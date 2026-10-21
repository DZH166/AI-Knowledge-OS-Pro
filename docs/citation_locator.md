# Citation Locator

Citation locators describe where evidence lives.

## Implemented Locator Types

- Document chunk locator.
- Page or heading-style document context where available.
- Image source detail locator.
- Audio timestamp locator.
- Video timestamp and frame locator.

## Why It Matters

RAG answers are only useful when the user can return to the evidence. A locator connects generated text back to a real source, chunk, transcript segment or media frame.

## Current Limitations

- Browser-level validation for every locator type is still limited.
- Code repository locators with file path and line ranges are planned for V4.0.

## Planned Code Locator

```text
file_path
line_start
line_end
symbol_name
```
