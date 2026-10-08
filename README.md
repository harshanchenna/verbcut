# verbcut

**Status: POC.** This is a proof of concept, built in roughly a day. It
demonstrates the core idea end to end but has real gaps — see below before
relying on it for anything.

Text-based video editing: transcribe a video locally, edit the words in the
transcript (delete a filler word, delete a sentence, strike through anything
you don't want), and the matching footage is cut out of the export. No
timeline, no waveform-scrubbing — you edit text.

```
"So, um, today we're going to talk about, you know, onboarding."
```
Delete "um," and "you know, " in the transcript, hit Export, and the rendered
video skips straight over those words.

## How it works

1. **Transcribe** the video locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
   (CTranslate2, CPU, int8), using the `tiny` or `base` Whisper model, to get
   word-level timestamps.
2. **Edit** is just a list of words with `[start, end]` and a `deleted` flag,
   saved to a `<video>.verbcut.json` project file next to your media. Your
   original video is never touched.
3. Deletions are turned into **keep-ranges**: the spans of the original video
   to keep. Small gaps left by deletions are merged (so you don't get a cut
   for every single word), and each kept range is padded by a few
   milliseconds so cuts don't clip the start or end of a syllable.
4. **Render** concatenates the keep-ranges with `ffmpeg`, with a short audio
   fade at each cut edge to avoid clicks.

## What works

- Local transcription with word-level timestamps (`verbcut transcribe`).
- Keep-range math: deletions → merged, padded keep-ranges (fully unit tested,
  no model or ffmpeg needed — see `tests/test_ranges.py`).
- One-click filler-word removal (configurable word/phrase list: "um", "uh",
  "like", "you know", "I mean", "sort of", "kind of", ...).
- One-click long-silence trimming (configurable threshold).
- Rendering with ffmpeg (re-encode; short audio fades at cuts).
- A local web UI: open a video by path, it transcribes (or loads a saved
  project), click a word to seek, click/shift-click to select a range,
  delete the selection (undo-able for the last manual delete), remove
  fillers, trim silences, export.
- Non-destructive project files (`<video>.verbcut.json`): transcript + edits,
  re-openable, re-editable.
- A CLI for scripting: `transcribe`, `remove-fillers`, `serve`.

## What doesn't (yet)

- No true audio crossfade between segments — just a short fade-in/fade-out
  at each cut edge, which avoids clicks but isn't a blended crossfade.
- No stream-copy export: every render is a full re-encode. Fine for short
  clips, slow for long ones.
- No speaker diarization, no multi-track editing, no drag-to-reorder of
  transcript segments (only delete / undo-delete).
- Single-file projects only; no batch processing.
- The web UI takes a local filesystem path, not a file upload — by design,
  for a local tool, but worth knowing.
- Undo only covers the last manual "delete selection" action, not bulk
  filler/silence removal (those are easy to re-run from the saved project).
- Not tested on anything but short clips on Linux.

## Install

Needs [ffmpeg](https://ffmpeg.org/) — but you don't have to install it
yourself: `verbcut` depends on
[`imageio-ffmpeg`](https://github.com/imageio/imageio-ffmpeg), which bundles
a static ffmpeg binary, so there's no system package or sudo required.

```bash
uv sync          # or: pip install -e .
```

## Run

```bash
# Transcribe a video (writes in.mp4.verbcut.json)
verbcut transcribe in.mp4 --model base

# Remove filler words (and long silences) and render in one step
verbcut remove-fillers in.mp4 -o out.mp4

# Local web UI (edit transcript by hand, click Export)
verbcut serve
# then open http://127.0.0.1:8765 and enter a path to a local video file
```

CLI help: `verbcut --help`, `verbcut transcribe --help`, etc.

## Tests

Unit tests cover the keep-range math (deletions → keep-ranges, gap merging,
padding clipped at neighbors, silence detection) and filler-word/project
logic directly — none of them need a Whisper model or ffmpeg, so they run
fast and work in CI with no model download.

```bash
uv run pytest
```

## Project layout

```
src/verbcut/
  core/
    ranges.py      # pure keep-range math (unit tested)
    fillers.py      # filler word/phrase + long-silence detection
    transcribe.py   # faster-whisper wrapper (tiny/base only)
    media.py        # ffprobe helpers
    render.py       # ffmpeg render (filter_complex trim + concat)
    project.py       # project file (JSON) load/save
  cli.py             # typer CLI
  server.py          # FastAPI app
  templates/, static/  # web UI
tests/               # unit tests, no model/ffmpeg required
```

## License and dependencies

MIT, see `LICENSE`. All direct Python dependencies (faster-whisper, fastapi,
uvicorn, jinja2, typer, imageio-ffmpeg, python-multipart, pydantic,
starlette) are MIT/BSD/Apache-2.0 licensed and compatible with MIT
distribution. `ffmpeg` itself is invoked as a separate external binary
process (via the bundled static build from `imageio-ffmpeg`, which includes
GPL-licensed codec libraries) — it's not linked into this project, so it
doesn't affect this repo's MIT license, but note that redistributing that
*specific static ffmpeg binary* carries its own (GPL) terms if you ship it
yourself.

## Clean-room note

Built independently; no code, UI text, or assets were copied from any other
project. "Text-based video editing" is used here as a generic description of
the technique, not a reference to any specific product.
