#!/usr/bin/env python3
"""Frame, resize and compress docs images to the repo standard.

Standard (see skills/docs-images/SKILL.md):
  - max 2048 px wide, max 3200 px tall; larger images are downscaled
  - PNG: pngquant (lossy palette, quality 65-90) then oxipng (lossless)
  - JPEG: re-encoded at quality 85, progressive, metadata stripped
  - GIF: gifsicle -O3 (lossless frame optimisation)
  - SVG and other formats are left alone

Usage:
  python3 scripts/optimize-images.py            # optimise everything under images/
  python3 scripts/optimize-images.py path ...   # optimise the given files or folders
  python3 scripts/optimize-images.py --check    # exit 1 if any image needs work
  python3 scripts/optimize-images.py --frame CAPTURE.png images/screens/<platform>/<name>.png
      # composite a bare capture onto the gradient backdrop with even padding,
      # apply annotations from CAPTURE.json if present (or --spec FILE), write
      # it to the destination, then resize and compress it. The bare capture
      # and its spec are also copied to captures/<same path> for re-framing.

Annotation spec (JSON; all keys optional; rect = [x, y, w, h] in capture pixels):
  {
    "frame": {"padding": 0.07, "corner_radius": 24, "shadow": true},
    "dim": 0.5,                                        # default 0.5 when highlights exist, else 0
    "highlights": [{"rect": [x, y, w, h], "radius": 16, "ring": true}],
    "badges": [{"n": 1, "x": 100, "y": 200}],
    "arrows": [{"from": [x1, y1], "to": [x2, y2], "curve": 0.18}],
    "blurs": [{"rect": [x, y, w, h], "radius": 10, "strength": 12}],
    "ring_color": "#FFFFFF"
  }
Highlighted regions stay bright with a feathered edge and a thin ring; the rest
of the canvas drops behind the dim layer. Blurs soft-obscure a region (keys,
emails). Badges are numbered white circles. Arrows are curved white strokes
ending in a dot. Badges and arrows carry a soft shadow.

The script is idempotent. A file is rewritten only when it is oversized or
when re-compressing it saves more than TOLERANCE of its size. Re-running on
an already optimised tree changes nothing.

Requires: Pillow (pip install pillow), pngquant, oxipng. gifsicle is optional
and only needed for GIFs.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_WIDTH = 2048
MAX_HEIGHT = 3200
PNGQUANT_QUALITY = "65-90"
JPEG_QUALITY = 85
TOLERANCE = 0.10  # rewrite only if the new file is at least this much smaller

ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = ROOT / "images"
SUPPORTED = {".png", ".jpg", ".jpeg", ".gif"}

# Framing. Padding is a fraction of the capture's longer side, keyed by the
# platform folder the destination lives in (images/screens/<platform>/).
BACKDROP = ROOT / "scripts" / "backdrop.jpg"
CAPTURE_DIR = ROOT / "captures"  # bare captures, mirroring images/ so a screen can be re-framed later
FRAME_PADDING = {"mac": 0.07, "windows": 0.07, "dashboard": 0.05, "ios": 0.10, "android": 0.10}
FRAME_RADIUS = {"ios": 48, "android": 48}  # corner radius for opaque captures; others use 24
SHADOW_OFFSET, SHADOW_BLUR, SHADOW_ALPHA = 18, 36, 128

# Annotations (spec JSON next to the capture; coordinates in capture pixels).
FEATHER = 6        # highlight edge feather, px
BADGE_R = 26       # badge circle radius, px
ARROW_W = 7        # arrow stroke, px
RING_W = 2.5       # highlight ring stroke, px
STROKE = "#FFFFFF"
SS = 3             # supersampling factor for anti-aliased vector overlays
BADGE_FONT = "/System/Library/Fonts/SFNS.ttf"

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: pip install pillow")


def need(tool: str, optional: bool = False) -> str | None:
    path = shutil.which(tool)
    if path is None and not optional:
        sys.exit(f"{tool} is required but not on PATH. See skills/docs-images/SKILL.md")
    return path


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def fit(width: int, height: int) -> tuple[int, int] | None:
    """Return the downscaled size if the image exceeds the limits, else None."""
    scale = min(MAX_WIDTH / width, MAX_HEIGHT / height, 1.0)
    if scale >= 1.0:
        return None
    return max(1, round(width * scale)), max(1, round(height * scale))


def resize_raster(src: Path, dst: Path, size: tuple[int, int], fmt: str) -> None:
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("P", "1"):
            # Pillow silently uses NEAREST for palette images; convert first.
            im = im.convert("RGBA" if "transparency" in im.info else "RGB")
        elif im.mode == "LA":
            im = im.convert("RGBA")
        elif im.mode == "L":
            im = im.convert("RGB")
        im = im.resize(size, Image.LANCZOS)
        if fmt == "JPEG":
            im = im.convert("RGB")
            im.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        else:
            im.save(dst, "PNG", optimize=True)


def optimise_png(src: Path, tmp: Path) -> tuple[Path, bool]:
    with Image.open(src) as im:
        target = fit(*im.size)
    work = tmp / "work.png"
    if target:
        resize_raster(src, work, target, "PNG")
    else:
        shutil.copyfile(src, work)

    quant = tmp / "quant.png"
    res = run([
        "pngquant", "--quality", PNGQUANT_QUALITY, "--speed", "1", "--strip",
        "--force", "--skip-if-larger", "--output", str(quant), str(work),
    ])
    # exit 98 = larger than input, 99 = quality floor not met; keep lossless copy
    if res.returncode in (98, 99) or not quant.exists():
        quant = work
    elif res.returncode != 0:
        raise RuntimeError(f"pngquant failed: {res.stderr.strip()}")

    res = run(["oxipng", "-o", "4", "--strip", "safe", "-q", str(quant)])
    if res.returncode != 0:
        raise RuntimeError(f"oxipng failed: {res.stderr.strip()}")
    return quant, target is not None


def optimise_jpeg(src: Path, tmp: Path) -> tuple[Path, bool]:
    out = tmp / "out.jpg"
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)  # bake in EXIF rotation before metadata is stripped
        target = fit(*im.size)
        if target:
            resize_raster(src, out, target, "JPEG")
        else:
            im.convert("RGB").save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return out, target is not None


def optimise_gif(src: Path, tmp: Path) -> tuple[Path, bool]:
    if need("gifsicle", optional=True) is None:
        raise RuntimeError("gifsicle not installed; GIF skipped")
    with Image.open(src) as im:
        target = fit(*im.size)
    out = tmp / "out.gif"
    cmd = ["gifsicle", "-O3"]
    if target:
        cmd += ["--resize-fit", f"{MAX_WIDTH}x{MAX_HEIGHT}"]
    cmd += [str(src), "-o", str(out)]
    res = run(cmd)
    if res.returncode != 0:
        raise RuntimeError(f"gifsicle failed: {res.stderr.strip()}")
    return out, target is not None


HANDLERS = {".png": optimise_png, ".jpg": optimise_jpeg, ".jpeg": optimise_jpeg, ".gif": optimise_gif}


def load_spec(src: Path, spec_path: Path | None) -> dict:
    """Annotation spec: --spec FILE, else CAPTURE.json beside the capture, else empty."""
    path = spec_path or src.with_suffix(".json")
    if not path.is_file():
        return {}
    spec = json.loads(path.read_text())
    if not isinstance(spec, dict):
        raise SystemExit(f"{path}: spec must be a JSON object")
    return spec


def frame(src: Path, dst: Path, spec: dict | None = None) -> None:
    """Composite a bare capture onto the gradient backdrop with even padding,
    then apply annotations from the spec.

    Captures that carry their own alpha shadow (macOS window and browser-window
    captures) are pasted as-is. Fully opaque captures (phone screenshots,
    cropped regions) get rounded corners and a drop shadow. The spec's "frame"
    key overrides padding, corner_radius and shadow.
    """
    from PIL import ImageDraw, ImageFilter

    spec = spec or {}
    fr = spec.get("frame", {})
    platform = dst.parent.name
    with Image.open(src) as im:
        cap = ImageOps.exif_transpose(im).convert("RGBA")
    ww, wh = cap.size
    pad = fr.get("padding", FRAME_PADDING.get(platform, 0.07))
    pad = round(pad * max(ww, wh)) if pad <= 1 else int(pad)
    w, h = ww + 2 * pad, wh + 2 * pad

    with Image.open(BACKDROP) as bd:
        scale = max(w / bd.width, h / bd.height)  # cover the canvas, centred
        bd = bd.convert("RGB").resize((round(bd.width * scale), round(bd.height * scale)), Image.LANCZOS)
    x0, y0 = (bd.width - w) // 2, (bd.height - h) // 2
    canvas = bd.crop((x0, y0, x0 + w, y0 + h)).convert("RGBA")

    opaque = cap.getchannel("A").getextrema()[0] == 255
    radius = fr.get("corner_radius", FRAME_RADIUS.get(platform, 24) if opaque else 0)
    if fr.get("shadow", opaque):
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (pad, pad + SHADOW_OFFSET, pad + ww - 1, pad + wh - 1 + SHADOW_OFFSET), radius=radius, fill=(0, 0, 0, SHADOW_ALPHA))
        canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR)))
    if radius:
        mask = Image.new("L", (ww, wh), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, ww - 1, wh - 1), radius=radius, fill=255)
        cap.putalpha(ImageChops_multiply(cap.getchannel("A"), mask))
    canvas.alpha_composite(cap, (pad, pad))

    annotate(canvas, spec, pad, pad)

    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(dst, "PNG")


def ImageChops_multiply(a, b):
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


def _badge_font(size: int):
    from PIL import ImageFont
    try:
        f = ImageFont.truetype(BADGE_FONT, size)
        names = [n.decode() if isinstance(n, bytes) else n for n in f.get_variation_names()]
        if "Bold" in names:
            f.set_variation_by_name("Bold")
        return f
    except (OSError, AttributeError):
        return ImageFont.load_default(size)


def _overlay(canvas, draw_fn, shadow=(0, 3, 6, 0.55)) -> None:
    """Draw vector shapes anti-aliased (supersampled), with an optional soft shadow.

    draw_fn(draw, s) must draw at scale s. shadow = (dx, dy, blur, opacity) or None.
    """
    from PIL import ImageDraw, ImageFilter

    w, h = canvas.size
    layer = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), SS)
    layer = layer.resize((w, h), Image.LANCZOS)
    if shadow:
        dx, dy, blur, opacity = shadow
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sh.putalpha(layer.getchannel("A").point(lambda a: int(a * opacity)))
        shifted = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shifted.paste(sh.filter(ImageFilter.GaussianBlur(blur)), (dx, dy))
        canvas.alpha_composite(shifted)
    canvas.alpha_composite(layer)


def annotate(canvas, spec: dict, ox: int, oy: int) -> None:
    """Apply blurs, dim + highlights, rings, arrows and badges. ox/oy offset capture coords to canvas."""
    from PIL import ImageDraw, ImageFilter

    W, H = canvas.size
    for bl in spec.get("blurs", []):
        x, y, w, h = bl["rect"]
        r, strength = bl.get("radius", 10), bl.get("strength", 12)
        x, y, m = x + ox, y + oy, 3 * strength
        region = canvas.crop((x - m, y - m, x + w + m, y + h + m)).filter(ImageFilter.GaussianBlur(strength))
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
        canvas.paste(region.crop((m, m, m + w, m + h)), (x, y), mask)

    highlights = spec.get("highlights", [])
    dim = spec.get("dim", 0.5 if highlights else 0)
    if dim:
        mask = Image.new("L", (W, H), round(255 * dim))
        d = ImageDraw.Draw(mask)
        for hl in highlights:
            x, y, w, h = hl["rect"]
            d.rounded_rectangle((x + ox, y + oy, x + ox + w - 1, y + oy + h - 1), radius=hl.get("radius", 14), fill=0)
        black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        black.putalpha(mask.filter(ImageFilter.GaussianBlur(FEATHER)))
        canvas.alpha_composite(black)

    rings = [hl for hl in highlights if hl.get("ring", True)]
    if rings:
        color = spec.get("ring_color", STROKE)

        def draw_rings(d, s):
            for hl in rings:
                x, y, w, h = hl["rect"]
                d.rounded_rectangle(((x + ox) * s, (y + oy) * s, (x + ox + w) * s, (y + oy + h) * s),
                                    radius=hl.get("radius", 14) * s, outline=color, width=round(RING_W * s))
        _overlay(canvas, draw_rings)

    if spec.get("arrows"):
        def draw_arrows(d, s):
            for a in spec["arrows"]:
                (x0, y0), (x1, y1) = a["from"], a["to"]
                x0, y0, x1, y1 = x0 + ox, y0 + oy, x1 + ox, y1 + oy
                curve = a.get("curve", 0.18)
                cx, cy = (x0 + x1) / 2 - (y1 - y0) * curve, (y0 + y1) / 2 + (x1 - x0) * curve
                pts = [(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1) * s,
                        ((1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1) * s) for t in (i / 48 for i in range(49))]
                d.line(pts, fill=STROKE, width=round(ARROW_W * s), joint="curve")
                for (px, py), rr in ((pts[0], ARROW_W * s / 2), (pts[-1], ARROW_W * 1.6 * s)):
                    d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=STROKE)
        _overlay(canvas, draw_arrows)

    if spec.get("badges"):
        font = _badge_font(round(BADGE_R * 1.25 * SS))

        def draw_badges(d, s):
            for b in spec["badges"]:
                bx, by, r = (b["x"] + ox) * s, (b["y"] + oy) * s, BADGE_R * s
                d.ellipse((bx - r, by - r, bx + r, by + r), fill=STROKE)
                d.text((bx, by), str(b["n"]), font=font, fill="#111111", anchor="mm")
        _overlay(canvas, draw_badges)


def keep_capture(src: Path, dst: Path, spec_path: Path | None) -> None:
    """Copy the bare capture (and its spec) to captures/, mirroring the destination's path under images/."""
    dst = dst.resolve()
    if not dst.is_relative_to(IMAGE_DIR):
        return
    raw = CAPTURE_DIR / dst.relative_to(IMAGE_DIR)
    raw.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != raw:
        shutil.copyfile(src, raw)
        print(f"capture    kept as {raw.relative_to(ROOT)}")
    spec_src = spec_path or src.with_suffix(".json")
    spec_dst = raw.with_suffix(".json")
    if spec_src.is_file() and spec_src.resolve() != spec_dst:
        shutil.copyfile(spec_src, spec_dst)
        print(f"spec       kept as {spec_dst.relative_to(ROOT)}")


def collect(args: list[str]) -> list[Path]:
    roots = [Path(a) for a in args] if args else [IMAGE_DIR]
    files: list[Path] = []
    for r in roots:
        if r.is_dir():
            files += [p for p in sorted(r.rglob("*")) if p.suffix.lower() in SUPPORTED]
        elif r.is_file() and r.suffix.lower() in SUPPORTED:
            files.append(r)
    return files


def process(path: Path, check: bool) -> tuple[str, int, int]:
    """Return (status, before, after). status: ok | resized | compressed | needs-work | error"""
    before = path.stat().st_size
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        try:
            out, resized = HANDLERS[path.suffix.lower()](path, tmp)
        except RuntimeError as e:
            print(f"  ! {path}: {e}", file=sys.stderr)
            return "error", before, before
        after = out.stat().st_size
        smaller = after < before * (1 - TOLERANCE)
        if not resized and not smaller:
            return "ok", before, before
        if check:
            return "needs-work", before, after
        shutil.copyfile(out, path)
        return ("resized" if resized else "compressed"), before, after


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", help="files or folders (default: images/)")
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if any image needs work")
    ap.add_argument("--frame", action="store_true",
                    help="paths are CAPTURE DEST: frame CAPTURE onto the backdrop at DEST, then optimise DEST")
    ap.add_argument("--spec", type=Path, help="annotation spec JSON for --frame (default: CAPTURE.json beside the capture)")
    ns = ap.parse_args()

    need("pngquant")
    need("oxipng")

    if ns.frame:
        if len(ns.paths) != 2:
            ap.error("--frame needs exactly two paths: CAPTURE DEST")
        src, dst = Path(ns.paths[0]), Path(ns.paths[1])
        if not src.is_file():
            ap.error(f"capture not found: {src}")
        if dst.suffix.lower() != ".png":
            ap.error("DEST must be a .png")
        if ns.spec and not ns.spec.is_file():
            ap.error(f"spec not found: {ns.spec}")
        frame(src, dst, load_spec(src, ns.spec))
        keep_capture(src, dst, ns.spec)
        ns.paths = [str(dst)]

    files = collect(ns.paths)
    if not files:
        print("no images found")
        return 0

    rel = lambda p: str(p.resolve().relative_to(ROOT)) if p.resolve().is_relative_to(ROOT) else str(p)
    total_before = total_after = 0
    flagged: list[str] = []
    for f in files:
        status, before, after = process(f, ns.check)
        total_before += before
        total_after += after
        if status == "ok":
            continue
        if status in ("needs-work", "error"):
            flagged.append(rel(f))
        print(f"{status:<10} {before/1024:8.0f} KB -> {after/1024:7.0f} KB  {rel(f)}")

    print(f"\n{len(files)} images, {total_before/1024/1024:.1f} MB -> {total_after/1024/1024:.1f} MB")
    if ns.check and flagged:
        print(f"\n{len(flagged)} image(s) need optimising. Run: python3 scripts/optimize-images.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
