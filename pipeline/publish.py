"""Publish an approved video to YouTube and/or Instagram (called from the phone app via GitHub Actions)."""
import argparse
import os
import sys
import time
from pathlib import Path

import requests

from .common import WORK, download_asset, load_manifest, log, now_iso, settings, update_item

IG_VER = os.environ.get("IG_API_VERSION", "v23.0")


# ---------------- YouTube ----------------

def youtube_token():
    r = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "grant_type": "refresh_token",
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
    })
    if r.status_code != 200:
        raise RuntimeError(f"YouTube sign-in failed: {r.text[:300]}")
    return r.json()["access_token"]


def youtube_upload(video, item, thumb=None):
    s = settings()
    token = youtube_token()
    body = {
        "snippet": {
            "title": item["title"][:100],
            "description": item.get("description", "")[:4900],
            "tags": item.get("tags", [])[:15],
            "categoryId": s.get("youtube_category_id", "27"),
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": s.get("youtube_privacy", "public"),
            "selfDeclaredMadeForKids": bool(s.get("youtube_made_for_kids", True)),
            "containsSyntheticMedia": True,  # required label for realistic AI imagery
            "embeddable": True,
        },
    }
    size = Path(video).stat().st_size
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        json=body, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube upload start failed: {r.status_code} {r.text[:400]}")
    with open(video, "rb") as f:
        up = requests.put(r.headers["Location"], data=f,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"},
                          timeout=1800)
    if up.status_code not in (200, 201):
        raise RuntimeError(f"YouTube upload failed: {up.status_code} {up.text[:400]}")
    vid = up.json()["id"]
    if thumb:
        try:
            t = requests.post(
                f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                data=Path(thumb).read_bytes(), timeout=120)
            if t.status_code != 200:
                log("thumbnail not set (channel may need phone verification):", t.text[:200])
        except Exception as e:  # noqa: BLE001
            log("thumbnail error:", e)
    url = f"https://youtube.com/shorts/{vid}" if not item.get("wide") else f"https://youtu.be/{vid}"
    return {"id": vid, "url": url, "at": now_iso(), "privacy": up.json().get("status", {}).get("privacyStatus")}


# ---------------- Instagram ----------------

def _ig(method, path, **kw):
    r = requests.request(method, f"https://graph.instagram.com/{IG_VER}/{path}", timeout=120, **kw)
    if r.status_code != 200:
        raise RuntimeError(f"Instagram {path} failed: {r.status_code} {r.text[:400]}")
    return r.json()


def instagram_upload(video, item, public_url):
    token = os.environ["IG_ACCESS_TOKEN"]
    user = os.environ.get("IG_USER_ID") or _ig("GET", "me", params={"fields": "user_id", "access_token": token})["user_id"]
    base = {"media_type": "REELS", "caption": item.get("caption", item["title"])[:2100],
            "share_to_feed": "true", "access_token": token}
    try:
        c = _ig("POST", f"{user}/media", data={**base, "upload_type": "resumable"})
        size = Path(video).stat().st_size
        with open(video, "rb") as f:
            up = requests.post(f"https://rupload.facebook.com/ig-api-upload/{IG_VER}/{c['id']}",
                               headers={"Authorization": f"OAuth {token}", "offset": "0",
                                        "file_size": str(size)}, data=f, timeout=1800)
        if up.status_code != 200:
            raise RuntimeError(f"resumable upload failed: {up.status_code} {up.text[:300]}")
    except Exception as e:  # noqa: BLE001
        log("resumable upload failed, trying public URL:", str(e)[:300])
        c = _ig("POST", f"{user}/media", data={**base, "video_url": public_url})
    for _ in range(60):  # wait up to ~10 minutes for Instagram to process
        st = _ig("GET", c["id"], params={"fields": "status_code,status", "access_token": token})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram could not process the video: {st.get('status')}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram processing timed out")
    pub = _ig("POST", f"{user}/media_publish", data={"creation_id": c["id"], "access_token": token})
    link = ""
    try:
        link = _ig("GET", pub["id"], params={"fields": "permalink", "access_token": token}).get("permalink", "")
    except Exception:  # noqa: BLE001
        pass
    return {"id": pub["id"], "url": link, "at": now_iso()}


# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="day id (2026-10-28) or week id (week-2026-W44)")
    ap.add_argument("--slot", required=True)
    ap.add_argument("--targets", default="both", choices=["both", "youtube", "instagram"])
    ap.add_argument("--title", default="")
    ap.add_argument("--caption", default="")
    a = ap.parse_args()
    kind = "weekly" if a.id.startswith("week-") else "daily"
    m = load_manifest(a.id, kind)
    item = next((i for i in m["items"] if str(i["slot"]) == str(a.slot)), None)
    if not item or not item.get("video_file"):
        sys.exit(f"No video found for {a.id} slot {a.slot}")
    edits = {}
    if a.title.strip():
        edits["title"] = a.title.strip()[:100]
    if a.caption.strip():
        edits["caption"] = a.caption.strip()
    item.update(edits)
    update_item(a.id, a.slot, kind=kind, status="publishing", error="", **edits)

    work = WORK / "publish" / a.id
    video = download_asset(a.id, item["video_file"], work)
    thumb = download_asset(a.id, item["poster_file"], work) if item.get("wide") else None
    public_url = item["video_url"].split("?")[0]

    want = ["youtube", "instagram"] if a.targets == "both" else [a.targets]
    results, errors = {}, []
    for target in want:
        if (item.get(target) or {}).get("id"):
            log(f"{target}: already published, skipping")
            continue
        try:
            if target == "youtube":
                results["youtube"] = youtube_upload(video, item, thumb)
            else:
                results["instagram"] = instagram_upload(video, item, public_url)
            log(f"{target}: published", results[target].get("url"))
        except KeyError as e:
            errors.append(f"{target}: missing secret {e}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{target}: {str(e)[:400]}")
    update_item(a.id, a.slot, kind=kind, status="failed" if errors else "published",
                error=" | ".join(errors), **results)
    if errors:
        sys.exit("\n".join(errors))


if __name__ == "__main__":
    main()
