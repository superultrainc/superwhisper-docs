---
name: docs-images
description: Add, replace, or optimise images in the Superwhisper docs repo. Use whenever a screenshot, diagram, GIF, or any file under images/ is added or changed, or when asked to check image sizes, compress images, or fix a failing "Images" CI check.
---

# Docs images

Every raster image committed to this repo must pass `scripts/optimize-images.py --check`.
CI runs that check on every pull request, scoped to the images the PR added or
changed. Run the optimiser before you commit and the check never fails.

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

1. Pick the destination path (see Layout below). Use the existing name if you are
   replacing a screenshot, so page references keep working.
2. For a bare capture, frame and optimise in one step:
   ```
   python3 scripts/optimize-images.py --frame ~/Desktop/capture.png images/screens/mac/new-screen.png
   ```
   For an image that is already framed or needs no backdrop (diagrams, banners),
   copy it into place and optimise it:
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

## Annotations

To call out part of a screen, put a JSON spec beside the capture with the same
name (`capture.json` next to `capture.png`) or pass `--spec FILE`. `--frame` applies
it and copies it to `captures/` with the raw. Coordinates are in capture pixels
(the 2x capture, before framing). Get them by viewing the capture, not the rendered
image. All keys are optional.

```json
{
  "highlights": [{"rect": [x, y, w, h], "radius": 16, "ring": true}],
  "dim": 0.5,
  "badges": [{"n": 1, "x": 100, "y": 200}],
  "arrows": [{"from": [x1, y1], "to": [x2, y2], "curve": 0.18}],
  "blurs": [{"rect": [x, y, w, h], "radius": 10, "strength": 12}],
  "frame": {"padding": 0.07, "corner_radius": 24, "shadow": true}
}
```

- **highlights** keep a region bright with a feathered edge and a thin white ring;
  everything else drops behind the dim layer. `dim` defaults to 0.5 when highlights
  exist. Set `"ring": false` to cut a region out of the dim without drawing a ring.
- **badges** are numbered white circles. Place one per step, in reading order.
- **arrows** are curved white strokes ending in a dot. `curve` bends them; 0 is straight.
- **blurs** soft-obscure a region such as a license key or email column.
- **frame** overrides the padding, corner radius, and shadow the platform folder implies.

Keep annotations in the spec, never baked into the capture. That is what lets a
screen be re-rendered when the UI, backdrop, or copy changes. To re-render every
annotated screen from its raw, loop over `captures/screens/*/*.png` with `--frame`.

## Layout

```
images/
  screens/<platform>/<screen-name>.png   product screenshots; platform is mac, windows, ios, android, dashboard
  enterprise/                            enterprise-only flows
  docs-banner-poster.jpg                 site assets
captures/
  screens/<platform>/<screen-name>.png   bare capture behind the image of the same path; written by --frame
  screens/<platform>/<screen-name>.json  its annotation spec, if any
```

`captures/` is not served and the optimiser never touches it. Every framed screenshot
should have its bare capture there under the same path.

Screen names are kebab-case and describe the screen, not the page that uses it
(`modes-editor-cloud.png`, not `custom-modes-figure-2.png`). Scrolled states get a
numeric suffix (`configuration-1.png`, `configuration-2.png`).

## Where screenshots come from

Capture the bare window at 2x (Retina), dark mode, default window size. Do not add
a backdrop or padding in the capture tool. Then frame it straight into place:

```
python3 scripts/optimize-images.py --frame ~/Desktop/capture.png images/screens/mac/new-screen.png
```

That one command composites the capture onto the standard gradient
(`scripts/backdrop.jpg`) with even padding, writes it to the destination, then
resizes and compresses it. It also copies the bare capture to `captures/` at the
same relative path, so the screen can be re-framed later without a re-shoot.
Commit both files. Padding follows the platform folder in the destination
path. macOS window and browser captures keep their own shadow and corners; phone
screenshots and cropped regions get rounded corners and a drop shadow. Never commit
a raw capture. If a screenshot shows real names, paths, or dictations, re-shoot it
with demo data.

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
