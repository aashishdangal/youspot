"""Config file handling: a small JSON file, prompted for on first run."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer

_LEGACY_CONFIG_DIR = Path.home() / ".config" / "ytspot"


def _choose_config_dir(os_name: str, appdata: str | None) -> Path:
    """The decision, kept pure so both platforms are testable on either.

    (Faking os.name wholesale is not an option: pathlib then tries to build a
    WindowsPath and refuses to do so on a POSIX machine.)
    """
    if os_name == "nt" and appdata:
        return Path(appdata) / "ytspot"
    return _LEGACY_CONFIG_DIR


def default_config_dir() -> Path:
    """Where config lives: %APPDATA% on Windows, ~/.config elsewhere."""
    return _choose_config_dir(os.name, os.environ.get("APPDATA"))


DEFAULT_CONFIG_DIR = default_config_dir()

DEFAULTS: dict[str, Any] = {
    "music_dir": "",
    "archive_path": str(DEFAULT_CONFIG_DIR / "archive.txt"),
    "quality": "320",
    "singles_album": "YouTube Imports",
}


def config_path() -> Path:
    override = os.environ.get("YTSPOT_CONFIG")
    if override:
        return Path(override).expanduser()
    preferred = DEFAULT_CONFIG_DIR / "config.json"
    # Keep using a config written before this moved to %APPDATA%.
    legacy = _LEGACY_CONFIG_DIR / "config.json"
    if not preferred.is_file() and legacy.is_file():
        return legacy
    return preferred


def read_config() -> dict[str, Any] | None:
    """Return the stored config merged over the defaults, or None if unset."""
    path = config_path()
    if not path.is_file():
        return None
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"Could not read config at {path}: {exc}") from exc
    if not isinstance(stored, dict):
        raise typer.BadParameter(f"Config at {path} is not a JSON object")
    return {**DEFAULTS, **stored}


def write_config(cfg: dict[str, Any]) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return path


def load_config() -> dict[str, Any]:
    """Load the config, prompting for the music folder on first run."""
    cfg = read_config()
    if cfg and cfg.get("music_dir"):
        return cfg

    typer.secho("First run: ytspot needs a folder to save imported MP3s.", bold=True)
    typer.echo(
        "Use the folder you have added (or will add) to\n"
        "Spotify > Settings > Library > Show Local Files > Add a source."
    )
    default = str(Path.home() / "Music" / "ytspot")
    answer = typer.prompt("Music folder", default=default)
    music_dir = Path(answer).expanduser()
    try:
        music_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise typer.BadParameter(f"Could not create {music_dir}: {exc}") from exc

    cfg = {**DEFAULTS, **(cfg or {}), "music_dir": str(music_dir)}
    path = write_config(cfg)
    typer.secho(f"Saved config to {path}", fg=typer.colors.GREEN)
    return cfg


def music_dir(cfg: dict[str, Any]) -> Path:
    return Path(cfg["music_dir"]).expanduser()


def archive_path(cfg: dict[str, Any]) -> Path:
    return Path(cfg.get("archive_path") or DEFAULTS["archive_path"]).expanduser()
