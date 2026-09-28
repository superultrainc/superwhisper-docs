---
name: docs-images
description: Add, replace, or optimise images in the Superwhisper docs repo. Use whenever a screenshot, diagram, GIF, or any file under images/ is added or changed, or when asked to check image sizes, compress images, or fix a failing "Images" CI check.
---

# Docs images

Every raster image committed to this repo must pass `scripts/optimize-images.py --check`.
CI runs that check on every pull request that touches `images/`. Run the optimiser
before you commit and the check never fails.

## Standard

| Rule | Value |
|---|---|
| Max width | 2048 px |
| Max height | 3200 px |
| PNG | pngquant, quality 65-90, then oxipng level 4, metadata stripped |
| JPEG | quality 85, progressive, metadata stripped |
| GIF | gifsicle `-O3` |
| SVG | untouched |

Screenshots are rendered at 2x (Retina). 2048 px wide is more than 2x the widest content
column Mintlify renders, so nothing is lost on screen. Phone screenshots are tall
and narrow, which is why the height limit is separate.

## Procedure

1. Put the file in the right folder (see Layout below). Use the existing name if you
   are replacing a screenshot, so page references keep working.
2. Run the optimiser on what you added:
   ```
   python3 scripts/optimize-images.py images/screens/mac/new-screen.png
   ```
   With no arguments it walks all of `images/`. It is safe to re-run; already
   optimised files are left alone.
3. Reference the image from the page with a root-relative path:
   ```mdx
   <Frame>
     <img src="/images/screens/mac/new-screen.png" alt="Describe what the reader should see" />
   </Frame>
   ```
   Widths, if needed, are percentages (`width="50%"`), never pixels.
4. Confirm before committing:
   ```
   python3 scripts/optimize-images.py --check
   ```
   Exit code 0 means every image is compliant.

## Layout

```
images/
  screens/<platform>/<screen-name>.png   product screenshots; platform is mac, windows, ios, android, dashboard
  enterprise/                            enterprise-only flows
  docs-banner-poster.jpg                 site assets
```

Screen names are kebab-case and describe the screen, not the page that uses it
(`modes-editor-cloud.png`, not `custom-modes-figure-2.png`). Scrolled states get a
numeric suffix (`configuration-1.png`, `configuration-2.png`).

## Where screenshots come from

Raw captures, annotation specs, and the render pipeline live outside this repo, in a
private folder, because captures can contain real names, paths, and dictations. The
pipeline produces framed 2x PNGs that are copied into `images/screens/` and then
optimised here. Never commit a raw capture. If a screenshot shows real user data,
re-shoot it with demo data.

## Tool setup

macOS:
```
brew install pngquant oxipng gifsicle
pip3 install pillow
```

Debian/Ubuntu:
```
sudo apt-get install pngquant gifsicle python3-pil
# oxipng: download a release from https://github.com/oxipng/oxipng/releases
```

The CI job in `.github/workflows/images.yml` shows the exact install steps.

## Failure modes

- **Check fails with `needs-work`**: run the optimiser without `--check`, commit the result.
- **Check fails with `error ... gifsicle not installed`**: install gifsicle or leave the GIF as is
  and ask a maintainer to optimise it.
- **pngquant quality floor not met**: the script falls back to lossless oxipng only. That is
  expected for images with gradients or photos. Nothing to fix.
- **A screenshot looks soft after optimising**: it was downscaled. Check the source was
  captured at 2x and not larger than 2048 px wide after framing.
