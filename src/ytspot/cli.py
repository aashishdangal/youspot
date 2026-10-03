"""Typer CLI for ytspot."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer

from . import config as config_module
from . import downloader, titles
from .downloader import Plan, ResolveError, Target

cli = typer.Typer(
    help="Import YouTube audio into Spotify's Local Files as tagged MP3s.",
    no_args_is_help=True,
    add_completion=False,
)


class Reporter:
    """Prints one line per video: "[12/48] Artist - Title ... ok"."""

    def __init__(self) -> None:
        self._open_line = False

    def _prefix(self, target: Target, total: int) -> str:
        width = len(str(total))
        return f"[{target.index:>{width}}/{total}]"

    def starting(self, target: Target, total: int, label: str) -> None:
        typer.echo(f"{self._prefix(target, total)} {label} ... ", nl=False)
        self._open_line = True

    def imported(self, target: Target, total: int, path: Path) -> None:
        self._close(typer.style("ok", fg=typer.colors.GREEN))

    def skipped(self, target: Target, total: int, label: str) -> None:
        self._close_fresh(
            f"{self._prefix(target, total)} {label} ... "
            + typer.style("skipped (already imported)", fg=typer.colors.YELLOW)
        )

    def failed(self, target: Target, total: int, label: str, reason: str) -> None:
        if self._open_line:
            self._close(typer.style(f"failed: {reason}", fg=typer.colors.RED))
        else:
            self._close_fresh(
                f"{self._prefix(target, total)} {label} ... "
                + typer.style(f"failed: {reason}", fg=typer.colors.RED)
            )

    def _close(self, text: str) -> None:
        typer.echo(text)
        self._open_line = False

    def _close_fresh(self, text: str) -> None:
        if self._open_line:
            typer.echo("")
        typer.echo(text)
        self._open_line = False


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        typer.secho(
            "FFmpeg was not found on your PATH. ytspot needs it to make MP3s.\n"
            "Install it with:  brew install ffmpeg",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)


def _show_dry_run(plan: Plan, destination: Path) -> None:
    typer.secho(f"Album:  {plan.album}", bold=True)
    typer.echo(f"Folder: {destination}")
    if plan.album_artist:
        typer.echo(f"Album artist: {plan.album_artist}")
    typer.echo(f"{plan.total} track(s) would be imported:\n")
    for target in plan.targets:
        artist, title = titles.split_artist_title(target.raw_title, {})
        filename = titles.track_filename(artist, title, target.track_number)
        typer.echo(f"  {target.index:>3}. {filename}")
    typer.echo(
        "\nTags are guessed from playlist titles here; a real run uses each "
        "video's full metadata."
    )


@cli.command("get")
def get(
    url: str = typer.Argument(..., help="A YouTube video or playlist URL."),
    items: str = typer.Option(
        None,
        "--items",
        help="Playlist positions to import, e.g. 1-10, 1,5,8 or 3:12:2.",
    ),
    music_dir: Path = typer.Option(
        None, "--music-dir", help="Override the configured music folder."
    ),
    album: str = typer.Option(
        None, "--album", help="Override the album name used for these tracks."
    ),
    quality: str = typer.Option(
        None, "--quality", help="MP3 bitrate, e.g. 320 (default) or 192."
    ),
    no_archive: bool = typer.Option(
        False,
        "--no-archive",
        help="Ignore the download archive and re-import videos already fetched.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be imported without downloading."
    ),
) -> None:
    """Import a YouTube video or playlist."""
    cfg = config_module.load_config()
    root = (music_dir or config_module.music_dir(cfg)).expanduser()
    bitrate = quality or cfg.get("quality") or "320"
    archive = None if no_archive else config_module.archive_path(cfg)

    if not dry_run:
        _require_ffmpeg()

    typer.echo("Reading URL ...")
    try:
        plan = downloader.resolve(url, items, cfg.get("singles_album") or "YouTube Imports")
    except ResolveError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        detail = " ".join(str(exc).split()).replace("ERROR: ", "")
        typer.secho(f"Could not read {url}: {detail}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if album:
        plan.album = album
    if items and not plan.is_playlist:
        typer.secho(
            "--items only applies to playlists; importing the single video.",
            fg=typer.colors.YELLOW,
        )

    destination = downloader.album_dir(root, plan.album)

    if dry_run:
        _show_dry_run(plan, destination)
        return

    kind = "playlist" if plan.is_playlist else "video"
    typer.secho(f'{plan.total} track(s) from {kind} "{plan.album}"', bold=True)
    typer.echo(f"Saving to {destination}\n")

    result = downloader.import_plan(
        plan,
        music_root=root,
        quality=bitrate,
        archive=archive,
        reporter=Reporter(),
    )

    typer.echo("")
    typer.secho(
        f"Imported {result.imported}, skipped {result.skipped}, failed {result.failed}",
        bold=True,
    )
    typer.echo(f"Folder: {destination}")

    if result.failures:
        typer.secho("\nFailures:", fg=typer.colors.RED, bold=True)
        for failure in result.failures:
            typer.echo(f"  #{failure.index}  {failure.label} - {failure.reason}")
        raise typer.Exit(code=1)

    if result.imported:
        typer.echo(
            "\nIf these are new to Spotify: Settings > Local Files > Add a source, "
            "then pick the folder above."
        )


@cli.command("config")
def config_command(
    show: bool = typer.Option(False, "--show", help="Print the current config."),
    set_music_dir: Path = typer.Option(
        None, "--set-music-dir", help="Set the folder imported MP3s are saved to."
    ),
) -> None:
    """Show or change ytspot's configuration."""
    if set_music_dir:
        target = set_music_dir.expanduser()
        target.mkdir(parents=True, exist_ok=True)
        cfg = {**config_module.DEFAULTS, **(config_module.read_config() or {})}
        cfg["music_dir"] = str(target)
        path = config_module.write_config(cfg)
        typer.secho(f"music_dir = {target}", fg=typer.colors.GREEN)
        typer.echo(f"Saved to {path}")
        return

    # With no flags, showing the config is the useful default.
    cfg = config_module.read_config()
    path = config_module.config_path()
    if not cfg:
        typer.echo(f"No config yet. It will be created at {path} on first import.")
        return
    typer.echo(f"Config: {path}")
    for key in ("music_dir", "archive_path", "quality", "singles_album"):
        typer.echo(f"  {key} = {cfg.get(key)}")


def app() -> None:
    """Console-script entry point.

    Lets `ytspot <url>` work as a shorthand for `ytspot get <url>`, while
    keeping `ytspot config` available as a subcommand.
    """
    argv = sys.argv[1:]
    if argv and not argv[0].startswith("-") and argv[0] not in {"get", "config"}:
        argv = ["get", *argv]
    cli(args=argv, prog_name="ytspot")


if __name__ == "__main__":
    app()
