"""Tests for the platform-specific branches, which CI on one OS cannot reach."""

from pathlib import Path

import pytest

from ytspot import cli, config, titles


def test_config_dir_uses_appdata_on_windows():
    chosen = config._choose_config_dir("nt", r"C:\Users\you\AppData\Roaming")
    assert chosen.name == "ytspot"
    assert "AppData" in str(chosen)


def test_config_dir_falls_back_when_appdata_is_missing():
    assert config._choose_config_dir("nt", None) == Path.home() / ".config" / "ytspot"


def test_config_dir_on_posix():
    assert config._choose_config_dir("posix", None) == Path.home() / ".config" / "ytspot"
    assert config.default_config_dir() == Path.home() / ".config" / "ytspot"


@pytest.mark.parametrize(
    ("platform", "os_name", "expected"),
    [
        ("darwin", "posix", "brew install ffmpeg"),
        ("win32", "nt", "winget install Gyan.FFmpeg"),
        ("linux", "posix", "sudo apt install ffmpeg"),
    ],
)
def test_ffmpeg_hint_matches_the_platform(monkeypatch, platform, os_name, expected):
    monkeypatch.setattr("sys.platform", platform)
    monkeypatch.setattr("os.name", os_name)
    assert expected in cli._ffmpeg_install_hint()


def test_filename_cap_is_shorter_on_windows():
    # Windows caps a whole path at 260 chars by default, so components must
    # leave room for the music and album folders.
    assert titles._MAX_FILENAME_LEN in (120, 180)


@pytest.mark.parametrize(
    "name",
    [
        "AC/DC",
        "Artist: Live",
        "What?",
        'He said "hi"',
        "a<b>c",
        "pipe|name",
        "back\\slash",
        "star*",
    ],
)
def test_filenames_are_safe_for_windows_too(name):
    # None of the characters Windows rejects may survive, on any platform,
    # so a library made on a Mac still copies to a Windows machine.
    result = titles.safe_filename(name)
    assert not set(result) & set('/\\:*?"<>|')
    assert not result.endswith((" ", "."))
