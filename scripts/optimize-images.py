#!/usr/bin/env python3
"""Resize and compress every image under images/ to the docs standard.

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

The script is idempotent. A file is rewritten only when it is oversized or
when re-compressing it saves more than TOLERANCE of its size. Re-running on
an already optimised tree changes nothing.

Requires: Pillow (pip install pillow), pngquant, oxipng. gifsicle is optional
and only needed for GIFs.
"""

from __future__ import annotations

import argparse
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

try:
    from PIL import Image
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
    ns = ap.parse_args()

    need("pngquant")
    need("oxipng")

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
