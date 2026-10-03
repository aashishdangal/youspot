"""End-to-end smoke test for ytspot. Works on macOS, Linux and Windows.

Does real downloads against YouTube, then checks the files and tags that come
out. Runs entirely in a temp folder with its own config, so your real music
library and your real config are never touched.

    uv run python scripts/smoke_test.py
    uv run python scripts/smoke_test.py --keep   # leave the files to inspect
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CHECK_TAGS = PROJECT / "scripts" / "check_tags.py"
SEARCH = "ytsearch2:kevin macleod carefree"

passed = 0
failed: list[str] = []


def bold(text: str) -> None:
    print(f"\n{text}")


def ok(label: str) -> None:
    global passed
    passed += 1
    print(f"  ok    {label}")


def bad(label: str, detail: str = "") -> None:
    failed.append(label)
    print(f"  FAIL  {label}{f' ({detail})' if detail else ''}")


def check(condition: bool, label: str, detail: str = "") -> bool:
    ok(label) if condition else bad(label, detail)
    return bool(condition)


def ytspot(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the CLI by module path, so no PATH setup is needed."""
    return subprocess.run(
        [sys.executable, "-m", "ytspot.cli", *args],
        cwd=PROJECT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def first_search_result_id() -> str | None:
    """Resolve a real video id, so no id is hardcoded and the test cannot rot."""
    from yt_dlp import YoutubeDL

    with YoutubeDL({"extract_flat": "in_playlist", "quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info("ytsearch1:kevin macleod carefree", download=False)
    entries = (info or {}).get("entries") or []
    return entries[0].get("id") if entries else None


def check_tags(folder: Path, *extra: str) -> bool:
    result = subprocess.run(
        [sys.executable, str(CHECK_TAGS), str(folder), *extra],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip())
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="Keep the sandbox folder.")
    args = parser.parse_args()

    bold("Preflight")
    if not check(shutil.which("ffmpeg") is not None, "ffmpeg installed", "not on PATH"):
        print("\n  Install FFmpeg and try again.")
        return 1
    try:
        import yt_dlp  # noqa: F401

        ok("yt-dlp importable")
    except ImportError:
        bad("yt-dlp importable", "run: uv sync")
        return 1

    sandbox = Path(tempfile.mkdtemp(prefix="ytspot-smoke-"))
    music = sandbox / "music"
    archive = sandbox / "archive.txt"
    config = sandbox / "config.json"
    music.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "music_dir": str(music),
                "archive_path": str(archive),
                "quality": "320",
                "singles_album": "YouTube Imports",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "YTSPOT_CONFIG": str(config), "PYTHONIOENCODING": "utf-8"}

    bold("Sandbox")
    print(f"  {sandbox}")

    try:
        bold("1. Unit tests")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=PROJECT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        last = (result.stdout or result.stderr).strip().splitlines()[-1:]
        check(result.returncode == 0, f"pytest: {last[0] if last else 'no output'}")

        bold("2. CLI")
        result = ytspot("--help", env=env)
        check("Import YouTube audio" in result.stdout, "--help works")
        result = ytspot("config", env=env)
        check(str(music) in result.stdout, "config reads the sandbox music_dir")

        bold("3. Dry run")
        result = ytspot(SEARCH, "--album", "Dry Run", "--dry-run", env=env)
        check("would be imported" in result.stdout, "reports a plan")
        check(
            not any(music.rglob("*.*")),
            "downloaded nothing",
            f"{len(list(music.rglob('*.*')))} files",
        )

        bold("4. Playlist import (2 tracks, real download)")
        result = ytspot(SEARCH, "--album", "Smoke Test", env=env)
        check(result.returncode == 0, "exit code 0", f"got {result.returncode}")
        check(
            "Imported 2, skipped 0, failed 0" in result.stdout,
            "summary: imported 2",
            result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "",
        )
        check("[1/2]" in result.stdout, "progress counter [1/2]")

        bold("   Tags")
        check(
            check_tags(
                music / "Smoke Test",
                "--expect-tracks", "2",
                "--expect-album", "Smoke Test",
                "--expect-bitrate", "320",
                "--numbered",
            ),
            "all tag checks",
        )

        lines = [ln for ln in archive.read_text(encoding="utf-8").splitlines() if ln.strip()]
        check(len(lines) == 2, "archive holds 2 video ids", f"{len(lines)} lines")

        bold("5. Re-run skips what is already imported")
        # Re-run the exact videos the archive recorded, not the search: search
        # results drift, and a genuinely new result would be imported (which is
        # correct behaviour, but makes for a flaky test).
        before = {path.name for path in (music / "Smoke Test").glob("*.mp3")}
        recorded_id = lines[0].split()[-1]
        result = ytspot(f"https://www.youtube.com/watch?v={recorded_id}", env=env)
        check("skipped (already imported)" in result.stdout, "reports skipping")
        check("Imported 0" in result.stdout, "imported nothing new")
        after = {path.name for path in (music / "Smoke Test").glob("*.mp3")}
        check(before == after, "no new files written", f"{len(after - before)} added")

        bold("6. Single video at --quality 192")
        # A ytsearch: URL is always a playlist, even with one result, so the
        # single-video path needs a real watch?v= URL.
        video_id = first_search_result_id()
        if not check(bool(video_id), "resolved a video id to test with"):
            return 1
        # --no-archive because step 4 already recorded this video.
        result = ytspot(
            f"https://www.youtube.com/watch?v={video_id}",
            "--quality", "192",
            "--no-archive",
            env=env,
        )
        check("Imported 1" in result.stdout, "imported 1", result.stdout.strip()[-80:])
        check("YouTube Imports" in result.stdout, "album is YouTube Imports")
        bold("   Tags")
        check(
            check_tags(
                music / "YouTube Imports",
                "--expect-tracks", "1",
                "--expect-album", "YouTube Imports",
                "--expect-bitrate", "192",
            ),
            "all tag checks",
        )

        bold("7. --items 1-1")
        result = ytspot(
            "ytsearch3:kevin macleod", "--items", "1-1",
            "--album", "Items Test", "--dry-run", env=env,
        )
        check("1 track(s) would be imported" in result.stdout, "only 1 track planned")

        bold("8. Unavailable video")
        result = ytspot("https://www.youtube.com/watch?v=aaaaaaaaaaa", env=env)
        check(result.returncode == 1, "exits 1", f"got {result.returncode}")
        combined = result.stdout + result.stderr
        check("unavailable" in combined.lower(), "reports the real reason")

    finally:
        if args.keep:
            print(f"\nFiles kept at: {sandbox}")
        else:
            shutil.rmtree(sandbox, ignore_errors=True)

    print("")
    if failed:
        print(f"{passed} passed, {len(failed)} failed.")
        for label in failed:
            print(f"  - {label}")
    else:
        print(f"All {passed} checks passed.")

    print("\nNot covered here (needs a human):")
    print("  - Spotify: Settings > Library > Show Local Files > Add a source,")
    print("    fully quit and reopen Spotify, check the album appears")
    print("  - Tag quality on URLs you care about: run a --dry-run and look")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
