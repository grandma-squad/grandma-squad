"""Create the day's Shorts (or redo one slot) and put them up for review.

Usage:
  python -m pipeline.generate_day                       # today's batch
  python -m pipeline.generate_day --date 2026-10-28 --slots 2 --note "make it about rain"
"""
import argparse
import datetime as dt
import random
import sys
import time
import traceback

from . import ai, render, script_writer, tts
from .common import (ASSETS, WORK, character, characters, git_commit_push, load_manifest, log,
                     settings, today, update_item, upload_assets)


def grandma_for(day, slot):
    chars = characters()
    return chars[(day.toordinal() * 3 + slot - 1) % len(chars)]


def ensure_reference(char):
    ref = ASSETS / "characters" / f"{char['id']}.png"
    if not ref.exists():
        log("creating reference portrait for", char["name"])
        ai.image(f"{settings().get('visual_style', '')}. Character portrait of {char['look']}, "
                 "smiling warmly at the camera, upper body, softly blurred cozy home background", ref, aspect="3:4", seed=sum(map(ord, char["id"])) * 97,
                 mock_label=char["name"])
        git_commit_push([ref], f"reference portrait: {char['name']}")
    return ref


def make_video(day_id, slot, char, note=""):
    s = settings()
    work = WORK / day_id / f"slot{slot}"
    render.clean(work)
    work.mkdir(parents=True, exist_ok=True)
    ref = ensure_reference(char)

    story = script_writer.write(char, note=note, seed=random.randint(1, 10**9), slot=slot)
    log(f"slot {slot}: {story['title']}")
    colors = [(244, 196, 140), (170, 210, 235), (190, 225, 170), (240, 180, 190), (215, 195, 240)]
    scenes = []
    for i, sc in enumerate(story["scenes"]):
        img = ai.image(sc["image_prompt"], work / f"scene{i}.png", refs=[ref], aspect="9:16",
                       mock_label=f"{char['kid_name']} · scene {i + 1}", mock_color=colors[i % 5])
        audio = tts.speak(sc["narration"], char, work / f"voice{i}.mp3")
        scenes.append({"image": img, "audio": audio, "narration": sc["narration"],
                       "label": str(sc.get("on_screen", ""))[:40]})

    video = work / f"slot{slot}.mp4"
    secs = render.render_short(scenes, story["title"], work, video)
    poster = render.poster(scenes[0]["image"], story["title"], work / f"slot{slot}.jpg")
    urls = upload_assets(day_id, [video, poster])

    tags = [t.strip("#") for t in story.get("tags", [])][:15]
    hashtags = " ".join(story.get("mission_hashtags", []) + s["default_hashtags"])
    note = ""
    if story.get("mission") in ("HEALTH TIP", "EXERCISE"):
        note = ("\n\nThis video shares general wellness information, not medical advice. "
                "Please check with your doctor before starting new exercises or if you have a health condition.")
    description = (f"{story.get('description', '')}\n\n"
                   f"Today's grandma wisdom: {story.get('fact', '')}{note}\n\n"
                   f"Meet {char['name']} and the {s['channel_name']}: grandmothers from every corner of the world "
                   f"sharing recipes, health tips and gentle exercises every day.\n\n{hashtags}")
    caption = f"{story.get('instagram_caption', story['title'])}\n\n{hashtags}"
    v = int(time.time())
    item = update_item(
        day_id, slot,
        status="review", grandma=char["id"], grandma_name=char["name"],
        title=story["title"], topic=story.get("topic", ""), fact=story.get("fact", ""),
        activity=story["activity"], topic_type=story["topic_type"], mission=story.get("mission", ""),
        narration=[sc["narration"] for sc in story["scenes"]],
        description=description, tags=tags, caption=caption,
        video_url=urls[video.name] + f"?v={v}", poster_url=urls[poster.name] + f"?v={v}",
        video_file=video.name, poster_file=poster.name, duration=round(secs, 1),
        youtube={}, instagram={}, error="",
    )
    script_writer.add_history({"date": day_id, "slot": slot, "grandma": char["id"], "title": story["title"],
                               "fact": story.get("fact", ""), "activity": story["activity"],
                               "topic_type": story["topic_type"]})
    git_commit_push([script_writer.HISTORY], f"history: {story['title']}")
    return item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--slots", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    day = dt.date.fromisoformat(a.date) if a.date else today()
    day_id = day.isoformat()
    n = settings()["videos_per_day"]
    slots = [int(x) for x in a.slots.split(",") if x.strip()] or list(range(1, n + 1))

    existing = {str(i["slot"]): i for i in load_manifest(day_id)["items"]}
    failures = 0
    for slot in slots:
        prev = existing.get(str(slot), {})
        if not a.slots and prev.get("status") in ("review", "published", "publishing"):
            log(f"slot {slot} already done, skipping")
            continue
        char = character(prev["grandma"]) if prev.get("grandma") else grandma_for(day, slot)
        update_item(day_id, slot, status="generating", grandma=char["id"], grandma_name=char["name"],
                    error="", note=a.note)
        try:
            make_video(day_id, slot, char, note=a.note)
        except Exception as e:  # noqa: BLE001
            failures += 1
            traceback.print_exc()
            update_item(day_id, slot, status="failed", error=str(e)[:500])
    if failures == len(slots):
        sys.exit(1)


if __name__ == "__main__":
    main()
