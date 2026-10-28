"""Writes one short video script for a grandma, avoiding repeats.

Daily missions (config/settings.json): video 1 = ancient or quick traditional recipe,
video 2 = health tip, video 3 = simple exercise for older adults.
"""
import random

from . import ai
from .common import DATA, load_json, save_json, settings

HISTORY = DATA / "history.json"
STYLE = ("3D animated movie style, warm cinematic lighting, vertical 9:16 composition, "
         "no text, no logos, no watermark")


def history():
    return load_json(HISTORY, default=[])


def add_history(entry):
    h = history()
    h.append(entry)
    save_json(HISTORY, h[-600:])


def mission_for(slot):
    missions = settings().get("missions", {})
    key = str((int(slot) - 1) % max(len(missions), 1) + 1)
    return missions.get(key, {"name": "RECIPE", "goal": "a traditional recipe", "settings": ["her kitchen"]})


def pick_setting(char, mission, rng):
    opts = mission.get("settings") or settings().get("activities", ["at home"])
    recent = {h.get("activity") for h in history()[-30:] if h.get("grandma") == char["id"]}
    return rng.choice([o for o in opts if o not in recent] or opts)


EXTRA_RULES = {
    "RECIPE": """- It must be a real, well-known dish or drink from {heritage} cuisine (ancient or traditional is best),
  simple enough for a home cook. Say the dish name, the main ingredients and the steps in order.
- Benefits must be honest and modest (for example "rich in fibre", "warms you up", "gentle on the stomach").
  Never claim a food cures or treats a disease.
- Adults handle knives and hot stoves; show safe kitchen habits.""",
    "HEALTH TIP": """- One clear habit only, supported by mainstream health advice (WHO, national health services).
  Explain exactly what to do and why it helps, in plain words. No supplements, no medicines, no doses,
  no miracle claims, no advice to stop any treatment.
- End the last scene with a short friendly reminder to ask a doctor about personal health questions.""",
    "EXERCISE": """- One gentle exercise that is safe for most older adults. Give exact, easy steps with counts or seconds
  (for example "lift your knee, hold for 3 seconds, do it 10 times on each side").
- Include one safety tip (hold a sturdy chair, move slowly, stop if anything hurts, breathe normally).
- Benefits must be realistic (balance, flexibility, circulation, strength, mood).""",
}


def write(char, note="", seed=None, slot=1):
    s = settings()
    rng = random.Random(seed)
    mission = mission_for(slot)
    setting = pick_setting(char, mission, rng)
    recent_titles = [h["title"] for h in history()[-120:] if h.get("title")]
    n = s["scenes_per_video"]
    rules = EXTRA_RULES.get(mission["name"], "").format(heritage=char["heritage"])
    prompt = f"""
You write scripts for "{s['channel_name']}", a YouTube Shorts channel for {s['audience']}.
Grandmothers from every culture of the world talk straight to the camera, to people of their OWN age,
like a friend chatting with friends over tea: "my dear friends", "at our age", "when our knees complain".
Each video shares one piece of real, useful wisdom in a warm, lively, slightly cheeky way.

Today's grandma: {char['name']} (people call her "{char['kid_name']}"), {char['heritage']} heritage.
Personality: {char['personality']}.
Setting: {setting}, with authentic, respectful details from her culture.
Today's video: {mission['name']} — {mission['goal']}.
{('Extra instruction from the producer: ' + note) if note else ''}

Do NOT repeat any of these recent titles or their topics: {recent_titles}

Rules:
- Exactly {n} scenes. EACH scene's narration is 2 full sentences, 14 to 22 words.
  Total narration 95 to 125 words (about 45 seconds spoken). Short one-line scenes are NOT acceptable.
- Every video follows this exact story, like a caring friend talking:
  Scene 1, THE PROBLEM: she shares a common problem people our age have, in first person, honestly
    (e.g. "My knees ache when I climb the stairs, my dear", "Some evenings I feel so tired and cold",
    "I used to wake up three times every night").
  Scenes 2 to 4, DO THIS: "So I do this..." then clear numbered steps, ONE action per scene, in order.
  Scene 5, HOW IT HELPS: how this improved things for her and why it works, honestly and modestly.
  Scene 6, TRY IT AND TELL ME: she asks the viewer to try it and tell her in the comments how they feel,
    with warm, motherly, encouraging words (e.g. "Try it tomorrow morning, my dear, and tell me how your
    knees feel. You deserve to feel good, and I'm proud of you for taking care of yourself."). Vary the wording.
- Speak to fellow seniors as equals, never like talking to children. Use relatable life-after-60 moments
  (grandchildren visiting, stiff mornings, retirement days, cooking for the family, walking with friends).
- Clear, simple words, short sentences, warm first-person grandma voice.
- Everything must be accurate and widely documented. No made-up facts or numbers.
{rules}
- Portray her culture respectfully and naturally. No accents written into the text, no stereotypes.
- on_screen: a short caption for that scene, max 5 words, e.g. "Stiff knees?", "Step 1: Sit tall",
  "Step 2: Lift one knee", "How it helps", "Try it and tell me!".
- image_prompt: show EXACTLY the action the narration describes in that scene (if she says "chop the
  onion", show her hands chopping an onion; if she says "lift your right knee", show her holding a chair
  and lifting her right knee). In the first and last scenes she faces the camera and talks like she is
  chatting with a friend; describe
  her expression, the setting and the camera angle (close-ups of food or movements are welcome).
  Do not describe her face details. Never include text, labels or signs in the image.

Return JSON only, with this shape:
{{
  "title": "catchy YouTube title under 70 characters, include one emoji",
  "topic": "2 to 5 word topic, e.g. the dish or the habit",
  "fact": "the key takeaway in one plain sentence (for a recipe: dish name and main benefit)",
  "scenes": [{{"narration": "what grandma says", "on_screen": "short caption", "image_prompt": "..."}}],
  "description": "3 to 4 sentence YouTube description; for a recipe list the ingredients; end by asking viewers to try it and share in the comments how it went",
  "tags": ["8 to 12 short tags"],
  "instagram_caption": "friendly caption, 1 to 3 short lines, 2 emojis max"
}}
"""
    mock = {
        "title": f"{char['kid_name']}'s 3-ingredient soup 🍲",
        "topic": "simple soup",
        "fact": "A simple lentil soup is rich in fibre and protein.",
        "scenes": [
            {"narration": "Come into my kitchen, dear. Today I'm making the soup my grandmother taught me.",
             "image_prompt": "kitchen"},
            {"narration": "Wash one cup of lentils. Add them to a pot with four cups of water.", "image_prompt": "pot"},
            {"narration": "Add a chopped onion and a pinch of salt. Let it simmer for twenty minutes.",
             "image_prompt": "simmer"},
            {"narration": "Lentils give you fibre and protein. It's gentle, warm and very filling.",
             "image_prompt": "bowl"},
            {"narration": "Share a bowl with someone you love. See you tomorrow for more grandma wisdom!",
             "image_prompt": "waving"},
        ][:n],
        "description": "A simple soup. What should Grandma cook next?",
        "tags": ["recipe", "soup"],
        "instagram_caption": "Grandma's soup 🍲",
    }
    story, scenes = None, []
    for attempt in range(4):
        story = ai.text_json(prompt, mock_result=mock)
        scenes = story.get("scenes", [])[:n]
        words = sum(len(str(sc.get("narration", "")).split()) for sc in scenes)
        if len(scenes) >= 4 and (words >= 65 or story is mock):
            break
        prompt += (f"\n\nYour last answer had {len(scenes)} scenes and only {words} words. "
                   f"Write exactly {n} scenes with 2 full sentences each, 80 to 110 words in total.")
    if len(scenes) < 3:
        raise RuntimeError("script came back with too few scenes")
    for sc in scenes:
        sc["image_prompt"] = f"{s.get('visual_style', STYLE)}. {char['look']}. {sc['image_prompt']}"
    story["scenes"] = scenes
    story["activity"] = setting
    story["topic_type"] = mission["name"]
    story["mission"] = mission["name"]
    story["mission_hashtags"] = mission.get("hashtags", [])
    story["title"] = story.get("title", "Grandma Squad")[:95]
    return story
