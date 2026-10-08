from verbcut.core.fillers import mark_filler_words, mark_long_silences


def word(text, start, end, deleted=False):
    return {"text": text, "start": start, "end": end, "deleted": deleted}


def test_mark_filler_words_single_word():
    words = [word("so", 0, 0.3), word("um", 0.3, 0.6), word("hello", 0.6, 1.0)]
    out = mark_filler_words(words)
    assert [w["deleted"] for w in out] == [False, True, False]


def test_mark_filler_words_is_case_insensitive_and_punctuation_tolerant():
    words = [word("Um,", 0, 0.3), word("hello", 0.3, 1.0)]
    out = mark_filler_words(words)
    assert out[0]["deleted"] is True
    assert out[1]["deleted"] is False


def test_mark_filler_words_does_not_mutate_input():
    words = [word("um", 0, 0.3)]
    mark_filler_words(words)
    assert words[0]["deleted"] is False


def test_mark_filler_words_phrase():
    words = [
        word("it", 0, 0.2),
        word("was", 0.2, 0.4),
        word("you", 0.4, 0.6),
        word("know", 0.6, 0.8),
        word("great", 0.8, 1.2),
    ]
    out = mark_filler_words(words)
    assert [w["deleted"] for w in out] == [False, False, True, True, False]


def test_mark_filler_words_preserves_existing_deletions():
    words = [word("already", 0, 0.3, deleted=True), word("um", 0.3, 0.6)]
    out = mark_filler_words(words)
    assert out[0]["deleted"] is True
    assert out[1]["deleted"] is True


def test_mark_long_silences_adds_synthetic_deleted_entries():
    words = [word("hello", 0.0, 1.0), word("world", 3.0, 3.5)]
    out = mark_long_silences(words, total_duration=3.5, min_silence=1.0, keep=0.2)
    synthetic = [w for w in out if w.get("synthetic")]
    assert len(synthetic) == 1
    assert synthetic[0]["deleted"] is True
    # Trimmed region should be inside the 1.0-3.0 silence, leaving `keep`
    # seconds of silence around it.
    assert synthetic[0]["start"] > 1.0
    assert synthetic[0]["end"] < 3.0


def test_mark_long_silences_ignores_short_gaps():
    words = [word("hello", 0.0, 1.0), word("world", 1.2, 1.5)]
    out = mark_long_silences(words, total_duration=1.5, min_silence=1.0)
    assert not any(w.get("synthetic") for w in out)
