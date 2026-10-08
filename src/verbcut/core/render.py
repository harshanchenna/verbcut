"""Render keep-ranges to an output file with ffmpeg.

Uses a single ffmpeg invocation with a filter_complex graph: trim/atrim each
keep-range, apply a short audio fade at each cut edge to avoid clicks, then
concat video+audio pairs. Re-encodes (fine for a POC; stream-copy concat needs
keyframe-aligned cuts which word-level timestamps won't give you).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg

from .ranges import Range

FADE = 0.015  # seconds, short audio fade at each cut edge to avoid clicks


def ffmpeg_path() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def build_filter_complex(ranges: list[Range], has_video: bool) -> tuple[str, str, str]:
    """Build the filter_complex graph string for the given keep-ranges.

    Returns (filter_complex, video_out_label_or_empty, audio_out_label).
    """
    parts = []
    v_labels = []
    a_labels = []
    for i, (start, end) in enumerate(ranges):
        dur = end - start
        fade = min(FADE, dur / 2 - 0.001) if dur > 0.01 else 0.0
        if has_video:
            parts.append(f"[0:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS[v{i}]")
            v_labels.append(f"[v{i}]")
        a_filter = f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS"
        if fade > 0:
            a_filter += f",afade=t=in:st=0:d={fade:.6f},afade=t=out:st={max(dur - fade, 0):.6f}:d={fade:.6f}"
        parts.append(f"{a_filter}[a{i}]")
        a_labels.append(f"[a{i}]")

    n = len(ranges)
    if has_video:
        concat_inputs = "".join(f"{v}{a}" for v, a in zip(v_labels, a_labels))
        parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[vout][aout]")
        return ";".join(parts), "[vout]", "[aout]"
    else:
        concat_inputs = "".join(a_labels)
        parts.append(f"{concat_inputs}concat=n={n}:v=0:a=1[aout]")
        return ";".join(parts), "", "[aout]"


def render(
    media_path: str | Path,
    ranges: list[Range],
    output_path: str | Path,
    *,
    has_video: bool = True,
    threads: int = 2,
    extra_args: list[str] | None = None,
) -> Path:
    """Render the given keep-ranges from media_path into output_path with ffmpeg."""
    if not ranges:
        raise ValueError("no keep-ranges to render (everything deleted?)")

    filter_complex, v_out, a_out = build_filter_complex(ranges, has_video)

    cmd = [
        "nice",
        "-n",
        "19",
        ffmpeg_path(),
        "-y",
        "-threads",
        str(threads),
        "-i",
        str(media_path),
        "-filter_complex",
        filter_complex,
    ]
    if v_out:
        cmd += ["-map", v_out]
    cmd += ["-map", a_out]
    cmd += extra_args or []
    cmd += [str(output_path)]

    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return Path(output_path)
