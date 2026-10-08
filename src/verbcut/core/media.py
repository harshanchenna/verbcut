"""ffprobe helpers: duration and stream info for a media file."""

from __future__ import annotations

import json
import subprocess

import imageio_ffmpeg


def ffprobe_path() -> str:
    """ffprobe isn't bundled by imageio-ffmpeg, but ffmpeg -version output
    tells us where sibling binaries would be; imageio-ffmpeg only ships
    ffmpeg, so we shell out to ffmpeg itself to get stream info via
    `-f null` + `-v quiet -print_format` is unreliable. Instead we ask ffmpeg
    to probe via its own `-i` stderr parse is fragile, so we implement probing
    with ffmpeg's `-f ffmetadata`-free approach: use ffmpeg itself with
    the `-print_format json` option is actually an ffprobe-only flag, so if a
    real ffprobe is on PATH we use it; otherwise shell out to the bundled
    ffmpeg using a null output and parse duration from stderr.
    """
    import shutil

    found = shutil.which("ffprobe")
    return found or ""


def probe(media_path: str) -> dict:
    """Return {"duration": float, "has_video": bool, "has_audio": bool}."""
    ffprobe = ffprobe_path()
    if ffprobe:
        out = subprocess.run(
            [
                ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                media_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        data = json.loads(out)
        duration = float(data.get("format", {}).get("duration", 0.0))
        streams = data.get("streams", [])
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        return {"duration": duration, "has_video": has_video, "has_audio": has_audio}

    # Fall back to the bundled ffmpeg binary, parsing stderr.
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ffmpeg, "-i", media_path, "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    stderr = proc.stderr
    has_video = "Video:" in stderr
    has_audio = "Audio:" in stderr
    duration = 0.0
    for line in stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            # "Duration: 00:00:05.12, start: ..."
            ts = line.split(",")[0].split("Duration:")[1].strip()
            h, m, s = ts.split(":")
            duration = int(h) * 3600 + int(m) * 60 + float(s)
            break
    return {"duration": duration, "has_video": has_video, "has_audio": has_audio}
