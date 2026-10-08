"""Filler-word and filler-phrase detection, and long-silence trimming helpers.

Pure text/range logic, no I/O — kept separate from ranges.py so the filler
word list is easy to find and configure.
"""

from __future__ import annotations

import re

from .ranges import Word, find_silences

DEFAULT_FILLER_WORDS = {
    "um",
    "umm",
    "uh",
    "uhh",
    "er",
    "erm",
    "ah",
    "like",
    "hmm",
}

# Multi-word filler phrases, checked against a sliding window of word text.
DEFAULT_FILLER_PHRASES = [
    ["you", "know"],
    ["i", "mean"],
    ["sort", "of"],
    ["kind", "of"],
]


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def mark_filler_words(
    words: list[dict],
    *,
    filler_words: set[str] | None = None,
    filler_phrases: list[list[str]] | None = None,
) -> list[dict]:
    """Return a new list of word dicts with `deleted=True` set on filler words
    and filler phrases. Does not mutate the input. Words already deleted stay
    deleted; this only ever adds deletions.
    """
    filler_words = filler_words if filler_words is not None else DEFAULT_FILLER_WORDS
    filler_phrases = (
        filler_phrases if filler_phrases is not None else DEFAULT_FILLER_PHRASES
    )

    out = [dict(w) for w in words]
    norm = [_normalize(w["text"]) for w in out]

    for i, w in enumerate(out):
        if norm[i] in filler_words:
            w["deleted"] = True

    for phrase in filler_phrases:
        n = len(phrase)
        phrase_norm = [_normalize(p) for p in phrase]
        for i in range(len(out) - n + 1):
            if norm[i : i + n] == phrase_norm:
                for j in range(i, i + n):
                    out[j]["deleted"] = True

    return out


def mark_long_silences(
    words: list[dict],
    *,
    total_duration: float,
    min_silence: float = 0.6,
    keep: float = 0.3,
) -> list[dict]:
    """Trim long silences down to `keep` seconds by inserting synthetic
    "deleted" filler words covering the trimmed portion of each silence.

    This doesn't touch real words; it returns the original words list plus
    synthetic zero-text deleted words marking the parts of long silences to
    cut, so the same words_to_keep_ranges() pipeline handles silence trimming
    and word deletion uniformly.
    """
    out = [dict(w) for w in words]
    silences = find_silences(
        [Word.from_dict(w) for w in words],
        min_silence=min_silence,
        total_duration=total_duration,
    )
    for start, end in silences:
        trim_start = start + keep / 2
        trim_end = end - keep / 2
        if trim_end > trim_start:
            out.append(
                {
                    "text": "",
                    "start": trim_start,
                    "end": trim_end,
                    "deleted": True,
                    "synthetic": True,
                }
            )
    out.sort(key=lambda w: w["start"])
    return out
