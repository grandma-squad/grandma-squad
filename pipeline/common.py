"""Shared helpers: paths, config, day manifests, git and GitHub release helpers."""
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"
DAYS = DATA / "days"
ASSETS = ROOT / "assets"
WORK = ROOT / "work"  # scratch area, never committed

MOCK = os.environ.get("MOCK") == "1"  # offline test mode: no network calls


def log(*args):
    print("[grandma-squad]", *args, flush=True)


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def settings():
    return load_json(CONFIG / "settings.json")


def characters():
    return load_json(CONFIG / "characters.json")


def character(cid):
    for c in characters():
        if c["id"] == cid:
            return c
    raise KeyError(cid)


def today():
    tz = ZoneInfo(settings().get("timezone", "UTC"))
    return dt.datetime.now(tz).date()


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


# ---------- day manifests (data/days/<id>.json) ----------

def manifest_path(day_id):
    return DAYS / f"{day_id}.json"


def load_manifest(day_id, kind="daily"):
    m = load_json(manifest_path(day_id))
    if m is None:
        m = {"id": day_id, "kind": kind, "items": []}
    return m


def get_item(manifest, slot):
    for it in manifest["items"]:
        if str(it["slot"]) == str(slot):
            return it
    it = {"slot": slot}
    manifest["items"].append(it)
    manifest["items"].sort(key=lambda x: str(x["slot"]))
    return it


def update_item(day_id, slot, kind="daily", **fields):
    """Pull latest, update one item, save and push (retries on conflicts)."""
    for attempt in range(6):
        git_pull()
        m = load_manifest(day_id, kind)
        it = get_item(m, slot)
        it.update(fields)
        it["updated"] = now_iso()
        save_json(manifest_path(day_id), m)
        if git_commit_push([manifest_path(day_id)], f"{day_id} slot {slot}: {fields.get('status', 'update')}"):
            return it
        time.sleep(3 + attempt * 2)
    raise RuntimeError("could not push manifest update")


# ---------- git ----------

def _git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, check=check, capture_output=True, text=True)


def in_actions():
    return os.environ.get("GITHUB_ACTIONS") == "true"


def git_pull():
    if not in_actions():
        return
    _git("pull", "--rebase", "--autostash", "-q", check=False)


def git_commit_push(paths, message):
    """Commit the given paths and push. Returns True on success. No-op outside Actions."""
    if not in_actions():
        return True
    _git("config", "user.name", "grandma-squad-bot", check=False)
    _git("config", "user.email", "bot@users.noreply.github.com", check=False)
    _git("add", *[str(p) for p in paths], check=False)
    if _git("diff", "--cached", "--quiet", check=False).returncode == 0:
        return True
    _git("commit", "-q", "-m", message)
    for _ in range(4):
        if _git("push", "-q", check=False).returncode == 0:
            return True
        _git("pull", "--rebase", "-q", check=False)
    return False


# ---------- GitHub releases (video storage) ----------

def repo():
    return os.environ.get("GITHUB_REPOSITORY", "OWNER/REPO")


def release_tag(day_id):
    return f"v-{day_id}"


def asset_url(day_id, name):
    return f"https://github.com/{repo()}/releases/download/{release_tag(day_id)}/{name}"


def upload_assets(day_id, files):
    """Upload files to the day's release (created if missing). Returns {name: url}."""
    urls = {Path(f).name: asset_url(day_id, Path(f).name) for f in files}
    if not in_actions():
        log("local run: skipping release upload", [str(f) for f in files])
        return urls
    tag = release_tag(day_id)
    if subprocess.run(["gh", "release", "view", tag], cwd=ROOT, capture_output=True).returncode != 0:
        subprocess.run(["gh", "release", "create", tag, "--title", f"Videos {day_id}",
                        "--notes", "Daily Grandma Squad videos (drafts for review)."],
                       cwd=ROOT, check=True, capture_output=True)
    subprocess.run(["gh", "release", "upload", tag, *[str(f) for f in files], "--clobber"],
                   cwd=ROOT, check=True)
    return urls


def download_asset(day_id, name, dest_dir):
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gh", "release", "download", release_tag(day_id), "-p", name,
                    "-D", str(dest_dir), "--clobber"], cwd=ROOT, check=True)
    return dest_dir / name


def run(cmd, **kw):
    """Run a command, raising with its stderr on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(map(str, cmd))}\n{r.stderr[-3000:]}")
    return r.stdout
