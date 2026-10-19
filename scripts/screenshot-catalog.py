#!/usr/bin/env python3
"""Keep the screenshot catalog in captures/ in step with the docs.

Two files, both CSV:

  captures/screenshot-catalog.csv   one row per screenshot, shipped or planned
  captures/page-catalog.csv         one row per page that shows or plans one

The screenshot catalog mixes two kinds of column. `status`, `priority`, and
`notes` are written by hand. Every other column is derived from the repo and
rewritten on each run. The page catalog is derived entirely.

A planned screenshot is a marker in a page, where the image will go:

  {/* IMAGE: images/screens/mac/meetings-tab.png | Meetings tab with a few meetings */}

Replace the marker with the <img> tag once the shot exists.

Usage:
  python3 scripts/screenshot-catalog.py           rewrite both catalogs
  python3 scripts/screenshot-catalog.py --check   exit 1 if either is stale
"""

import csv
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "captures" / "screenshot-catalog.csv"
PAGES = ROOT / "captures" / "page-catalog.csv"
CATALOGED = ("images/screens/", "images/enterprise/")
STATUSES = ("current", "reshoot", "restyle", "new", "check")
DONE = "current"

SHOT_FIELDS = ["image", "platform", "status", "priority", "pages", "alt",
               "bare_capture", "annotated", "notes"]
PAGE_FIELDS = ["page", "images", "planned", "to_do"]

IMG_SRC = re.compile(r'(?:src="|\]\()/(images/[^")\s]+)')
IMG_TAG = re.compile(r"<img\b[^>]*?>", re.S)
ALT = re.compile(r'alt="([^"]*)"')
MARKER = re.compile(r"\{/\*\s*IMAGE:\s*(images/\S+)\s*\|\s*(.*?)\s*\*/\}")


def scan_pages():
    """Map each image to the pages that show it or plan it, plus its alt text."""
    shown, planned, alts = {}, {}, {}
    for mdx in sorted(ROOT.rglob("*.mdx")):
        if "node_modules" in mdx.parts:
            continue
        page = mdx.relative_to(ROOT).as_posix()
        text = mdx.read_text()
        for image in IMG_SRC.findall(text):
            shown.setdefault(image, set()).add(page)
        for tag in IMG_TAG.findall(text):
            src, alt = IMG_SRC.search(tag), ALT.search(tag)
            if src and alt:
                alts.setdefault(src.group(1), alt.group(1))
        for image, description in MARKER.findall(text):
            planned.setdefault(image, set()).add(page)
            alts.setdefault(image, description)
    return shown, planned, alts


def platform(image):
    """images/screens/<platform>/x.png, images/enterprise/x.png, or a loose file."""
    parts = image.split("/")
    if parts[1] == "screens":
        return parts[2] if len(parts) > 3 else "other"
    return parts[1]


def build():
    shown, planned, alts = scan_pages()
    rows = {}
    if SHOTS.exists():
        for row in csv.DictReader(SHOTS.open()):
            rows[row["image"]] = row

    on_disk = {
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "images").rglob("*")
        if p.is_file() and p.relative_to(ROOT).as_posix().startswith(CATALOGED)
    }
    problems = []
    for image in on_disk | set(planned):
        if image not in rows:
            rows[image] = {"image": image, "status": "new" if image in planned and image not in on_disk else "check"}
    for image, row in sorted(rows.items()):
        exists = image in on_disk
        if not exists and image not in planned and row.get("status") != "new":
            problems.append(f"{image}: no file and no page plans it. Delete the row or mark it new.")
        if row.get("status") not in STATUSES:
            problems.append(f"{image}: status {row.get('status')!r} is not one of {', '.join(STATUSES)}")
        if exists and row.get("status") == "new":
            problems.append(f"{image}: the file exists but the status is still new")
        capture = ROOT / "captures" / Path(image).relative_to("images")
        row.update(
            platform=platform(image),
            pages=";".join(sorted(shown.get(image, set()) | planned.get(image, set()))),
            alt=alts.get(image, row.get("alt", "")),
            bare_capture="y" if capture.exists() else "n",
            annotated="y" if capture.with_suffix(".json").exists() else "n",
        )

    page_rows = {}
    for image, row in rows.items():
        for page in filter(None, row["pages"].split(";")):
            entry = page_rows.setdefault(page, {"page": page, "images": [], "planned": [], "to_do": 0})
            name = Path(image).name
            (entry["images"] if image in shown and page in shown[image] else entry["planned"]).append(name)
            if row["status"] != DONE:
                entry["to_do"] += 1
    for entry in page_rows.values():
        entry["images"] = ";".join(sorted(entry["images"]))
        entry["planned"] = ";".join(sorted(entry["planned"]))

    shots = sorted(rows.values(), key=lambda r: (r["platform"], r["image"]))
    pages = sorted(page_rows.values(), key=lambda r: r["page"])
    return render(SHOT_FIELDS, shots), render(PAGE_FIELDS, pages), problems, shots


def render(fields, rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main():
    check = "--check" in sys.argv[1:]
    shots_csv, pages_csv, problems, shots = build()
    stale = [p for p, text in ((SHOTS, shots_csv), (PAGES, pages_csv))
             if not p.exists() or p.read_text() != text]
    if check:
        for path in stale:
            print(f"stale: {path.relative_to(ROOT)}. Run python3 scripts/screenshot-catalog.py")
    else:
        SHOTS.write_text(shots_csv)
        PAGES.write_text(pages_csv)
    for problem in problems:
        print(f"problem: {problem}")
    counts = {}
    for row in shots:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print("screenshots: " + ", ".join(f"{counts[s]} {s}" for s in STATUSES if s in counts))
    sys.exit(1 if problems or (check and stale) else 0)


if __name__ == "__main__":
    main()
