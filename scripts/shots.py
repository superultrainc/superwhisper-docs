#!/usr/bin/env python3
"""Keep Mac app screenshots in step with the installed Superwhisper build.

Manifest: captures/shots.json. One entry per screenshot that needs the app in a
known state: how to reach that state, what demo data it needs, and the app
version it was last shot on. The shot list itself stays in
captures/screenshot-catalog.csv. This file adds the "how" and the "when".

Usage:
  scripts/shots.py stale              shots not taken on the installed version
  scripts/shots.py show IMAGE         steps and demo data for one shot
  scripts/shots.py windows            Superwhisper windows on screen, with ids
  scripts/shots.py capture IMAGE [--window-id N] [--popup]
                                      capture a window, frame it, stamp the version
  scripts/shots.py seed               add manifest entries for catalog rows with none

`capture` runs: screencapture -x -l <id>, then optimize-images.py --frame,
then records version and date. Reach the screen first (an agent or a person).
It does not edit pages or the catalog status. Set status to current by hand.
"""
import argparse, csv, json, subprocess, sys, tempfile, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "captures" / "shots.json"
CATALOG = ROOT / "captures" / "screenshot-catalog.csv"
APP = Path("/Applications/superwhisper.app/Contents/Info.plist")

JXA = r"""
ObjC.import('CoreGraphics');
var l=ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(1|16,0)));
JSON.stringify(l.filter(w=>/superwhisper/i.test(w.kCGWindowOwnerName)&&w.kCGWindowLayer==0)
 .map(w=>({id:w.kCGWindowNumber,pid:w.kCGWindowOwnerPID,title:w.kCGWindowName||"",w:w.kCGWindowBounds.Width,h:w.kCGWindowBounds.Height})))
"""


def app_version() -> str:
    out = subprocess.run(["defaults", "read", str(APP.with_suffix("")), "CFBundleShortVersionString"],
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit("superwhisper.app not found in /Applications")
    return out.stdout.strip()


def windows() -> list[dict]:
    out = subprocess.run(["osascript", "-l", "JavaScript", "-e", JXA], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


DRIVER = "/Applications/CuaDriver.app/Contents/MacOS/cua-driver"


def driver_capture(wid: int, out: Path) -> None:
    """Fallback when screencapture -l fails (agent shells): window-only PNG via cua-driver."""
    import base64
    pid = next((w["pid"] for w in windows() if w["id"] == wid), None)
    args = {"window_id": wid, "capture_mode": "vision"}
    if pid:
        args["pid"] = pid
    r = subprocess.run([DRIVER, "call", "get_window_state", json.dumps(args)], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout[r.stdout.index("{"):])
        out.write_bytes(base64.b64decode(j["screenshot_png_b64"]))
    except Exception as e:
        sys.exit(f"capture failed (screencapture and cua-driver): {e}")


def popup_capture(wid: int, out: Path) -> None:
    """Window plus any open popup/menu: grab the screen region over the window,
    then reuse the alpha (rounded corners) of the window-only capture as a mask.
    The grab is cropped to the window bounds, so nothing outside it is kept.
    Bring the window to the front and open the popup first. The window must be unobscured."""
    import base64, io
    from PIL import Image
    w = next((w for w in windows() if w["id"] == wid), None)
    if not w:
        sys.exit("window not found")
    b = json.loads(subprocess.run([DRIVER, "call", "list_windows", "{}"], capture_output=True, text=True).stdout)["windows"]
    b = next(x["bounds"] for x in b if x["window_id"] == wid)
    reg = f'{int(b["x"])},{int(b["y"])},{int(b["width"])},{int(b["height"])}'
    # grab first: any driver call after the popup opens can dismiss it
    subprocess.run(["screencapture", "-x", "-R", reg, str(out)], check=True)
    base = out.with_name("base.png"); driver_capture(wid, base)
    mask = Image.open(base).convert("RGBA").getchannel("A")
    im = Image.open(out).convert("RGBA")
    if im.size != mask.size:
        mask = mask.resize(im.size)
    im.putalpha(mask); im.save(out)


def load() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def save(m: dict) -> None:
    MANIFEST.write_text(json.dumps(dict(sorted(m.items())), indent=2) + "\n")


def catalog() -> dict:
    with CATALOG.open() as f:
        return {r["image"]: r for r in csv.DictReader(f)}


def cmd_seed(_):
    m, cat = load(), catalog()
    added = 0
    for img, row in cat.items():
        if row["platform"] != "mac" or img in m:
            continue
        m[img] = {"steps": row["notes"], "demo_data": "", "app_version": "", "captured": ""}
        added += 1
    save(m)
    print(f"added {added}, total {len(m)}")


def cmd_stale(ns):
    ver, m, cat = app_version(), load(), catalog()
    rows = []
    for img, e in m.items():
        status = cat.get(img, {}).get("status", "?")
        if e.get("app_version") != ver:
            rows.append((status, img, e.get("app_version") or "never"))
    for status, img, v in sorted(rows):
        print(f"{status:<8} {v:<8} {img}")
    print(f"\ninstalled {ver}: {len(rows)} of {len(m)} shots not taken on this version")


def cmd_show(ns):
    e = load().get(ns.image)
    if not e:
        sys.exit(f"not in manifest: {ns.image}")
    print(json.dumps(e, indent=2))


def cmd_windows(_):
    for w in windows():
        print(f"{w['id']}  {w['w']:.0f}x{w['h']:.0f}  {w['title']!r}")


def cmd_capture(ns):
    m = load()
    if ns.image not in m:
        sys.exit(f"not in manifest: {ns.image} (run seed)")
    wins = windows()
    if ns.window_id:
        wid = ns.window_id
    elif len(wins) == 1:
        wid = wins[0]["id"]
    else:
        sys.exit("expected one Superwhisper window, found %d. Pass --window-id (see `windows`)." % len(wins))
    with tempfile.TemporaryDirectory() as d:
        raw = Path(d) / "capture.png"
        if ns.popup:
            popup_capture(wid, raw)
        else:
            r = subprocess.run(["screencapture", "-x", "-l", str(wid), str(raw)], capture_output=True)
            if r.returncode or not raw.exists() or raw.stat().st_size == 0:
                driver_capture(wid, raw)
        subprocess.run([sys.executable, str(ROOT / "scripts/optimize-images.py"), "--frame", str(raw),
                        str(ROOT / ns.image)], check=True)
    m[ns.image].update(app_version=app_version(), captured=datetime.date.today().isoformat())
    save(m)
    print(f"captured {ns.image} on {m[ns.image]['app_version']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed").set_defaults(f=cmd_seed)
    p = sub.add_parser("stale"); p.set_defaults(f=cmd_stale)
    p = sub.add_parser("show"); p.add_argument("image"); p.set_defaults(f=cmd_show)
    sub.add_parser("windows").set_defaults(f=cmd_windows)
    p = sub.add_parser("capture"); p.add_argument("image"); p.add_argument("--window-id", type=int); p.add_argument("--popup", action="store_true", help="include open menus/popups"); p.set_defaults(f=cmd_capture)
    ns = ap.parse_args()
    ns.f(ns)


if __name__ == "__main__":
    main()
