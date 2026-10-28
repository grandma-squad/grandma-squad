"""Free AI calls: Gemini API (if a key is set), Cloudflare Workers AI free tier, then Pollinations.ai."""
import base64
import json
import os
import random
import re
import time
import urllib.parse
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from .common import MOCK, log, settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _key():
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _gemini(model, parts, gen_config, timeout=180):
    r = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": _key(), "Content-Type": "application/json"},
        json={"contents": [{"role": "user", "parts": parts}], "generationConfig": gen_config},
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini {model} HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def _cf():
    return os.environ.get("CF_ACCOUNT_ID", "").strip(), os.environ.get("CF_API_TOKEN", "").strip()


def _cf_run(model, payload, timeout=180):
    acct, tok = _cf()
    r = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
                      headers={"Authorization": f"Bearer {tok}"}, json=payload, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"Cloudflare {model} HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["result"]


CF_TEXT_MODEL = os.environ.get("CF_TEXT_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
CF_IMAGE_MODEL = os.environ.get("CF_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")


def _extract_json(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def text_json(prompt, mock_result=None):
    """Ask an LLM for a JSON object. Retries, then falls back to Pollinations."""
    if MOCK:
        return mock_result
    errors = []
    if _key():
        model = os.environ.get("GEMINI_TEXT_MODEL") or settings()["gemini_text_model"]
        for attempt in range(4):
            try:
                data = _gemini(model, [{"text": prompt}],
                               {"responseMimeType": "application/json", "temperature": 1.0})
                txt = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
                return _extract_json(txt)
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))
                log("gemini text failed:", str(e)[:200])
                time.sleep(10 * (attempt + 1))
    if all(_cf()):
        for attempt in range(3):
            try:
                res = _cf_run(CF_TEXT_MODEL, {"max_tokens": 1800, "temperature": 0.9, "messages": [
                    {"role": "system", "content": "You are a careful scriptwriter. Reply with one valid JSON object only, no other text."},
                    {"role": "user", "content": prompt}]})
                out = res.get("response", res)
                return out if isinstance(out, dict) else _extract_json(str(out))
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))
                log("cloudflare text failed:", str(e)[:200])
                time.sleep(10)
    for attempt in range(2):
        try:
            r = requests.post("https://text.pollinations.ai/openai", timeout=180, json={
                "model": "openai",
                "messages": [{"role": "system", "content": "Reply with one valid JSON object only."},
                             {"role": "user", "content": prompt}],
                "seed": random.randint(1, 10**6),
            })
            r.raise_for_status()
            return _extract_json(r.json()["choices"][0]["message"]["content"])
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
            log("pollinations text failed:", str(e)[:200])
            time.sleep(15)
    raise RuntimeError("All text providers failed: " + " | ".join(errors[-3:]))


_GEMINI_IMAGE_OFF = False


def image(prompt, out_path, refs=(), aspect="9:16", seed=None, mock_label="", mock_color=(240, 200, 160)):
    """Generate an image to out_path. refs = reference image paths for character consistency."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if MOCK:
        _placeholder(out_path, mock_label or prompt[:80], aspect, mock_color)
        return out_path
    global _GEMINI_IMAGE_OFF
    errors = []
    if _key() and not _GEMINI_IMAGE_OFF:
        model = os.environ.get("GEMINI_IMAGE_MODEL") or settings()["gemini_image_model"]
        parts = []
        for ref in refs:
            if Path(ref).exists():
                parts.append({"inlineData": {"mimeType": "image/png",
                                             "data": base64.b64encode(Path(ref).read_bytes()).decode()}})
        lead = ("Use the woman in the reference photo as the same character (same face, hair, age and skin tone). "
                if parts else "")
        parts.append({"text": lead + prompt})
        for attempt in range(3):
            try:
                data = _gemini(model, parts, {"responseModalities": ["IMAGE"],
                                              "imageConfig": {"aspectRatio": aspect}})
                for p in data["candidates"][0]["content"]["parts"]:
                    inline = p.get("inlineData") or p.get("inline_data")
                    if inline:
                        Image.open(BytesIO(base64.b64decode(inline["data"]))).convert("RGB").save(out_path)
                        return out_path
                raise RuntimeError("no image in response")
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))
                log("gemini image failed:", str(e)[:200])
                if any(k in str(e) for k in ("429", "RESOURCE_EXHAUSTED", "limit: 0", "billing", "403")):
                    _GEMINI_IMAGE_OFF = True  # no free image quota: stop trying Gemini for this run
                    break
                time.sleep(10)
    if all(_cf()):
        shape = {"9:16": "tall vertical portrait framing, subject centered", "16:9": "wide framing",
                 "3:4": "portrait framing, subject centered"}.get(aspect, "")
        for attempt in range(3):
            try:
                res = _cf_run(CF_IMAGE_MODEL, {"prompt": f"{prompt[:1800]}, {shape}", "steps": 6,
                                               "seed": seed or random.randint(1, 10**6)})
                Image.open(BytesIO(base64.b64decode(res["image"]))).convert("RGB").save(out_path)
                return out_path
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))
                log("cloudflare image failed:", str(e)[:200])
                time.sleep(8)
    w, h = (1080, 1920) if aspect == "9:16" else (1920, 1080) if aspect == "16:9" else (1024, 1024)
    for attempt in range(2):
        try:
            url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:1500])
                   + f"?width={w}&height={h}&nologo=true&model=flux&seed={seed or random.randint(1, 10**6)}")
            r = requests.get(url, timeout=240)
            r.raise_for_status()
            Image.open(BytesIO(r.content)).convert("RGB").save(out_path)
            return out_path
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
            log("pollinations image failed:", str(e)[:200])
            time.sleep(20)
    raise RuntimeError("All image providers failed: " + " | ".join(errors[-3:]))


def _placeholder(path, label, aspect, color):
    w, h = (1080, 1920) if aspect == "9:16" else (1920, 1080) if aspect == "16:9" else (1024, 1024)
    img = Image.new("RGB", (w, h), color)
    d = ImageDraw.Draw(img)
    for i in range(0, max(w, h) * 2, 90):
        d.line([(i, 0), (i - h, h)], fill=tuple(max(0, c - 18) for c in color), width=30)
    d.ellipse([w * 0.3, h * 0.25, w * 0.7, h * 0.25 + w * 0.4], fill=(255, 235, 215), outline=(90, 60, 40), width=8)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 54)
    except OSError:
        font = ImageFont.load_default()
    words, lines, line = label.split(), [], ""
    for wd in words:
        if len(line) + len(wd) > 22:
            lines.append(line)
            line = wd
        else:
            line = (line + " " + wd).strip()
    lines.append(line)
    y = int(h * 0.6)
    for ln in lines[:6]:
        tw = d.textlength(ln, font=font)
        d.text(((w - tw) / 2, y), ln, fill=(60, 40, 30), font=font)
        y += 70
    img.save(path)
