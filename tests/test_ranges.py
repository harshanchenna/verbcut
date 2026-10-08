"""Unit tests for the keep-range math. No whisper, no ffmpeg."""

from verbcut.core.ranges import (
    find_silences,
    merge_ranges,
    total_kept_duration,
    words_to_keep_ranges,
)


def word(text, start, end, deleted=False):
    return {"text": text, "start": start, "end": end, "deleted": deleted}


def test_no_deletions_keeps_everything_with_pad_clipped_to_neighbors():
    words = [word("a", 0.0, 1.0), word("b", 1.0, 2.0), word("c", 2.0, 3.0)]
    ranges = words_to_keep_ranges(words, pad=0.1, min_gap=0.0, total_duration=3.0)
    # Adjacent words with no deletions and no gaps should merge into one range.
    assert ranges == [(0.0, 3.0)]


def test_single_deletion_splits_the_range():
    words = [word("a", 0.0, 1.0), word("b", 1.0, 2.0, deleted=True), word("c", 2.0, 3.0)]
    ranges = words_to_keep_ranges(words, pad=0.0, min_gap=0.0)
    assert ranges == [(0.0, 1.0), (2.0, 3.0)]


def test_pad_extends_but_does_not_cross_into_deleted_neighbor():
    words = [word("a", 0.0, 1.0), word("b", 1.0, 2.0, deleted=True), word("c", 2.0, 3.0)]
    ranges = words_to_keep_ranges(words, pad=0.3, min_gap=0.0, total_duration=3.0)
    # "a" pads forward but is clipped at its own end (1.0) because "b" is deleted
    # and immediately follows; "c" pads backward clipped to its own start (2.0),
    # and its trailing pad is clipped by total_duration.
    assert ranges == [(0.0, 1.0), (2.0, 3.0)]


def test_pad_extends_into_natural_gap_between_kept_words():
    words = [word("a", 0.0, 1.0), word("b", 1.5, 2.5)]
    ranges = words_to_keep_ranges(words, pad=0.2, min_gap=0.0)
    # Gap between a.end=1.0 and b.start=1.5: padding can use up to that gap.
    # b is the last word, so its trailing pad isn't clipped by a neighbor.
    assert ranges == [(0.0, 1.2), (1.3, 2.7)]


def test_min_gap_merges_close_kept_ranges():
    words = [
        word("a", 0.0, 1.0),
        word("filler", 1.0, 1.05, deleted=True),
        word("b", 1.05, 2.0),
    ]
    ranges = words_to_keep_ranges(words, pad=0.0, min_gap=0.12)
    # The gap left by the deleted filler (0.05s) is below min_gap, so the two
    # surrounding kept ranges merge into one rather than leaving a micro-cut.
    assert ranges == [(0.0, 2.0)]


def test_min_gap_does_not_merge_far_apart_ranges():
    words = [
        word("a", 0.0, 1.0),
        word("filler", 1.0, 2.0, deleted=True),
        word("b", 2.0, 3.0),
    ]
    ranges = words_to_keep_ranges(words, pad=0.0, min_gap=0.12)
    assert ranges == [(0.0, 1.0), (2.0, 3.0)]


def test_everything_deleted_gives_no_ranges():
    words = [word("a", 0.0, 1.0, deleted=True), word("b", 1.0, 2.0, deleted=True)]
    assert words_to_keep_ranges(words) == []


def test_empty_transcript_gives_no_ranges():
    assert words_to_keep_ranges([]) == []


def test_total_duration_clips_trailing_pad():
    words = [word("a", 0.0, 1.0), word("b", 2.9, 3.0)]
    ranges = words_to_keep_ranges(words, pad=0.5, min_gap=0.0, total_duration=3.0)
    for _, end in ranges:
        assert end <= 3.0
    for start, _ in ranges:
        assert start >= 0.0


def test_total_kept_duration_sums_ranges():
    assert total_kept_duration([(0.0, 1.0), (2.0, 2.5)]) == 1.5
    assert total_kept_duration([]) == 0.0


def test_merge_ranges_basic():
    assert merge_ranges([(0.0, 1.0), (1.0, 2.0)], min_gap=0.0) == [(0.0, 2.0)]
    assert merge_ranges([(0.0, 1.0), (1.5, 2.0)], min_gap=0.0) == [(0.0, 1.0), (1.5, 2.0)]
    assert merge_ranges([(0.0, 1.0), (1.05, 2.0)], min_gap=0.1) == [(0.0, 2.0)]
    assert merge_ranges([(0.0, 2.0), (1.0, 1.5)], min_gap=0.0) == [(0.0, 2.0)]


def test_merge_ranges_empty():
    assert merge_ranges([]) == []


def test_find_silences_detects_gap_between_words():
    words = [word("a", 0.0, 1.0), word("b", 2.0, 2.5)]
    silences = find_silences(words, min_silence=0.5)
    assert silences == [(1.0, 2.0)]


def test_find_silences_ignores_short_gaps():
    words = [word("a", 0.0, 1.0), word("b", 1.1, 2.0)]
    assert find_silences(words, min_silence=0.5) == []


def test_find_silences_includes_trailing_silence_with_total_duration():
    words = [word("a", 0.0, 1.0)]
    silences = find_silences(words, min_silence=0.5, total_duration=3.0)
    assert silences == [(1.0, 3.0)]


def test_deletion_duration_shrinks_output_as_expected():
    """Deleting a 1-second sentence from a 10s transcript should shrink the
    kept duration by (about) 1 second — the core guarantee for the acceptance
    demo (verified against ffprobe on real renders separately)."""
    words = [
        word("intro", 0.0, 4.0),
        word("deleteme", 4.0, 5.0, deleted=True),
        word("outro", 5.0, 10.0),
    ]
    ranges = words_to_keep_ranges(words, pad=0.0, min_gap=0.0, total_duration=10.0)
    kept = total_kept_duration(ranges)
    assert kept == 9.0
