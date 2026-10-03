"""Assert that imported MP3s carry the tags Spotify needs.

Used by scripts/smoke-test.sh; exits non-zero if anything is wrong.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mutagen.id3 import ID3
from mutagen.mp3 import MP3

failures: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    if ok:
        print(f"    ok    {label}")
    else:
        print(f"    FAIL  {label}{f' ({detail})' if detail else ''}")
        failures.append(label)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--expect-tracks", type=int, required=True)
    parser.add_argument("--expect-album", required=True)
    parser.add_argument("--expect-bitrate", type=int, default=320)
    parser.add_argument(
        "--numbered",
        action="store_true",
        help="Expect track numbers and NN- prefixed filenames (playlists).",
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        check(False, "album folder exists", str(folder))
        return 1

    mp3s = sorted(folder.glob("*.mp3"))
    check(
        len(mp3s) == args.expect_tracks,
        f"{args.expect_tracks} MP3 file(s) present",
        f"found {len(mp3s)}",
    )

    strays = [p for p in folder.iterdir() if p.is_file() and p.suffix != ".mp3"]
    check(not strays, "no stray files left behind", ", ".join(p.name for p in strays))

    for position, path in enumerate(mp3s, start=1):
        print(f"  {path.name}")
        tags, audio = ID3(path), MP3(path)

        # Spotify is unreliable at reading ID3v2.4, so v2.3 is required.
        check(tags.version[1] == 3, "ID3v2.3", f"got v2.{tags.version[1]}")

        kbps = audio.info.bitrate // 1000
        check(
            abs(kbps - args.expect_bitrate) <= 8,
            f"~{args.expect_bitrate}kbps",
            f"got {kbps}kbps",
        )

        for frame in ("TIT2", "TPE1", "TALB", "TPE2"):
            value = str(tags.get(frame) or "")
            check(bool(value.strip()), f"{frame} set", "empty")

        check(
            str(tags.get("TALB")) == args.expect_album,
            f'album is "{args.expect_album}"',
            str(tags.get("TALB")),
        )

        art = tags.getall("APIC")
        check(
            bool(art) and len(art[0].data) > 1000,
            "cover art embedded",
            f"{len(art[0].data) if art else 0} bytes",
        )
        if art:
            check(art[0].mime == "image/jpeg", "cover art is JPEG", art[0].mime)

        if args.numbered:
            check(
                str(tags.get("TRCK")) == f"{position}/{args.expect_tracks}",
                f"track number {position}/{args.expect_tracks}",
                str(tags.get("TRCK")),
            )
            check(
                path.name.startswith(f"{position:02d} - "),
                f'filename starts "{position:02d} - "',
                path.name,
            )
        else:
            check("TRCK" not in tags, "no track number on a single", str(tags.get("TRCK")))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
