"""Local transcription with word-level timestamps, via faster-whisper (CPU int8).

Kept to tiny/base models only — this runs on a shared, memory-constrained box.
"""

from __future__ import annotations

import os

from .project import Project

ALLOWED_MODELS = {"tiny", "tiny.en", "base", "base.en"}


def transcribe(
    media_path: str,
    *,
    model_size: str = "base",
    cpu_threads: int = 2,
    language: str | None = None,
) -> Project:
    """Transcribe media_path with word-level timestamps and return a Project.

    Lowers this process's scheduling priority (nice) and caps CPU threads so
    transcription doesn't starve other work on a shared box.
    """
    if model_size not in ALLOWED_MODELS:
        raise ValueError(
            f"model_size must be one of {sorted(ALLOWED_MODELS)}, got {model_size!r}"
        )

    try:
        os.nice(19)
    except (AttributeError, OSError):
        pass  # not available on this platform; caller should wrap with `nice`

    from faster_whisper import WhisperModel  # imported lazily: slow + optional for tests

    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=cpu_threads)

    segments, info = model.transcribe(
        media_path,
        word_timestamps=True,
        language=language,
        vad_filter=True,
    )

    words: list[dict] = []
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    for segment in segments:
        for w in segment.words or []:
            words.append(
                {
                    "text": w.word.strip(),
                    "start": float(w.start),
                    "end": float(w.end),
                    "deleted": False,
                }
            )
            duration = max(duration, float(w.end))

    return Project(media_path=media_path, duration=duration, words=words, model=model_size)
