"""Local web UI: FastAPI + vanilla JS. Binds to localhost only, by convention
(see cli.serve default host 127.0.0.1) — this is a local tool, not a hosted
service, and the /media endpoint serves arbitrary local file paths by design.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from .core import media as media_mod
from .core.fillers import mark_filler_words, mark_long_silences
from .core.project import Project
from .core.ranges import total_kept_duration, words_to_keep_ranges
from .core.render import render as render_ranges
from .core.transcribe import transcribe as run_transcribe

app = FastAPI(title="verbcut")

_here = Path(__file__).parent
templates = Jinja2Templates(directory=str(_here / "templates"))
app.mount("/static", StaticFiles(directory=str(_here / "static")), name="static")


def _project_path_for(media_path: Path) -> Path:
    return media_path.with_suffix(media_path.suffix + ".verbcut.json")


class OpenRequest(BaseModel):
    path: str
    model: str = "base"


class ToggleRequest(BaseModel):
    path: str
    indices: list[int]
    deleted: bool = True


class SimpleRequest(BaseModel):
    path: str


class ExportRequest(BaseModel):
    path: str
    output: str


def _project_response(proj: Project, media_path: Path) -> dict:
    ranges = words_to_keep_ranges(proj.words, total_duration=proj.duration)
    return {
        "words": proj.words,
        "duration": proj.duration,
        "kept_duration": total_kept_duration(ranges),
        "media_url": f"/media?path={media_path.resolve()}",
    }


@app.get("/", response_class=None)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/media")
def get_media(path: str):
    p = Path(path)
    if not p.exists():
        raise HTTPException(404, "file not found")
    return FileResponse(str(p))


@app.post("/api/open")
def open_media(req: OpenRequest):
    media_path = Path(req.path).expanduser()
    if not media_path.exists():
        raise HTTPException(404, f"no such file: {media_path}")

    project_path = _project_path_for(media_path)
    if project_path.exists():
        proj = Project.load(project_path)
    else:
        proj = run_transcribe(str(media_path), model_size=req.model)
        proj.save(project_path)

    return _project_response(proj, media_path)


@app.post("/api/toggle-delete")
def toggle_delete(req: ToggleRequest):
    media_path = Path(req.path).expanduser()
    project_path = _project_path_for(media_path)
    proj = Project.load(project_path)
    proj.set_deleted(req.indices, req.deleted)
    proj.save(project_path)
    return _project_response(proj, media_path)


@app.post("/api/remove-fillers")
def remove_fillers(req: SimpleRequest):
    media_path = Path(req.path).expanduser()
    project_path = _project_path_for(media_path)
    proj = Project.load(project_path)
    proj.words = mark_filler_words(proj.words)
    proj.save(project_path)
    return _project_response(proj, media_path)


@app.post("/api/trim-silences")
def trim_silences(req: SimpleRequest):
    media_path = Path(req.path).expanduser()
    project_path = _project_path_for(media_path)
    proj = Project.load(project_path)
    proj.words = mark_long_silences(proj.words, total_duration=proj.duration)
    proj.save(project_path)
    return _project_response(proj, media_path)


@app.post("/api/export")
def export(req: ExportRequest):
    media_path = Path(req.path).expanduser()
    project_path = _project_path_for(media_path)
    proj = Project.load(project_path)

    info = media_mod.probe(str(media_path))
    ranges = words_to_keep_ranges(proj.words, total_duration=proj.duration)
    if not ranges:
        raise HTTPException(400, "nothing left to render: everything is deleted")

    output_path = Path(req.output).expanduser()
    render_ranges(media_path, ranges, output_path, has_video=info["has_video"])
    return {
        "output": str(output_path),
        "kept_duration": total_kept_duration(ranges),
        "original_duration": proj.duration,
    }
