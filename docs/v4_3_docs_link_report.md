# V4.3 Docs Link Report

Generated at: 2026-07-04 Asia/Shanghai

## Scope

V4.3 adds executable documentation integrity checks so the GitHub README and major docs can be trusted by a reviewer following the project from the repository home page.

## Command

```powershell
python scripts/check_docs_links.py
```

## Result

Passed.

```text
docs_links=checked
files=88
local_links=45
local_images=7
mermaid_blocks=11
result=passed
```

## What Is Checked

- README and non-archived docs Markdown files.
- Local Markdown links.
- Local image targets.
- Mermaid code fences.
- Repository path escape attempts.

## Boundary

The script intentionally does not call external URLs. GitHub badge availability and remote CI status are validated by GitHub itself; this local gate focuses on broken local paths and missing repository assets.
