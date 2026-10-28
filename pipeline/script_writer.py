"""Writes one short video script for a grandma, avoiding repeats."""
import random

from . import ai
from .common import DATA, load_json, save_json, settings

HISTORY = DATA / "history.json"
STYLE = ("photorealistic real-life photo, natural warm light, shallow depth of field, cinematic, "
         "vertical 9:16 composition with the subject in the upper two-thirds, family-friendly, "
         "no text, no logos, no watermark")


def history():
    return load_json(HISTORY, default=[])


def add_history(entry):
    h = history()
    h.append(entry)
    save_json(HISTORY, h[-400:])


def pick_activity_and_topic(char, rng):
    s = settings()
    recent = history()[-60:]
    used_acts = {h.get("activity") for h in recent if h.get("grandma") == char["id"]}
    acts = [a for a in s["activities"] if a not in used_acts] or s["activities"]
    recent_types = [h.get("topic_type") for h in recent[-6:]]
    types = [t for t in s["topic_types"] if t not in recent_types] or s["topic_types"]
    return rng.choice(acts), rng.choice(types)


def write(char, note="", seed=None, slot=1):
    s = settings()
    rng = random.Random(seed)
    activity, topic_type = pick_activity_and_topic(char, rng)
    recent_titles = [h["title"] for h in history()[-80:] if h.get("title")]
    n = s["scenes_per_video"]
    missions = s.get("missions", {})
    mission = missions.get(str((int(slot) - 1) % max(len(missions), 1) + 1), {"name": "THINK", "goal": "a surprising fact"})
    prompt = f"""
You write scripts for "{s['channel_name']}", a YouTube Shorts and Instagram Reels channel for {s['audience']}.
Five naughty, funny, big-hearted grandmothers from different cultures. In every video one of them does
something real-life and a little mischievous that makes the world THINK, LAUGH or PROTECT.

Today's grandma: {char['name']} (kids call her "{char['kid_name']}"), {char['heritage']} heritage.
Personality: {char['personality']}.
Activity in this video: {activity}.
Today's mission: {mission['name']} — {mission['goal']}.
Topic type: {topic_type}. Connect the topic naturally to the activity.
{('Extra instruction from the producer: ' + note) if note else ''}

Do NOT repeat any of these recent titles or their facts: {recent_titles}

Rules:
- Exactly {n} scenes. EACH scene's narration is 2 full sentences, 14 to 22 words.
  Total narration 75 to 100 words (about 35 seconds spoken). Short one-line scenes are NOT acceptable.
- Scene 1 is a hook question that makes anyone, child or adult, curious. Last scene ends with a cheerful sign-off
  that invites viewers to come back tomorrow (vary the wording).
- Clear, simple words everyone can follow. Short sentences. Warm, witty, playful grandma voice, first person.
- Pick facts that surprise adults too, not only children.
- The fact must be specific, scientifically accurate and widely documented (the kind found in an
  encyclopedia). Explain the "why" or "how" in plain words. No vague claims, no made-up numbers or statistics.
- Family-friendly and safe to copy: seatbelts in cars, helmets on bikes, life jackets near water, adults handle
  stoves and sharp tools. Never show or suggest anything dangerous a child might copy.
- Mischief is always harmless and kind: nobody gets hurt, humiliated or scared for real.
- Portray the grandma's culture respectfully and naturally. No accents written into the text, no stereotypes.
- image_prompt: describe ONE photorealistic real-life moment for that scene, always including the grandma
  doing the activity, her expression, the setting, the camera angle. Do not describe her face details
  (a reference photo is used). Never include text or signs in the image.

Return JSON only, with this shape:
{{
  "title": "catchy YouTube title under 70 characters, include one emoji",
  "topic": "2 to 5 word topic",
  "fact": "the core fact in one plain sentence",
  "scenes": [{{"narration": "what grandma says", "image_prompt": "..."}}],
  "description": "2 to 3 sentence YouTube description, ending with a question that invites comments",
  "tags": ["8 to 12 short tags"],
  "instagram_caption": "friendly caption, 1 to 3 short lines, 2 emojis max"
}}
"""
    mock = {
        "title": f"Why is the sea salty? 🌊 {char['kid_name']} explains",
        "topic": "salty sea",
        "fact": "Rain slowly washes tiny bits of salt from rocks into rivers, and rivers carry it to the sea.",
        "scenes": [
            {"narration": "Have you ever tasted the sea? Why is it so salty?", "image_prompt": "at the beach"},
            {"narration": "When rain falls on rocks, it washes away tiny, tiny bits of salt.", "image_prompt": "rocks"},
            {"narration": "Rivers carry that salt all the way to the sea, day after day.", "image_prompt": "river"},
            {"narration": "The sun dries up some water, but the salt stays behind!", "image_prompt": "sun"},
            {"narration": "So the sea keeps its salt. Come back tomorrow for another surprise, little friends!",
             "image_prompt": "waving"},
        ][:n],
        "description": "A gentle fact about the ocean. What should Grandma explore next?",
        "tags": ["kids", "science", "ocean"],
        "instagram_caption": "Why is the sea salty? 🌊",
    }
    story, scenes = None, []
    for attempt in range(4):
        story = ai.text_json(prompt, mock_result=mock)
        scenes = story.get("scenes", [])[:n]
        words = sum(len(str(sc.get("narration", "")).split()) for sc in scenes)
        if len(scenes) >= 4 and (words >= 60 or story is mock):
            break
        prompt += (f"\n\nYour last answer had {len(scenes)} scenes and only {words} words. "
                   f"Write exactly {n} scenes with 2 full sentences each, 75 to 100 words in total.")
    if len(scenes) < 3:
        raise RuntimeError("script came back with too few scenes")
    for sc in scenes:
        sc["image_prompt"] = (f"{char['look']}. {sc['image_prompt']}. {STYLE}")
    story["scenes"] = scenes
    story["activity"] = activity
    story["topic_type"] = topic_type
    story["mission"] = mission["name"]
    story["title"] = story.get("title", "Grandma Squad")[:95]
    return story
