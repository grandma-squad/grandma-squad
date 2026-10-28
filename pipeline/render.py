"""Turns pictures + voice into finished videos with ffmpeg."""
import os
import random
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import ASSETS, log, run, settings
from .tts import duration

W, H, FPS = 1080, 1920, 30
FONT_NAME = os.environ.get("FONT_NAME", "DejaVu Sans")
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p"]
AAC = ["-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]


def _font(size):
    for name in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _cover(img_path, out_path, w, h):
    img = Image.open(img_path).convert("RGB")
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, max(0, int((img.height - h) * 0.4))
    img.crop((left, top, left + w, top + h)).save(out_path, quality=95)
    return out_path


MOTIONS = [
    ("1+0.13*on/{F}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),            # zoom in
    ("1.13-0.13*on/{F}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),         # zoom out
    ("1.13", "(iw-iw/zoom)*on/{F}", "ih/2-(ih/zoom/2)"),                  # pan right
    ("1.13", "(iw-iw/zoom)*(1-on/{F})", "ih/2-(ih/zoom/2)"),              # pan left
    ("1.13", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-on/{F})"),              # tilt up
]


def scene_clip(img, audio, out, motion, pad=0.4, first=False, last=False):
    secs = duration(audio) + pad
    frames = int(secs * FPS)
    z, x, y = (e.format(F=frames) for e in MOTIONS[motion % len(MOTIONS)])
    covered = Path(out).with_suffix(".cover.jpg")
    _cover(img, covered, W, H)
    fade = []
    if first:
        fade.append("fade=t=in:st=0:d=0.3")
    else:
        fade.append("fade=t=in:st=0:d=0.15")
    fade.append(f"fade=t=out:st={secs - 0.15:.2f}:d=0.15")
    vf = (f"scale={W * 2}:{H * 2},zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS},"
          + ",".join(fade) + ",format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(covered), "-i", str(audio),
         "-filter_complex", f"[0:v]{vf}[v];[1:a]apad,atrim=0:{secs:.3f},aresample=44100[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{secs:.3f}", *X264, *AAC, str(out)])
    return secs


def _ass_text(t):
    return t.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _ts(t):
    h, rem = divmod(max(0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _chunks(text, max_chars=20):
    words, out, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def build_ass(timeline, title, total, path):
    """timeline: list of (start, speech_secs, narration)."""
    channel = settings()["channel_name"]
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT_NAME},88,&H0000E5FF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,60,560,1
Style: Title,{FONT_NAME},60,&H00FFFFFF,&H00FFFFFF,&H00305FE0,&H00305FE0,-1,0,0,0,100,100,0,0,3,18,0,8,70,70,230,1
Style: Brand,{FONT_NAME},38,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,1,0,1,3,2,7,50,50,130,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [f"Dialogue: 0,{_ts(0)},{_ts(total)},Brand,,0,0,0,,{_ass_text(channel)}",
             f"Dialogue: 1,{_ts(0.2)},{_ts(min(3.6, total))},Title,,0,0,0,,{{\\fad(200,300)}}{_ass_text(_plain(title))}"]
    for start, speech, text in timeline:
        chunks = _chunks(text)
        weights = [len(c) + 3 for c in chunks]
        t = start + 0.05
        for c, wgt in zip(chunks, weights):
            d = speech * wgt / sum(weights)
            lines.append(f"Dialogue: 2,{_ts(t)},{_ts(t + d)},Sub,,0,0,0,,{{\\fad(60,0)}}{_ass_text(c.upper())}")
            t += d
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def _music():
    files = sorted((ASSETS / "music").glob("*.mp3"))
    return random.choice(files) if files else None


def render_short(scenes, title, workdir, out_mp4):
    """scenes: list of dicts with 'image', 'audio', 'narration'."""
    workdir = Path(workdir)
    clips, timeline, t = [], [], 0.0
    motion0 = random.randrange(len(MOTIONS))
    for i, sc in enumerate(scenes):
        clip = workdir / f"clip{i}.mp4"
        speech = duration(sc["audio"])
        secs = scene_clip(sc["image"], sc["audio"], clip, motion0 + i,
                          first=(i == 0), last=(i == len(scenes) - 1))
        timeline.append((t, speech, sc["narration"]))
        t += secs
        clips.append(clip)
    total = t
    lst = workdir / "clips.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    joined = workdir / "joined.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    ass = workdir / "subs.ass"
    build_ass(timeline, title, total, ass)
    music = _music()
    fonts = ASSETS / "fonts"
    sub_filter = f"ass={ass.as_posix()}" + (f":fontsdir={fonts.as_posix()}" if fonts.exists() else "")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music),
                "-filter_complex",
                f"[0:v]{sub_filter},fade=t=out:st={total - 0.4:.2f}:d=0.4[v];"
                f"[1:a]volume=0.10,afade=t=out:st={total - 1.2:.2f}:d=1.2[m];"
                f"[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-vf", f"{sub_filter},fade=t=out:st={total - 0.4:.2f}:d=0.4"]
    cmd += ["-t", f"{total:.3f}", *X264, *AAC, "-movflags", "+faststart", str(out_mp4)]
    run(cmd)
    return total


def _outlined(d, xy, text, font, fill, outline=(0, 0, 0), width=6):
    x, y = xy
    for dx in range(-width, width + 1, 2):
        for dy in range(-width, width + 1, 2):
            d.text((x + dx, y + dy), text, font=font, fill=outline)
    d.text((x, y), text, font=font, fill=fill)


def _plain(text):
    """Drop emoji (PIL fonts can't draw them)."""
    return " ".join("".join(ch for ch in text if ord(ch) < 0x2190 or 0x2200 <= ord(ch) < 0x2300).split())


def _wrap(d, text, font, max_w):
    text = _plain(text)
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(test, font=font) > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def poster(img, title, out, size=(540, 960)):
    """Small vertical preview image for the review app."""
    w, h = size
    tmp = Path(out).with_suffix(".tmp.jpg")
    _cover(img, tmp, w, h)
    im = Image.open(tmp)
    d = ImageDraw.Draw(im)
    font = _font(40)
    y = 60
    for line in _wrap(d, title, font, w - 60)[:3]:
        tw = d.textlength(line, font=font)
        _outlined(d, ((w - tw) / 2, y), line, font, (255, 255, 255), width=3)
        y += 52
    im.save(out, quality=88)
    tmp.unlink(missing_ok=True)
    return out


def thumbnail_wide(img, title, out):
    tmp = Path(out).with_suffix(".tmp.jpg")
    _cover(img, tmp, 1280, 720)
    im = Image.open(tmp)
    d = ImageDraw.Draw(im)
    font = _font(78)
    lines = _wrap(d, title, font, 1180)[:3]
    y = 720 - 40 - len(lines) * 92
    for line in lines:
        _outlined(d, (50, y), line, font, (255, 230, 0), width=6)
        y += 92
    im.save(out, quality=90)
    tmp.unlink(missing_ok=True)
    return out


def title_card(text, sub, out_png, size=(1920, 1080), bg_img=None):
    w, h = size
    if bg_img and Path(bg_img).exists():
        im = Image.open(bg_img).convert("RGB")
        scale = max(w / im.width, h / im.height)
        im = im.resize((round(im.width * scale), round(im.height * scale))).crop((0, 0, w, h))
        im = im.filter(ImageFilter.GaussianBlur(25))
        im = Image.blend(im, Image.new("RGB", (w, h), (40, 20, 10)), 0.45)
    else:
        im = Image.new("RGB", (w, h), (224, 95, 48))
    d = ImageDraw.Draw(im)
    big, small = _font(110), _font(56)
    lines = _wrap(d, text, big, w - 200)[:3]
    y = h / 2 - len(lines) * 65 - 40
    for line in lines:
        tw = d.textlength(line, font=big)
        _outlined(d, ((w - tw) / 2, y), line, big, (255, 255, 255), width=6)
        y += 130
    tw = d.textlength(sub, font=small)
    _outlined(d, ((w - tw) / 2, y + 20), sub, small, (255, 225, 90), width=4)
    im.save(out_png)
    return out_png


def _card_clip(png, secs, out):
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(png), "-f", "lavfi", "-i",
         "anullsrc=r=44100:cl=stereo", "-t", f"{secs}", "-vf",
         f"scale=1920:1080,fade=t=in:st=0:d=0.3,fade=t=out:st={secs - 0.3}:d=0.3,format=yuv420p",
         "-r", str(FPS), *X264, *AAC, "-shortest", str(out)])


def render_weekly(parts, workdir, out_mp4, week_title):
    """parts: list of dicts {video, title, grandma, poster_src}. Returns chapter list [(secs, label)]."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    clips, chapters, t = [], [], 0.0
    intro = workdir / "intro.png"
    title_card(week_title, settings()["channel_name"] + " — the whole week!", intro,
               bg_img=parts[0].get("poster_src"))
    _card_clip(intro, 4, workdir / "c_intro.mp4")
    clips.append(workdir / "c_intro.mp4")
    chapters.append((0, "Welcome"))
    t += 4
    for i, p in enumerate(parts):
        card = workdir / f"card{i}.png"
        title_card(p["title"], p["grandma"], card, bg_img=p.get("poster_src"))
        _card_clip(card, 2.5, workdir / f"c_card{i}.mp4")
        wide = workdir / f"c_wide{i}.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p["video"]), "-filter_complex",
             "[0:v]split[a][b];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
             "boxblur=40:6,eq=brightness=-0.08[bg];[b]scale=-2:1080[fg];"
             f"[bg][fg]overlay=(W-w)/2:0,fps={FPS},format=yuv420p[v];[0:a]aresample=44100[a]",
             "-map", "[v]", "-map", "[a]", *X264, *AAC, str(wide)])
        chapters.append((t, f"{p['grandma']}: {p['title']}"))
        clips += [workdir / f"c_card{i}.mp4", wide]
        t += 2.5 + duration(wide)
    lst = workdir / "weekly.txt"
    lst.write_text("".join(f"file '{Path(c).resolve()}'\n" for c in clips))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         *X264, *AAC, "-movflags", "+faststart", str(out_mp4)])
    return chapters


def clean(path):
    shutil.rmtree(path, ignore_errors=True)
