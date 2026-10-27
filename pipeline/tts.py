"""Free text-to-speech with Microsoft Edge voices (edge-tts)."""
import asyncio
from pathlib import Path

from .common import MOCK, log, run

FALLBACK_VOICE = "en-US-JennyNeural"


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.strip())


async def _speak(text, voice, rate, pitch, out):
    import edge_tts  # installed in the GitHub workflow
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))


def speak(text, char, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if MOCK:
        secs = max(2.0, len(text.split()) / 2.6)
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             "sine=frequency=220:sample_rate=24000", "-af", "volume=0.05", "-t", f"{secs:.2f}",
             str(out_path)])
        return out_path
    for voice in (char.get("voice"), FALLBACK_VOICE):
        for attempt in range(3):
            try:
                asyncio.run(_speak(text, voice, char.get("rate", "+0%"), char.get("pitch", "+0Hz"), out_path))
                if out_path.exists() and out_path.stat().st_size > 1000:
                    return out_path
            except Exception as e:  # noqa: BLE001
                log(f"tts failed ({voice}):", str(e)[:200])
    raise RuntimeError("text-to-speech failed")
