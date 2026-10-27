"""Builds the phone app website: the app itself plus recent videos (same address, so the
app can save/share them) and today.json for the iPhone Shortcut that saves videos to Photos."""
import json
import shutil
import subprocess
from pathlib import Path

from .common import DAYS, ROOT, load_json, log, release_tag, repo

SITE = ROOT / "_site"
KEEP_DAYS = 14


def main():
    shutil.rmtree(SITE, ignore_errors=True)
    shutil.copytree(ROOT / "docs", SITE)
    files = sorted(p.stem for p in DAYS.glob("*.json"))
    daily = [f for f in files if not f.startswith("week-")][-KEEP_DAYS:]
    weekly = [f for f in files if f.startswith("week-")][-2:]
    latest = None
    for day_id in daily + weekly:
        m = load_json(DAYS / f"{day_id}.json", {"items": []})
        names = [n for it in m["items"] if it.get("status") != "rejected"
                 for n in (it.get("video_file"), it.get("poster_file")) if n]
        if not names:
            continue
        out = SITE / "media" / day_id
        out.mkdir(parents=True, exist_ok=True)
        for n in names:
            r = subprocess.run(["gh", "release", "download", release_tag(day_id), "-p", n, "-D", str(out),
                                "--clobber"], cwd=ROOT, capture_output=True, text=True)
            if r.returncode != 0:
                log("could not copy", day_id, n, r.stderr[-200:])
        if not day_id.startswith("week-"):
            latest = (day_id, m)
    owner, name = repo().split("/")
    base = f"https://{owner.lower()}.github.io/{name}/"
    today = {"date": None, "videos": []}
    if latest:
        day_id, m = latest
        today["date"] = day_id
        for it in m["items"]:
            if it.get("video_file") and it.get("status") in ("review", "published"):
                today["videos"].append({
                    "slot": it["slot"], "grandma": it.get("grandma_name", ""), "title": it.get("title", ""),
                    "url": f"{base}media/{day_id}/{it['video_file']}",
                })
    (SITE / "today.json").write_text(json.dumps(today, indent=2, ensure_ascii=False))
    log("site built:", sum(1 for _ in SITE.rglob("*.mp4")), "videos")


if __name__ == "__main__":
    main()
