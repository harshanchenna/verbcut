"""verbcut command-line interface.

    verbcut transcribe in.mp4                     # writes in.verbcut.json
    verbcut remove-fillers in.mp4 -o out.mp4       # transcribe (if needed) + cut fillers + render
    verbcut serve                                  # local web UI
"""

from __future__ import annotations

from pathlib import Path

import typer

from .core import media as media_mod
from .core.fillers import mark_filler_words, mark_long_silences
from .core.project import Project
from .core.ranges import words_to_keep_ranges
from .core.render import render as render_ranges
from .core.transcribe import ALLOWED_MODELS, transcribe as run_transcribe

app = typer.Typer(help="Local, transcript-based video editor.")


def _project_path_for(media_path: Path) -> Path:
    return media_path.with_suffix(media_path.suffix + ".verbcut.json")


@app.command()
def transcribe(
    media: Path = typer.Argument(..., exists=True, help="Input audio/video file."),
    model: str = typer.Option("base", help=f"Whisper model: one of {sorted(ALLOWED_MODELS)}."),
    threads: int = typer.Option(2, help="CPU threads for transcription."),
    project: Path | None = typer.Option(None, help="Where to save the project JSON."),
):
    """Transcribe MEDIA with word-level timestamps and save a project file."""
    proj = run_transcribe(str(media), model_size=model, cpu_threads=threads)
    out = project or _project_path_for(media)
    proj.save(out)
    typer.echo(f"Transcribed {len(proj.words)} words, {proj.duration:.2f}s -> {out}")


@app.command(name="remove-fillers")
def remove_fillers(
    media: Path = typer.Argument(..., exists=True, help="Input audio/video file."),
    output: Path = typer.Option(..., "-o", "--output", help="Output video path."),
    model: str = typer.Option("base", help=f"Whisper model: one of {sorted(ALLOWED_MODELS)}."),
    trim_silence: bool = typer.Option(True, help="Also trim long silences."),
    threads: int = typer.Option(2, help="CPU threads."),
):
    """Transcribe (if no project exists yet), strip filler words, render OUTPUT."""
    project_path = _project_path_for(media)
    if project_path.exists():
        proj = Project.load(project_path)
        typer.echo(f"Using existing transcript: {project_path}")
    else:
        proj = run_transcribe(str(media), model_size=model, cpu_threads=threads)
        proj.save(project_path)
        typer.echo(f"Transcribed {len(proj.words)} words -> {project_path}")

    words = mark_filler_words(proj.words)
    if trim_silence:
        words = mark_long_silences(words, total_duration=proj.duration)

    info = media_mod.probe(str(media))
    ranges = words_to_keep_ranges(words, total_duration=proj.duration)
    render_ranges(media, ranges, output, has_video=info["has_video"], threads=threads)
    typer.echo(f"Rendered -> {output}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8765),
    reload: bool = typer.Option(False),
):
    """Run the local web UI."""
    import uvicorn

    uvicorn.run("verbcut.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
