# Grandma Squad — free daily video studio

Every morning this makes **3 YouTube Shorts** of five grandmas doing real-life things
(driving, baking, camping, gardening…) while sharing one fun fact or life lesson — family-friendly, for all ages.
On Sundays it joins the week's published Shorts into **one long video**.

You review everything in the **Squad Studio** app on your phone and post from your phone.
Nothing goes public unless you post it.

**Cost: $0.** It runs on free services: GitHub Actions (computer time), GitHub Pages (the phone app),
Gemini API free tier or Pollinations.ai (scripts and pictures), and Microsoft Edge voices (narration).

---

## How it works

```
8:37 pm  GitHub's free servers wake up (your phone can sleep)
         → AI writes 3 scripts (never repeats a fact)
         → AI draws 5 realistic scenes per video, same grandma face every day
         → Edge voice narrates, ffmpeg adds motion + big subtitles
         → the 3 videos appear in Squad Studio on your phone
9:30 pm  (optional) an iPhone Shortcut saves them into your Photos, album "Grandma Squad"
You      watch → Save & post → post as a Short in the YouTube app → "I've posted it"
Sunday   → weekly compilation (16:9, chapters) arrives the same way
```

You post from your own phone, so there is **no YouTube API setup**.
The grandmas live in `config/characters.json`; activities and topics in `config/settings.json`.

---

## One-time setup (about 30 minutes)

### 1. Create the YouTube channel (~5 min)
- YouTube (sign in as ram4utube2026@gmail.com) → profile → **Create a channel** → **Grandma Squad**.
  In YouTube Studio → Settings → Default settings, set audience to **No, it's not made for kids**.

### 2. Put this project on GitHub (~10 min)
1. Create a free account at github.com.
2. Create a **public** repository named `grandma-squad` (public keeps the servers free; nothing secret is in it).
3. Upload all files from this folder, including the hidden `.github` folder
   (or on a computer with the GitHub CLI, run `./setup.sh`).
4. Repository → Settings → Pages → Source: **GitHub Actions**.
5. Actions tab → **Update phone app** → Run workflow. Your app address:
   `https://YOUR-USERNAME.github.io/grandma-squad/`

### 3. Gemini key — optional but recommended (~3 min)
The videos are made on GitHub's computers while you sleep, and the AI that writes the scripts and draws the
pictures needs an account to answer. A free Gemini key (aistudio.google.com/apikey, no card needed) gives
better pictures and the same grandma face every day. **Without it, the free no-key backup (Pollinations.ai)
is used automatically**, but faces vary more and it is busier.
Save it in Repo → Settings → Secrets and variables → Actions → New secret: `GEMINI_API_KEY`.

### 4. Install Squad Studio on your iPhone (~5 min)
1. github.com → Settings → Developer settings → **Fine-grained tokens** → Generate:
   *Only select repositories* → grandma-squad; permissions **Actions: Read and write**, **Contents: Read-only**.
2. Open your app address in **Safari** → Share → **Add to Home Screen**.
3. Open Squad Studio → enter your GitHub username, `grandma-squad`, the token → **Connect**.
4. Settings → **Make today's videos now** for the first batch (about 15–20 minutes).

### 5. Auto-save videos to Photos every morning — optional (~5 min)
iPhone **Shortcuts** app → Automation → **+** → Time of Day → 9:30 PM, Daily → **Run Immediately** →
New Blank Automation, then add these actions:
1. **Get Contents of URL** → `https://YOUR-USERNAME.github.io/grandma-squad/today.json`
2. **Get Dictionary Value** → key `videos`
3. **Repeat with Each** (item in Dictionary Value):
   - **Get Dictionary Value** → key `url` in Repeat Item
   - **Get Contents of URL** → Dictionary Value
   - **Save to Photo Album** → album "Grandma Squad" (create it in Photos first)
4. **Show Notification** → "Grandma Squad videos are ready"

Allow access the first time it asks. Rejected videos are never included.

---

## Daily use
1. Open Squad Studio, watch each video and **check the fact** on the card.
2. Tap **Save & post** → **Get video** → **Save or share video**:
   - **Save Video**, then post it in the **YouTube** app (+ → Short → pick the video). Choose "not made for kids" and turn on
     "altered or synthetic content" — the grandmas are AI-made.
   - **Copy title / description** and paste them in.
3. Tap **I've posted it ✓** so it moves to Done (and joins the Sunday compilation).
4. **Redo** → fresh version (you can type what to change). **Reject** → hides it.

### Optional: fully automatic publishing
If you later want the Publish button to post by itself, follow `AUTO-PUBLISH.md`,
then turn on "API auto-publish" in the app's Settings.

## Limits worth knowing
- The grandmas appear in moving pictures (zoom and pan), not lip-synced video.
- Free AI tiers have daily limits. If Gemini is busy, the backup takes over; if both fail,
  the card shows "Needs attention" — tap **Make it again** later.
- The app keeps the last 14 days of videos; older ones stay in the repository's Releases.
- Optional music: drop royalty-free `.mp3` files (YouTube Audio Library) into `assets/music/`.
- Change posting time: edit the `cron` line in `.github/workflows/daily.yml` (times are UTC).

## Files
| Path | What it is |
|---|---|
| `pipeline/generate_day.py` | Makes the daily Shorts (or redoes one) |
| `pipeline/weekly.py` | Sunday compilation |
| `pipeline/publish.py` | Optional API auto-publish |
| `pipeline/build_site.py` | Builds the phone app with recent videos and today.json |
| `pipeline/script_writer.py` | Script prompt and safety rules |
| `pipeline/render.py` | Motion, subtitles, posters (ffmpeg) |
| `docs/` | Squad Studio phone app |
| `.github/workflows/` | Daily, redo, status, weekly, app update (+ optional publish) |
| `data/days/` | One small status file per day (the app reads these) |
