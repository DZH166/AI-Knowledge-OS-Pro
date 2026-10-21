# V4.3 README Asset Report

Generated at: 2026-07-04 Asia/Shanghai

## Scope

V4.3 validates the GitHub README media surface so a reviewer does not see broken local images, missing screenshot placeholders or an embedded demo GIF that has not been captured yet.

## Executable Check

```powershell
python scripts/check_readme_assets.py
```

The checker validates:

- Local README image paths stay inside the repository.
- Local README images use expected image suffixes.
- Required showcase screenshots exist under `docs/assets/screenshots/`.
- External badge images are counted but not downloaded.
- `docs/assets/demo/v4_3_demo_walkthrough.gif` is not embedded as an image until the file exists.

## Required Showcase Assets

| Asset | Status |
| --- | --- |
| `docs/assets/screenshots/dashboard.png` | Present |
| `docs/assets/screenshots/upload-center.png` | Present |
| `docs/assets/screenshots/knowledge-chat.png` | Present |
| `docs/assets/screenshots/media-library.png` | Present |
| `docs/assets/screenshots/video-detail.png` | Present |
| `docs/assets/screenshots/learning-archive.png` | Present |
| `docs/assets/screenshots/task-center.png` | Present |

## Current Result

- Local README images: 7.
- External badge images: 6.
- Required screenshots found: 7.
- Result: passed.

## Boundaries

- The check is intentionally local and deterministic; it does not call GitHub or download external badges.
- The demo GIF remains planned and is documented as a walkthrough target rather than embedded as a broken image.
- Screenshots use synthetic demo data and must not include secrets, user uploads, local absolute paths or private documents.

