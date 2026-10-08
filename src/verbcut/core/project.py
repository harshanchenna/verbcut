"""Project file: transcript + edits, saved as JSON so edits are non-destructive.

The source media is never modified. A .verbcut.json project file holds the
source media path, the transcript (words with start/end/deleted), and basic
metadata. Rendering reads the project file and produces a new output file.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass
class Project:
    media_path: str
    duration: float
    words: list[dict] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION
    model: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Project":
        return Project(
            media_path=d["media_path"],
            duration=float(d["duration"]),
            words=d.get("words", []),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            model=d.get("model", ""),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @staticmethod
    def load(path: str | Path) -> "Project":
        data = json.loads(Path(path).read_text())
        return Project.from_dict(data)

    def set_deleted(self, indices: list[int], deleted: bool = True) -> None:
        for i in indices:
            self.words[i]["deleted"] = deleted
