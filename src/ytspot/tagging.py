"""ID3 tagging via mutagen, written the way Spotify's local-file reader likes."""

from __future__ import annotations

from pathlib import Path

from mutagen.id3 import (
    APIC,
    COMM,
    ID3,
    TALB,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TRCK,
    WOAS,
    ID3NoHeaderError,
)

VARIOUS_ARTISTS = "Various Artists"


def write_tags(
    mp3_path: str | Path,
    *,
    title: str,
    artist: str,
    album: str,
    album_artist: str | None = None,
    track_number: int | None = None,
    track_total: int | None = None,
    cover_bytes: bytes | None = None,
    year: str | None = None,
    source_url: str | None = None,
) -> None:
    """Write tags to an MP3, replacing anything FFmpeg left behind."""
    path = Path(mp3_path)
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    tags.delall("APIC")
    tags.add(TIT2(encoding=3, text=title))
    tags.add(TPE1(encoding=3, text=artist))
    tags.add(TALB(encoding=3, text=album))
    tags.add(TPE2(encoding=3, text=album_artist or artist))

    if track_number is not None:
        value = f"{track_number}/{track_total}" if track_total else str(track_number)
        tags.add(TRCK(encoding=3, text=value))

    if year:
        tags.add(TDRC(encoding=3, text=year))

    if source_url:
        tags.add(WOAS(url=source_url))
        tags.delall("COMM")
        tags.add(COMM(encoding=3, lang="eng", desc="", text=f"Imported from {source_url}"))

    if cover_bytes:
        tags.add(
            APIC(encoding=0, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes)
        )

    # v2_version=3 matters: Spotify's local-file reader is unreliable with
    # ID3v2.4 frames, which is mutagen's default.
    tags.save(path, v2_version=3)
