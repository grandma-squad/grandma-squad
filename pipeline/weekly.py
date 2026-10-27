"""Weekend compilation: joins the week's Shorts into one long 16:9 video for review."""
import argparse
import datetime as dt
import sys
import time

from . import render
from .common import (MOCK, WORK, download_asset, load_manifest, log, settings, today, update_item,
                     upload_assets)


def fmt(secs):
    m, s = divmod(int(secs), 60)
    return f"{m}:{s:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="any day in the week (default today)")
    ap.add_argument("--include-unpublished", action="store_true")
    a = ap.parse_args()
    end = dt.date.fromisoformat(a.date) if a.date else today()
    start = end - dt.timedelta(days=6)
    iso = end.isocalendar()
    week_id = f"week-{iso.year}-W{iso.week:02d}"
    work = WORK / week_id
    render.clean(work)
    work.mkdir(parents=True, exist_ok=True)

    parts = []
    for i in range(7):
        day_id = (start + dt.timedelta(days=i)).isoformat()
        for it in sorted(load_manifest(day_id)["items"], key=lambda x: str(x["slot"])):
            ok = it.get("status") == "published" or (
                a.include_unpublished and it.get("status") == "review")
            if not ok or not it.get("video_file"):
                continue
            d = work / day_id
            if MOCK:
                src = WORK / day_id / f"slot{it['slot']}"
                video, post = src / it["video_file"], src / it["poster_file"]
            else:
                video = download_asset(day_id, it["video_file"], d)
                post = download_asset(day_id, it["poster_file"], d)
            parts.append({"video": video, "title": it["title"], "grandma": it.get("grandma_name", ""),
                          "poster_src": post})
    if len(parts) < 2:
        log("not enough approved videos this week for a compilation")
        sys.exit(0)

    s = settings()
    title = f"Grandma Squad Week {iso.week}: {len(parts)} Amazing Things to Learn! 👵✨"[:95]
    update_item(week_id, "weekly", kind="weekly", status="generating", title=title, error="")
    try:
        out = work / "weekly.mp4"
        chapters = render.render_weekly(parts, work, out, f"{len(parts)} amazing things this week!")
        thumb = render.thumbnail_wide(parts[0]["poster_src"], f"{len(parts)} amazing things this week!",
                                      work / "weekly.jpg")
        urls = upload_assets(week_id, [out, thumb])
        chap_txt = "\n".join(f"{fmt(t)} {label}" for t, label in chapters)
        description = (f"A whole week of fun facts and life lessons from the {s['channel_name']}: "
                       f"five grandmas who share one amazing thing every day.\n\nChapters:\n{chap_txt}\n\n"
                       + " ".join(h for h in s["default_hashtags"] if h != "#Shorts"))
        v = int(time.time())
        update_item(week_id, "weekly", kind="weekly", status="review", title=title,
                    grandma_name="All five grandmas", description=description,
                    tags=["kids learning", "fun facts for kids", "grandma", "science for kids", "compilation"],
                    caption=f"A whole week with the Grandma Squad 👵✨\n\n#GrandmaSquad #KidsLearning",
                    video_url=urls[out.name] + f"?v={v}", poster_url=urls[thumb.name] + f"?v={v}",
                    video_file=out.name, poster_file=thumb.name, wide=True,
                    duration=round(render.duration(out), 1), youtube={}, instagram={})
    except Exception as e:  # noqa: BLE001
        update_item(week_id, "weekly", kind="weekly", status="failed", error=str(e)[:500])
        raise


if __name__ == "__main__":
    main()
