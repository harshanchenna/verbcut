"""Pure range math: turn a transcript with deleted words into ffmpeg keep-ranges.

No I/O, no whisper, no ffmpeg here — this module is unit-testable on its own.

Model
-----
A transcript is a list of words, each ``{"text": str, "start": float, "end": float,
"deleted": bool}`` in seconds, sorted by start time and covering (roughly) the
whole media duration. Deleting a word marks it ``deleted``. The editor then wants
"keep ranges": the list of ``[start, end)`` spans of the *original* media to keep,
in order, which ffmpeg will concatenate to produce the edited output.

Turning deletions into keep-ranges needs three things:
  1. Build one range per surviving (non-deleted) word.
  2. Merge adjacent/close ranges so natural pauses between kept words aren't
     turned into needless extra cut points.
  3. Pad each range by a few milliseconds so a cut doesn't clip the onset/offset
     of a syllable right at a word boundary, without padding past a neighboring
     deleted word's own boundary (so padding never un-deletes audio from the
     words either side of this one).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    deleted: bool = False

    @staticmethod
    def from_dict(d: dict) -> "Word":
        return Word(
            text=d["text"],
            start=float(d["start"]),
            end=float(d["end"]),
            deleted=bool(d.get("deleted", False)),
        )


Range = tuple[float, float]


def _pad_word_range(words: list[Word], i: int, pad: float) -> Range:
    """Range for words[i], padded by `pad` seconds but clipped so it never
    crosses into the previous/next word's own span (whether that neighbor is
    kept or deleted)."""
    w = words[i]
    start = w.start - pad
    end = w.end + pad

    if i > 0:
        prev = words[i - 1]
        start = max(start, prev.end)
    else:
        start = max(start, 0.0)

    if i < len(words) - 1:
        nxt = words[i + 1]
        end = min(end, nxt.start)
    end = max(end, w.end)  # never shrink below the word's own end
    start = min(start, w.start)  # never shrink above the word's own start

    return (start, end)


def merge_ranges(ranges: list[Range], min_gap: float = 0.0) -> list[Range]:
    """Merge ranges that overlap or are separated by a gap <= min_gap.

    Ranges must be sorted by start; output is sorted, non-overlapping, and
    gaps between consecutive output ranges are always > min_gap.
    """
    if not ranges:
        return []

    merged: list[list[float]] = [list(ranges[0])]
    for start, end in ranges[1:]:
        last = merged[-1]
        if start <= last[1] + min_gap:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def words_to_keep_ranges(
    words: list[dict] | list[Word],
    *,
    pad: float = 0.03,
    min_gap: float = 0.12,
    total_duration: float | None = None,
) -> list[Range]:
    """Compute the keep-ranges for a transcript with some words deleted.

    Args:
        words: full ordered transcript (kept and deleted words), each with
            start/end/deleted. Must be sorted by start time.
        pad: seconds to extend each kept word's range by on each side, to avoid
            clipping syllable onsets/offsets. Clipped against neighboring words.
        min_gap: consecutive kept ranges separated by a gap <= this many seconds
            are merged into one range (keeps natural pauses, avoids churn of
            many tiny cuts).
        total_duration: if given, ranges are clipped to [0, total_duration].

    Returns:
        A list of (start, end) tuples, sorted, non-overlapping, in seconds.
        Empty if every word is deleted (or there are no words).
    """
    parsed = [w if isinstance(w, Word) else Word.from_dict(w) for w in words]
    parsed = sorted(parsed, key=lambda w: w.start)

    raw_ranges = [
        _pad_word_range(parsed, i, pad) for i, w in enumerate(parsed) if not w.deleted
    ]
    raw_ranges.sort()

    merged = merge_ranges(raw_ranges, min_gap=min_gap)

    if total_duration is not None:
        clipped = []
        for start, end in merged:
            start = max(0.0, min(start, total_duration))
            end = max(0.0, min(end, total_duration))
            if end > start:
                clipped.append((start, end))
        merged = clipped

    return merged


def total_kept_duration(ranges: list[Range]) -> float:
    return sum(end - start for start, end in ranges)


def find_silences(
    words: list[dict] | list[Word],
    *,
    min_silence: float = 0.6,
    total_duration: float | None = None,
) -> list[Range]:
    """Find silence gaps between words (and before the first / after the last
    word, if total_duration is given) that are at least `min_silence` seconds.
    """
    parsed = [w if isinstance(w, Word) else Word.from_dict(w) for w in words]
    parsed = sorted(parsed, key=lambda w: w.start)

    silences: list[Range] = []
    cursor = 0.0
    for w in parsed:
        if w.start - cursor >= min_silence:
            silences.append((cursor, w.start))
        cursor = max(cursor, w.end)

    if total_duration is not None and total_duration - cursor >= min_silence:
        silences.append((cursor, total_duration))

    return silences
