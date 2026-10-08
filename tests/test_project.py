from verbcut.core.project import Project


def test_save_and_load_roundtrip(tmp_path):
    proj = Project(
        media_path="in.mp4",
        duration=10.0,
        words=[{"text": "hi", "start": 0.0, "end": 0.5, "deleted": False}],
        model="base",
    )
    path = tmp_path / "proj.json"
    proj.save(path)

    loaded = Project.load(path)
    assert loaded.media_path == "in.mp4"
    assert loaded.duration == 10.0
    assert loaded.words == proj.words
    assert loaded.model == "base"
    assert loaded.schema_version == 1


def test_set_deleted():
    proj = Project(
        media_path="in.mp4",
        duration=1.0,
        words=[
            {"text": "a", "start": 0.0, "end": 0.5, "deleted": False},
            {"text": "b", "start": 0.5, "end": 1.0, "deleted": False},
        ],
    )
    proj.set_deleted([1])
    assert proj.words[0]["deleted"] is False
    assert proj.words[1]["deleted"] is True

    proj.set_deleted([1], deleted=False)
    assert proj.words[1]["deleted"] is False
